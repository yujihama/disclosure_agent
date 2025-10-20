from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DocumentUploadLimits(BaseModel):
    """Surface upload constraints to the front end."""

    max_files: int = Field(..., ge=1, description="Maximum number of files accepted per request.")
    max_file_size_mb: int = Field(..., ge=1, description="Maximum size of a PDF in megabytes.")


class DocumentUploadResult(BaseModel):
    """Details about a single processed document in the batch."""

    document_id: Optional[str] = Field(None, description="Internal identifier for the stored PDF.")
    filename: str = Field(..., description="Original filename supplied by the client.")
    size_bytes: int = Field(..., ge=0, description="Raw file size in bytes.")
    status: Literal["accepted", "rejected"] = Field(..., description="Processing outcome.")
    errors: list[str] = Field(default_factory=list, description="Validation errors encountered.")
    detected_type: Optional[str] = Field(
        None, description="Predicted document type identifier (e.g., securities_report)."
    )
    detected_type_label: Optional[str] = Field(None, description="Human readable document type label.")
    detection_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score for the predicted type (0-1).",
    )
    matched_keywords: list[str] = Field(
        default_factory=list,
        description="Template keywords that supported the predicted type.",
    )
    detection_reason: Optional[str] = Field(
        None,
        description="LLM-generated reason explaining the document type classification.",
    )
    processing_status: Optional[
        Literal[
            "queued",
            "pending_classification",
            "processing",
            "extracting_text",
            "extracting_vision",
            "extracting_tables",
            "detecting_sections",
            "structured",
            "completed",
            "failed",
            "rejected",
        ]
    ] = Field(
        None,
        description="Background processing status managed by Celery workers.",
    )
    manual_type: Optional[str] = Field(None, description="User-selected document type override.")
    manual_type_label: Optional[str] = Field(
        None, description="Display name for the user-selected document type."
    )
    selected_type: Optional[str] = Field(
        None, description="Effective document type after applying overrides."
    )
    selected_type_label: Optional[str] = Field(
        None, description="Display name for the effective document type."
    )
    # 構造化データ関連フィールド
    structured_data: Optional[dict[str, Any]] = Field(
        None, description="Structured data extracted from the document."
    )
    extraction_method: Optional[Literal["text", "vision", "hybrid"]] = Field(
        None, description="Method used for text extraction."
    )
    extraction_metadata: Optional[dict[str, Any]] = Field(
        None, description="Metadata about the extraction process."
    )


class DocumentUploadResponse(BaseModel):
    """Batch-level response emitted after uploads are accepted."""

    batch_id: str = Field(..., description="Identifier for the upload batch.")
    task_id: Optional[str] = Field(
        None, description="Identifier of the asynchronous processing task, when scheduled."
    )
    limits: DocumentUploadLimits
    documents: list[DocumentUploadResult]


class DocumentTypeUpdateRequest(BaseModel):
    """Payload submitted when a user overrides the detected document type."""

    document_type: Optional[str] = Field(
        None,
        description="New document type identifier to apply. Pass null to clear the override.",
    )


class DocumentMutationResponse(BaseModel):
    """Response payload returned after document metadata mutations."""

    document: DocumentUploadResult


class DocumentListResponse(BaseModel):
    """Response payload containing a list of documents."""

    documents: list[DocumentUploadResult]
    total: int = Field(..., description="Total number of documents.")
