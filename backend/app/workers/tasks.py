from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from ..core.config import get_settings
from ..services.metadata_store import DocumentMetadataStore
from ..services.structuring import TableExtractor, TextExtractor, VisionExtractor
from ..services.structuring.section_detector import SectionDetector
from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="documents.process")
def process_documents_task(document_ids: list[str]) -> dict[str, list[dict[str, str]]]:
    """
    ドキュメントのバッチ処理タスク（順次処理）
    各ドキュメントに対して構造化処理を実行する
    """

    settings = get_settings()
    metadata_store = DocumentMetadataStore(settings)
    processed: list[dict[str, str]] = []

    for document_id in document_ids:
        try:
            # メタデータを読み込んで書類種別を確認
            metadata = metadata_store.load(document_id)
            selected_type = metadata.manual_type or metadata.detected_type
            
            # 書類種別が「unknown」または未設定の場合はスキップ
            if not selected_type or selected_type == "unknown":
                logger.info(
                    f"Skipping structuring for document {document_id}: "
                    f"type is {selected_type or 'unset'}"
                )
                metadata_store.update_processing_status(document_id, status="pending_classification")
                processed.append({"document_id": document_id, "status": "skipped", "reason": "unknown_type"})
                continue
            
            metadata_store.update_processing_status(document_id, status="processing")
            
            # 構造化タスクを直接同期実行
            result = structure_document_task(document_id)
            
            if result.get("status") == "structured":
                processed.append({"document_id": document_id, "status": "completed"})
            else:
                processed.append({"document_id": document_id, "status": "failed"})
                
        except FileNotFoundError:
            logger.warning("No metadata found for document %s", document_id)
            processed.append({"document_id": document_id, "status": "failed"})
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to process document %s", document_id, exc_info=exc)
            try:
                metadata_store.update_processing_status(document_id, status="failed")
            except:
                pass
            processed.append({"document_id": document_id, "status": "failed"})

    # 処理完了後に期限切れドキュメントをクリーンアップ
    try:
        deleted_count = metadata_store.cleanup_expired()
        if deleted_count > 0:
            logger.info(f"Auto-cleanup: deleted {deleted_count} expired documents")
    except Exception as exc:
        logger.warning(f"Auto-cleanup failed: {exc}")

    return {"processed": processed}


@celery_app.task(name="documents.cleanup_expired")
def cleanup_expired_documents_task() -> dict[str, int]:
    """期限切れのドキュメントを削除する定期タスク"""

    settings = get_settings()
    metadata_store = DocumentMetadataStore(settings)
    
    try:
        deleted_count = metadata_store.cleanup_expired()
        logger.info(f"Cleanup task completed: deleted {deleted_count} expired documents")
        return {"deleted_count": deleted_count}
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Cleanup task failed", exc_info=exc)
        return {"deleted_count": 0, "error": str(exc)}


