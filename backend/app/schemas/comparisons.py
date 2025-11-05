"""比較API用のスキーマ定義"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ComparisonRequest(BaseModel):
    """比較リクエスト"""
    
    document_ids: list[str] = Field(
        ...,
        min_length=2,
        description="比較対象のドキュメントIDリスト（最低2つ必要）",
    )
    iterative_search_mode: Literal["off", "high_only", "all"] = Field(
        default="off",
        description="追加探索モード: off=追加探索なし, high_only=重要度highのみ, all=全セクション",
    )


class ComparisonTaskResponse(BaseModel):
    """比較タスク開始レスポンス"""
    
    comparison_id: str = Field(..., description="比較ID（タスクID）")
    status: str = Field(..., description="タスクステータス（processing）")
    message: str = Field(..., description="メッセージ")


class ComparisonStatusResponse(BaseModel):
    """比較ステータスレスポンス"""
    
    comparison_id: str
    status: str = Field(..., description="pending, processing, completed, failed")
    progress: Optional[int] = Field(None, description="進捗率（0-100）", ge=0, le=100)
    step: Optional[str] = Field(None, description="現在の処理ステップ")
    current_section: Optional[str] = Field(None, description="現在処理中のセクション名")
    total_sections: Optional[int] = Field(None, description="処理対象の総セクション数")
    completed_sections: Optional[int] = Field(None, description="完了したセクション数")
    error: Optional[str] = Field(None, description="エラーメッセージ（failedの場合）")


class DocumentMetadataOverride(BaseModel):
    """ドキュメントメタデータのオーバーライド"""
    
    company_name: Optional[str] = Field(None, description="会社名（手動入力）")
    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100, description="年度（西暦）")


class DocumentInfoResponse(BaseModel):
    """ドキュメント情報レスポンス"""
    
    document_id: str
    filename: str
    document_type: Optional[str] = None
    document_type_label: Optional[str] = None
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    extraction_confidence: Optional[float] = None


class SectionMappingResponse(BaseModel):
    """セクションマッピングレスポンス"""
    
    doc1_section: str
    doc2_section: str
    confidence_score: float
    mapping_method: str


class NumericalDifferenceResponse(BaseModel):
    """数値差分レスポンス"""
    
    section: str
    item_name: str
    value1: float
    value2: float
    difference: float
    difference_pct: Optional[float] = None
    unit1: Optional[str] = None
    unit2: Optional[str] = None
    normalized_unit: Optional[str] = None
    is_significant: bool


class TextDifferenceResponse(BaseModel):
    """テキスト差分レスポンス"""
    
    section: str
    match_ratio: float
    added_text: list[str] = Field(default_factory=list)
    removed_text: list[str] = Field(default_factory=list)
    changed_text: list[tuple[str, str]] = Field(default_factory=list)
    semantic_similarity: Optional[float] = None


class AdditionalSearchResult(BaseModel):
    """追加探索の結果"""
    
    iteration: int = Field(..., description="探索回数（1, 2, ...）")
    search_keywords: list[str] = Field(default_factory=list, description="使用した検索フレーズ")
    found_sections: list[dict[str, Any]] = Field(
        default_factory=list,
        description="発見されたセクション（doc1_section, doc2_section, similarityを含む）",
    )
    analysis: dict[str, Any] = Field(default_factory=dict, description="追加分析の結果")


class SectionDetailedComparisonResponse(BaseModel):
    """セクション別詳細差分レスポンス"""
    
    section_name: str
    doc1_page_range: str
    doc2_page_range: str
    text_changes: dict[str, Any] = Field(default_factory=dict)
    numerical_changes: list[dict[str, Any]] = Field(default_factory=list)
    tone_analysis: dict[str, Any] = Field(default_factory=dict)
    importance: Literal["high", "medium", "low"]
    importance_reason: str
    summary: str
    # マッピング情報（1:Nマッピング対応）
    doc1_section_name: str = Field(default="", description="doc1のセクション名")
    doc2_section_name: str = Field(default="", description="doc2のセクション名")
    mapping_confidence: float = Field(default=1.0, description="マッピングの信頼度スコア")
    mapping_method: str = Field(default="exact", description="マッピング方法（exact/semantic）")
    # 追加探索の結果
    additional_searches: list[AdditionalSearchResult] = Field(
        default_factory=list,
        description="追加探索の結果（反復探索が実行された場合）",
    )
    has_additional_context: bool = Field(
        default=False,
        description="追加探索が実行され、追加のコンテキストが含まれているかどうか",
    )


class ComparisonResponse(BaseModel):
    """比較結果レスポンス"""
    
    comparison_id: str
    mode: str
    doc1_info: DocumentInfoResponse
    doc2_info: DocumentInfoResponse
    section_mappings: list[SectionMappingResponse] = Field(default_factory=list)
    numerical_differences: list[NumericalDifferenceResponse] = Field(default_factory=list)
    text_differences: list[TextDifferenceResponse] = Field(default_factory=list)
    section_detailed_comparisons: list[SectionDetailedComparisonResponse] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"]
    created_at: str

