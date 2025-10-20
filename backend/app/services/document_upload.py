from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence
from uuid import uuid4

import fitz  # PyMuPDF
from fastapi import UploadFile

from ..core.config import Settings, resolve_upload_storage_path
from .classifier import ClassificationResult, get_document_classifier
from .metadata_store import DocumentMetadata, DocumentMetadataStore

logger = logging.getLogger(__name__)

PDF_SIGNATURE = b"%PDF"
_DEFAULT_SAMPLE_BYTES = 64_000
_MAX_PAGES_TO_EXTRACT = 5  # 最初の5ページからテキストを抽出


class UploadValidationError(Exception):
    """Base class for upload validation issues."""


class TooManyFilesError(UploadValidationError):
    """Raised when the number of submitted files exceeds the configured limit."""


class NoFilesProvidedError(UploadValidationError):
    """Raised when the request does not contain any files."""


@dataclass(slots=True)
class ProcessedDocument:
    document_id: Optional[str]
    filename: str
    size_bytes: int
    status: str
    errors: List[str]
    detected_type: Optional[str]
    detected_type_label: Optional[str]
    detection_confidence: Optional[float]
    matched_keywords: List[str]
    detection_reason: Optional[str]
    processing_status: Optional[str]
    manual_type: Optional[str]
    manual_type_label: Optional[str]
    selected_type: Optional[str]
    selected_type_label: Optional[str]
    storage_path: Optional[str] = None

    def to_dict(self) -> dict:
        """Return serialisable representation for API responses."""

        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "errors": self.errors,
            "detected_type": self.detected_type,
            "detected_type_label": self.detected_type_label,
            "detection_confidence": self.detection_confidence,
            "matched_keywords": self.matched_keywords,
            "detection_reason": self.detection_reason,
            "processing_status": self.processing_status,
            "manual_type": self.manual_type,
            "manual_type_label": self.manual_type_label,
            "selected_type": self.selected_type,
            "selected_type_label": self.selected_type_label,
        }


@dataclass(slots=True)
class UploadBatchResult:
    batch_id: str
    documents: List[ProcessedDocument]

    @property
    def accepted_document_ids(self) -> List[str]:
        return [
            doc.document_id
            for doc in self.documents
            if doc.status == "accepted" and doc.document_id is not None
        ]