@celery_app.task(name="documents.structure")
def structure_document_task(document_id: str) -> dict[str, any]:
    """
    ドキュメントを構造化処理するタスク
    
    Args:
        document_id: 処理対象のドキュメントID
        
    Returns:
        処理結果を含む辞書
    """
    settings = get_settings()
    metadata_store = DocumentMetadataStore(settings)
    
    try:
        # メタデータを取得
        metadata = metadata_store.load(document_id)
        pdf_path = Path(metadata.stored_path)
        
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            metadata_store.update_processing_status(document_id, status="failed")
            return {"document_id": document_id, "status": "failed", "error": "PDF not found"}
        
        logger.info(f"Starting structuring for document {document_id}: {metadata.filename}")
        
        # ステップ1: テキスト抽出
        metadata_store.update_processing_status(document_id, status="extracting_text")
        text_extractor = TextExtractor()
        text_result = text_extractor.extract(pdf_path)
        
        extraction_method = "text"
        full_text = text_result.text
        extraction_metadata = {
            "text_extraction": {
                "success": text_result.success,
                "page_count": text_result.page_count,
                "error": text_result.error,
            }
        }
        
        # ステップ2: テキスト抽出が不十分な場合、Vision APIでフォールバック
        if not text_result.success:
            logger.info(f"Text extraction insufficient for {document_id}, falling back to Vision API")
            metadata_store.update_processing_status(document_id, status="extracting_vision")
            
            vision_extractor = VisionExtractor(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                batch_size=10,  # 10ページずつバッチ並列処理
                max_workers=10,  # 最大10スレッド並列実行
            )
            vision_result = vision_extractor.extract(pdf_path)
            
            if vision_result.success:
                full_text = vision_result.text
                extraction_method = "vision"
                extraction_metadata["vision_extraction"] = {
                    "success": vision_result.success,
                    "page_count": vision_result.page_count,
                    "tokens_used": vision_result.tokens_used,
                    "error": vision_result.error,
                }
            else:
                logger.warning(f"Vision extraction also failed for {document_id}")
                extraction_metadata["vision_extraction"] = {
                    "success": False,
                    "error": vision_result.error,
                }
        
        # ステップ3: テーブル抽出
        metadata_store.update_processing_status(document_id, status="extracting_tables")
        table_extractor = TableExtractor()
        table_result = table_extractor.extract(pdf_path)
        
        extraction_metadata["table_extraction"] = {
            "success": table_result.success,
            "table_count": table_result.table_count,
            "page_count": table_result.page_count,
            "error": table_result.error,
        }
        
        # ステップ4: 構造化データを保存
        structured_data = {
            "full_text": full_text,
            "pages": text_result.pages if text_result.success else [],
            "tables": table_result.tables if table_result.success else [],
        }
        
        # ステップ4.5: セクション検出（書類種別が判明している場合）
        document_type = metadata.manual_type or metadata.detected_type
        if document_type and settings.openai_api_key and text_result.success:
            try:
                logger.info(f"Starting section detection for {document_id} (type: {document_type})")
                metadata_store.update_processing_status(document_id, status="detecting_sections")
                
                from openai import OpenAI
                openai_client = OpenAI(
                    api_key=settings.openai_api_key,
                    timeout=settings.openai_timeout_seconds,
                )
                
                detector = SectionDetector(
                    openai_client=openai_client,
                    document_type=document_type,
                    batch_size=10,  # 10ページずつバッチ処理
                    max_workers=5  # 最大5バッチを並列実行
                )
                
                sections = detector.detect_sections(text_result.pages)
                
                # セクション情報抽出（財務指標、会計コメント、事実、主張）
                try:
                    logger.info(f"Starting section content extraction for {document_id}")
                    metadata_store.update_processing_status(document_id, status="extracting_section_content")
                    
                    from app.services.structuring.section_content_extractor import SectionContentExtractor
                    content_extractor = SectionContentExtractor(
                        openai_client=openai_client,
                        max_workers=3  # 最大3セクションを並列処理
                    )
                    
                    sections_with_content = content_extractor.extract_all_sections(
                        sections=sections,
                        pages=text_result.pages,
                        tables=table_result.tables if table_result.success else []
                    )
                    
                    structured_data["sections"] = sections_with_content
                    
                    extraction_metadata["section_content_extraction"] = {
                        "success": True,
                        "sections_processed": len([
                            s for s in sections_with_content.values()
                            if "extracted_content" in s
                        ]),
                    }
                    
                    logger.info(f"Section content extraction completed for {document_id}")
                    
                except Exception as exc:
                    logger.warning(f"Section content extraction failed for {document_id}: {exc}", exc_info=True)
                    # 抽出失敗時でもセクション情報は保存
                    structured_data["sections"] = sections
                    extraction_metadata["section_content_extraction"] = {
                        "success": False,
                        "error": str(exc),
                    }
                
                extraction_metadata["section_detection"] = {
                    "success": True,
                    "section_count": len(sections),
                    "document_type": document_type,
                }
                
                logger.info(f"Section detection completed for {document_id}: {len(sections)} sections detected")
                
            except Exception as exc:
                logger.warning(f"Section detection failed for {document_id}: {exc}", exc_info=True)
                extraction_metadata["section_detection"] = {
                    "success": False,
                    "error": str(exc),
                }
        else:
            if not document_type:
                logger.info(f"Skipping section detection for {document_id}: document type unknown")
            elif not settings.openai_api_key:
                logger.info(f"Skipping section detection for {document_id}: OpenAI API key not set")
            elif not text_result.success:
                logger.info(f"Skipping section detection for {document_id}: text extraction failed")
        
        metadata_store.save_structured_data(
            document_id,
            structured_data=structured_data,
            extraction_method=extraction_method,
            extraction_metadata=extraction_metadata,
        )
        
        # ステップ5: 処理完了
        metadata_store.update_processing_status(document_id, status="structured")
        logger.info(f"Successfully structured document {document_id}")
        
        return {
            "document_id": document_id,
            "status": "structured",
            "extraction_method": extraction_method,
            "metadata": extraction_metadata,
        }
        
    except FileNotFoundError:
        logger.error(f"Metadata not found for document {document_id}")
        return {"document_id": document_id, "status": "failed", "error": "Metadata not found"}
    except Exception as exc:
        logger.exception(f"Failed to structure document {document_id}", exc_info=exc)
        try:
            metadata_store.update_processing_status(document_id, status="failed")
        except:
            pass
        return {"document_id": document_id, "status": "failed", "error": str(exc)}


