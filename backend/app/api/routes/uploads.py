from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ...core.config import get_settings
from ...schemas.documents import (
    DocumentListResponse,
    DocumentMutationResponse,
    DocumentTypeUpdateRequest,
    DocumentUploadLimits,
    DocumentUploadResponse,
    DocumentUploadResult,
)
from ...services.document_upload import (
    DocumentUploadManager,
    NoFilesProvidedError,
    TooManyFilesError,
    UploadValidationError,
)
from ...services.metadata_store import DocumentMetadataStore
from ...services.classifier import get_document_classifier
from ...workers.tasks import process_documents_task

router = APIRouter()
logger = logging.getLogger(__name__)


def _metadata_to_result(metadata, classifier) -> DocumentUploadResult:
    selected_type = metadata.manual_type or metadata.detected_type
    selected_label = metadata.manual_type_label or metadata.detected_type_label

    return DocumentUploadResult(
        document_id=metadata.document_id,
        filename=metadata.filename,
        size_bytes=metadata.size_bytes,
        status=metadata.status,  # type: ignore[arg-type]
        errors=[],
        detected_type=metadata.detected_type,
        detected_type_label=metadata.detected_type_label,
        detection_confidence=metadata.detection_confidence,
        matched_keywords=metadata.matched_keywords,
        detection_reason=metadata.detection_reason,
        processing_status=metadata.processing_status,  # type: ignore[arg-type]
        manual_type=metadata.manual_type,
        manual_type_label=metadata.manual_type_label,
        selected_type=selected_type,
        selected_type_label=selected_label,
        # 構造化データ関連フィールド
        structured_data=metadata.structured_data,
        extraction_method=metadata.extraction_method,  # type: ignore[arg-type]
        extraction_metadata=metadata.extraction_metadata,
    )


@router.get(
    "/",
    summary="List all documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    tags=["documents"],
)
async def list_documents() -> DocumentListResponse:
    """Retrieve metadata for all uploaded documents."""
    
    settings = get_settings()
    classifier = get_document_classifier(settings)
    metadata_store = DocumentMetadataStore(settings)
    
    metadata_list = metadata_store.list_all()
    
    documents = [_metadata_to_result(metadata, classifier) for metadata in metadata_list]
    
    return DocumentListResponse(
        documents=documents,
        total=len(documents),
    )


@router.post(
    "/",
    summary="Upload disclosure documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["documents"],
)
async def upload_documents(
    files: Annotated[List[UploadFile], File(description="One or more PDF documents.")],
) -> DocumentUploadResponse:
    """Accept multiple disclosure PDFs, validate them, and enqueue processing."""

    settings = get_settings()
    manager = DocumentUploadManager(settings=settings)

    try:
        batch_result = await manager.process(files)
    except NoFilesProvidedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TooManyFilesError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unexpected error while processing uploads", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process the provided documents.",
        ) from exc

    task_id = None
    accepted_ids = batch_result.accepted_document_ids
    
    # 書類種別が「unknown」でない書類のみをキューイング対象とする
    metadata_store = DocumentMetadataStore(settings)
    queueable_ids = []
    for doc_id in accepted_ids:
        try:
            metadata = metadata_store.load(doc_id)
            selected_type = metadata.manual_type or metadata.detected_type
            if selected_type and selected_type != "unknown":
                queueable_ids.append(doc_id)
            else:
                # 未判定の書類はステータスを「分類待ち」に更新
                metadata.processing_status = "pending_classification"
                metadata_store.save(metadata)
                logger.info(f"Document {doc_id} has unknown type, skipping structuring task")
        except FileNotFoundError:
            logger.warning(f"Metadata for document {doc_id} not found, skipping")
    
    # Celeryタスクをキューイング
    if queueable_ids:
        try:
            async_result = process_documents_task.delay(queueable_ids)
            task_id = async_result.id
            logger.info(f"Enqueued Celery task {task_id} for {len(queueable_ids)} documents")
        except Exception as exc:  # pragma: no cover - Celery connection optional in tests
            logger.warning("Failed to enqueue Celery task: %s", exc, exc_info=exc)

    response_documents = [
        DocumentUploadResult(**doc.to_dict()) for doc in batch_result.documents
    ]

    limits = DocumentUploadLimits(
        max_files=settings.document_upload_max_files,
        max_file_size_mb=settings.document_upload_max_file_size_mb,
    )

    return DocumentUploadResponse(
        batch_id=batch_result.batch_id,
        task_id=task_id,
        limits=limits,
        documents=response_documents,
    )


@router.get(
    "/{document_id}",
    summary="Get document metadata",
    response_model=DocumentMutationResponse,
    status_code=status.HTTP_200_OK,
    tags=["documents"],
)
async def get_document(document_id: str) -> DocumentMutationResponse:
    """Retrieve metadata for a specific document."""
    
    settings = get_settings()
    classifier = get_document_classifier(settings)
    metadata_store = DocumentMetadataStore(settings)
    
    try:
        metadata = metadata_store.load(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    
    result = _metadata_to_result(metadata, classifier)
    return DocumentMutationResponse(document=result)


@router.patch(
    "/{document_id}",
    summary="Override detected document type",
    response_model=DocumentMutationResponse,
    status_code=status.HTTP_200_OK,
    tags=["documents"],
)
async def update_document_type(
    document_id: str,
    payload: DocumentTypeUpdateRequest,
) -> DocumentMutationResponse:
    """Persist a user-selected document type override."""

    settings = get_settings()
    classifier = get_document_classifier(settings)
    metadata_store = DocumentMetadataStore(settings)

    requested_type = payload.document_type
    manual_type: Optional[str]
    manual_label: Optional[str]

    if requested_type is None:
        manual_type = None
        manual_label = None
    elif requested_type == "unknown":
        manual_type = "unknown"
        manual_label = "未判定"
    else:
        if not classifier.is_supported_type(requested_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported document type override provided.",
            )
        manual_type = requested_type
        manual_label = classifier.get_display_name(requested_type)

    try:
        metadata = metadata_store.upsert_manual_type(
            document_id,
            manual_type=manual_type,
            manual_type_label=manual_label,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # 書類種別が有効になった場合、構造化タスクをキューイング
    selected_type = metadata.manual_type or metadata.detected_type
    if selected_type and selected_type != "unknown":
        # ステータスを「キュー待ち」に更新
        metadata.processing_status = "queued"
        metadata_store.save(metadata)
        
        # 構造化タスクをキューイング
        try:
            async_result = process_documents_task.delay([document_id])
            logger.info(
                f"Enqueued structuring task {async_result.id} for document {document_id} "
                f"after manual type selection: {selected_type}"
            )
        except Exception as exc:  # pragma: no cover - Celery connection optional
            logger.warning("Failed to enqueue structuring task: %s", exc, exc_info=exc)

    result = _metadata_to_result(metadata, classifier)
    return DocumentMutationResponse(document=result)
