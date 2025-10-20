from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.metadata_store import DocumentMetadata, DocumentMetadataStore


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """テスト用の設定を作成"""
    return Settings(
        document_upload_max_files=5,
        document_upload_max_file_size_mb=2,
        upload_storage_dir=str(tmp_path / "uploads"),
        metadata_storage_dir=str(tmp_path / "metadata"),
        openai_api_key=None,
        document_classification_use_llm=False,
    )


@pytest.fixture
def client(test_settings: Settings, monkeypatch) -> TestClient:
    """テスト用のFastAPIクライアントを作成"""
    from functools import lru_cache
    
    @lru_cache
    def get_test_settings() -> Settings:
        return test_settings
    
    monkeypatch.setattr("app.core.config.get_settings", get_test_settings)
    
    app = create_app()
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    """ヘルスチェックエンドポイントのテスト"""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_valid_pdf(client: TestClient) -> None:
    """有効なPDFのアップロードテスト"""
    pdf_content = "%PDF-1.7\n有価証券報告書\n金融商品取引法\n事業年度\n連結財務諸表\n".encode("utf-8")
    files = {"files": ("report.pdf", BytesIO(pdf_content), "application/pdf")}
    
    response = client.post("/api/documents/", files=files)
    
    assert response.status_code == 202
    data = response.json()
    assert "batch_id" in data
    assert "documents" in data
    assert len(data["documents"]) == 1
    
    document = data["documents"][0]
    assert document["status"] == "accepted"
    assert document["filename"] == "report.pdf"
    assert document["document_id"] is not None


def test_upload_empty_file(client: TestClient) -> None:
    """空のファイルのアップロードテスト"""
    files = {"files": ("empty.pdf", BytesIO(b""), "application/pdf")}
    
    response = client.post("/api/documents/", files=files)
    
    assert response.status_code == 202
    data = response.json()
    document = data["documents"][0]
    assert document["status"] == "rejected"
    assert any("empty" in error.lower() for error in document["errors"])


def test_upload_non_pdf_file(client: TestClient) -> None:
    """PDF以外のファイルのアップロードテスト"""
    files = {"files": ("notes.txt", BytesIO(b"not a pdf"), "text/plain")}
    
    response = client.post("/api/documents/", files=files)
    
    assert response.status_code == 202
    data = response.json()
    document = data["documents"][0]
    assert document["status"] == "rejected"
    assert any("PDF" in error for error in document["errors"])


def test_upload_oversized_file(client: TestClient) -> None:
    """サイズ上限を超えるファイルのアップロードテスト"""
    # 3MB（上限2MB）
    large_content = b"%PDF-1.7\n" + b"x" * (3 * 1024 * 1024)
    files = {"files": ("large.pdf", BytesIO(large_content), "application/pdf")}
    
    response = client.post("/api/documents/", files=files)
    
    assert response.status_code == 202
    data = response.json()
    document = data["documents"][0]
    assert document["status"] == "rejected"
    assert any("exceeds the limit" in error for error in document["errors"])


def test_get_document(client: TestClient, test_settings: Settings) -> None:
    """個別ドキュメント取得のテスト"""
    # まずアップロード
    pdf_content = b"%PDF-1.7\nTest Document\n"
    files = {"files": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
    upload_response = client.post("/api/documents/", files=files)
    document_id = upload_response.json()["documents"][0]["document_id"]
    
    # ドキュメントを取得
    response = client.get(f"/api/documents/{document_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["document"]["document_id"] == document_id
    assert data["document"]["filename"] == "test.pdf"


def test_get_nonexistent_document(client: TestClient) -> None:
    """存在しないドキュメントの取得テスト"""
    response = client.get("/api/documents/nonexistent-id")
    assert response.status_code == 404


def test_list_documents(client: TestClient) -> None:
    """ドキュメント一覧取得のテスト"""
    # 複数ファイルをアップロード
    pdf_content = b"%PDF-1.7\nTest\n"
    files = [
        ("files", ("doc1.pdf", BytesIO(pdf_content), "application/pdf")),
        ("files", ("doc2.pdf", BytesIO(pdf_content), "application/pdf")),
    ]
    client.post("/api/documents/", files=files)
    
    # 一覧を取得
    response = client.get("/api/documents/")
    
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert data["total"] >= 2


def test_update_document_type(client: TestClient) -> None:
    """書類種別の手動設定テスト"""
    # まずアップロード
    pdf_content = b"%PDF-1.7\nTest Document\n"
    files = {"files": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
    upload_response = client.post("/api/documents/", files=files)
    document_id = upload_response.json()["documents"][0]["document_id"]
    
    # 書類種別を変更
    response = client.patch(
        f"/api/documents/{document_id}",
        json={"document_type": "integrated_report"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["document"]["manual_type"] == "integrated_report"
    assert data["document"]["selected_type"] == "integrated_report"


def test_clear_manual_document_type(client: TestClient) -> None:
    """書類種別の手動設定クリアテスト"""
    # まずアップロード
    pdf_content = b"%PDF-1.7\nTest\n"
    files = {"files": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
    upload_response = client.post("/api/documents/", files=files)
    document_id = upload_response.json()["documents"][0]["document_id"]
    
    # 書類種別を設定
    client.patch(f"/api/documents/{document_id}", json={"document_type": "integrated_report"})
    
    # クリア
    response = client.patch(f"/api/documents/{document_id}", json={"document_type": None})
    
    assert response.status_code == 200
    data = response.json()
    assert data["document"]["manual_type"] is None


def test_update_nonexistent_document(client: TestClient) -> None:
    """存在しないドキュメントの更新テスト"""
    response = client.patch(
        "/api/documents/nonexistent-id",
        json={"document_type": "integrated_report"},
    )
    assert response.status_code == 404


def test_update_with_invalid_document_type(client: TestClient) -> None:
    """無効な書類種別の設定テスト"""
    # まずアップロード
    pdf_content = b"%PDF-1.7\nTest\n"
    files = {"files": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
    upload_response = client.post("/api/documents/", files=files)
    document_id = upload_response.json()["documents"][0]["document_id"]
    
    # 無効な書類種別を設定
    response = client.patch(
        f"/api/documents/{document_id}",
        json={"document_type": "invalid_type"},
    )
    
    assert response.status_code == 400
    assert "Unsupported document type" in response.json()["detail"]

