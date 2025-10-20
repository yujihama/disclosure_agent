#!/usr/bin/env python3
"""設定値デバッグスクリプト"""
import logging
import sys
sys.path.insert(0, '.')

# ログレベルを設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from app.core.config import get_settings

settings = get_settings()

print("=" * 60)
print("CONFIGURATION DEBUG")
print("=" * 60)
print(f"Environment: {settings.environment}")
print(f"OpenAI API Key: {settings.openai_api_key}")
print(f"OpenAI API Key present: {bool(settings.openai_api_key)}")
if settings.openai_api_key:
    print(f"OpenAI API Key length: {len(settings.openai_api_key)}")
    print(f"OpenAI API Key first 30 chars: {settings.openai_api_key[:30]}...")
print(f"OpenAI Model: {settings.openai_model}")
print(f"LLM Classification Use: {settings.document_classification_use_llm}")
print(f"Max Prompt Chars: {settings.document_classification_max_prompt_chars}")
print("=" * 60)

# Classifierの初期化をテスト
print("\nTesting DocumentClassifier initialization...")
from app.services.classifier import DocumentClassifier

classifier = DocumentClassifier(settings=settings)
print(f"Classifier created successfully")
print(f"Classifier has OpenAI client: {classifier._openai_client is not None}")
print(f"Classifier LLM enabled: {classifier._llm_enabled}")

# OpenAI clientを直接テスト
print("\nTesting OpenAI client directly...")
try:
    from openai import OpenAI
    test_client = OpenAI(api_key=settings.openai_api_key, timeout=10.0)
    print(f"OpenAI client created: {test_client}")
    
    # シンプルなテストリクエスト
    print("\nSending test request to OpenAI...")
    response = test_client.chat.completions.create(
        model="gpt-4o-mini",  # 有効なモデル名
        messages=[
            {"role": "user", "content": "Hello, say 'test' in JSON format"}
        ],
        response_format={"type": "json_object"}
    )
    print(f"OpenAI API response: {response.choices[0].message.content}")
except Exception as e:
    print(f"ERROR testing OpenAI client: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# テスト分類
print("\n" + "=" * 60)
print("Testing classification...")
print("=" * 60)
test_result = classifier.classify(
    filename="test.pdf",
    text_sample="有価証券報告書 第一部 企業情報"
)
print(f"Classification result: {test_result}")
if test_result:
    print(f"  - document_type: {test_result.document_type}")
    print(f"  - confidence: {test_result.confidence}")
    print(f"  - reason: {test_result.reason}")
else:
    print("  - Result is None - check logs above for errors")

