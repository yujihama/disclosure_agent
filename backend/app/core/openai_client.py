"""OpenAI クライアントを設定に基づいて生成するヘルパー."""

from __future__ import annotations

import logging
from typing import Any

from .config import Settings

logger = logging.getLogger(__name__)


def create_openai_client(
    settings: Settings,
    *,
    api_key: str | None = None,
    timeout: float | None = None,
) -> Any | None:
    """環境設定に合わせた OpenAI 互換クライアントを生成する."""

    api_token = api_key or settings.openai_api_key
    if not api_token:
        logger.warning("OpenAI APIキーが設定されていないため、クライアントを生成できません")
        return None

    try:
        from openai import AzureOpenAI, OpenAI  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency guard
        logger.warning("openai ライブラリがインストールされていないため、LLM機能を無効化します")
        return None

    client_kwargs: dict[str, Any] = {}
    timeout_seconds = timeout if timeout is not None else settings.openai_timeout_seconds
    if timeout_seconds and timeout_seconds > 0:
        client_kwargs["timeout"] = timeout_seconds

    if settings.use_azure_openai:
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_version:
            logger.warning(
                "Azure OpenAI を使用するには APP_AZURE_OPENAI_ENDPOINT と APP_AZURE_OPENAI_API_VERSION の設定が必要です"
            )
            return None

        client_kwargs.update(
            {
                "azure_endpoint": settings.azure_openai_endpoint,
                "api_key": api_token,
                "api_version": settings.azure_openai_api_version,
            }
        )

        try:
            return AzureOpenAI(**client_kwargs)
        except Exception as exc:  # pragma: no cover - SDK init errors
            logger.warning("Azure OpenAI クライアントの初期化に失敗しました: %s", exc, exc_info=exc)
            return None

    client_kwargs["api_key"] = api_token

    try:
        return OpenAI(**client_kwargs)
    except Exception as exc:  # pragma: no cover - SDK init errors
        logger.warning("OpenAI クライアントの初期化に失敗しました: %s", exc, exc_info=exc)
        return None
