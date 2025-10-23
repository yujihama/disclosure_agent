"""
比較エンジン

ドキュメント間の比較処理を行うサービス。
整合性チェック、差分分析、多資料比較をサポート。
"""

from __future__ import annotations

import difflib
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
        if self.settings.openai_api_key:
            from openai import OpenAI
            self.openai_client = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.openai_timeout_seconds,
            )
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
1. 会社名を抽出してください（正式名称）
2. 対象年度（西暦）を抽出してください

【テキスト】
{text_sample[:3000]}

【出力形式】
JSON形式で以下のフォーマットで回答してください：
{{
  "company_name": "株式会社〇〇",
  "fiscal_year": 2024,
  "confidence": 0.95
}}

会社名または年度が見つからない場合は、該当フィールドをnullにしてください。
confidenceは抽出の信頼度を0.0～1.0で示してください。
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
        
        # 会社名の一致確認
        same_company = (
            doc1.company_name 
            and doc2.company_name 
            and doc1.company_name == doc2.company_name
        )
        
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
            doc1_info, doc2_info, structured1, structured2, result.section_mappings, progress_callback, mode
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
        異なる書類種別のセクションを意味的にマッピング（LLM使用）
        
        Args:
            doc1_info: ドキュメント1の情報
            doc2_info: ドキュメント2の情報
            structured1: ドキュメント1の構造化データ
            structured2: ドキュメント2の構造化データ
            
        Returns:
            セクションマッピングのリスト
        """
        from .templates import load_template
        
        mappings: list[SectionMapping] = []
        
        if not self.openai_client:
            logger.warning("OpenAI APIキーが設定されていないため、意味的マッピングをスキップします")
            return mappings
        
        # 両方のテンプレートを読み込み
        try:
            template1 = load_template(doc1_info.document_type) if doc1_info.document_type else None
            template2 = load_template(doc2_info.document_type) if doc2_info.document_type else None
        except FileNotFoundError as exc:
            logger.warning(f"テンプレート読み込みに失敗: {exc}")
            return mappings
        
        if not template1 or not template2:
            logger.warning("テンプレートが不足しているため、意味的マッピングをスキップします")
            return mappings
        
        # セクション名を抽出
        sections1 = self._extract_section_names(template1)
        sections2 = self._extract_section_names(template2)
        
        # LLMでマッピングを生成
        try:
            import json
            
            prompt = f"""
以下は2つの異なる種類の開示資料のセクション一覧です。
意味的に対応するセクションをマッピングしてください。

【資料1: {doc1_info.document_type_label}】
{json.dumps(sections1, ensure_ascii=False, indent=2)}

【資料2: {doc2_info.document_type_label}】
{json.dumps(sections2, ensure_ascii=False, indent=2)}

【出力形式】
JSON配列で以下のフォーマットで回答してください：
[
  {{
    "doc1_section": "事業等のリスク",
    "doc2_section": "リスク情報",
    "confidence": 0.95,
    "reason": "両方とも企業が直面するリスクについて記述している"
  }},
  ...
]

