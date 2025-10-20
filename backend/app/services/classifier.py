from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..core.config import Settings, get_settings
from .templates import list_templates

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClassificationResult:
    """Represents the predicted document type for an uploaded document."""

    document_type: str
    display_name: str
    confidence: float
    matched_keywords: List[str]
    reason: Optional[str] = None


class DocumentClassifier:
    """Classify disclosure documents using template heuristics with optional LLM assistance."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        template_store: Optional[Dict[str, dict]] = None,
        openai_client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._templates = template_store or list_templates()

        self._keyword_map: Dict[str, List[str]] = {}
        self._display_map: Dict[str, str] = {}
        self._llm_options: List[Dict[str, Any]] = []

        for doc_type, template in self._templates.items():
            keywords = template.get("keywords_for_detection", []) or []
            keyword_list = [kw.lower() for kw in keywords if isinstance(kw, str)]
            self._keyword_map[doc_type] = keyword_list

            display_name = template.get("display_name", doc_type)
            self._display_map[doc_type] = display_name

            self._llm_options.append(
                {
                    "id": doc_type,
                    "display_name": display_name,
                    "description": template.get("description", ""),
                    "keywords": keyword_list[:8],
                }
            )

        # Sentinel entry for documents that cannot be classified confidently.
        self._display_map.setdefault("unknown", "未判定")
        self._keyword_map.setdefault("unknown", [])
        self._llm_options.append(
            {
                "id": "unknown",
                "display_name": "未判定",
                "description": "どのテンプレートにも明確に該当しない場合に選択してください。",
                "keywords": [],
            }
        )

        self._max_prompt_chars = max(0, int(self._settings.document_classification_max_prompt_chars))
        self._openai_model = self._settings.openai_model
        self._llm_enabled = bool(
            self._settings.document_classification_use_llm and self._settings.openai_api_key
        )

        # デバッグログ
        logger.info(f"DocumentClassifier initialization:")
        logger.info(f"  - use_llm setting: {self._settings.document_classification_use_llm}")
        logger.info(f"  - api_key present: {bool(self._settings.openai_api_key)}")
        logger.info(f"  - _llm_enabled: {self._llm_enabled}")

        if openai_client is not None:
            self._openai_client = openai_client if self._llm_enabled else None
            logger.info(f"  - Using provided OpenAI client: {self._openai_client is not None}")
        elif self._llm_enabled:
            self._openai_client = self._build_openai_client()
            logger.info(f"  - Built OpenAI client: {self._openai_client is not None}")
        else:
            self._openai_client = None
            logger.info(f"  - No OpenAI client (LLM disabled)")
        
        logger.info(f"  - Final _openai_client: {self._openai_client is not None}")

    def classify(self, *, filename: str, text_sample: str) -> Optional[ClassificationResult]:
        """Return the best classification for the provided content sample using LLM."""

        if not self._openai_client:
            logger.error("LLM-based classification requires OpenAI client to be configured")
            return None

        haystack = f"{filename} {text_sample}".lower()

        llm_result = self._classify_with_llm(
            filename=filename,
            text_sample=text_sample,
            haystack=haystack,
            template_result=None,
        )
        return llm_result

    def get_display_name(self, document_type: str) -> str:
        return self._display_map.get(document_type, document_type)

    def is_supported_type(self, document_type: str) -> bool:
        return document_type in self._display_map and document_type != "unknown"

    def list_supported_types(self) -> List[str]:
        return [doc_type for doc_type in self._display_map if doc_type != "unknown"]

    def _classify_with_templates(self, haystack: str) -> Optional[ClassificationResult]:
        best_type: Optional[str] = None
        best_matches: List[str] = []

        for doc_type, keywords in self._keyword_map.items():
            if doc_type == "unknown" or not keywords:
                continue
            matches = [kw for kw in keywords if kw and kw in haystack]
            if len(matches) > len(best_matches):
                best_type = doc_type
                best_matches = matches

        if not best_type or not best_matches:
            return None

        total_keywords = len(self._keyword_map[best_type]) or 1
        confidence = min(1.0, len(best_matches) / total_keywords)
        display_name = self.get_display_name(best_type)

        return ClassificationResult(
            document_type=best_type,
            display_name=display_name,
            confidence=round(confidence, 2),
            matched_keywords=best_matches,
            reason=None,
        )

    def _classify_with_llm(
        self,
        *,
        filename: str,
        text_sample: str,
        haystack: str,
        template_result: Optional[ClassificationResult],
    ) -> Optional[ClassificationResult]:
        if not self._openai_client:
            return None

        excerpt = text_sample[: self._max_prompt_chars] if self._max_prompt_chars else text_sample
        prompt = self._render_prompt(filename=filename, excerpt=excerpt)

        schema = {
            "name": "document_classification",
            "schema": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "enum": [option["id"] for option in self._llm_options],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string"},
                },
                "required": ["document_type", "confidence"],
                "additionalProperties": False,
            },
        }

        request_payload = {
            "model": self._openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a meticulous assistant that classifies Japanese corporate "
                        "disclosure documents. Respond ONLY with valid JSON that matches the "
                        "provided schema."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }

        response_format = {"type": "json_schema", "json_schema": schema}

        try:
            response = self._invoke_openai(request_payload, response_format)
        except Exception as exc:  # pragma: no cover - network/SDK errors
            logger.warning("OpenAI classification request failed: %s", exc, exc_info=exc)
            return None

        raw = self._extract_output_text(response)
        if not raw:
            logger.warning("OpenAI classification returned empty output")
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse OpenAI classification payload: %s", exc, exc_info=exc)
            return None

        document_type = payload.get("document_type")
        if not isinstance(document_type, str):
            return None

        if document_type not in self._display_map:
            logger.warning("OpenAI classification returned unsupported type: %s", document_type)
            return None

        if document_type == "unknown":
            matched_keywords: List[str] = []
        else:
            matched_keywords = self._collect_keywords(document_type, haystack) or []

        raw_confidence = payload.get("confidence")
        if isinstance(raw_confidence, (int, float)):
            numeric_confidence = float(raw_confidence)
        else:
            numeric_confidence = 0.5

        numeric_confidence = round(max(0.0, min(numeric_confidence, 1.0)), 2)

        # LLMから返された判定理由を取得
        reason = payload.get("reason")
        if not isinstance(reason, str):
            reason = None

        return ClassificationResult(
            document_type=document_type,
            display_name=self.get_display_name(document_type),
            confidence=numeric_confidence,
            matched_keywords=matched_keywords,
            reason=reason,
        )

    def _invoke_openai(self, request_payload: Dict[str, Any], response_format: Dict[str, Any]) -> Any:
        # Chat Completions APIを使用
        chat_api = getattr(self._openai_client, "chat", None)
        if chat_api is None:
            raise RuntimeError("OpenAI client does not expose a chat API")
        
        completions_api = getattr(chat_api, "completions", None)
        if completions_api is None:
            raise RuntimeError("OpenAI client does not expose a chat.completions API")

        try:
            return completions_api.create(**request_payload, response_format=response_format)
        except TypeError as type_error:
            if "response_format" not in str(type_error):
                raise
            logger.info(
                "OpenAI client does not support response_format; falling back to manual parsing.",
                exc_info=type_error,
            )
            return completions_api.create(**request_payload)

    def _collect_keywords(self, document_type: str, haystack: str) -> List[str]:
        keywords = self._keyword_map.get(document_type) or []
        return [kw for kw in keywords if kw and kw in haystack]

    def _render_prompt(self, *, filename: str, excerpt: str) -> str:
        options_text = "\n".join(
            f"- id: {option['id']}\n"
            f"  display_name: {option['display_name']}\n"
            f"  description: {option['description']}\n"
            f"  keywords: {', '.join(option['keywords']) or 'なし'}"
            for option in self._llm_options
        )
        excerpt_text = excerpt.strip() or "(本文が抽出できませんでした)"
        return (
            "次のPDF書類の種別を判定してください。候補は必ず以下のIDのいずれかです。\n"
            f"{options_text}\n\n"
            f"ファイル名: {filename}\n"
            "本文抜粋:\n"
            f"{excerpt_text}"
        )

    def _extract_output_text(self, response: Any) -> str:
        # Chat Completions APIのレスポンス構造に対応
        choices = getattr(response, "choices", [])
        if choices:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message:
                content = getattr(message, "content", None)
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return ""

    def _build_openai_client(self) -> Any | None:
        try:
            from openai import OpenAI
        except ImportError:  # pragma: no cover - optional dependency guard
            logger.warning("OpenAI SDK not available; document classification will use templates only.")
            return None

        client_kwargs: Dict[str, Any] = {}
        if self._settings.openai_api_key:
            client_kwargs["api_key"] = self._settings.openai_api_key
        timeout = float(self._settings.openai_timeout_seconds or 0)
        if timeout > 0:
            client_kwargs["timeout"] = timeout

        try:
            return OpenAI(**client_kwargs)
        except Exception as exc:  # pragma: no cover - SDK init errors
            logger.warning("Failed to initialise OpenAI client: %s", exc, exc_info=exc)
            return None


def get_document_classifier(settings: Optional[Settings] = None) -> DocumentClassifier:
    """Return a classifier instance configured for the current environment."""

    return DocumentClassifier(settings=settings)