@celery_app.task(name="comparisons.compare", bind=True)
def compare_documents_task(self, comparison_id: str, document_ids: list[str], iterative_search_mode: str = "off") -> dict:
    """
    ドキュメント比較タスク（非同期処理）
    
    Args:
        comparison_id: 比較ID
        document_ids: 比較対象のドキュメントIDリスト
        iterative_search_mode: 追加探索モード（"off", "high_only", "all"）
        
    Returns:
        比較結果の辞書
    """
    from ..services.comparison_engine import ComparisonOrchestrator, DocumentInfo
    import json
    from pathlib import Path
    
    logger.info(f"比較タスク開始: comparison_id={comparison_id}, documents={document_ids}, iterative_search_mode={iterative_search_mode}")
    
    settings = get_settings()
    metadata_store = DocumentMetadataStore(settings)
    orchestrator = ComparisonOrchestrator(settings, max_workers=5)  # 最大5セクション並列分析
    
    try:
        # 進捗状態を更新: メタデータ読み込み中
        self.update_state(
            state='PROGRESS',
            meta={'step': 'loading_metadata', 'progress': 10}
        )
        
        # ドキュメントメタデータを取得
        doc_infos: list[DocumentInfo] = []
        structured_data_list: list[dict] = []
        
        for idx, doc_id in enumerate(document_ids):
            try:
                metadata = metadata_store.load(doc_id)
            except FileNotFoundError:
                error_msg = f"ドキュメント {doc_id} が見つかりません"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 構造化データを取得
            structured_data = metadata.structured_data or {}
            structured_data_list.append(structured_data)
            
            # 会社名・年度を抽出
            company_name = None
            fiscal_year = None
            extraction_confidence = 0.0
            
            full_text = structured_data.get("full_text") or structured_data.get("text", "")
            if full_text:
                text_sample = full_text[:5000]
                company_name, fiscal_year, extraction_confidence = (
                    orchestrator.extract_metadata_with_llm(doc_id, text_sample)
                )
            
            doc_info = DocumentInfo(
                document_id=doc_id,
                filename=metadata.filename,
                document_type=metadata.manual_type or metadata.detected_type,
                document_type_label=metadata.manual_type_label or metadata.detected_type_label,
                company_name=company_name,
                fiscal_year=fiscal_year,
                extraction_confidence=extraction_confidence,
            )
            doc_infos.append(doc_info)
            
            # 進捗更新
            progress = 10 + (idx + 1) * 10 // len(document_ids)
            self.update_state(
                state='PROGRESS',
                meta={'step': 'loading_metadata', 'progress': progress}
            )
        
        # 進捗状態を更新: 比較処理中
        self.update_state(
            state='PROGRESS',
            meta={'step': 'comparing', 'progress': 30}
        )
        
        # 進捗コールバック関数を定義
        def update_progress(current_section: str, completed_sections: int, total_sections: int):
            # 30% (比較開始) から 90% (保存前) までの範囲で進捗を計算
            if total_sections > 0:
                section_progress = (completed_sections / total_sections) * 60  # 60%の範囲
                overall_progress = 30 + int(section_progress)
            else:
                overall_progress = 30
            
            self.update_state(
                state='PROGRESS',
                meta={
                    'step': 'analyzing_sections',
                    'progress': overall_progress,
                    'current_section': current_section,
                    'completed_sections': completed_sections,
                    'total_sections': total_sections
                }
            )
        
        # 比較を実行（進捗コールバックを渡す）
        comparison_result = orchestrator.compare_documents(
            doc_infos, 
            structured_data_list,
            progress_callback=update_progress,
            iterative_search_mode=iterative_search_mode
        )
        
        # 進捗状態を更新: 結果保存中
        self.update_state(
            state='PROGRESS',
            meta={'step': 'saving_result', 'progress': 90}
        )
        
        # 結果をJSONとして保存
        from ..core.config import resolve_upload_storage_path
        upload_dir = resolve_upload_storage_path(settings)
        comparison_dir = upload_dir.parent / "comparisons"
        comparison_dir.mkdir(parents=True, exist_ok=True)
        
        result_path = comparison_dir / f"{comparison_id}.json"
        logger.info(f"比較結果を保存: {result_path}")
        
        # ComparisonResultをdictに変換
        from dataclasses import asdict
        result_dict = asdict(comparison_result)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"比較タスク完了: comparison_id={comparison_id}")
        
        return {
            "status": "completed",
            "comparison_id": comparison_id,
            "result_path": str(result_path),
        }
        
    except Exception as exc:
        logger.exception(f"比較タスク失敗: comparison_id={comparison_id}", exc_info=exc)
        return {
            "status": "failed",
            "comparison_id": comparison_id,
            "error": str(exc),
        }
