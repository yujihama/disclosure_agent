from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from ..core.config import Settings, resolve_metadata_storage_path, resolve_upload_storage_path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DocumentMetadata:
    document_id: str
    filename: str
    stored_path: str
    size_bytes: int
    detected_type: Optional[str] = None
    detected_type_label: Optional[str] = None
    detection_confidence: Optional[float] = None
    matched_keywords: list[str] = field(default_factory=list)
    detection_reason: Optional[str] = None  # LLM判定の根拠
    manual_type: Optional[str] = None
    manual_type_label: Optional[str] = None
    status: str = "accepted"
    processing_status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    # 構造化データ関連フィールド
    structured_data: Optional[dict[str, Any]] = None
    extraction_method: Optional[str] = None  # "text", "vision", "hybrid"
    extraction_metadata: Optional[dict[str, Any]] = None

    def touch(self) -> None:
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DocumentMetadataStore:
    """Persist document metadata as JSON files under the metadata storage directory."""

    def __init__(self, settings: Settings) -> None:
        self._base_path = resolve_metadata_storage_path(settings)
        self._upload_path = resolve_upload_storage_path(settings)
        self._retention_hours = settings.document_retention_hours

    def _path_for(self, document_id: str) -> Path:
        return self._base_path / f"{document_id}.json"

    def save(self, metadata: DocumentMetadata) -> None:
        metadata.touch()
        path = self._path_for(metadata.document_id)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(metadata.to_dict(), handle, ensure_ascii=False, indent=2)

    def load(self, document_id: str) -> DocumentMetadata:
        path = self._path_for(document_id)
        if not path.exists():
            msg = f"Metadata for document_id={document_id!r} not found."
            raise FileNotFoundError(msg)

        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return DocumentMetadata(**raw)

    def upsert_manual_type(
        self,
        document_id: str,
        *,
        manual_type: Optional[str],
        manual_type_label: Optional[str],
    ) -> DocumentMetadata:
        metadata = self.load(document_id)
        metadata.manual_type = manual_type
        metadata.manual_type_label = manual_type_label
        metadata.touch()
        self.save(metadata)
        return metadata

    def update_processing_status(self, document_id: str, *, status: str) -> DocumentMetadata:
        metadata = self.load(document_id)
        metadata.processing_status = status
        metadata.touch()
        self.save(metadata)
        return metadata
    
    def save_structured_data(
        self,
        document_id: str,
        *,
        structured_data: dict[str, Any],
        extraction_method: str,
        extraction_metadata: Optional[dict[str, Any]] = None,
    ) -> DocumentMetadata:
        """構造化データを保存"""
        metadata = self.load(document_id)
        metadata.structured_data = structured_data
        metadata.extraction_method = extraction_method
        metadata.extraction_metadata = extraction_metadata or {}
        metadata.touch()
        self.save(metadata)
        return metadata
    
    def get_structured_data(self, document_id: str) -> Optional[dict[str, Any]]:
        """構造化データを取得"""
        try:
            metadata = self.load(document_id)
            return metadata.structured_data
        except FileNotFoundError:
            return None
    
    def list_all(self) -> list[DocumentMetadata]:
        """すべてのドキュメントメタデータを取得"""
        metadata_list = []
        for json_file in self._base_path.glob("*.json"):
            try:
                with json_file.open("r", encoding="utf-8") as handle:
                    raw = json.load(handle)
                metadata_list.append(DocumentMetadata(**raw))
            except Exception:
                # 破損したファイルはスキップ
                continue
        # 作成日時の新しい順でソート
        metadata_list.sort(key=lambda m: m.created_at, reverse=True)
        return metadata_list
    
    def delete(self, document_id: str) -> None:
        """ドキュメントのメタデータとPDFファイルを削除"""
        # メタデータを読み込んでPDFパスを取得
        try:
            metadata = self.load(document_id)
            pdf_path = Path(metadata.stored_path)
            if pdf_path.exists():
                pdf_path.unlink()
                logger.info(f"Deleted PDF file: {pdf_path}")
        except FileNotFoundError:
            logger.warning(f"Metadata not found for document_id={document_id}, skipping PDF deletion")
        except Exception as exc:
            logger.warning(f"Failed to delete PDF for document_id={document_id}: {exc}")
        
        # メタデータファイルを削除
        metadata_path = self._path_for(document_id)
        if metadata_path.exists():
            metadata_path.unlink()
            logger.info(f"Deleted metadata file: {metadata_path}")
    
    def list_expired(self) -> list[DocumentMetadata]:
        """保持期限を超過したドキュメントを取得"""
        cutoff_time = datetime.utcnow().replace(tzinfo=None) - timedelta(hours=self._retention_hours)
        expired = []
        
        for metadata in self.list_all():
            try:
                # created_atをdatetimeに変換（ISOフォーマット）
                # タイムゾーン情報を削除してnaive datetimeとして比較
                created_at_str = metadata.created_at.replace('Z', '').replace('+00:00', '')
                created_at = datetime.fromisoformat(created_at_str)
                if created_at < cutoff_time:
                    expired.append(metadata)
            except Exception as exc:
                logger.warning(f"Failed to parse created_at for document_id={metadata.document_id}: {exc}")
                continue
        
        return expired
    
    def cleanup_expired(self) -> int:
        """期限切れのドキュメントを削除して、削除件数を返す"""
        expired = self.list_expired()
        deleted_count = 0
        
        for metadata in expired:
            try:
                self.delete(metadata.document_id)
                deleted_count += 1
            except Exception as exc:
                logger.error(f"Failed to delete expired document {metadata.document_id}: {exc}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired documents")
        
        return deleted_count
    
    def save_comparison_result(self, comparison_result: dict[str, Any]) -> None:
        """
        比較結果を保存
        
        Args:
            comparison_result: 比較結果の辞書
        """
        comparison_id = comparison_result.get("comparison_id")
        if not comparison_id:
            raise ValueError("comparison_id is required")
        
        # 比較結果用のディレクトリを作成
        comparisons_path = self._base_path.parent / "comparisons"
        comparisons_path.mkdir(parents=True, exist_ok=True)
        
        # 比較結果を保存
        result_path = comparisons_path / f"{comparison_id}.json"
        with result_path.open("w", encoding="utf-8") as handle:
            json.dump(comparison_result, handle, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved comparison result: {comparison_id}")
    
    def load_comparison_result(self, comparison_id: str) -> dict[str, Any]:
        """
        比較結果を読み込み
        
        Args:
            comparison_id: 比較ID
            
        Returns:
            比較結果の辞書
        """
        comparisons_path = self._base_path.parent / "comparisons"
        result_path = comparisons_path / f"{comparison_id}.json"
        
        if not result_path.exists():
            msg = f"Comparison result for comparison_id={comparison_id!r} not found."
            raise FileNotFoundError(msg)
        
        with result_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    
    def list_comparisons(self) -> list[dict[str, Any]]:
        """
        すべての比較結果を取得
        
        Returns:
            比較結果のリスト
        """
        comparisons_path = self._base_path.parent / "comparisons"
        if not comparisons_path.exists():
            return []
        
        comparisons = []
        for json_file in comparisons_path.glob("*.json"):
            try:
                with json_file.open("r", encoding="utf-8") as handle:
                    comparisons.append(json.load(handle))
            except Exception:
                # 破損したファイルはスキップ
                continue
        
        # 作成日時の新しい順でソート
        comparisons.sort(key=lambda c: c.get("created_at", ""), reverse=True)
        return comparisons