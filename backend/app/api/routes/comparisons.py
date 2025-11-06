"""比較API エンドポイント（非同期版）"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

from celery.result import AsyncResult
from ...workers.celery_app import celery_app
from fastapi import APIRouter, Depends, HTTPException, status

from ...core.config import Settings, get_settings
from ...schemas.comparisons import (
    ComparisonRequest,
    ComparisonResponse,
    ComparisonStatusResponse,
    ComparisonTaskResponse,
    DocumentInfoResponse,
    KPITimeSeriesComparisonResponse,
    LogicalRelationshipChangeResponse,
    NumericalDifferenceResponse,
    SectionDetailedComparisonResponse,
    SectionMappingResponse,
    TextDifferenceResponse,
)
from ...services.metadata_store import DocumentMetadataStore
from ...workers.tasks import compare_documents_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.post("", response_model=ComparisonTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def create_comparison(
    req: ComparisonRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComparisonTaskResponse:
    """
    ドキュメント間の比較を非同期で開始
    
    - 最低2つのドキュメントIDが必要
    - 即座にcomparison_idを返す（202 Accepted）
    - 実際の比較処理はバックグラウンドで実行
    """
    import uuid
    
    logger.info(f"=== 比較リクエスト受信 ===")
    logger.info(f"document_ids: {req.document_ids}")
    logger.info(f"iterative_search_mode: {req.iterative_search_mode}")
    
    # ドキュメントの存在確認
    metadata_store = DocumentMetadataStore(settings)
    for doc_id in req.document_ids:
        try:
            metadata_store.load(doc_id)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ドキュメント {doc_id} が見つかりません",
            )
    
    # 比較IDを生成
    comparison_id = str(uuid.uuid4())
    
    # Celeryタスクを起動
    compare_documents_task.apply_async(
        args=[comparison_id, req.document_ids, req.iterative_search_mode],
        task_id=comparison_id
    )
    
    logger.info(f"比較タスクを起動しました: comparison_id={comparison_id}, documents={req.document_ids}")
    
    return ComparisonTaskResponse(
        comparison_id=comparison_id,
        status="processing",
        message="比較処理を開始しました。ステータスは GET /api/comparisons/{comparison_id}/status で確認できます。"
    )


@router.get("", response_model=list[dict])
def list_comparisons(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[dict]:
    """
    過去の比較結果一覧を取得
    
    - ファイル名（comparison_id）と作成日時を返す
    """
    comparison_dir = Path(settings.upload_storage_dir).parent / "comparisons"
    
    if not comparison_dir.exists():
        return []
    
    results = []
    for result_path in comparison_dir.glob("*.json"):
        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                result_dict = json.load(f)
            
            # ファイル名を常に使用
            results.append({
                "comparison_id": result_path.stem,
                "created_at": result_dict.get('created_at', ''),
                "mode": result_dict.get('mode', ''),
                "doc1_filename": result_dict.get('doc1_info', {}).get('filename', ''),
                "doc2_filename": result_dict.get('doc2_info', {}).get('filename', ''),
                "section_count": len(result_dict.get('section_detailed_comparisons', []))
            })
        except Exception as e:
            logger.warning(f"比較結果ファイル {result_path} の読み込みに失敗: {e}")
            continue
    
    # 作成日時の降順でソート
    results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return results


@router.get("/{comparison_id}/status", response_model=ComparisonStatusResponse)
def get_comparison_status(
    comparison_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComparisonStatusResponse:
    """
    比較タスクのステータスを確認
    
    - pending: 待機中
    - processing: 処理中
    - completed: 完了
    - failed: 失敗
    """
    try:
        result = celery_app.AsyncResult(comparison_id)
        
        if result.ready():
            # タスク完了
            if result.successful():
                task_result = result.get()
                if task_result.get("status") == "completed":
                    return ComparisonStatusResponse(
                        comparison_id=comparison_id,
                        status="completed",
                        progress=100,
                        step="completed"
                    )
                else:
                    return ComparisonStatusResponse(
                        comparison_id=comparison_id,
                        status="failed",
                        progress=0,
                        error=task_result.get("error", "不明なエラー")
                    )
            else:
                # タスクが例外で失敗
                return ComparisonStatusResponse(
                    comparison_id=comparison_id,
                    status="failed",
                    progress=0,
                    error=str(result.result)
                )
        else:
            # タスク実行中
            state = result.state
            info = result.info or {}
            
            if state == 'PENDING':
                return ComparisonStatusResponse(
                    comparison_id=comparison_id,
                    status="pending",
                    progress=0,
                    step="waiting"
                )
            elif state == 'PROGRESS':
                return ComparisonStatusResponse(
                    comparison_id=comparison_id,
                    status="processing",
                    progress=info.get('progress', 0),
                    step=info.get('step', 'processing'),
                    current_section=info.get('current_section'),
                    total_sections=info.get('total_sections'),
                    completed_sections=info.get('completed_sections')
                )
            else:
                return ComparisonStatusResponse(
                    comparison_id=comparison_id,
                    status="processing",
                    progress=0,
                    step=state.lower()
                )
    except AttributeError as exc:
        # Celeryバックエンドが無効な場合のフォールバック
        logger.error(f"Celeryバックエンドエラー: {exc}")
        # 結果ファイルから直接確認
        comparison_dir = Path(settings.upload_storage_dir).parent / "comparisons"
        result_path = comparison_dir / f"{comparison_id}.json"
        
        if result_path.exists():
            return ComparisonStatusResponse(
                comparison_id=comparison_id,
                status="completed",
                progress=100,
                step="completed"
            )
        else:
            return ComparisonStatusResponse(
                comparison_id=comparison_id,
                status="processing",
                progress=50,
                step="analyzing_sections"
            )
    except Exception as exc:
        logger.exception(f"ステータス確認中にエラー: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ステータス確認に失敗しました: {str(exc)}"
        )


@router.get("/{comparison_id}", response_model=ComparisonResponse)
def get_comparison_result(
    comparison_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComparisonResponse:
    """
    比較結果を取得
    
    - 完了している比較の結果を返す
    - まだ完了していない場合は404エラー
    """
    # 結果ファイルを読み込み
    comparison_dir = Path(settings.upload_storage_dir).parent / "comparisons"
    result_path = comparison_dir / f"{comparison_id}.json"
    
    if not result_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"比較結果が見つかりません: {comparison_id}。まだ処理中の可能性があります。"
        )
    
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            result_dict = json.load(f)
        
        # dict から ComparisonResponse に変換
        response = ComparisonResponse(
            comparison_id=result_dict['comparison_id'],
            mode=result_dict['mode'],
            doc1_info=DocumentInfoResponse(**result_dict['doc1_info']),
            doc2_info=DocumentInfoResponse(**result_dict['doc2_info']),
            section_mappings=[
                SectionMappingResponse(**m) for m in result_dict.get('section_mappings', [])
            ],
            numerical_differences=[
                NumericalDifferenceResponse(**d) for d in result_dict.get('numerical_differences', [])
            ],
            text_differences=[
                TextDifferenceResponse(**d) for d in result_dict.get('text_differences', [])
            ],
            section_detailed_comparisons=[
                SectionDetailedComparisonResponse(**d) for d in result_dict.get('section_detailed_comparisons', [])
            ],
            kpi_time_series_comparisons=[
                KPITimeSeriesComparisonResponse(**d) for d in result_dict.get('kpi_time_series_comparisons', [])
            ],
            logical_relationship_changes=[
                LogicalRelationshipChangeResponse(**d) for d in result_dict.get('logical_relationship_changes', [])
            ],
            priority=result_dict.get('priority', 'medium'),
            created_at=result_dict.get('created_at', '')
        )
        
        return response
        
    except Exception as exc:
        logger.error(f"比較結果の読み込みに失敗: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"比較結果の読み込みに失敗しました: {str(exc)}"
        )

