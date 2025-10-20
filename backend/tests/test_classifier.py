from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.services.classifier import DocumentClassifier


@dataclass
class _FakeResponse:
    output_text: str


class _FakeResponses:
    def __init__(self, response: _FakeResponse | None, should_raise: bool = False) -> None:
        self._response = response
        self._should_raise = should_raise

    def create(self, **_: object) -> _FakeResponse:
        if self._should_raise:
            raise RuntimeError("LLM call failed")
        if self._response is None:
            raise AssertionError("No response configured for fake client")
        return self._response


class _FakeOpenAI:
    def __init__(self, response: _FakeResponse | None, should_raise: bool = False) -> None:
        self.responses = _FakeResponses(response=response, should_raise=should_raise)


_EARNINGS_TEXT = """
決算短信
本書類は2024年3月期の連結業績速報です。売上高および営業利益について解説します。
"""


def test_classifier_uses_llm_for_classification() -> None:
    settings = Settings(
        openai_api_key="test-key",
        document_classification_use_llm=True,
    )
    fake_response = _FakeResponse(
        output_text='{"document_type": "earnings_report", "confidence": 0.87}'
    )
    classifier = DocumentClassifier(settings=settings, openai_client=_FakeOpenAI(fake_response))

    result = classifier.classify(filename="report.pdf", text_sample=_EARNINGS_TEXT)

    assert result is not None
    assert result.document_type == "earnings_report"
    assert pytest.approx(result.confidence, rel=0, abs=1e-6) == 0.87
    assert "決算短信" in result.matched_keywords


def test_classifier_returns_none_on_llm_failure() -> None:
    settings = Settings(
        openai_api_key="test-key",
        document_classification_use_llm=True,
    )
    classifier = DocumentClassifier(
        settings=settings,
        openai_client=_FakeOpenAI(response=None, should_raise=True),
    )

    result = classifier.classify(filename="report.pdf", text_sample=_EARNINGS_TEXT)

    assert result is None


def test_classifier_returns_none_when_llm_not_configured() -> None:
    settings = Settings(
        openai_api_key=None,
        document_classification_use_llm=False,
    )
    classifier = DocumentClassifier(settings=settings, openai_client=None)

    result = classifier.classify(filename="report.pdf", text_sample=_EARNINGS_TEXT)

    assert result is None