対応するセクションがない場合は、そのセクションはスキップしてください。
confidenceは0.0～1.0で、マッピングの信頼度を示してください。
"""
            
            logger.info("LLMでセクションマッピングを開始")
            
            response = self.openai_client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": "あなたは企業開示資料の構造分析エキスパートです。"},
                    {"role": "user", "content": prompt},
                ],
                
                response_format={"type": "json_object"},
            )
            
            # レスポンスをパース
            result = json.loads(response.choices[0].message.content)
            mapping_list = result.get("mappings", [])
            
            for item in mapping_list:
                mapping = SectionMapping(
                    doc1_section=item["doc1_section"],
                    doc2_section=item["doc2_section"],
                    confidence_score=item.get("confidence", 0.5),
                    mapping_method="semantic",
                )
                mappings.append(mapping)
            
            logger.info(f"意味的マッピング完了: {len(mappings)}個のセクション")
            
        except Exception as exc:
            logger.error(f"意味的マッピングに失敗: {exc}", exc_info=True)
        
        return mappings
    
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
            # すべてのセクションをサブミット
            future_to_mapping = {
                executor.submit(
                    self._analyze_single_section,
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
                ): mapping
                for mapping in section_mappings
            }
            
            # 完了したセクションを収集
            section_results = {}
            for future in as_completed(future_to_mapping):
                mapping = future_to_mapping[future]
                
                try:
                    result = future.result()
                    if result is not None:
                        section_results[mapping.doc1_section] = result
                        processed_count += 1
                        logger.info(f"セクション分析完了 [{processed_count}/{total_sections}]: {mapping.doc1_section}")
                        
                        # 進捗コールバックを呼び出し
                        if progress_callback:
                            progress_callback(
                                current_section=mapping.doc1_section,
                                completed_sections=processed_count,
                                total_sections=total_sections
                            )
                    else:
                        skipped_count += 1
                        logger.warning(f"セクション分析スキップ: {mapping.doc1_section}")
                        
                except Exception as exc:
                    logger.error(f"セクション詳細分析に失敗 ({mapping.doc1_section}): {exc}", exc_info=True)
                    skipped_count += 1
        
        # 元の順番でソート（section_mappingsの順序を維持）
        for mapping in section_mappings:
            if mapping.doc1_section in section_results:
                detailed_comparisons.append(section_results[mapping.doc1_section])
        
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
    ) -> Optional[SectionDetailedComparison]:
        """
        単一セクションの分析（並列実行用）
        
        Returns:
            分析結果、またはスキップ時はNone
        """
        try:
            section1_info = sections1.get(mapping.doc1_section, {})
            section2_info = sections2.get(mapping.doc2_section, {})
            
            if not section1_info or not section2_info:
                logger.warning(f"セクション情報が見つかりません（スキップ）: {mapping.doc1_section}")
                return None
            
            # セクション範囲のテキストとテーブルを抽出
            section1_text = self._extract_section_text(section1_info, all_pages1)
            section2_text = self._extract_section_text(section2_info, all_pages2)
            
            section1_tables = self._extract_section_tables(section1_info, all_tables1)
            section2_tables = self._extract_section_tables(section2_info, all_tables2)
            
            # LLMで詳細分析
            detailed = self._analyze_section_with_llm(
                section_name=mapping.doc1_section,
                text1=section1_text,
                text2=section2_text,
                tables1=section1_tables,
                tables2=section2_tables,
                doc1_page_range=f"{section1_info.get('start_page', '?')}-{section1_info.get('end_page', '?')}",
                doc2_page_range=f"{section2_info.get('start_page', '?')}-{section2_info.get('end_page', '?')}",
                document_type=doc1_info.document_type or "",
                doc1_info=doc1_info,
                doc2_info=doc2_info,
                comparison_mode=comparison_mode,
            )
            
            return detailed
            
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
    
    def _analyze_section_with_llm(
        self,
        section_name: str,
        text1: str,
        text2: str,
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
            text1: ドキュメント1のセクションテキスト
            text2: ドキュメント2のセクションテキスト
            tables1: ドキュメント1のセクションテーブル
            tables2: ドキュメント2のセクションテーブル
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
            
            # テーブルサマリーを作成
            tables1_summary = self._summarize_tables(tables1)
            tables2_summary = self._summarize_tables(tables2)
            
            # 比較モードに応じてプロンプトを切り替え
            logger.info(f"プロンプト生成開始: comparison_mode={comparison_mode}, section_name={section_name}")
            logger.info(f"ComparisonMode.DIFF_ANALYSIS_COMPANY={ComparisonMode.DIFF_ANALYSIS_COMPANY}")
            logger.info(f"comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY: {comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY}")
            if comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY:
                # 会社間比較のプロンプト
                logger.info("会社間比較プロンプトを生成します")
                prompt = self._build_company_comparison_prompt(
                    doc_type_label, section_name,
                    text1, text2, tables1_summary, tables2_summary,
                    doc1_page_range, doc2_page_range,
                    doc1_info, doc2_info
                )
            else:
                # 年度間比較・整合性チェックのプロンプト（既存）
                logger.info("年度間比較プロンプトを生成します")
                prompt = self._build_temporal_comparison_prompt(
                    doc_type_label, section_name,
                    text1, text2, tables1_summary, tables2_summary,
                    doc1_page_range, doc2_page_range
                )
            
            logger.info(f"セクション詳細分析開始: {section_name} (モード: {comparison_mode})")
            
            # 比較モードに応じてシステムメッセージを調整
            if comparison_mode == ComparisonMode.DIFF_ANALYSIS_COMPANY:
                system_message = f"あなたは「{doc_type_label}」の分析エキスパートです。異なる企業間の開示内容の違いを正確に検出し、投資家や利害関係者にとっての重要度を判定してください。"
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
            
            # 結果を構造化
            detailed = SectionDetailedComparison(
                section_name=section_name,
                doc1_page_range=doc1_page_range,
                doc2_page_range=doc2_page_range,
                text_changes=result.get("text_changes", {}),
                numerical_changes=result.get("numerical_changes", []),
                tone_analysis=result.get("tone_analysis", {}),
                importance=result.get("importance", "medium"),
                importance_reason=result.get("importance_reason", ""),
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

