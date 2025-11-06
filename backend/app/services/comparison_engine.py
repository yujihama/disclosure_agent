"""
比較エンジン

ドキュメント間の比較処理を行うサービス。
整合性チェック、差分分析、多資料比較をサポート。
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)


class ComparisonMode(str, Enum):
    """比較モード"""
    
    CONSISTENCY_CHECK = "consistency_check"  # 整合性チェック（同じ会社の異なる書類）
    DIFF_ANALYSIS_COMPANY = "diff_analysis_company"  # 差分分析（異なる会社の同じ書類）
    DIFF_ANALYSIS_YEAR = "diff_analysis_year"  # 差分分析（同じ会社の異なる年度）
    MULTI_DOCUMENT = "multi_document"  # 多資料比較（3つ以上）


@dataclass(slots=True)
class DocumentInfo:
    """ドキュメント情報"""
    
    document_id: str
    filename: str
    document_type: Optional[str] = None
    document_type_label: Optional[str] = None
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    extraction_confidence: Optional[float] = None


@dataclass(slots=True)
class SectionMapping:
    """セクションマッピング（書類間の対応項目）"""
    
    doc1_section: str
    doc2_section: str
    confidence_score: float = 1.0  # 信頼度スコア (0.0-1.0)
    mapping_method: str = "exact"  # "exact", "semantic", "manual"


@dataclass(slots=True)
class NumericalDifference:
    """数値差分"""
    
    section: str
    item_name: str
    value1: float
    value2: float
    difference: float
    difference_pct: Optional[float] = None  # パーセント差異
    unit1: Optional[str] = None
    unit2: Optional[str] = None
    normalized_unit: Optional[str] = None
    is_significant: bool = True  # 有意な差異かどうか
    threshold: float = 0.01  # 許容誤差（デフォルト0.01%）


@dataclass(slots=True)
class TextDifference:
    """テキスト差分"""
    
    section: str
    match_ratio: float  # 一致率 (0.0-1.0)
    added_text: list[str] = field(default_factory=list)
    removed_text: list[str] = field(default_factory=list)
    changed_text: list[tuple[str, str]] = field(default_factory=list)
    semantic_similarity: Optional[float] = None  # 意味類似度


@dataclass(slots=True)
class SectionDetailedComparison:
    """セクション別詳細差分分析結果"""
    
    section_name: str
    doc1_page_range: str  # "1-5"
    doc2_page_range: str  # "1-5"
    text_changes: dict[str, Any] = field(default_factory=dict)  # added, removed, modified
    numerical_changes: list[dict[str, Any]] = field(default_factory=list)
    tone_analysis: dict[str, Any] = field(default_factory=dict)
    importance: Literal["high", "medium", "low"] = "medium"
    importance_reason: str = ""
    summary: str = ""  # このセクションの差異の要約
    # マッピング情報（1:Nマッピング対応）
    doc1_section_name: str = ""  # doc1のセクション名（明示的に）
    doc2_section_name: str = ""  # doc2のセクション名（明示的に）
    mapping_confidence: float = 1.0  # マッピングの信頼度スコア
    mapping_method: str = "exact"  # マッピング方法（exact/semantic）
    # 追加探索の結果
    additional_searches: list[dict[str, Any]] = field(default_factory=list)  # 追加探索の結果
    has_additional_context: bool = False  # 追加探索が実行されたか


@dataclass(slots=True)
class ComparisonResult:
    """比較結果"""
    
    comparison_id: str
    mode: ComparisonMode
    doc1_info: DocumentInfo
    doc2_info: DocumentInfo
    section_mappings: list[SectionMapping] = field(default_factory=list)
    numerical_differences: list[NumericalDifference] = field(default_factory=list)
    text_differences: list[TextDifference] = field(default_factory=list)
    section_detailed_comparisons: list[SectionDetailedComparison] = field(default_factory=list)
    kpi_time_series_comparisons: list[dict[str, Any]] = field(default_factory=list)  # 時系列比較結果
    logical_relationship_changes: list[dict[str, Any]] = field(default_factory=list)  # 論理関係変化
    priority: Literal["high", "medium", "low"] = "medium"
    created_at: Optional[str] = None


class ComparisonOrchestrator:
    """
    比較オーケストレータ
    
    複数のドキュメントの比較モードを判定し、適切な比較処理を実行する。
    """
    
    def __init__(self, settings=None, max_workers: int = 5):
        from ..core.config import get_settings
        self.settings = settings or get_settings()
        self.max_workers = max_workers  # セクション分析の並列数
        
        # OpenAI クライアント初期化
        # 比較処理用のタイムアウトが設定されている場合はそれを使用、なければタイムアウトなし
        if self.settings.openai_api_key:
            from openai import OpenAI
            timeout = self.settings.openai_comparison_timeout_seconds
            # Noneの場合はタイムアウトを無効化（比較処理は長時間かかるため）
            client_kwargs = {"api_key": self.settings.openai_api_key}
            if timeout is not None:
                client_kwargs["timeout"] = timeout
            self.openai_client = OpenAI(**client_kwargs)
        else:
            self.openai_client = None
    
    def extract_metadata_with_llm(
        self,
        document_id: str,
        text_sample: str,
    ) -> tuple[Optional[str], Optional[int], float]:
        """
        LLMを使用してドキュメントから会社名と年度を抽出
        
        Args:
            document_id: ドキュメントID
            text_sample: 抽出対象のテキスト（冒頭部分）
            
        Returns:
            (会社名, 年度, 信頼度スコア)
        """
        if not self.openai_client:
            logger.warning("OpenAI APIキーが設定されていないため、メタデータ抽出をスキップします")
            return None, None, 0.0
        
        try:
            # プロンプトを構築
            prompt = f"""
以下は日本の企業開示資料の冒頭部分です。

【タスク】
1. 会社名を抽出してください
   - **必ず日本語の正式名称で統一**してください
   - 英語表記（例：FUJIFILM Holdings Corporation）が記載されている場合でも、対応する日本語名（例：富士フイルムホールディングス株式会社）を抽出してください
   - 法人格（株式会社、ホールディングスなど）を含めた完全な正式名称を記載してください
   
2. 対象年度（西暦）を抽出してください

【テキスト】
{text_sample[:3000]}

【出力形式】
JSON形式で以下のフォーマットで回答してください：
{{
  "company_name": "富士フイルムホールディングス株式会社",
  "fiscal_year": 2024,
  "confidence": 0.95
}}