class DocumentUploadManager:
    """Coordinate validations, storage, and classification for uploaded documents."""

    def __init__(
        self,
        *,
        settings: Settings,
        classifier=None,
        storage_dir: Optional[Path] = None,
        sample_bytes: int = _DEFAULT_SAMPLE_BYTES,
    ) -> None:
        self._settings = settings
        self._classifier = classifier or get_document_classifier(settings)
        self._metadata_store = DocumentMetadataStore(settings)
        self._storage_path = (
            resolve_upload_storage_path(settings) if storage_dir is None else Path(storage_dir)
        )
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._sample_bytes = sample_bytes
        self._max_files = settings.document_upload_max_files
        self._max_file_size_bytes = settings.document_upload_max_file_size_mb * 1024 * 1024

    async def process(self, files: Sequence[UploadFile]) -> UploadBatchResult:
        if not files:
            raise NoFilesProvidedError("At least one PDF must be provided.")
        if len(files) > self._max_files:
            raise TooManyFilesError(
                f"Maximum number of files exceeded. Up to {self._max_files} files are allowed."
            )

        documents: List[ProcessedDocument] = []
        for upload in files:
            processed = await self._handle_single_file(upload)
            documents.append(processed)

        return UploadBatchResult(batch_id=str(uuid4()), documents=documents)

    async def _handle_single_file(self, upload: UploadFile) -> ProcessedDocument:
        filename = upload.filename or "document.pdf"
        logger.info(f"Processing file: {filename}")
        
        await upload.seek(0)
        payload = await upload.read()
        size_bytes = len(payload)
        await upload.close()
        logger.info(f"File read complete: {filename}, size: {size_bytes} bytes")

        errors: List[str] = []
        if size_bytes == 0:
            errors.append("The file is empty.")

        if size_bytes > self._max_file_size_bytes:
            errors.append(
                f"File size {self._bytes_to_mb(size_bytes):.2f}MB exceeds the limit of "
                f"{self._settings.document_upload_max_file_size_mb}MB."
            )

        if not self._is_pdf(upload.content_type, payload):
            errors.append("Only valid PDF documents can be uploaded.")

        detected_result: Optional[ClassificationResult] = None
        if not errors:
            logger.info(f"Extracting text from PDF: {filename}")
            text_sample = self._extract_text_sample(payload)
            logger.info(f"Text extracted: {len(text_sample)} characters from {filename}")
            
            logger.info(f"Classifying document: {filename}")
            detected_result = self._classifier.classify(filename=filename, text_sample=text_sample)
            if detected_result:
                logger.info(
                    f"Classification result for {filename}: "
                    f"type={detected_result.document_type}, "
                    f"confidence={detected_result.confidence}"
                )
            else:
                logger.warning(f"Classification failed for {filename}")

        document_id: Optional[str] = None
        storage_path: Optional[str] = None
        if not errors:
            document_id = str(uuid4())
            storage_path = str(self._storage_path / f"{document_id}.pdf")
            try:
                with open(storage_path, "wb") as handle:
                    handle.write(payload)
            except OSError as exc:
                logger.exception("Failed to persist uploaded PDF", exc_info=exc)
                errors.append("Unable to persist uploaded document. Please retry later.")

        status = "accepted" if not errors else "rejected"
        detected_type = detected_result.document_type if detected_result else None
        detected_label = detected_result.display_name if detected_result else None
        confidence = detected_result.confidence if detected_result else None
        matched_keywords = detected_result.matched_keywords if detected_result else []
        detection_reason = detected_result.reason if detected_result else None

        manual_type: Optional[str] = None
        manual_label: Optional[str] = None
        processing_status = "queued" if status == "accepted" else "rejected"
        selected_type = manual_type or detected_type
        selected_label = manual_label or detected_label

        processed = ProcessedDocument(
            document_id=document_id,
            filename=filename,
            size_bytes=size_bytes,
            status=status,
            errors=errors,
            detected_type=detected_type,
            detected_type_label=detected_label,
            detection_confidence=confidence,
            matched_keywords=matched_keywords,
            detection_reason=detection_reason,
            processing_status=processing_status,
            manual_type=manual_type,
            manual_type_label=manual_label,
            selected_type=selected_type,
            selected_type_label=selected_label,
            storage_path=storage_path,
        )

        if status == "accepted" and document_id and storage_path:
            metadata = DocumentMetadata(
                document_id=document_id,
                filename=filename,
                stored_path=storage_path,
                size_bytes=size_bytes,
                detected_type=detected_type,
                detected_type_label=detected_label,
                detection_confidence=confidence,
                matched_keywords=matched_keywords,
                detection_reason=detection_reason,
                manual_type=manual_type,
                manual_type_label=manual_label,
                status=status,
                processing_status="queued",
            )
            self._metadata_store.save(metadata)

        return processed

    def _is_pdf(self, content_type: Optional[str], payload: bytes) -> bool:
        if content_type and content_type.lower() not in {"application/pdf", "application/x-pdf"}:
            return False
        return payload.startswith(PDF_SIGNATURE)

    def _extract_text_sample(self, payload: bytes) -> str:
        """PDFからテキストを抽出（最初の数ページから）"""
        try:
            # PyMuPDFを使用してPDFからテキストを抽出
            pdf_stream = io.BytesIO(payload)
            with fitz.open(stream=pdf_stream, filetype="pdf") as doc:
                text_parts = []
                # 最初の数ページからテキストを抽出
                max_pages = min(len(doc), _MAX_PAGES_TO_EXTRACT)
                for page_num in range(max_pages):
                    page = doc[page_num]
                    text = page.get_text()
                    if text:
                        text_parts.append(text)
                
                full_text = "\n".join(text_parts)
                # サンプルサイズに制限
                if len(full_text) > self._sample_bytes:
                    return full_text[:self._sample_bytes]
                return full_text
        except Exception as exc:
            logger.warning("Failed to extract text from PDF: %s", exc, exc_info=exc)
            # フォールバック: バイト列から直接デコード試行
            sample = payload[: self._sample_bytes]
            try:
                return sample.decode("utf-8", errors="ignore")
            except UnicodeDecodeError:
                return sample.decode("latin-1", errors="ignore")

    @staticmethod
    def _bytes_to_mb(size: int) -> float:
        return size / (1024 * 1024)
