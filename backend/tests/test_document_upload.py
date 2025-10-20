from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.services.document_upload import (
    DocumentUploadManager,
    NoFilesProvidedError,
    TooManyFilesError,
)


def _make_upload(filename: str, data: bytes, content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(data), headers={"content-type": content_type})


@pytest.mark.asyncio
async def test_accepts_valid_pdf(tmp_path: Path) -> None:
    settings = Settings(
        document_upload_max_files=5,
        document_upload_max_file_size_mb=2,
        upload_storage_dir=str(tmp_path),
        metadata_storage_dir=str(tmp_path / "metadata"),
        openai_api_key=None,
        document_classification_use_llm=False,
    )
    manager = DocumentUploadManager(settings=settings, storage_dir=tmp_path)
    payload = b"%PDF-1.7\nSample Disclosure Document\n"

    batch = await manager.process([_make_upload("report.pdf", payload)])
    assert len(batch.documents) == 1

    document = batch.documents[0]
    assert document.status == "accepted"
    assert document.document_id is not None
    assert (tmp_path / f"{document.document_id}.pdf").exists()
    assert document.processing_status == "queued"
    assert document.manual_type is None


@pytest.mark.asyncio
async def test_rejects_non_pdf_file(tmp_path: Path) -> None:
    settings = Settings(
        document_upload_max_files=5,
        document_upload_max_file_size_mb=2,
        upload_storage_dir=str(tmp_path),
        metadata_storage_dir=str(tmp_path / "metadata"),
        openai_api_key=None,
        document_classification_use_llm=False,
    )
    manager = DocumentUploadManager(settings=settings, storage_dir=tmp_path)

    batch = await manager.process(
        [_make_upload("notes.txt", b"not a pdf", content_type="text/plain")]
    )
    document = batch.documents[0]
    assert document.status == "rejected"
    assert any("Only valid PDF" in error for error in document.errors)


@pytest.mark.asyncio
async def test_raises_when_too_many_files(tmp_path: Path) -> None:
    settings = Settings(
        document_upload_max_files=1,
        document_upload_max_file_size_mb=2,
        upload_storage_dir=str(tmp_path),
        metadata_storage_dir=str(tmp_path / "metadata"),
        openai_api_key=None,
        document_classification_use_llm=False,
    )
    manager = DocumentUploadManager(settings=settings, storage_dir=tmp_path)
    payload = b"%PDF-1.7\nSample\n"

    with pytest.raises(TooManyFilesError):
        await manager.process(
            [
                _make_upload("a.pdf", payload),
                _make_upload("b.pdf", payload),
            ]
        )


@pytest.mark.asyncio
async def test_raises_when_no_files(tmp_path: Path) -> None:
    settings = Settings(
        document_upload_max_files=5,
        document_upload_max_file_size_mb=2,
        upload_storage_dir=str(tmp_path),
        metadata_storage_dir=str(tmp_path / "metadata"),
        openai_api_key=None,
        document_classification_use_llm=False,
    )
    manager = DocumentUploadManager(settings=settings, storage_dir=tmp_path)

    with pytest.raises(NoFilesProvidedError):
        await manager.process([])