【重要な注意事項】
- company_nameは**必ず日本語**で記載してください（英語名は使用しないこと）
- 会社名または年度が見つからない場合は、該当フィールドをnullにしてください
- confidenceは抽出の信頼度を0.0～1.0で示してください
"""
            
            logger.info(f"LLMでメタデータ抽出を開始: document_id={document_id}")
            
            response = self.openai_client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": "あなたは企業開示資料の分析エキスパートです。"},
                    {"role": "user", "content": prompt},
                ],
                
                response_format={"type": "json_object"},
            )
            
            # レスポンスをパース
            import json
            result = json.loads(response.choices[0].message.content)
            
            company_name = result.get("company_name")
            fiscal_year = result.get("fiscal_year")
            confidence = result.get("confidence", 0.5)
            
            logger.info(
                f"メタデータ抽出完了: company={company_name}, year={fiscal_year}, "
                f"confidence={confidence}"
            )
            
            return company_name, fiscal_year, confidence
            
        except Exception as exc:
            logger.error(f"メタデータ抽出に失敗: {exc}", exc_info=True)
            return None, None, 0.0
    
    def determine_mode(
        self,
        doc_infos: list[DocumentInfo],
    ) -> ComparisonMode:
        """
        ドキュメント情報から適切な比較モードを判定
        
        Args:
            doc_infos: ドキュメント情報のリスト
            
        Returns:
            判定された比較モード
        """
        if len(doc_infos) < 2:
            raise ValueError("比較には最低2つのドキュメントが必要です")
        
        # 多資料比較モード（3つ以上）
        if len(doc_infos) >= 3:
            logger.info("多資料比較モードを選択（3つ以上のドキュメント）")
            return ComparisonMode.MULTI_DOCUMENT
        
        doc1, doc2 = doc_infos[0], doc_infos[1]
        
        # 会社名の一致確認（正規化して比較）
        def normalize_company_name(name: str) -> str:
            """会社名を正規化（カタカナ→ひらがな、英語も統一）"""
            import re
            import unicodedata
            
            # 括弧内を削除
            name = re.sub(r'\([^)]*\)', '', name)
            # 法人格を削除
            name = re.sub(r'株式会社|有限会社|合同会社|Corporation|Corp\.|Inc\.|Ltd\.|Limited|Holdings|ホールディングス|holding', '', name, flags=re.IGNORECASE)
            # スペース、ハイフン、ドット、記号を削除
            name = re.sub(r'[\s\-\.\,ー、。]', '', name)
            # 全角英数字を半角に
            name = unicodedata.normalize('NFKC', name)
            # カタカナをひらがなに変換（統一のため）
            def kata_to_hira(s):
                return ''.join([chr(ord(ch) - 96) if 'ァ' <= ch <= 'ヴ' else ch for ch in s])
            name = kata_to_hira(name)
            return name.strip().lower()
        
        same_company = False
        if doc1.company_name and doc2.company_name:
            # まず元の名前で完全一致を試す
            if doc1.company_name.strip() == doc2.company_name.strip():
                same_company = True
                logger.info(f"会社名が完全一致: '{doc1.company_name}'")
            else:
                norm1 = normalize_company_name(doc1.company_name)
                norm2 = normalize_company_name(doc2.company_name)
                # 正規化後の一致、または主要部分の一致（3文字以上で一方が他方を含む）
                if norm1 and norm2 and len(norm1) >= 3 and len(norm2) >= 3:
                    if norm1 == norm2 or norm1 in norm2 or norm2 in norm1:
                        same_company = True
                        logger.info(f"会社名を同一と判定: '{doc1.company_name}' ≈ '{doc2.company_name}' (正規化後: '{norm1}' ≈ '{norm2}')")
                
                if not same_company:
                    logger.info(f"会社名が異なると判定: '{doc1.company_name}' vs '{doc2.company_name}' (正規化後: '{norm1}' vs '{norm2}')")
        
        # 書類種別の一致確認
        same_type = (
            doc1.document_type 
            and doc2.document_type 
            and doc1.document_type == doc2.document_type
        )
        
        # 年度の確認
        same_year = (
            doc1.fiscal_year is not None
            and doc2.fiscal_year is not None
            and doc1.fiscal_year == doc2.fiscal_year
        )
        
        # モード判定ロジック
        if same_company and not same_type:
            # 同じ会社、異なる書類種別 → 整合性チェック
            logger.info(
                f"整合性チェックモードを選択（会社: {doc1.company_name}, "
                f"書類: {doc1.document_type_label} vs {doc2.document_type_label}）"
            )
            return ComparisonMode.CONSISTENCY_CHECK
        
        if not same_company and same_type:
            # 異なる会社、同じ書類種別 → 差分分析（会社間比較）
            logger.info(
                f"差分分析モード（会社間）を選択（{doc1.company_name} vs {doc2.company_name}）"
            )
            return ComparisonMode.DIFF_ANALYSIS_COMPANY
        
        if same_company and same_type and not same_year:
            # 同じ会社、同じ書類種別、異なる年度 → 差分分析（年度間比較）
            logger.info(
                f"差分分析モード（年度間）を選択（{doc1.company_name}, "
                f"{doc1.fiscal_year}年度 vs {doc2.fiscal_year}年度）"
            )
            return ComparisonMode.DIFF_ANALYSIS_YEAR
        
        # デフォルトは差分分析（会社間）
        logger.info("デフォルトで差分分析モード（会社間）を選択")
        return ComparisonMode.DIFF_ANALYSIS_COMPANY
    
    def compare_documents(
        self,
        doc_infos: list[DocumentInfo],
        structured_data_list: list[dict[str, Any]],
        progress_callback: Optional[callable] = None,
        iterative_search_mode: Literal["off", "high_only", "all"] = "off",
    ) -> ComparisonResult:
        """
        ドキュメントを比較する
        
        Args:
            doc_infos: ドキュメント情報のリスト
            structured_data_list: 各ドキュメントの構造化データのリスト
            progress_callback: 進捗更新用のコールバック関数（オプション）
            
        Returns:
            比較結果
        """
        # 比較モードを判定
        mode = self.determine_mode(doc_infos)
        
        # 2つのドキュメント比較のみサポート（初期実装）
        if len(doc_infos) != 2:
            raise NotImplementedError("現在は2つのドキュメント間の比較のみサポートしています")
        
        doc1_info, doc2_info = doc_infos[0], doc_infos[1]
        structured1, structured2 = structured_data_list[0], structured_data_list[1]
        
        # 比較結果を生成
        import uuid
        from datetime import datetime
        
        result = ComparisonResult(
            comparison_id=str(uuid.uuid4()),
            mode=mode,
            doc1_info=doc1_info,
            doc2_info=doc2_info,
            created_at=datetime.utcnow().isoformat() + "Z",
        )
        
        # セクションマッピングを実行
        result.section_mappings = self._map_sections(
            doc1_info, doc2_info, structured1, structured2
        )
        
        # 数値比較を実行
        result.numerical_differences = self._compare_numbers(
            doc1_info, doc2_info, structured1, structured2, result.section_mappings
        )
        
        # テキスト比較を実行
        result.text_differences = self._compare_text(
            doc1_info, doc2_info, structured1, structured2, result.section_mappings
        )
        
        # セクション別詳細差分分析を実行
        result.section_detailed_comparisons = self._compare_sections_detailed(
            doc1_info, doc2_info, structured1, structured2, result.section_mappings, progress_callback, mode, iterative_search_mode
        )
        
        # 時系列比較分析を実行（原文記載ベース）
        result.kpi_time_series_comparisons = self._compare_kpi_time_series(
            doc1_info, doc2_info, structured1, structured2, result.section_mappings
        )
        
        # 論理関係の変化分析を実行
        result.logical_relationship_changes = self._compare_logical_relationships(
            doc1_info, doc2_info, structured1, structured2, result.section_mappings
        )
        
        return result
    
    def _map_sections(
        self,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
    ) -> list[SectionMapping]:
        """
        ドキュメント間のセクションをマッピング
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            
        Returns:
            セクションマッピングのリスト
        """
        mappings: list[SectionMapping] = []
        
        # 同じ書類種別の場合、完全一致マッピング
        if doc1_info.document_type == doc2_info.document_type:
            mappings = self._map_sections_exact(doc1_info, structured1, structured2)
        else:
            # 異なる書類種別の場合、意味的マッピング（LLM使用）
            mappings = self._map_sections_semantic(
                doc1_info, doc2_info, structured1, structured2
            )
        
        return mappings
    
    def _map_sections_exact(
        self,
        doc_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
    ) -> list[SectionMapping]:
        """
        同じ書類種別のセクションを完全一致でマッピング
        
        Args:
            doc_info: ドキュメント情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            
        Returns:
            セクションマッピングのリスト
        """
        mappings: list[SectionMapping] = []
        
        # 実際に検出されたセクションを使用してマッピングを作成
        # これにより、テンプレートと検出されたセクション名のミスマッチを回避
        sections1 = structured1.get("sections", {})
        sections2 = structured2.get("sections", {})
        
        if not sections1 or not sections2:
            logger.warning("セクション情報が不足しているため、セクションマッピングをスキップします")
            return mappings
        
        # 両方のドキュメントに存在する共通セクションをマッピング
        common_sections = set(sections1.keys()) & set(sections2.keys())
        
        for section_name in sorted(common_sections):
            mapping = SectionMapping(
                doc1_section=section_name,
                doc2_section=section_name,
                confidence_score=1.0,
                mapping_method="exact",
            )
            mappings.append(mapping)
        
        logger.info(f"完全一致マッピング: {len(mappings)}個のセクション（実際に検出された共通セクションのみ）")
        return mappings
    
    def _create_nested_mappings(
        self,
        parent: dict,
        parent_path: str,
        mappings: list[SectionMapping]
    ) -> None:
        """
        ネストされたセクションのマッピングを再帰的に作成
        
        Args:
            parent: 親セクションの辞書
            parent_path: これまでの階層パス（例: "企業情報 - 企業の概況"）
            mappings: マッピングを追加するリスト
        """
        # subsections（サブセクション）を処理
        for subsection in parent.get("subsections", []):
            subsection_name = subsection.get("name")
            if subsection_name:
                # 親階層と結合
                combined_path = f"{parent_path} - {subsection_name}"
                mapping = SectionMapping(
                    doc1_section=combined_path,
                    doc2_section=combined_path,
                    confidence_score=1.0,
                    mapping_method="exact",
                )
                mappings.append(mapping)
                
                # さらに深い階層を再帰的に処理
                self._create_nested_mappings(subsection, combined_path, mappings)
        
        # items（項目）を処理
        for item in parent.get("items", []):
            item_name = item.get("name")
            if item_name:
                # 親階層と結合
                combined_path = f"{parent_path} - {item_name}"
                mapping = SectionMapping(
                    doc1_section=combined_path,
                    doc2_section=combined_path,
                    confidence_score=1.0,
                    mapping_method="exact",
                )
                mappings.append(mapping)
                
                # itemsの中にさらにサブセクションがある場合も処理
                self._create_nested_mappings(item, combined_path, mappings)
    
    def _map_sections_semantic(
        self,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
    ) -> list[SectionMapping]:
        """
        異なる書類種別のセクションを意味的にマッピング（Embedding使用）
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            
        Returns:
            セクションマッピングのリスト
        """
        mappings: list[SectionMapping] = []
        
        logger.info(
            f"意味的マッピング開始（Embedding使用）: {doc1_info.document_type_label} vs {doc2_info.document_type_label}"
        )
        
        if not self.openai_client:
            logger.warning("OpenAI APIキーが設定されていないため、意味的マッピングをスキップします")
            return mappings
        
        # 実際に検出されたセクション情報を取得
        detected_sections1 = structured1.get("sections", {})
        detected_sections2 = structured2.get("sections", {})
        
        if not detected_sections1 or not detected_sections2:
            logger.warning(
                f"セクション情報が不足しているため、意味的マッピングをスキップします "
                f"(doc1={len(detected_sections1)}, doc2={len(detected_sections2)})"
            )
            return mappings
        
        logger.info(f"マッピング対象セクション: doc1={len(detected_sections1)}個, doc2={len(detected_sections2)}個")
        
        try:
            # 各セクションのembeddingを取得
            embeddings1 = self._get_section_embeddings(detected_sections1)
            embeddings2 = self._get_section_embeddings(detected_sections2)
            
            # コサイン類似度でマッピング
            mappings = self._map_by_cosine_similarity(
                embeddings1, embeddings2, threshold=0.7
            )
            
            logger.info(f"意味的マッピング完了（Embedding使用）: {len(mappings)}個のセクション")
            
        except Exception as exc:
            logger.error(f"意味的マッピングに失敗: {exc}", exc_info=True)
        
        return mappings
    
    def _get_section_embeddings(
        self, sections: dict[str, dict]
    ) -> dict[str, tuple[str, list[float]]]:
        """
        各セクションのembeddingを取得
        
        Args:
            sections: セクション情報の辞書
            
        Returns:
            {section_name: (embedding_text, embedding_vector)}
        """
        from .structuring.section_content_extractor import create_embedding_text
        
        embeddings = {}
        
        # ベクトル化用のテキストを作成
        embedding_texts = {}
        for section_name, section_info in sections.items():
            extracted_content = section_info.get("extracted_content", {})
            if extracted_content:
                # extracted_contentがある場合は、それを使ってテキストを作成
                embedding_text = create_embedding_text(section_name, extracted_content)
            else:
                # extracted_contentがない場合は、セクション名のみ
                embedding_text = f"セクション名: {section_name}"
            
            embedding_texts[section_name] = embedding_text
        
        # バッチでembeddingを取得（最大100個ずつ）
        section_names = list(embedding_texts.keys())
        batch_size = 100
        
        for i in range(0, len(section_names), batch_size):
            batch_names = section_names[i:i + batch_size]
            batch_texts = [embedding_texts[name] for name in batch_names]
            
            try:
                response = self.openai_client.embeddings.create(
                    model=self.settings.openai_embedding_model,
                    input=batch_texts,
                )
                
                for j, section_name in enumerate(batch_names):
                    embedding_vector = response.data[j].embedding
                    embeddings[section_name] = (embedding_texts[section_name], embedding_vector)
                    
            except Exception as exc:
                logger.error(f"Embedding取得に失敗（バッチ{i//batch_size + 1}）: {exc}", exc_info=True)
                # 失敗した場合はスキップ
                continue
        
        logger.info(f"Embedding取得完了: {len(embeddings)}個のセクション")
        return embeddings
    
    def _map_by_cosine_similarity(
        self,
        embeddings1: dict[str, tuple[str, list[float]]],
        embeddings2: dict[str, tuple[str, list[float]]],
        threshold: float = 0.7,
    ) -> list[SectionMapping]:
        """
        コサイン類似度でセクションをマッピング
        
        Args:
            embeddings1: ドキュメント1のembeddings
            embeddings2: ドキュメント2のembeddings
            threshold: マッピングの閾値（0.0～1.0）
            
        Returns:
            セクションマッピングのリスト
        """
        import numpy as np
        
        mappings: list[SectionMapping] = []
        
        # 各セクション1に対して、最も類似度が高いセクション2を見つける
        for section1_name, (text1, vec1) in embeddings1.items():
            best_match = None
            best_similarity = threshold  # 閾値以上のもののみマッチング
            
            for section2_name, (text2, vec2) in embeddings2.items():
                # コサイン類似度を計算
                similarity = self._cosine_similarity(vec1, vec2)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = section2_name
            
            if best_match:
                mapping = SectionMapping(
                    doc1_section=section1_name,
                    doc2_section=best_match,
                    confidence_score=float(best_similarity),
                    mapping_method="semantic_embedding",
                )
                mappings.append(mapping)
                logger.debug(
                    f"マッピング: {section1_name} -> {best_match} "
                    f"(類似度: {best_similarity:.3f})"
                )
        
        return mappings
    
    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        コサイン類似度を計算
        
        Args:
            vec1: ベクトル1
            vec2: ベクトル2
            
        Returns:
            コサイン類似度（0.0～1.0）
        """
        import numpy as np
        
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        
        return dot_product / (norm_v1 * norm_v2)
    
    def _extract_section_names(self, template: dict[str, Any]) -> list[str]:
        """
        テンプレートからセクション名を抽出
        
        Args:
            template: テンプレート辞書
            
        Returns:
            セクション名のリスト
        """
        names: list[str] = []
        
        for section in template.get("sections", []):
            section_name = section.get("name")
            if section_name:
                names.append(section_name)
            
            # サブセクション、items、さらに深い階層を再帰的に抽出
            self._extract_nested_names(section, section_name, names)
        
        return names
    
    def _extract_nested_names(
        self,
        parent: dict,
        parent_path: str,
        names: list[str]
    ) -> None:
        """
        ネストされたセクション名を再帰的に抽出
        
        Args:
            parent: 親セクションの辞書
            parent_path: これまでの階層パス（例: "企業情報 - 企業の概況"）
            names: セクション名を追加するリスト
        """
        # subsections（サブセクション）を処理
        for subsection in parent.get("subsections", []):
            subsection_name = subsection.get("name")
            if subsection_name:
                # 親階層と結合
                combined_path = f"{parent_path} - {subsection_name}"
                names.append(combined_path)
                
                # さらに深い階層を再帰的に処理
                self._extract_nested_names(subsection, combined_path, names)
        
        # items（項目）を処理
        for item in parent.get("items", []):
            item_name = item.get("name")
            if item_name:
                # 親階層と結合
                combined_path = f"{parent_path} - {item_name}"
                names.append(combined_path)
                
                # itemsの中にさらにサブセクションがある場合も処理
                self._extract_nested_names(item, combined_path, names)
    
    def _compare_numbers(
        self,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
        section_mappings: list[SectionMapping],
    ) -> list[NumericalDifference]:
        """
        数値データを比較し、差分を検出
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            section_mappings: セクションマッピング
            
        Returns:
            数値差分のリスト
        """
        differences: list[NumericalDifference] = []
        
        # 両方のドキュメントからテーブルデータを取得
        tables1 = structured1.get("tables", [])
        tables2 = structured2.get("tables", [])
        
        if not tables1 or not tables2:
            logger.info("テーブルデータが不足しているため、数値比較をスキップします")
            return differences
        
        # セクションマッピングに基づいてテーブルをペアリング
        for mapping in section_mappings:
            # 簡易実装：セクション名に基づいてテーブルを検索
            # 実際には、セクションとテーブルの関連付けがより複雑になる可能性がある
            
            # ドキュメント1のテーブルから数値を抽出
            for table1 in tables1:
                table1_data = table1.get("data", [])
                
                # ドキュメント2のテーブルから対応する数値を検索
                for table2 in tables2:
                    table2_data = table2.get("data", [])
                    
                    # テーブル間で数値を比較
                    table_diffs = self._compare_table_data(
                        mapping.doc1_section,
                        table1_data,
                        table2_data,
                    )
                    differences.extend(table_diffs)
        
        logger.info(f"数値差分検出: {len(differences)}件")
        return differences
    
    def _compare_kpi_time_series(
        self,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
        section_mappings: list[SectionMapping],
    ) -> list[dict[str, Any]]:
        """
        時系列財務データを比較（原文記載ベース）
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            section_mappings: セクションマッピング
            
        Returns:
            時系列比較結果のリスト
        """
        comparisons: list[dict[str, Any]] = []
        
        # セクションマッピングに基づいて比較
        for mapping in section_mappings:
            section1 = mapping.doc1_section
            section2 = mapping.doc2_section
            
            # 両方のセクションから時系列データを取得
            kpi_series1 = self._get_kpi_time_series_from_section(structured1, section1)
            kpi_series2 = self._get_kpi_time_series_from_section(structured2, section2)
            
            # 同じ指標を比較
            for kpi1 in kpi_series1:
                indicator = kpi1.get('indicator', '')
                # 同じ指標を探す
                kpi2 = next(
                    (k for k in kpi_series2 if k.get('indicator') == indicator),
                    None
                )
                
                if kpi2:
                    comparison = self._compare_single_kpi_series(
                        section1, indicator, kpi1, kpi2
                    )
                    if comparison:
                        comparisons.append(comparison)
        
        logger.info(f"時系列比較完了: {len(comparisons)}件")
        return comparisons
    
    def _get_kpi_time_series_from_section(
        self,
        structured: dict[str, Any],
        section_name: str,
    ) -> list[dict[str, Any]]:
        """セクションから時系列データを取得"""
        sections = structured.get("sections", {})
        section = sections.get(section_name, {})
        extracted_content = section.get("extracted_content", {})
        return extracted_content.get("kpi_time_series", [])
    
    def _compare_single_kpi_series(
        self,
        section: str,
        indicator: str,
        kpi1: dict[str, Any],
        kpi2: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """単一のKPI時系列を比較"""
        time_series1 = kpi1.get("time_series", [])
        time_series2 = kpi2.get("time_series", [])
        
        if not time_series1 or not time_series2:
            return None
        
        # 原文に記載されているトレンド表現の変化を検出
        trend1 = kpi1.get("stated_metrics", {}).get("trend_stated")
        trend2 = kpi2.get("stated_metrics", {}).get("trend_stated")
        
        # 原文に記載されている目標値の変化を検出
        target1 = kpi1.get("target_stated", {})
        target2 = kpi2.get("target_stated", {})
        
        # 原文に記載されているコメントの変化を検出
        comment1 = kpi1.get("stated_metrics", {}).get("comment")
        comment2 = kpi2.get("stated_metrics", {}).get("comment")
        
        changes = []
        
        # トレンド表現の変化
        if trend1 != trend2:
            changes.append({
                "type": "trend_stated_change",
                "previous": trend1,
                "current": trend2,
                "description": f"トレンド表現が「{trend1}」から「{trend2}」に変化"
            })
        
        # 目標値の変化
        if target1.get("target_description") != target2.get("target_description"):
            changes.append({
                "type": "target_change",
                "previous": target1.get("target_description"),
                "current": target2.get("target_description"),
                "description": f"目標値の記載が変更"
            })
        
        # コメントの変化
        if comment1 != comment2:
            changes.append({
                "type": "comment_change",
                "previous": comment1,
                "current": comment2,
                "description": f"コメントが変更"
            })
        
        if not changes:
            return None
        
        return {
            "section": section,
            "indicator": indicator,
            "time_series1": time_series1,
            "time_series2": time_series2,
            "changes": changes,
        }
    
    def _compare_logical_relationships(
        self,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
        section_mappings: list[SectionMapping],
    ) -> list[dict[str, Any]]:
        """
        論理関係の変化を分析
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            section_mappings: セクションマッピング
            
        Returns:
            論理関係変化のリスト
        """
        changes: list[dict[str, Any]] = []
        
        # セクションマッピングに基づいて比較
        for mapping in section_mappings:
            section1 = mapping.doc1_section
            section2 = mapping.doc2_section
            
            # 両方のセクションから論理関係を取得
            rels1 = self._get_logical_relationships_from_section(structured1, section1)
            rels2 = self._get_logical_relationships_from_section(structured2, section2)
            
            # 論理関係の追加・削除・変更を検出
            rels1_by_type = {}
            for rel in rels1:
                rel_type = rel.get('relationship_type', '')
                key = self._get_relationship_key(rel)
                rels1_by_type[key] = rel
            
            rels2_by_type = {}
            for rel in rels2:
                rel_type = rel.get('relationship_type', '')
                key = self._get_relationship_key(rel)
                rels2_by_type[key] = rel
            
            # 追加された論理関係
            for key, rel2 in rels2_by_type.items():
                if key not in rels1_by_type:
                    changes.append({
                        "section": section2,
                        "change_type": "added",
                        "relationship": rel2,
                    })
            
            # 削除された論理関係
            for key, rel1 in rels1_by_type.items():
                if key not in rels2_by_type:
                    changes.append({
                        "section": section1,
                        "change_type": "removed",
                        "relationship": rel1,
                    })
            
            # 変更された論理関係
            for key in rels1_by_type:
                if key in rels2_by_type:
                    rel1 = rels1_by_type[key]
                    rel2 = rels2_by_type[key]
                    
                    # original_textの変化を検出
                    if rel1.get('original_text') != rel2.get('original_text'):
                        changes.append({
                            "section": section2,
                            "change_type": "modified",
                            "previous": rel1,
                            "current": rel2,
                        })
        
        logger.info(f"論理関係変化検出: {len(changes)}件")
        return changes
    
    def _get_logical_relationships_from_section(
        self,
        structured: dict[str, Any],
        section_name: str,
    ) -> list[dict[str, Any]]:
        """セクションから論理関係を取得"""
        sections = structured.get("sections", {})
        section = sections.get(section_name, {})
        extracted_content = section.get("extracted_content", {})
        return extracted_content.get("logical_relationships", [])
    
    def _get_relationship_key(self, rel: dict[str, Any]) -> str:
        """論理関係のキーを生成（比較用）"""
        rel_type = rel.get('relationship_type', '')
        
        # 関係タイプに応じてキーを生成
        if rel_type == 'causality':
            subject = rel.get('subject', '')
            reason = rel.get('reason', '')
            return f"{rel_type}:{subject}:{reason}"
        elif rel_type == 'condition_consequence':
            condition = rel.get('condition', '')
            consequence = rel.get('consequence', '')
            return f"{rel_type}:{condition}:{consequence}"
        elif rel_type == 'problem_solution':
            problem = rel.get('problem', '')
            solution = rel.get('solution', '')
            return f"{rel_type}:{problem}:{solution}"
        elif rel_type == 'premise_conclusion':
            premise = rel.get('premise', '')
            conclusion = rel.get('conclusion', '')
            return f"{rel_type}:{premise}:{conclusion}"
        else:
            # フォールバック: original_textを使用
            return f"{rel_type}:{rel.get('original_text', '')[:100]}"
    
    def _compare_table_data(
        self,
        section: str,
        table1_data: list[list[str]],
        table2_data: list[list[str]],
    ) -> list[NumericalDifference]:
        """
        テーブルデータ内の数値を比較
        
        Args:
            section: セクション名
            table1_data: テーブル1のデータ（行のリスト）
            table2_data: テーブル2のデータ（行のリスト）
            
        Returns:
            数値差分のリスト
        """
        differences: list[NumericalDifference] = []
        
        # 簡易実装：行ごとに比較
        min_rows = min(len(table1_data), len(table2_data))
        
        for row_idx in range(min_rows):
            row1 = table1_data[row_idx]
            row2 = table2_data[row_idx]
            
            # 行の項目名（最初の列と仮定）
            item_name = row1[0] if len(row1) > 0 else f"行{row_idx + 1}"
            
            # 数値セルを比較
            min_cols = min(len(row1), len(row2))
            
            for col_idx in range(1, min_cols):  # 最初の列は項目名なのでスキップ
                cell1 = row1[col_idx]
                cell2 = row2[col_idx]
                
                # 数値を抽出
                value1, unit1 = self._extract_number_and_unit(cell1)
                value2, unit2 = self._extract_number_and_unit(cell2)
                
                if value1 is None or value2 is None:
                    continue  # 数値でない場合はスキップ
                
                # 単位を正規化
                normalized1, norm_unit1 = self._normalize_unit(value1, unit1)
                normalized2, norm_unit2 = self._normalize_unit(value2, unit2)
                
                # 差分を計算
                difference = normalized1 - normalized2
                
                # パーセント差分を計算
                difference_pct = None
                if normalized1 != 0:
                    difference_pct = (difference / abs(normalized1)) * 100
                
                # 有意な差異かチェック（許容誤差0.01%）
                is_significant = not self._is_number_within_tolerance(
                    normalized1, normalized2, tolerance_pct=0.01
                )
                
                # 差異がある場合のみ記録
                if is_significant:
                    diff = NumericalDifference(
                        section=section,
                        item_name=item_name,
                        value1=value1,
                        value2=value2,
                        difference=difference,
                        difference_pct=difference_pct,
                        unit1=unit1,
                        unit2=unit2,
                        normalized_unit=norm_unit1,
                        is_significant=is_significant,
                    )
                    differences.append(diff)
        
        return differences
    
    def _extract_number_and_unit(self, text: str) -> tuple[Optional[float], Optional[str]]:
        """
        テキストから数値と単位を抽出
        
        Args:
            text: 抽出対象のテキスト
            
        Returns:
            (数値, 単位) または (None, None)
        """
        if not isinstance(text, str):
            return None, None
        
        # カンマを削除
        text = text.replace(",", "").strip()
        
        # 数値パターンを検索（整数、小数、負の数）
        import re
        match = re.search(r"(-?\d+(?:\.\d+)?)", text)
        
        if not match:
            return None, None
        
        try:
            value = float(match.group(1))
        except ValueError:
            return None, None
        
        # 単位を抽出（数値以降のテキスト）
        unit_text = text[match.end():].strip()
        unit = unit_text if unit_text else None
        
        return value, unit
    
    def _normalize_unit(self, value: float, unit: Optional[str]) -> tuple[float, str]:
        """
        単位を正規化（千円、百万円など）
        
        Args:
            value: 数値
            unit: 単位（例: "千円", "百万円"）
            
        Returns:
            正規化された値と単位
        """
        if not unit:
            return value, "円"
        
        unit_lower = unit.lower().replace(" ", "")
        
        # 千円 -> 円
        if "千円" in unit_lower or "千" in unit_lower:
            return value * 1_000, "円"
        
        # 百万円 -> 円
        if "百万円" in unit_lower or "百万" in unit_lower:
            return value * 1_000_000, "円"
        
        # 十億円 -> 円
        if "十億円" in unit_lower or "十億" in unit_lower:
            return value * 1_000_000_000, "円"
        
        return value, unit
    
    def _is_number_within_tolerance(
        self,
        value1: float,
        value2: float,
        tolerance_pct: float = 0.01,
    ) -> bool:
        """
        2つの数値が許容誤差範囲内かチェック
        
        Args:
            value1: 数値1
            value2: 数値2
            tolerance_pct: 許容誤差（パーセント、デフォルト0.01%）
            
        Returns:
            許容範囲内ならTrue
        """
        if value1 == 0 and value2 == 0:
            return True
        
        if value1 == 0 or value2 == 0:
            return False
        
        diff_pct = abs(value1 - value2) / max(abs(value1), abs(value2)) * 100
        return diff_pct <= tolerance_pct
    
    def _compare_text(
        self,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
        section_mappings: list[SectionMapping],
    ) -> list[TextDifference]:
        """
        テキストを比較し、差分を検出
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            section_mappings: セクションマッピング
            
        Returns:
            テキスト差分のリスト
        """
        differences: list[TextDifference] = []
        
        text1 = structured1.get("full_text") or structured1.get("text", "")
        text2 = structured2.get("full_text") or structured2.get("text", "")
        
        if not text1 or not text2:
            logger.info("テキストデータが不足しているため、テキスト比較をスキップします")
            return differences
        
        # セクションマッピングに基づいてテキストを比較
        # 簡易実装：全体のテキストを比較（全セクション対象）
        for mapping in section_mappings:
            section_name = mapping.doc1_section
            
            # テキストの一致率を計算（difflib）
            matcher = difflib.SequenceMatcher(None, text1[:5000], text2[:5000])
            match_ratio = matcher.ratio()
            
            # 差分を抽出
            added_text = []
            removed_text = []
            changed_text = []
            
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "delete":
                    removed_text.append(text1[i1:i2])
                elif tag == "insert":
                    added_text.append(text2[j1:j2])
                elif tag == "replace":
                    changed_text.append((text1[i1:i2], text2[j1:j2]))
            
            # 意味類似度を計算（sentence-transformersは後で実装）
            semantic_similarity = None
            
            diff = TextDifference(
                section=section_name,
                match_ratio=match_ratio,
                added_text=added_text[:10],  # 最初の10個のみ
                removed_text=removed_text[:10],
                changed_text=changed_text[:10],
                semantic_similarity=semantic_similarity,
            )
            differences.append(diff)
        
        logger.info(f"テキスト差分検出: {len(differences)}件")
        return differences
    
    def _compare_sections_detailed(
        self,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        structured1: dict[str, Any],
        structured2: dict[str, Any],
        section_mappings: list[SectionMapping],
        progress_callback: Optional[callable] = None,
        comparison_mode: Optional[ComparisonMode] = None,
        iterative_search_mode: Literal["off", "high_only", "all"] = "off",
    ) -> list[SectionDetailedComparison]:
        """
        マッピングされた各セクションに対して詳細な差分分析を実行
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            section_mappings: セクションマッピング
            progress_callback: 進捗更新用のコールバック関数（オプション）
            
        Returns:
            セクション別詳細差分のリスト
        """
        detailed_comparisons: list[SectionDetailedComparison] = []
        
        if not self.openai_client:
            logger.info("OpenAI APIキーが設定されていないため、セクション別詳細分析をスキップします")
            return detailed_comparisons
        
        # セクション情報を取得
        sections1 = structured1.get("sections", {})
        sections2 = structured2.get("sections", {})
        
        if not sections1 or not sections2:
            logger.info("セクション情報が不足しているため、セクション別詳細分析をスキップします")
            return detailed_comparisons
        
        all_pages1 = structured1.get("pages", [])
        all_pages2 = structured2.get("pages", [])
        all_tables1 = structured1.get("tables", [])
        all_tables2 = structured2.get("tables", [])
        
        # 各セクションマッピングに対して詳細分析（全セクション対象）
        # まず、実際に処理可能なセクション数をカウント
        valid_sections = []
        for mapping in section_mappings:
            section1_info = sections1.get(mapping.doc1_section, {})
            section2_info = sections2.get(mapping.doc2_section, {})
            if section1_info and section2_info:
                valid_sections.append(mapping)
        
        total_sections = len(valid_sections)
        logger.info(f"セクション別詳細分析開始: 全{total_sections}セクションを並列処理します（最大{self.max_workers}並列）")
        
        # セクション分析を並列実行
        detailed_comparisons = []
        processed_count = 0
        skipped_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # すべてのセクションをサブミット（反復探索モードに応じて分岐）
            if iterative_search_mode == "off":
                # 既存の実装（追加探索なし）
                analyze_func = self._analyze_single_section
            else:
                # 反復探索付き実装
                analyze_func = self._analyze_single_section_with_integrated_search_decision
            
            future_to_mapping = {
                executor.submit(
                    analyze_func,
                    mapping,
                    sections1,
                    sections2,
                    all_pages1,
                    all_pages2,
                    all_tables1,
                    all_tables2,
                    doc1_info,
                    doc2_info,
                    comparison_mode,
                    iterative_search_mode,
                ): mapping
                for mapping in section_mappings
            }
            
            # 完了したセクションを収集（1:Nマッピング対応：リストで保持）
            section_results = []  # (mapping_index, result) のタプルのリスト
            for future in as_completed(future_to_mapping):
                mapping = future_to_mapping[future]
                
                try:
                    result = future.result()
                    if result is not None:
                        # マッピングのインデックスと結果をペアで保存
                        mapping_index = section_mappings.index(mapping)
                        section_results.append((mapping_index, result))
                        processed_count += 1
                        logger.info(f"セクション分析完了 [{processed_count}/{total_sections}]: {mapping.doc1_section} -> {mapping.doc2_section}")
                        
                        # 進捗コールバックを呼び出し
                        if progress_callback:
                            progress_callback(
                                current_section=mapping.doc1_section,
                                completed_sections=processed_count,
                                total_sections=total_sections
                            )
                    else:
                        skipped_count += 1
                        logger.warning(f"セクション分析スキップ: {mapping.doc1_section} -> {mapping.doc2_section}")
                        
                except Exception as exc:
                    logger.error(f"セクション詳細分析に失敗 ({mapping.doc1_section} -> {mapping.doc2_section}): {exc}", exc_info=True)
                    skipped_count += 1
        
        # 元の順番でソート（section_mappingsの順序を維持）
        section_results.sort(key=lambda x: x[0])  # インデックスでソート
        for _, result in section_results:
            detailed_comparisons.append(result)
        
        logger.info(f"セクション別詳細分析完了: 成功={processed_count}件, スキップ={skipped_count}件, 合計={len(detailed_comparisons)}件")
        return detailed_comparisons
    
    def _analyze_single_section(
        self,
        mapping: SectionMapping,
        sections1: dict,
        sections2: dict,
        all_pages1: list,
        all_pages2: list,
        all_tables1: list,
        all_tables2: list,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        comparison_mode: Optional[ComparisonMode] = None,
        iterative_search_mode: Literal["off", "high_only", "all"] = "off",
    ) -> Optional[SectionDetailedComparison]:
        """
        単一セクションの分析（並列実行用）
        
        Args:
            iterative_search_mode: 追加探索モード（この関数では使用しないが互換性のために受け取る）
        
        Returns:
            分析結果、またはスキップ時はNone
        """
        try:
            section1_info = sections1.get(mapping.doc1_section, {})
            section2_info = sections2.get(mapping.doc2_section, {})
            
            if not section1_info or not section2_info:
                logger.warning(f"セクション情報が見つかりません（スキップ）: {mapping.doc1_section}")
                return None
            
            # 抽出された情報を取得（extracted_contentがある場合はそれを使用）
            extracted_content1 = section1_info.get("extracted_content", {})
            extracted_content2 = section2_info.get("extracted_content", {})
            
            # extracted_contentがない場合は、原文を使用（後方互換性）
            if not extracted_content1 or not extracted_content2:
                logger.warning(
                    f"セクション {mapping.doc1_section} に extracted_content がありません。"
                    "原文を使用します（非推奨）"
                )
                # セクション範囲のテキストとテーブルを抽出
                section1_text = self._extract_section_text(section1_info, all_pages1)
                section2_text = self._extract_section_text(section2_info, all_pages2)
                
                section1_tables = self._extract_section_tables(section1_info, all_tables1)
                section2_tables = self._extract_section_tables(section2_info, all_tables2)
            else:
                section1_text = None
                section2_text = None
                section1_tables = []
                section2_tables = []
            
            # LLMで詳細分析
            detailed = self._analyze_section_with_llm(
                section_name=mapping.doc1_section,
                extracted_content1=extracted_content1,
                extracted_content2=extracted_content2,
                text1=section1_text,  # フォールバック用
                text2=section2_text,  # フォールバック用
                tables1=section1_tables,  # フォールバック用
                tables2=section2_tables,  # フォールバック用
                doc1_page_range=f"{section1_info.get('start_page', '?')}-{section1_info.get('end_page', '?')}",
                doc2_page_range=f"{section2_info.get('start_page', '?')}-{section2_info.get('end_page', '?')}",
                document_type=doc1_info.document_type or "",
                doc1_info=doc1_info,
                doc2_info=doc2_info,
                comparison_mode=comparison_mode,
            )
            
            # マッピング情報を追加（1:Nマッピング対応）
            detailed.doc1_section_name = mapping.doc1_section
            detailed.doc2_section_name = mapping.doc2_section
            detailed.mapping_confidence = mapping.confidence_score
            detailed.mapping_method = mapping.mapping_method
            
            return detailed
            
        except Exception as exc:
            logger.error(f"セクション分析処理でエラー ({mapping.doc1_section}): {exc}", exc_info=True)
            return None
    
    def _analyze_single_section_with_integrated_search_decision(
        self,
        mapping: SectionMapping,
        sections1: dict,
        sections2: dict,
        all_pages1: list,
        all_pages2: list,
        all_tables1: list,
        all_tables2: list,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        comparison_mode: Optional[ComparisonMode] = None,
        iterative_search_mode: Literal["off", "high_only", "all"] = "off",
    ) -> Optional[SectionDetailedComparison]:
        """
        単一セクションの分析を、初回LLMの判断に基づいて追加探索を含めて実行
        
        Args:
            iterative_search_mode: "off"=追加探索なし, "high_only"=重要度highのみ, "all"=全セクション
            
        Returns:
            拡張された分析結果、またはスキップ時はNone
        """
        try:
            section1_info = sections1.get(mapping.doc1_section, {})
            section2_info = sections2.get(mapping.doc2_section, {})
            
            if not section1_info or not section2_info:
                logger.warning(f"セクション情報が見つかりません（スキップ）: {mapping.doc1_section}")
                return None
            
            # ===== 初回分析（追加探索の判断を含む）=====
            logger.info(f"初回分析開始: {mapping.doc1_section}")
            
            # extracted_contentを取得
            extracted_content1 = section1_info.get("extracted_content", {})
            extracted_content2 = section2_info.get("extracted_content", {})
            
            # extracted_contentがない場合は、原文を使用（後方互換性）
            if not extracted_content1 or not extracted_content2:
                logger.warning(
                    f"セクション {mapping.doc1_section} に extracted_content がありません。"
                    "原文を使用します（非推奨）"
                )
                section1_text = self._extract_section_text(section1_info, all_pages1)
                section2_text = self._extract_section_text(section2_info, all_pages2)
                section1_tables = self._extract_section_tables(section1_info, all_tables1)
                section2_tables = self._extract_section_tables(section2_info, all_tables2)
            else:
                section1_text = None
                section2_text = None
                section1_tables = []
                section2_tables = []
            
            # LLMで詳細分析（追加探索の判断も含む）
            initial_analysis_result = self._analyze_section_with_llm_including_search_decision(
                section_name=mapping.doc1_section,
                extracted_content1=extracted_content1,
                extracted_content2=extracted_content2,
                text1=section1_text,
                text2=section2_text,
                tables1=section1_tables,
                tables2=section2_tables,
                doc1_page_range=f"{section1_info.get('start_page', '?')}-{section1_info.get('end_page', '?')}",
                doc2_page_range=f"{section2_info.get('start_page', '?')}-{section2_info.get('end_page', '?')}",
                doc1_info=doc1_info,
                doc2_info=doc2_info,
                comparison_mode=comparison_mode,
            )
            
            # initial_analysis_resultがNoneの場合のガード
            if initial_analysis_result is None:
                logger.error(f"initial_analysis_result が None です ({mapping.doc1_section})")
                return None
            
            # 結果をSectionDetailedComparisonに変換
            # CONSISTENCY_CHECKモードの場合、LLMレスポンスの構造化データをtext_changesに統合
            text_changes = initial_analysis_result.get("text_changes", {})
            if comparison_mode == ComparisonMode.CONSISTENCY_CHECK:
                text_changes = {
                    "contradictions": initial_analysis_result.get("contradictions", []),
                    "normal_differences": initial_analysis_result.get("normal_differences", []),
                    "complementary_info": initial_analysis_result.get("complementary_info", []),
                    "consistency_score": initial_analysis_result.get("consistency_score", 0),
                    "consistency_reason": initial_analysis_result.get("consistency_reason", "")
                }
            
            initial_result = SectionDetailedComparison(
                section_name=mapping.doc1_section,
                doc1_page_range=f"{section1_info.get('start_page', '?')}-{section1_info.get('end_page', '?')}",
                doc2_page_range=f"{section2_info.get('start_page', '?')}-{section2_info.get('end_page', '?')}",
                text_changes=text_changes,
                numerical_changes=initial_analysis_result.get("numerical_changes", []),
                tone_analysis=initial_analysis_result.get("tone_analysis", {}),
                importance=initial_analysis_result.get("importance", "medium"),
                importance_reason=initial_analysis_result.get("importance_reason", ""),
                summary=initial_analysis_result.get("summary", ""),
                doc1_section_name=mapping.doc1_section,
                doc2_section_name=mapping.doc2_section,
                mapping_confidence=mapping.confidence_score,
                mapping_method=mapping.mapping_method,
            )
            
            # ===== 追加探索の判断と実行 =====
            additional_search_info = initial_analysis_result.get("additional_search", {})
            
            # デバッグ: LLMレスポンスの内容を確認
            logger.info(f"=== セクション {mapping.doc1_section}: LLMレスポンス詳細 ===")
            logger.info(f"  initial_analysis_result keys: {list(initial_analysis_result.keys())}")
            logger.info(f"  additional_search_info: {additional_search_info}")
            
            llm_search_needed = additional_search_info.get("needed", False)
            llm_reason = additional_search_info.get("reason", "理由なし")
            search_phrases = additional_search_info.get("search_phrases", [])
            expected_findings = additional_search_info.get("expected_findings", "")
            
            # LLMの判断をログ出力
            logger.info(f"=== セクション {mapping.doc1_section}: LLMの追加探索判断 ===")
            logger.info(f"  LLM判断: needed={llm_search_needed}")
            logger.info(f"  理由: {llm_reason}")
            if search_phrases:
                logger.info(f"  検索フレーズ: {search_phrases}")
            if expected_findings:
                logger.info(f"  期待される発見: {expected_findings}")
            logger.info(f"  セクション重要度: {initial_result.importance}")
            logger.info(f"  iterative_search_mode: {iterative_search_mode}")
            
            # iterative_search_modeに基づいて最終判断
            search_needed = llm_search_needed
            override_reason = None
            
            if iterative_search_mode == "off":
                search_needed = False
                override_reason = "iterative_search_mode=offのため追加探索をスキップ"
            elif iterative_search_mode == "high_only" and initial_result.importance != "high":
                search_needed = False
                override_reason = f"iterative_search_mode=high_onlyだが重要度が{initial_result.importance}のため追加探索をスキップ"
            
            if override_reason:
                logger.info(f"  最終判断: {override_reason}")
            elif search_needed:
                logger.info(f"  最終判断: 追加探索を実行")
            else:
                logger.info(f"  最終判断: LLMが不要と判断したため追加探索をスキップ")
            
            if not search_needed:
                return initial_result
            
            # 追加探索を実行
            logger.info(f"=== セクション {mapping.doc1_section}: 追加探索を開始 ===")
            
            if not search_phrases:
                logger.warning(f"セクション {mapping.doc1_section}: 検索フレーズが生成されなかったため追加探索をスキップ")
                return initial_result
            
            # 追加探索を反復実行
            analyzed_sections = {mapping.doc1_section}
            additional_searches = []
            current_context = {
                "initial_analysis": initial_analysis_result,
                "search_reason": llm_reason,
            }
            max_iterations = 2
            
            for iteration in range(1, max_iterations + 1):
                logger.info(f"  第{iteration}回追加探索")
                
                # 今回の検索フレーズを使用（1回目は初回LLMのフレーズ、2回目以降は再生成）
                if iteration == 1:
                    current_phrases = search_phrases
                else:
                    # 前回の結果を踏まえて新しいフレーズを生成
                    current_phrases = self._regenerate_search_phrases(
                        base_section=mapping.doc1_section,
                        current_context=current_context,
                        previous_searches=additional_searches,
                    )
                    if not current_phrases:
                        logger.info(f"  第{iteration}回: 新しい検索フレーズが生成されなかったため終了")
                        break
                
                # 関連セクションを検索
                related_sections = self._search_related_sections_by_phrases(
                    search_phrases=current_phrases,
                    sections1=sections1,
                    sections2=sections2,
                    exclude_sections=analyzed_sections,
                    top_k=3,
                )
                
                if not related_sections:
                    logger.info(f"  第{iteration}回: 関連セクションが見つからなかったため終了")
                    break
                
                # 見つかったセクションを追加分析
                additional_analysis = self._analyze_related_sections_with_context(
                    base_section_name=mapping.doc1_section,
                    current_context=current_context,
                    related_sections=related_sections,
                    sections1=sections1,
                    sections2=sections2,
                    doc1_info=doc1_info,
                    doc2_info=doc2_info,
                )
                
                # 結果を記録
                search_result = {
                    "iteration": iteration,
                    "search_keywords": current_phrases,
                    "found_sections": [
                        {
                            "doc1_section": sec1,
                            "doc2_section": sec2,
                            "similarity": float(sim),
                        }
                        for sec1, sec2, sim in related_sections
                    ],
                    "analysis": additional_analysis,
                }
                additional_searches.append(search_result)
                
                # 分析済みセクションに追加
                for sec1, sec2, _ in related_sections:
                    analyzed_sections.add(sec1)
                
                # コンテキストを更新
                current_context[f"iteration_{iteration}"] = additional_analysis
                
                logger.info(f"  第{iteration}回探索完了: {len(related_sections)}個のセクションを追加分析")
            
            # 結果を統合
            initial_result.additional_searches = additional_searches
            initial_result.has_additional_context = len(additional_searches) > 0
            
            # サマリーを更新
            if additional_searches:
                initial_result.summary = self._generate_enhanced_summary_with_context(
                    base_summary=initial_result.summary,
                    additional_searches=additional_searches,
                    initial_search_reason=llm_reason,
                )
            
            logger.info(f"セクション {mapping.doc1_section}: 分析完了（追加探索{len(additional_searches)}回実行）")
            return initial_result
            
        except Exception as exc:
            logger.error(f"セクション分析処理でエラー ({mapping.doc1_section}): {exc}", exc_info=True)
            return None
    
    def _extract_section_text(
        self,
        section_info: dict,
        all_pages: list[dict],
    ) -> str:
        """
        セクション情報から該当ページのテキストを抽出
        
        Args:
            section_info: セクション情報（start_page, end_page, pages含む）
            all_pages: 全ページデータ
            
        Returns:
            セクションのテキスト
        """
        pages = section_info.get("pages", [])
        texts = []
        
        for page_num in pages:
            if 1 <= page_num <= len(all_pages):
                page = all_pages[page_num - 1]
                page_text = page.get("text", "")
                texts.append(page_text)
        
        return "\n".join(texts)
    
    def _extract_section_tables(
        self,
        section_info: dict,
        all_tables: list[dict],
    ) -> list[dict]:
        """
        セクション情報から該当ページのテーブルデータを抽出
        
        Args:
            section_info: セクション情報（start_page, end_page, pages含む）
            all_tables: 全テーブルデータ
            
        Returns:
            セクションのテーブルデータリスト
        """
        pages = section_info.get("pages", [])
        section_tables = []
        
        for table in all_tables:
            table_page = table.get("page", 0)
            if table_page in pages:
                section_tables.append(table)
        
        return section_tables
    
    def _summarize_tables(self, tables: list[dict]) -> str:
        """
        テーブルデータをサマリー形式に変換
        
        Args:
            tables: テーブルデータのリスト
            
        Returns:
            テーブルのサマリー文字列
        """
        if not tables:
            return "テーブルなし"
        
        summaries = []
        for i, table in enumerate(tables[:5]):  # 最大5個のテーブル
            data = table.get("data", [])
            row_count = len(data)
            col_count = len(data[0]) if data else 0
            
            # 最初の数行を抽出
            preview_rows = data[:3]
            preview = "\n".join([" | ".join(row) for row in preview_rows])
            
            summaries.append(
                f"テーブル{i+1} (ページ{table.get('page', '?')}): "
                f"{row_count}行 x {col_count}列\n{preview}\n..."
            )
        
        if len(tables) > 5:
            summaries.append(f"... 他 {len(tables) - 5} 個のテーブル")
        
        return "\n\n".join(summaries)
    
    def _build_company_comparison_prompt(
        self,
        doc_type_label: str,
        section_name: str,
        text1: str,
        text2: str,
        tables1_summary: str,
        tables2_summary: str,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        会社間比較用のプロンプトを生成
        """
        company1_name = doc1_info.company_name or "会社A"
        company2_name = doc2_info.company_name or "会社B"
        
        return f"""
以下は異なる2社の「{doc_type_label}」における「{section_name}」セクションです。
企業間の開示内容の違いを分析してください。

【{company1_name}】
ページ範囲: {doc1_page_range}
テキスト（抜粋）:
{text1[:3000]}

テーブルデータ:
{tables1_summary}

【{company2_name}】
ページ範囲: {doc2_page_range}
テキスト（抜粋）:
{text2[:3000]}

テーブルデータ:
{tables2_summary}

【分析タスク】
2社の「{section_name}」セクションの違いを以下の観点で分析してください：

1. **開示内容の違い**
   - {company1_name}のみに記載されている重要な内容（最大5個）
   - {company2_name}のみに記載されている重要な内容（最大5個）
   - 両社で異なる記載や方針の違い（最大5個）

2. **数値データの比較**
   - 両社の主要な数値指標の違い
   - 規模や比率の差異

3. **開示姿勢とトーンの違い**
   - 各社の開示の詳細度（詳細/標準/簡潔）
   - トーン（positive/neutral/negative）
   - ネガティブ度スコア（1-5）
   - 開示スタイルの違いの説明

4. **重要度判定**
   - この違いの重要度（high/medium/low）
   - 投資家や利害関係者にとっての意義

5. **サマリー**
   - 2社の違いを1-2文で要約

【出力形式】
JSON形式で以下のように回答してください：
{{
  "text_changes": {{
    "only_in_company1": ["内容1", "内容2"],
    "only_in_company2": ["内容1", "内容2"],
    "different_approaches": [
      {{
        "aspect": "側面",
        "company1_approach": "{company1_name}の方針",
        "company2_approach": "{company2_name}の方針"
      }}
    ]
  }},
  "numerical_changes": [
    {{
      "metric": "指標名",
      "company1_value": 数値1,
      "company2_value": 数値2,
      "difference_pct": 差異率,
      "context": "この違いの意味"
    }}
  ],
  "tone_analysis": {{
    "company1_detail_level": "詳細/標準/簡潔",
    "company2_detail_level": "詳細/標準/簡潔",
    "company1_tone": "positive/neutral/negative",
    "company2_tone": "positive/neutral/negative",
    "company1_negativity_score": 1.0～5.0,
    "company2_negativity_score": 1.0～5.0,
    "style_difference": "開示スタイルの違いの説明"
  }},
  "importance": "high/medium/low",
  "importance_reason": "重要度の理由",
  "summary": "2社の違いの要約"
}}
"""
    
    def _build_temporal_comparison_prompt(
        self,
        doc_type_label: str,
        section_name: str,
        text1: str,
        text2: str,
        tables1_summary: str,
        tables2_summary: str,
        doc1_page_range: str,
        doc2_page_range: str,
    ) -> str:
        """
        年度間比較・整合性チェック用のプロンプトを生成
        """
        return f"""
以下の2つの「{doc_type_label}」の「{section_name}」セクションを詳細に比較してください。

【ドキュメント1】
ページ範囲: {doc1_page_range}
テキスト（抜粋）:
{text1[:3000]}

テーブルデータ:
{tables1_summary}

【ドキュメント2】
ページ範囲: {doc2_page_range}
テキスト（抜粋）:
{text2[:3000]}

テーブルデータ:
{tables2_summary}

【分析タスク】
「{doc_type_label}」の「{section_name}」セクションの性質を踏まえて、以下を分析してください：

1. **テキストの主な違い**
   - 追加された内容（重要なもののみ、最大5個）
   - 削除された内容（重要なもののみ、最大5個）
   - 変更された内容（重要なもののみ、最大5個）

2. **数値データの違い**
   - テーブル内の数値の主要な変化
   - 重要な増減とその割合

3. **トーンや表現の違い**
   - ポジティブ/ネガティブのトーン（positive/neutral/negative）
   - ネガティブ度スコア（1-5）
   - トーンの違いの説明

4. **重要度判定**
   - 差異の重要度（high/medium/low）
   - その理由

5. **サマリー**
   - このセクションの差異を1-2文で要約

【出力形式】
JSON形式で以下のように回答してください：
{{
  "text_changes": {{
    "added": ["追加された内容1", "追加された内容2"],
    "removed": ["削除された内容1"],
    "modified": [
      {{"before": "変更前の内容", "after": "変更後の内容"}}
    ]
  }},
  "numerical_changes": [
    {{
      "item": "項目名",
      "value1": 数値1,
      "value2": 数値2,
      "change_pct": 変化率,
      "is_significant": true
    }}
  ],
  "tone_analysis": {{
    "tone1": "positive/neutral/negative",
    "tone2": "positive/neutral/negative",
    "negativity_score1": 1.0～5.0,
    "negativity_score2": 1.0～5.0,
    "difference": "トーンの違いの説明"
  }},
  "importance": "high/medium/low",
  "importance_reason": "重要度の理由",
  "summary": "このセクションの差異の要約"
}}
"""
    
    def _build_temporal_comparison_prompt_with_search(
        self,
        doc_type_label: str,
        section_name: str,
        text1: str,
        text2: str,
        tables1_summary: str,
        tables2_summary: str,
        doc1_page_range: str,
        doc2_page_range: str,
    ) -> str:
        """
        年度間比較用のプロンプトを生成（追加探索判断含む）
        """
        return f"""
以下の2つの「{doc_type_label}」の「{section_name}」セクションを詳細に比較してください。

【ドキュメント1】
ページ範囲: {doc1_page_range}
テキスト（抜粋）:
{text1[:3000]}

テーブルデータ:
{tables1_summary}

【ドキュメント2】
ページ範囲: {doc2_page_range}
テキスト（抜粋）:
{text2[:3000]}

テーブルデータ:
{tables2_summary}

【分析タスク】
「{doc_type_label}」の「{section_name}」セクションの性質を踏まえて、以下を分析してください：

1. **テキストの主な違い**
   - 追加された内容（重要なもののみ、最大5個）
   - 削除された内容（重要なもののみ、最大5個）
   - 変更された内容（重要なもののみ、最大5個）

2. **数値データの違い**
   - テーブル内の数値の主要な変化
   - 重要な増減とその割合

3. **トーンや表現の違い**
   - ポジティブ/ネガティブのトーン（positive/neutral/negative）
   - ネガティブ度スコア（1-5）
   - トーンの違いの説明

4. **重要度判定**
   - 差異の重要度（high/medium/low）
   - その理由

5. **サマリー**
   - このセクションの差異を1-2文で要約

【✨ 追加探索の判断】
このセクションの分析結果を踏まえて、以下を判断してください：

A. **追加探索の必要性**
   以下のような状況の場合、追加探索を推奨してください：
   - 矛盾や説明不足がある
   - 重大な変化の原因が不明
   - 数値の変化の背景が不明確
   - 他のセクションに関連情報がありそう
   - より深い理解のために追加コンテキストが必要

B. **検索フレーズの生成**
   追加探索が必要な場合、関連情報を見つけるための検索フレーズを3〜5個生成してください：
   - 具体的で検索しやすいフレーズ
   - セクション名や重要なキーワードを含む
   - 矛盾を解決したり、背景を理解するために有用なもの

【出力形式】
JSON形式で以下のように回答してください：
{{
  "text_changes": {{
    "added": ["追加された内容1", "追加された内容2"],
    "removed": ["削除された内容1"],
    "modified": [
      {{"before": "変更前の内容", "after": "変更後の内容"}}
    ]
  }},
  "numerical_changes": [
    {{
      "item": "項目名",
      "value1": 数値1,
      "value2": 数値2,
      "change_pct": 変化率,
      "is_significant": true
    }}
  ],
  "tone_analysis": {{
    "tone1": "positive/neutral/negative",
    "tone2": "positive/neutral/negative",
    "negativity_score1": 1.0～5.0,
    "negativity_score2": 1.0～5.0,
    "difference": "トーンの違いの説明"
  }},
  "importance": "high/medium/low",
  "importance_reason": "重要度の理由",
  "summary": "このセクションの差異の要約",
  
  "additional_search": {{
    "needed": true/false,
    "reason": "追加探索が必要/不要な理由",
    "search_phrases": [
      "検索フレーズ1（具体的なキーワードやトピック）",
      "検索フレーズ2",
      "検索フレーズ3"
    ],
    "expected_findings": "これらのフレーズで何を見つけることを期待しているか"
  }}
}}

注意：
- additional_search.neededがfalseの場合、search_phrasesは空配列で構いません
- search_phrasesは、他のセクションのタイトルや内容とマッチしやすい具体的なものにしてください
"""
    
    def _build_consistency_check_prompt(
        self,
        section_name: str,
        text1: str,
        text2: str,
        tables1_summary: str,
        tables2_summary: str,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        整合性チェック用のプロンプトを生成（異なる書類種別間の比較）
        """
        company_name = doc1_info.company_name or doc2_info.company_name or "同じ会社"
        doc1_type = doc1_info.document_type_label
        doc2_type = doc2_info.document_type_label
        
        return f"""
以下は{company_name}の異なる2種類の開示資料における「{section_name}」セクションです。
書類の性質の違いを考慮しながら、記載内容の整合性を評価してください。

【{doc1_type}】
ページ範囲: {doc1_page_range}
テキスト（抜粋）:
{text1[:3000]}

テーブルデータ:
{tables1_summary}

【{doc2_type}】
ページ範囲: {doc2_page_range}
テキスト（抜粋）:
{text2[:3000]}

テーブルデータ:
{tables2_summary}

【重要な前提】
- **{doc1_type}**と**{doc2_type}**は性質が異なる書類です
- 記載内容やスタイルが異なるのは正常です
- 問題となるのは「矛盾」や「明らかな不一致」のみです

【分析タスク】
以下の観点で整合性を評価してください：

1. **矛盾・不整合の検出**
   - 数値データの矛盾（同じ指標で異なる数値など）
   - 方針や戦略の矛盾（一方と逆の内容が記載されているなど）
   - 事実関係の不一致（年月日、組織名、役職名など）
   - 重大な矛盾があれば具体的に指摘（最大3個）

2. **正常な違い（書類の性質によるもの）**
   - 開示レベルの違い（法定書類は詳細、統合報告書は概要など）
   - 記載スタイルの違い（ステークホルダー向け vs 投資家向けなど）
   - 強調点の違い（ブランディング vs コンプライアンスなど）
   - 書類の性質として正常な違いを説明（最大3個）

3. **相互補完関係**
   - 一方が詳細、他方が概要で相互補完している内容
   - それぞれの書類の役割分担として適切な記載
   - 補完関係にある内容があれば説明（最大3個）

4. **整合性スコア**
   - 全体的な整合性を5段階で評価（1:重大な矛盾, 2:一部不整合, 3:概ね整合, 4:良好, 5:完全整合）
   - スコアの根拠を簡潔に説明

5. **重要度判定**
   - high: 明確な矛盾や重大な不整合がある
   - medium: 微細な不一致や説明不足がある
   - low: 正常な違いのみで整合性に問題なし

6. **サマリー**
   - 2つの書類の関係性を1-2文で要約

【出力形式】
JSON形式で以下のように回答してください：
{{
  "contradictions": [
    {{
      "type": "矛盾の種類（数値/方針/事実等）",
      "description": "具体的な矛盾の内容",
      "impact": "この矛盾の影響"
    }}
  ],
  "normal_differences": [
    {{
      "aspect": "違いの側面",
      "doc1_approach": "{doc1_type}での記載",
      "doc2_approach": "{doc2_type}での記載",
      "reason": "この違いが正常である理由"
    }}
  ],
  "complementary_info": [
    {{
      "topic": "トピック",
      "doc1_contribution": "{doc1_type}が提供する情報",
      "doc2_contribution": "{doc2_type}が提供する情報",
      "relationship": "相互補完の関係性"
    }}
  ],
  "consistency_score": 1～5,
  "consistency_reason": "スコアの根拠",
  "importance": "high/medium/low",
  "importance_reason": "重要度の理由",
  "summary": "2つの書類の関係性の要約"
}}

注意: contradictionsが空の場合、重要度はlowまたはmediumにしてください。
"""
    
    def _build_consistency_check_prompt_with_search(
        self,
        section_name: str,
        text1: str,
        text2: str,
        tables1_summary: str,
        tables2_summary: str,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        整合性チェック用のプロンプトを生成（追加探索判断含む）
        """
        company_name = doc1_info.company_name or doc2_info.company_name or "同じ会社"
        doc1_type = doc1_info.document_type_label
        doc2_type = doc2_info.document_type_label
        
        base_prompt = self._build_consistency_check_prompt(
            section_name, text1, text2, tables1_summary, tables2_summary,
            doc1_page_range, doc2_page_range, doc1_info, doc2_info
        )
        
        # 追加探索の判断セクションを追加
        additional_section = """

【✨ 追加探索の判断】
このセクションの整合性分析結果を踏まえて、以下を判断してください：

A. **追加探索の必要性**
   以下のような状況の場合、追加探索を推奨してください：
   - 矛盾が検出され、その原因や背景を探る必要がある
   - 数値の不一致について他のセクションで確認が必要
   - 方針の矛盾について、別のセクションに補足説明がありそう
   - 整合性スコアが3以下で、追加情報が必要

B. **検索フレーズの生成**
   追加探索が必要な場合、以下の観点で検索フレーズを生成：
   - 矛盾の原因を説明している可能性のあるセクションのキーワード
   - 関連する数値データがある可能性のあるトピック
   - 補足説明や詳細が記載されていそうなテーマ
"""
        
        # 出力形式にadditional_searchを追加
        output_section = """
  "additional_search": {{
    "needed": true/false,
    "reason": "追加探索が必要/不要な理由（矛盾の解決、背景の理解など）",
    "search_phrases": [
      "検索フレーズ1（矛盾に関連するキーワード）",
      "検索フレーズ2（数値データの出典等）",
      "検索フレーズ3（補足説明のトピック）"
    ],
    "expected_findings": "これらのフレーズで何を見つけることを期待しているか"
  }}
"""
        
        # 既存の出力形式の最後に追加
        prompt = base_prompt.replace(
            '  "summary": "2つの書類の関係性の要約"\n}}',
            f'  "summary": "2つの書類の関係性の要約",{output_section}\n}}'
        )
        
        # 追加探索の判断セクションを追加
        prompt = prompt.replace(
            "6. **サマリー**",
            "6. **サマリー**" + additional_section
        )
        
        return prompt
    
    def _build_company_comparison_prompt_with_search(
        self,
        doc_type_label: str,
        section_name: str,
        text1: str,
        text2: str,
        tables1_summary: str,
        tables2_summary: str,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        会社間比較用のプロンプトを生成（追加探索判断含む）
        """
        company1_name = doc1_info.company_name or "会社A"
        company2_name = doc2_info.company_name or "会社B"
        
        base_prompt = self._build_company_comparison_prompt(
            doc_type_label, section_name, text1, text2, tables1_summary, tables2_summary,
            doc1_page_range, doc2_page_range, doc1_info, doc2_info
        )
        
        additional_section = """

【✨ 追加探索の判断】
会社間比較の結果を踏まえて、以下を判断してください：

A. **追加探索の必要性**
   以下のような状況の場合、追加探索を推奨してください：
   - 一方の会社の記載が他方と大きく異なり、その背景を探る必要がある
   - 開示姿勢の違いが顕著で、他のセクションでも確認が必要
   - 数値の差異について、他のセクションに説明がありそう
   - ベストプラクティスの比較のため、追加情報が有用

B. **検索フレーズの生成**
   追加探索が必要な場合、以下の観点で検索フレーズを生成：
   - 差異の背景を説明していそうなトピック
   - 関連する戦略や方針が記載されているセクションのキーワード
   - 数値の根拠や詳細が記載されていそうなテーマ
"""
        
        output_section = """
  "additional_search": {{
    "needed": true/false,
    "reason": "追加探索が必要/不要な理由",
    "search_phrases": [
      "検索フレーズ1（差異の背景に関するキーワード）",
      "検索フレーズ2（関連戦略のトピック）",
      "検索フレーズ3"
    ],
    "expected_findings": "これらのフレーズで何を見つけることを期待しているか"
  }}
"""
        
        prompt = base_prompt.replace(
            '  "summary": "2社の違いの要約"\n}}',
            f'  "summary": "2社の違いの要約",{output_section}\n}}'
        )
        
        prompt = prompt.replace(
            "5. **サマリー**",
            "5. **サマリー**" + additional_section
        )
        
        return prompt
    
    def _analyze_section_with_llm(
        self,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        text1: Optional[str],
        text2: Optional[str],
        tables1: list[dict],
        tables2: list[dict],
        doc1_page_range: str,
        doc2_page_range: str,
        document_type: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        comparison_mode: Optional[ComparisonMode] = None,
    ) -> SectionDetailedComparison:
        """
        LLMでセクションの詳細差分分析を実行
        
        Args:
            section_name: セクション名
            extracted_content1: ドキュメント1の抽出情報
            extracted_content2: ドキュメント2の抽出情報
            text1: ドキュメント1のセクションテキスト（フォールバック用）
            text2: ドキュメント2のセクションテキスト（フォールバック用）
            tables1: ドキュメント1のセクションテーブル（フォールバック用）
            tables2: ドキュメント2のセクションテーブル（フォールバック用）
            doc1_page_range: ドキュメント1のページ範囲
            doc2_page_range: ドキュメント2のページ範囲
            document_type: 書類種別
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            comparison_mode: 比較モード（会社間 or 年度間）
            
        Returns:
            セクション別詳細差分
        """
        try:
            import json
            from .templates import load_template
            
            # テンプレートから書類種別の表示名を取得
            try:
                template = load_template(document_type)
                doc_type_label = template.get("display_name", document_type)
            except:
                doc_type_label = document_type
            
            # 比較モードに応じてプロンプトを切り替え
            logger.info(f"プロンプト生成開始: comparison_mode={comparison_mode}, section_name={section_name}")
            
            # extracted_contentがある場合はそれを使用、ない場合は原文を使用
            if extracted_content1 and extracted_content2:
                logger.info("extracted_contentを使用してプロンプトを生成します")
                use_extracted = True
            else:
                logger.warning("extracted_contentがないため、原文を使用します（非推奨）")
                use_extracted = False
                # テーブルサマリーを作成（フォールバック）
                tables1_summary = self._summarize_tables(tables1)
                tables2_summary = self._summarize_tables(tables2)
            
            if comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY:
                # 会社間比較のプロンプト
                logger.info("会社間比較プロンプトを生成します")
                if use_extracted:
                    prompt = self._build_company_comparison_prompt_from_extracted(
                        doc_type_label, section_name,
                        extracted_content1, extracted_content2,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
                else:
                    prompt = self._build_company_comparison_prompt(
                        doc_type_label, section_name,
                        text1, text2, tables1_summary, tables2_summary,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
            elif comparison_mode == ComparisonMode.CONSISTENCY_CHECK:
                # 整合性チェックのプロンプト（異なる書類種別間の比較）
                logger.info("整合性チェックプロンプトを生成します")
                if use_extracted:
                    prompt = self._build_consistency_check_prompt_from_extracted(
                        section_name,
                        extracted_content1, extracted_content2,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
                else:
                    prompt = self._build_consistency_check_prompt(
                        section_name,
                        text1, text2, tables1_summary, tables2_summary,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
            else:
                # 年度間比較のプロンプト
                logger.info("年度間比較プロンプトを生成します")
                if use_extracted:
                    prompt = self._build_temporal_comparison_prompt_from_extracted(
                        doc_type_label, section_name,
                        extracted_content1, extracted_content2,
                        doc1_page_range, doc2_page_range
                    )
                else:
                    prompt = self._build_temporal_comparison_prompt(
                        doc_type_label, section_name,
                        text1, text2, tables1_summary, tables2_summary,
                        doc1_page_range, doc2_page_range
                    )
            
            logger.info(f"セクション詳細分析開始: {section_name} (モード: {comparison_mode})")
            
            # 比較モードに応じてシステムメッセージを調整
            if comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY:
                system_message = f"あなたは「{doc_type_label}」の分析エキスパートです。異なる企業間の開示内容の違いを正確に検出し、投資家や利害関係者にとっての重要度を判定してください。"
            elif comparison_mode == ComparisonMode.CONSISTENCY_CHECK:
                system_message = f"あなたは企業開示資料の整合性分析エキスパートです。異なる種類の開示資料における記載内容の整合性を評価してください。書類の性質による正常な違いと、矛盾・不整合を明確に区別してください。"
            else:
                system_message = f"あなたは「{doc_type_label}」の分析エキスパートです。差異を正確に検出し、重要度を判定してください。"
            
            response = self.openai_client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # 整合性チェックの場合、新しいフィールドを既存の構造にマッピング
            text_changes = result.get("text_changes", {})
            if comparison_mode == ComparisonMode.CONSISTENCY_CHECK:
                # 新しいフィールドをtext_changesに統合
                text_changes = {
                    "contradictions": result.get("contradictions", []),
                    "normal_differences": result.get("normal_differences", []),
                    "complementary_info": result.get("complementary_info", []),
                    "consistency_score": result.get("consistency_score", 0),
                    "consistency_reason": result.get("consistency_reason", "")
                }
            
            # 重要度の判定（矛盾がある場合は自動的にhighに昇格）
            importance = result.get("importance", "medium")
            importance_reason = result.get("importance_reason", "")
            
            # 矛盾検出時は必ずhigh importanceに設定
            contradictions = text_changes.get("contradictions", [])
            if contradictions and len(contradictions) > 0:
                importance = "high"
                if not importance_reason:
                    importance_reason = f"矛盾が{len(contradictions)}件検出されました"
                else:
                    importance_reason = f"矛盾が{len(contradictions)}件検出されました。{importance_reason}"
            
            # 結果を構造化
            detailed = SectionDetailedComparison(
                section_name=section_name,
                doc1_page_range=doc1_page_range,
                doc2_page_range=doc2_page_range,
                text_changes=text_changes,
                numerical_changes=result.get("numerical_changes", []),
                tone_analysis=result.get("tone_analysis", {}),
                importance=importance,
                importance_reason=importance_reason,
                summary=result.get("summary", ""),
            )
            
            logger.info(f"セクション詳細分析完了: {section_name} (重要度: {detailed.importance})")
            return detailed
            
        except Exception as exc:
            logger.error(f"セクション詳細分析に失敗 ({section_name}): {exc}", exc_info=True)
            
            # エラー時のデフォルト値
            return SectionDetailedComparison(
                section_name=section_name,
                doc1_page_range=doc1_page_range,
                doc2_page_range=doc2_page_range,
                importance="low",
                importance_reason=f"分析失敗: {type(exc).__name__}",
                summary=f"分析に失敗しました: {str(exc)[:100]}",
            )
    
    def _format_extracted_content(self, extracted_content: dict) -> str:
        """
        extracted_contentをプロンプト用に整形
        
        Args:
            extracted_content: 抽出された情報
            
        Returns:
            整形されたテキスト
        """
        import json
        
        sections = []
        
        # 財務指標・数値情報
        financial_data = extracted_content.get("financial_data", [])
        if financial_data:
            sections.append("【財務指標・数値情報】")
            for item in financial_data:
                item_str = f"- {item.get('item', '')}: {item.get('value', '')} {item.get('unit', '')} ({item.get('period', '')})"
                if item.get('context'):
                    item_str += f"\n  補足: {item.get('context')}"
                sections.append(item_str)
        
        # 会計処理上のコメント
        accounting_notes = extracted_content.get("accounting_notes", [])
        if accounting_notes:
            sections.append("\n【会計処理上のコメント】")
            for note in accounting_notes:
                note_str = f"- {note.get('topic', '')} ({note.get('type', '')})\n  {note.get('content', '')}"
                sections.append(note_str)
        
        # 事実情報
        factual_info = extracted_content.get("factual_info", [])
        if factual_info:
            sections.append("\n【事実情報】")
            for fact in factual_info:
                fact_str = f"- {fact.get('category', '')} - {fact.get('item', '')}: {fact.get('value', '')}"
                sections.append(fact_str)
        
        # 主張・メッセージ
        messages = extracted_content.get("messages", [])
        if messages:
            sections.append("\n【主張・メッセージ】")
            for msg in messages:
                msg_str = f"- {msg.get('type', '')} (トーン: {msg.get('tone', '')})\n  {msg.get('content', '')}"
                sections.append(msg_str)
        
        # 時系列財務データ
        kpi_time_series = extracted_content.get("kpi_time_series", [])
        if kpi_time_series:
            sections.append("\n【時系列財務データ】")
            for kpi in kpi_time_series:
                indicator = kpi.get('indicator', '')
                unit = kpi.get('unit', '')
                time_series = kpi.get('time_series', [])
                time_series_str = ", ".join([
                    f"{ts.get('period', '')}: {ts.get('value', '')}{unit}"
                    for ts in time_series[:5]  # 最大5年分
                ])
                sections.append(f"- {indicator} ({unit}): {time_series_str}")
                stated_metrics = kpi.get('stated_metrics', {}) or {}
                if stated_metrics:
                    if stated_metrics.get('cagr_stated'):
                        sections.append(f"  CAGR: {stated_metrics.get('cagr_stated')}")
                    if stated_metrics.get('trend_stated'):
                        sections.append(f"  トレンド: {stated_metrics.get('trend_stated')}")
                target_stated = kpi.get('target_stated', {}) or {}
                if target_stated and target_stated.get('target_description'):
                    sections.append(f"  目標: {target_stated.get('target_description')}")
        
        # 論理関係
        logical_relationships = extracted_content.get("logical_relationships", [])
        if logical_relationships:
            sections.append("\n【論理関係】")
            for rel in logical_relationships[:5]:  # 最大5件
                rel_type = rel.get('relationship_type', '')
                original_text = rel.get('original_text', '')[:200]  # 最大200文字
                confidence = rel.get('confidence', 'medium')
                sections.append(f"- {rel_type} (信頼度: {confidence})\n  {original_text}")
        
        # セグメント別時系列データ
        segment_time_series = extracted_content.get("segment_time_series", [])
        if segment_time_series:
            sections.append("\n【セグメント別時系列データ】")
            for seg in segment_time_series[:3]:  # 最大3セグメント
                segment_name = seg.get('segment_name', '')
                revenue_ts = seg.get('revenue_time_series', [])
                revenue_str = ", ".join([
                    f"{ts.get('period', '')}: {ts.get('value', '')}"
                    for ts in revenue_ts[:3]  # 最大3年分
                ])
                sections.append(f"- {segment_name} (売上): {revenue_str}")
        
        if not sections:
            return "（抽出された情報なし）"
        
        return "\n".join(sections)
    
    def _build_company_comparison_prompt_from_extracted(
        self,
        doc_type_label: str,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        会社間比較用のプロンプトを生成（extracted_content使用）
        """
        company1_name = doc1_info.company_name or "会社A"
        company2_name = doc2_info.company_name or "会社B"
        
        content1_formatted = self._format_extracted_content(extracted_content1)
        content2_formatted = self._format_extracted_content(extracted_content2)
        
        return f"""
以下は異なる2社の「{doc_type_label}」における「{section_name}」セクションから抽出された情報です。
企業間の開示内容の違いを分析してください。

【{company1_name}】（ページ: {doc1_page_range}）
{content1_formatted}

【{company2_name}】（ページ: {doc2_page_range}）
{content2_formatted}

【分析タスク】
2社の「{section_name}」セクションの違いを以下の観点で分析してください：

1. **開示内容の違い**
   - {company1_name}のみに記載されている重要な内容（最大5個）
   - {company2_name}のみに記載されている重要な内容（最大5個）
   - 両社で異なる記載や方針の違い（最大5個）

2. **数値データの比較**
   - 両社の主要な数値指標の違い
   - 規模や比率の差異

3. **開示姿勢とトーンの違い**
   - 各社の開示の詳細度（詳細/標準/簡潔）
   - トーン（positive/neutral/negative）
   - ネガティブ度スコア（1-5）
   - 開示スタイルの違いの説明

4. **重要度判定**
   - この違いの重要度（high/medium/low）
   - 投資家や利害関係者にとっての意義

5. **サマリー**
   - 2社の違いを1-2文で要約

【出力形式】
JSON形式で以下のように回答してください：
{{
  "text_changes": {{
    "only_in_company1": ["内容1", "内容2"],
    "only_in_company2": ["内容1", "内容2"],
    "different_approaches": [
      {{
        "aspect": "側面",
        "company1_approach": "{company1_name}の方針",
        "company2_approach": "{company2_name}の方針"
      }}
    ]
  }},
  "numerical_changes": [
    {{
      "metric": "指標名",
      "company1_value": 数値1,
      "company2_value": 数値2,
      "difference_pct": 差異率,
      "context": "この違いの意味"
    }}
  ],
  "tone_analysis": {{
    "company1_detail_level": "詳細/標準/簡潔",
    "company2_detail_level": "詳細/標準/簡潔",
    "company1_tone": "positive/neutral/negative",
    "company2_tone": "positive/neutral/negative",
    "company1_negativity_score": 1.0～5.0,
    "company2_negativity_score": 1.0～5.0,
    "style_difference": "開示スタイルの違いの説明"
  }},
  "importance": "high/medium/low",
  "importance_reason": "重要度の理由",
  "summary": "2社の違いの要約"
}}
"""
    
    def _build_company_comparison_prompt_from_extracted_with_search(
        self,
        doc_type_label: str,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        会社間比較用のプロンプトを生成（extracted_content使用、追加探索判断含む）
        """
        base_prompt = self._build_company_comparison_prompt_from_extracted(
            doc_type_label, section_name,
            extracted_content1, extracted_content2,
            doc1_page_range, doc2_page_range,
            doc1_info, doc2_info
        )
        
        additional_section = """

【✨ 追加探索の判断】
会社間比較の結果を踏まえて、以下を判断してください：

A. **追加探索の必要性**
   以下のような状況の場合、追加探索を推奨してください：
   - 一方の会社の記載が他方と大きく異なり、その背景を探る必要がある
   - 開示姿勢の違いが顕著で、他のセクションでも確認が必要
   - 数値の差異について、他のセクションに説明がありそう
   - ベストプラクティスの比較のため、追加情報が有用

B. **検索フレーズの生成**
   追加探索が必要な場合、以下の観点で検索フレーズを生成：
   - 差異の背景を説明していそうなトピック
   - 関連する戦略や方針が記載されているセクションのキーワード
   - 数値の根拠や詳細が記載されていそうなテーマ
"""
        
        output_section = """
  "additional_search": {{
    "needed": true/false,
    "reason": "追加探索が必要/不要な理由",
    "search_phrases": [
      "検索フレーズ1（差異の背景に関するキーワード）",
      "検索フレーズ2（関連戦略のトピック）",
      "検索フレーズ3"
    ],
    "expected_findings": "これらのフレーズで何を見つけることを期待しているか"
  }}
"""
        
        prompt = base_prompt.replace(
            '  "summary": "2社の違いの要約"\n}}',
            f'  "summary": "2社の違いの要約",{output_section}\n}}'
        )
        
        prompt = prompt.replace(
            "5. **サマリー**",
            "5. **サマリー**" + additional_section
        )
        
        return prompt
    
    def _build_temporal_comparison_prompt_from_extracted(
        self,
        doc_type_label: str,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        doc1_page_range: str,
        doc2_page_range: str,
    ) -> str:
        """
        年度間比較・整合性チェック用のプロンプトを生成（extracted_content使用）
        """
        content1_formatted = self._format_extracted_content(extracted_content1)
        content2_formatted = self._format_extracted_content(extracted_content2)
        
        return f"""
以下の2つの「{doc_type_label}」の「{section_name}」セクションから抽出された情報を詳細に比較してください。

【ドキュメント1】（ページ: {doc1_page_range}）
{content1_formatted}

【ドキュメント2】（ページ: {doc2_page_range}）
{content2_formatted}

【分析タスク】
「{doc_type_label}」の「{section_name}」セクションの性質を踏まえて、以下を分析してください：

1. **情報の主な違い**
   - 追加された内容（重要なもののみ、最大5個）
   - 削除された内容（重要なもののみ、最大5個）
   - 変更された内容（重要なもののみ、最大5個）

2. **数値データの違い**
   - 財務指標の主要な変化
   - 重要な増減とその割合

3. **トーンや表現の違い**
   - ポジティブ/ネガティブのトーン（positive/neutral/negative）
   - ネガティブ度スコア（1-5）
   - トーンの違いの説明

4. **重要度判定**
   - 差異の重要度（high/medium/low）
   - その理由

5. **サマリー**
   - このセクションの差異を1-2文で要約

【出力形式】
JSON形式で以下のように回答してください：
{{
  "text_changes": {{
    "added": ["追加された内容1", "追加された内容2"],
    "removed": ["削除された内容1"],
    "modified": [
      {{"before": "変更前の内容", "after": "変更後の内容"}}
    ]
  }},
  "numerical_changes": [
    {{
      "item": "項目名",
      "value1": 数値1,
      "value2": 数値2,
      "change_pct": 変化率,
      "is_significant": true
    }}
  ],
  "tone_analysis": {{
    "tone1": "positive/neutral/negative",
    "tone2": "positive/neutral/negative",
    "negativity_score1": 1.0～5.0,
    "negativity_score2": 1.0～5.0,
    "difference": "トーンの違いの説明"
  }},
  "importance": "high/medium/low",
  "importance_reason": "重要度の理由",
  "summary": "このセクションの差異の要約"
}}
"""
    
    def _build_temporal_comparison_prompt_from_extracted_with_search(
        self,
        doc_type_label: str,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        doc1_page_range: str,
        doc2_page_range: str,
    ) -> str:
        """
        年度間比較用のプロンプトを生成（extracted_content使用、追加探索判断含む）
        """
        base_prompt = self._build_temporal_comparison_prompt_from_extracted(
            doc_type_label, section_name,
            extracted_content1, extracted_content2,
            doc1_page_range, doc2_page_range
        )
        
        additional_section = """

【✨ 追加探索の判断】
このセクションの分析結果を踏まえて、以下を判断してください：

A. **追加探索の必要性**
   以下のような状況の場合、追加探索を推奨してください：
   - 矛盾や説明不足がある
   - 重大な変化の原因が不明
   - 数値の変化の背景が不明確
   - 他のセクションに関連情報がありそう
   - より深い理解のために追加コンテキストが必要

B. **検索フレーズの生成**
   追加探索が必要な場合、関連情報を見つけるための検索フレーズを3〜5個生成してください：
   - 具体的で検索しやすいフレーズ
   - セクション名や重要なキーワードを含む
   - 矛盾を解決したり、背景を理解するために有用なもの
"""
        
        output_section = """
  "additional_search": {{
    "needed": true/false,
    "reason": "追加探索が必要/不要な理由",
    "search_phrases": [
      "検索フレーズ1（具体的なキーワードやトピック）",
      "検索フレーズ2",
      "検索フレーズ3"
    ],
    "expected_findings": "これらのフレーズで何を見つけることを期待しているか"
  }}
"""
        
        prompt = base_prompt.replace(
            '  "summary": "このセクションの差異の要約"\n}}',
            f'  "summary": "このセクションの差異の要約",{output_section}\n}}'
        )
        
        prompt = prompt.replace(
            "5. **サマリー**",
            "5. **サマリー**" + additional_section
        )
        
        return prompt
    
    def _build_consistency_check_prompt_from_extracted(
        self,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        整合性チェック用のプロンプトを生成（extracted_content使用）
        """
        company_name = doc1_info.company_name or doc2_info.company_name or "同じ会社"
        doc1_type = doc1_info.document_type_label
        doc2_type = doc2_info.document_type_label
        
        content1_formatted = self._format_extracted_content(extracted_content1)
        content2_formatted = self._format_extracted_content(extracted_content2)
        
        return f"""
以下は{company_name}の異なる2種類の開示資料における「{section_name}」セクションから抽出された情報です。
書類の性質の違いを考慮しながら、記載内容の整合性を評価してください。

【{doc1_type}】（ページ: {doc1_page_range}）
{content1_formatted}

【{doc2_type}】（ページ: {doc2_page_range}）
{content2_formatted}

【重要な前提】
- **{doc1_type}**と**{doc2_type}**は性質が異なる書類です
- 記載内容やスタイルが異なるのは正常です
- 問題となるのは「矛盾」や「明らかな不一致」のみです

【分析タスク】
以下の観点で整合性を評価してください：

1. **矛盾・不整合の検出**
   - 数値データの矛盾（同じ指標で異なる数値など）
   - 方針や戦略の矛盾（一方と逆の内容が記載されているなど）
   - 事実関係の不一致（年月日、組織名、役職名など）
   - 重大な矛盾があれば具体的に指摘（最大3個）

2. **正常な違い（書類の性質によるもの）**
   - 開示レベルの違い（法定書類は詳細、統合報告書は概要など）
   - 記載スタイルの違い（ステークホルダー向け vs 投資家向けなど）
   - 強調点の違い（ブランディング vs コンプライアンスなど）
   - 書類の性質として正常な違いを説明（最大3個）

3. **相互補完関係**
   - 一方が詳細、他方が概要で相互補完している内容
   - それぞれの書類の役割分担として適切な記載
   - 補完関係にある内容があれば説明（最大3個）

4. **整合性スコア**
   - 全体的な整合性を5段階で評価（1:重大な矛盾, 2:一部不整合, 3:概ね整合, 4:良好, 5:完全整合）
   - スコアの根拠を簡潔に説明

5. **重要度判定**
   - high: 明確な矛盾や重大な不整合がある
   - medium: 微細な不一致や説明不足がある
   - low: 正常な違いのみで整合性に問題なし

6. **サマリー**
   - 2つの書類の関係性を1-2文で要約

【出力形式】
JSON形式で以下のように回答してください：
{{
  "contradictions": [
    {{
      "type": "矛盾の種類（数値/方針/事実等）",
      "description": "具体的な矛盾の内容",
      "impact": "この矛盾の影響"
    }}
  ],
  "normal_differences": [
    {{
      "aspect": "違いの側面",
      "doc1_approach": "{doc1_type}での記載",
      "doc2_approach": "{doc2_type}での記載",
      "reason": "この違いが正常である理由"
    }}
  ],
  "complementary_info": [
    {{
      "topic": "トピック",
      "doc1_contribution": "{doc1_type}が提供する情報",
      "doc2_contribution": "{doc2_type}が提供する情報",
      "relationship": "相互補完の関係性"
    }}
  ],
  "consistency_score": 1～5,
  "consistency_reason": "スコアの根拠",
  "importance": "high/medium/low",
  "importance_reason": "重要度の理由",
  "summary": "2つの書類の関係性の要約"
}}

注意: contradictionsが空の場合、重要度はlowまたはmediumにしてください。
"""
    
    def _build_consistency_check_prompt_from_extracted_with_search(
        self,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> str:
        """
        整合性チェック用のプロンプトを生成（extracted_content使用、追加探索判断含む）
        """
        base_prompt = self._build_consistency_check_prompt_from_extracted(
            section_name,
            extracted_content1, extracted_content2,
            doc1_page_range, doc2_page_range,
            doc1_info, doc2_info
        )
        
        additional_section = """

【✨ 追加探索の判断】
このセクションの整合性分析結果を踏まえて、以下を判断してください：

A. **追加探索の必要性**
   以下のような状況の場合、追加探索を推奨してください：
   - 矛盾が検出され、その原因や背景を探る必要がある
   - 数値の不一致について他のセクションで確認が必要
   - 方針の矛盾について、別のセクションに補足説明がありそう
   - 整合性スコアが3以下で、追加情報が必要

B. **検索フレーズの生成**
   追加探索が必要な場合、以下の観点で検索フレーズを生成：
   - 矛盾の原因を説明している可能性のあるセクションのキーワード
   - 関連する数値データがある可能性のあるトピック
   - 補足説明や詳細が記載されていそうなテーマ
"""
        
        output_section = """
  "additional_search": {{
    "needed": true/false,
    "reason": "追加探索が必要/不要な理由（矛盾の解決、背景の理解など）",
    "search_phrases": [
      "検索フレーズ1（矛盾に関連するキーワード）",
      "検索フレーズ2（数値データの出典等）",
      "検索フレーズ3（補足説明のトピック）"
    ],
    "expected_findings": "これらのフレーズで何を見つけることを期待しているか"
  }}
"""
        
        # "summary"の行の後にadditional_searchを挿入
        search_str = '  "summary": "2つの書類の関係性の要約"\n}'
        replacement_str = '  "summary": "2つの書類の関係性の要約",' + output_section + '\n}'
        
        if search_str not in base_prompt:
            logger.warning("⚠️ replace対象文字列が見つかりません！")
            logger.warning(f"ベースプロンプトの最後200文字: {base_prompt[-200:]}")
        
        prompt = base_prompt.replace(search_str, replacement_str)
        
        # デバッグ: replace後に確認
        if 'additional_search' not in prompt:
            logger.error(f"❌ additional_searchがプロンプトに含まれませんでした！")
        else:
            logger.info(f"✅ additional_searchがプロンプトに正しく追加されました")
        
        prompt = prompt.replace(
            "6. **サマリー**",
            "6. **サマリー**" + additional_section
        )
        
        return prompt

    def _analyze_section_with_llm_including_search_decision(
        self,
        section_name: str,
        extracted_content1: dict,
        extracted_content2: dict,
        text1: Optional[str],
        text2: Optional[str],
        tables1: list[dict],
        tables2: list[dict],
        doc1_page_range: str,
        doc2_page_range: str,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
        comparison_mode: Optional[ComparisonMode] = None,
    ) -> dict[str, Any]:
        """
        LLMでセクションの詳細差分分析を実行（追加探索の判断を含む）
        
        Returns:
            分析結果の辞書（additional_searchフィールドを含む）
        """
        try:
            from .templates import load_template
            
            document_type = doc1_info.document_type or ""
            try:
                template = load_template(document_type)
                doc_type_label = template.get("display_name", document_type)
            except:
                doc_type_label = document_type
            
            logger.info(f"プロンプト生成開始（追加探索判断含む）: comparison_mode={comparison_mode}, section_name={section_name}")
            
            if extracted_content1 and extracted_content2:
                use_extracted = True
            else:
                use_extracted = False
                tables1_summary = self._summarize_tables(tables1)
                tables2_summary = self._summarize_tables(tables2)
            
            if comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY:
                if use_extracted:
                    prompt = self._build_company_comparison_prompt_from_extracted_with_search(
                        doc_type_label, section_name,
                        extracted_content1, extracted_content2,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
                else:
                    prompt = self._build_company_comparison_prompt_with_search(
                        doc_type_label, section_name,
                        text1, text2, tables1_summary, tables2_summary,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
            elif comparison_mode == ComparisonMode.CONSISTENCY_CHECK:
                if use_extracted:
                    prompt = self._build_consistency_check_prompt_from_extracted_with_search(
                        section_name,
                        extracted_content1, extracted_content2,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
                else:
                    prompt = self._build_consistency_check_prompt_with_search(
                        section_name,
                        text1, text2, tables1_summary, tables2_summary,
                        doc1_page_range, doc2_page_range,
                        doc1_info, doc2_info
                    )
            else:
                if use_extracted:
                    prompt = self._build_temporal_comparison_prompt_from_extracted_with_search(
                        doc_type_label, section_name,
                        extracted_content1, extracted_content2,
                        doc1_page_range, doc2_page_range
                    )
                else:
                    prompt = self._build_temporal_comparison_prompt_with_search(
                        doc_type_label, section_name,
                        text1, text2, tables1_summary, tables2_summary,
                        doc1_page_range, doc2_page_range
                    )
            
            if comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY:
                system_message = f"あなたは「{doc_type_label}」の分析エキスパートです。異なる企業間の開示内容の違いを正確に検出し、投資家や利害関係者にとっての重要度を判定してください。必要に応じて追加探索の必要性も判断してください。"
            elif comparison_mode == ComparisonMode.CONSISTENCY_CHECK:
                system_message = f"あなたは企業開示資料の整合性分析エキスパートです。異なる種類の開示資料における記載内容の整合性を評価してください。書類の性質による正常な違いと、矛盾・不整合を明確に区別してください。矛盾がある場合は追加探索の必要性も判断してください。"
            else:
                system_message = f"あなたは「{doc_type_label}」の分析エキスパートです。差異を正確に検出し、重要度を判定してください。必要に応じて追加探索の必要性も判断してください。"
            
            response = self.openai_client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            # レスポンスのコンテンツを取得
            content = response.choices[0].message.content
            if not content:
                logger.warning(f"LLMが空のレスポンスを返しました ({section_name})")
                return {
                    "text_changes": {},
                    "numerical_changes": [],
                    "tone_analysis": {},
                    "importance": "low",
                    "importance_reason": "LLMレスポンスが空",
                    "summary": "分析結果が取得できませんでした（空のレスポンス）",
                    "additional_search": {
                        "needed": False,
                        "reason": "LLMレスポンス不正",
                        "search_phrases": [],
                        "expected_findings": ""
                    }
                }
            
            result = json.loads(content)
            
            # LLMがnullを返した場合の対処
            if result is None:
                logger.warning(f"LLMがnullを返しました ({section_name})")
                return {
                    "text_changes": {},
                    "numerical_changes": [],
                    "tone_analysis": {},
                    "importance": "low",
                    "importance_reason": "LLMレスポンスがnull",
                    "summary": "分析結果が取得できませんでした",
                    "additional_search": {
                        "needed": False,
                        "reason": "LLMレスポンス不正",
                        "search_phrases": [],
                        "expected_findings": ""
                    }
                }
            
            return result
            
        except Exception as exc:
            logger.error(f"セクション詳細分析に失敗 ({section_name}): {exc}", exc_info=True)
            return {
                "text_changes": {},
                "numerical_changes": [],
                "tone_analysis": {},
                "importance": "low",
                "importance_reason": f"分析失敗: {type(exc).__name__}",
                "summary": f"分析に失敗しました: {str(exc)[:100]}",
                "additional_search": {
                    "needed": False,
                    "reason": "分析失敗のため追加探索をスキップ",
                    "search_phrases": [],
                    "expected_findings": ""
                }
            }
    
    def _search_related_sections_by_phrases(
        self,
        search_phrases: list[str],
        sections1: dict,
        sections2: dict,
        exclude_sections: set[str],
        top_k: int = 3,
    ) -> list[tuple[str, str, float]]:
        """
        検索フレーズを使ってコサイン類似度でセクションを検索
        """
        search_text = " ".join(search_phrases)
        
        try:
            search_embedding_response = self.openai_client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=[search_text],
            )
            search_vector = search_embedding_response.data[0].embedding
        except Exception as exc:
            logger.error(f"検索キーワードのEmbedding取得に失敗: {exc}")
            return []
        
        section_similarities = []
        
        for section_name, section_info in sections1.items():
            if section_name in exclude_sections:
                continue
            
            extracted_content = section_info.get("extracted_content", {})
            if not extracted_content:
                continue
            
            from .structuring.section_content_extractor import create_embedding_text
            section_text = create_embedding_text(section_name, extracted_content)
            
            try:
                section_embedding_response = self.openai_client.embeddings.create(
                    model=self.settings.openai_embedding_model,
                    input=[section_text],
                )
                section_vector = section_embedding_response.data[0].embedding
                similarity = self._cosine_similarity(search_vector, section_vector)
                
                # exclude_sectionsに含まれない場合は追加（sections2の存在チェックは不要）
                section_similarities.append((section_name, section_name, similarity))
                
            except Exception as exc:
                logger.warning(f"セクション {section_name} のEmbedding取得に失敗: {exc}")
                continue
        
        section_similarities.sort(key=lambda x: x[2], reverse=True)
        results = section_similarities[:top_k]
        
        logger.info(f"関連セクション検索結果（top {top_k}）: {results}")
        return results
    
    def _analyze_related_sections_with_context(
        self,
        base_section_name: str,
        current_context: dict,
        related_sections: list[tuple[str, str, float]],
        sections1: dict,
        sections2: dict,
        doc1_info: DocumentInfo,
        doc2_info: DocumentInfo,
    ) -> dict[str, Any]:
        """
        関連セクションを追加分析し、元の分析結果と統合
        """
        prompt = f"""
【ベースとなる分析】
セクション: {base_section_name}
分析結果:
{json.dumps(current_context.get("initial_analysis", {}), ensure_ascii=False, indent=2)[:2000]}

【関連セクションの情報】
以下の関連セクションから追加情報が見つかりました：
"""
        
        for section_name, _, similarity in related_sections:
            section1_info = sections1.get(section_name, {})
            section2_info = sections2.get(section_name, {})
            
            extracted1 = section1_info.get("extracted_content", {})
            extracted2 = section2_info.get("extracted_content", {})
            
            prompt += f"""

セクション名: {section_name} (類似度: {similarity:.3f})
ドキュメント1の内容: {json.dumps(extracted1, ensure_ascii=False)[:1500]}
ドキュメント2の内容: {json.dumps(extracted2, ensure_ascii=False)[:1500]}
"""
        
        prompt += """

【分析タスク】
これらの関連セクションの情報を踏まえて、以下を分析してください：

1. ベース分析で検出された矛盾や差分について、新たな説明や背景が見つかりましたか？
2. 追加の矛盾や重要な差分が見つかりましたか？
3. 全体的な理解が深まりましたか？

【出力形式】
JSON形式で以下のように回答してください：
{
  "new_findings": ["新たに分かったこと1", "新たに分かったこと2"],
  "resolved_contradictions": ["解決された矛盾の説明1", ...],
  "additional_contradictions": ["新たに見つかった矛盾1", ...],
  "enhanced_understanding": "全体的な理解の深まりの説明",
  "importance_update": "high/medium/low（重要度が変わった場合）"
}
"""
        
        response = self.openai_client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": "あなたは企業開示資料の総合的な分析エキスパートです。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    def _regenerate_search_phrases(
        self,
        base_section: str,
        current_context: dict,
        previous_searches: list[dict],
    ) -> list[str]:
        """
        前回の探索結果を踏まえて、新しい検索フレーズを生成
        """
        prompt = f"""
【ベースセクション】
{base_section}

【これまでの分析コンテキスト】
{json.dumps(current_context, ensure_ascii=False, indent=2)[:3000]}

【これまでの探索結果】
"""
        
        for search in previous_searches:
            prompt += f"""
第{search.get('iteration', 0)}回探索:
- 検索フレーズ: {search.get('search_keywords', [])}
- 発見されたセクション: {[s.get('doc1_section', '') for s in search.get('found_sections', [])]}
- 分析結果: {json.dumps(search.get('analysis', {}), ensure_ascii=False)[:1000]}
"""
        
        prompt += """

【タスク】
これまでの探索結果を踏まえて、さらに追加の探索が必要かどうかを判断し、
必要な場合は新しい検索フレーズを生成してください。

以下の場合は探索を終了してください（needed: false）：
- 十分な情報が集まった
- 矛盾が解決された
- これ以上の関連情報が見つかりそうにない

【出力形式】
JSON形式で以下のように回答してください：
{
  "needed": true/false,
  "reason": "追加探索が必要/不要な理由",
  "search_phrases": ["新しい検索フレーズ1", "新しい検索フレーズ2", ...],
  "what_to_find": "今回何を見つけようとしているか"
}
"""
        
        response = self.openai_client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": "あなたは企業開示資料の総合的な分析エキスパートです。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
        )
        
        result = json.loads(response.choices[0].message.content)
        
        if not result.get("needed", False):
            logger.info(f"追加探索不要と判断: {result.get('reason', '')}")
            return []
        
        phrases = result.get("search_phrases", [])
        logger.info(f"新しい検索フレーズ生成: {phrases}")
        logger.info(f"探索目的: {result.get('what_to_find', '')}")
        
        return phrases
    
    def _generate_enhanced_summary_with_context(
        self,
        base_summary: str,
        additional_searches: list[dict],
        initial_search_reason: str,
    ) -> str:
        """
        追加探索の結果を含めた統合サマリーを生成
        """
        if not additional_searches:
            return base_summary
        
        additional_info = []
        for search in additional_searches:
            analysis = search.get("analysis", {})
            new_findings = analysis.get("new_findings", [])
            if new_findings:
                additional_info.extend(new_findings[:2])
        
        if additional_info:
            enhanced = f"{base_summary}\n\n追加探索により、以下の情報が明らかになりました：{'; '.join(additional_info[:3])}"
        else:
            enhanced = f"{base_summary}\n\n追加探索を実施しましたが、新たな重要な発見はありませんでした。"
        
        return enhanced
