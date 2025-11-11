"""
セクション情報抽出サービス

各セクションから構造化情報（財務指標、会計コメント、事実、主張）を抽出する。
要約せず、原文の情報量を可能な限り保持する。
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SectionContentExtractor:
    """
    セクションから構造化情報を抽出するクラス
    
    各セクションから以下の情報を抽出：
    - 財務指標・数値情報
    - 会計処理上のコメント
    - 事実情報
    - 主張・メッセージ
    """
    
    def __init__(self, openai_client, settings=None, max_workers: int = 3):
        """
        Args:
            openai_client: OpenAIクライアント
            settings: 設定オブジェクト（モデル名を取得するため）
            max_workers: 並列実行する最大ワーカー数（デフォルト3）
        """
        from ...core.config import get_settings
        self.openai_client = openai_client
        self.settings = settings or get_settings()
        self.max_workers = max_workers
    
    def extract_all_sections(
        self,
        sections: dict[str, dict],
        pages: list[dict],
        tables: list[dict],
    ) -> dict[str, dict]:
        """
        全セクションの情報を並列抽出
        
        Args:
            sections: セクション情報の辞書（キー: セクション名）
            pages: ページデータのリスト
            tables: テーブルデータのリスト
            
        Returns:
            extracted_contentフィールドが追加されたセクション情報
        """
        if not self.openai_client:
            logger.warning("OpenAIクライアントが設定されていないため、情報抽出をスキップします")
            return sections
        
        if not sections:
            logger.warning("セクション情報が空のため、情報抽出をスキップします")
            return sections
        
        total_sections = len(sections)
        model = self.settings.section_extraction_model
        logger.info(
            f"セクション情報抽出開始: {total_sections}セクションを並列処理（最大{self.max_workers}並列、モデル: {model}）"
        )
        
        # 各セクションの処理準備
        section_items = []
        skipped_parent_count = 0
        exclusive_page_count = 0
        
        for section_name, section_info in sections.items():
            # 子セクションがあるかチェック
            has_children = self._has_child_sections(section_name, sections)
            
            if has_children:
                # 親固有のページを計算
                exclusive_pages = self._calculate_exclusive_pages(
                    section_name, section_info, sections
                )
                
                if len(exclusive_pages) == 0:
                    # 固有ページがない場合はスキップ
                    logger.info(
                        f"セクション {section_name} は子セクションで完全にカバーされているため抽出をスキップ"
                    )
                    skipped_parent_count += 1
                    continue
                else:
                    # 固有ページのみでテキストを抽出
                    section_info = section_info.copy()
                    section_info["pages"] = exclusive_pages
                    logger.info(
                        f"セクション {section_name} は固有の{len(exclusive_pages)}ページのみ抽出"
                    )
                    exclusive_page_count += 1
            
            # セクションのテキストとテーブルを抽出
            section_text = self._extract_section_text(section_info, pages)
            section_tables = self._extract_section_tables(section_info, tables)
            
            section_items.append({
                'section_name': section_name,
                'section_info': section_info,
                'section_text': section_text,
                'section_tables': section_tables,
            })
        
        if skipped_parent_count > 0:
            logger.info(
                f"親セクション抽出スキップ: {skipped_parent_count}個のセクションが子セクションで完全にカバーされています"
            )
        if exclusive_page_count > 0:
            logger.info(
                f"固有ページ抽出: {exclusive_page_count}個の親セクションが固有ページのみ抽出されました"
            )
        
        # 並列処理
        processed_count = 0
        skipped_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # すべてのセクションをサブミット
            future_to_section = {
                executor.submit(
                    self._extract_section_content,
                    item['section_name'],
                    item['section_text'],
                    item['section_tables'],
                ): item
                for item in section_items
            }
            
            # 完了したセクションを収集
            for future in as_completed(future_to_section):
                item = future_to_section[future]
                section_name = item['section_name']
                
                try:
                    extracted_content = future.result()
                    if extracted_content:
                        # extracted_contentをセクション情報に追加
                        sections[section_name]['extracted_content'] = extracted_content
                        processed_count += 1
                        logger.info(
                            f"セクション情報抽出完了 [{processed_count}/{total_sections}]: {section_name}"
                        )
                    else:
                        skipped_count += 1
                        logger.warning(f"セクション情報抽出スキップ: {section_name}")
                        
                except Exception as exc:
                    logger.error(
                        f"セクション情報抽出に失敗 ({section_name}): {exc}",
                        exc_info=True
                    )
                    skipped_count += 1
        
        logger.info(
            f"セクション情報抽出完了: 成功={processed_count}件, スキップ={skipped_count}件"
        )
        return sections
    
    def _has_child_sections(self, section_name: str, all_sections: dict) -> bool:
        """
        子セクションの存在チェック
        
        Args:
            section_name: 対象セクション名
            all_sections: 全セクションの辞書
            
        Returns:
            True: 子セクションあり、False: なし（リーフノード）
        """
        prefix = f"{section_name} - "
        return any(name.startswith(prefix) for name in all_sections.keys())
    
    def _calculate_exclusive_pages(
        self, section_name: str, section_info: dict, all_sections: dict
    ) -> list[int]:
        """
        セクション固有のページ（子セクションに含まれないページ）を計算
        
        Args:
            section_name: 対象セクション名
            section_info: 対象セクションの情報
            all_sections: 全セクションの辞書
            
        Returns:
            固有ページのリスト（ソート済み）
        """
        parent_pages = set(section_info.get("pages", []))
        
        # 子セクションのページを収集
        prefix = f"{section_name} - "
        child_pages = set()
        for name, info in all_sections.items():
            if name.startswith(prefix):
                child_pages.update(info.get("pages", []))
        
        # 親固有のページ = 親のページ - 子のページ
        exclusive_pages = sorted(parent_pages - child_pages)
        
        return exclusive_pages
    
    def _extract_section_text(
        self,
        section_info: dict,
        all_pages: list[dict],
    ) -> str:
        """
        セクション情報から該当ページのテキストを抽出
        
        Args:
            section_info: セクション情報（pages含む）
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
            section_info: セクション情報（pages含む）
            all_tables: 全テーブルデータ
            
        Returns:
            セクションのテーブルデータリスト
        """
        pages = section_info.get("pages", [])
        section_tables = []
        
        for table in all_tables:
            table_page = table.get("page_number", table.get("page", 0))
            if table_page in pages:
                section_tables.append(table)
        
        return section_tables
    
    def _extract_section_content(
        self,
        section_name: str,
        section_text: str,
        section_tables: list[dict],
    ) -> Optional[dict]:
        """
        単一セクションの情報抽出（リトライ処理付き）
        
        Args:
            section_name: セクション名
            section_text: セクションのテキスト
            section_tables: セクションのテーブルデータ
            
        Returns:
            抽出された情報、またはスキップ時はNone
        """
        # テキストが短すぎる場合はスキップ
        if len(section_text.strip()) < 100:
            logger.debug(f"セクション {section_name} はテキストが短いためスキップ")
            return None
        
        # テーブルサマリーを作成
        tables_summary = self._summarize_tables(section_tables)
        
        # プロンプトを構築
        prompt = self._build_extraction_prompt(
            section_name,
            section_text,
            tables_summary,
        )
        
        # 設定からリトライ設定を取得
        section_config = self.settings.get_section_extraction_config()
        max_retries = section_config.get("max_retries", 1)
        retry_delay = section_config.get("retry_delay", 1.0)
        
        # 最初は通常のモデル、リトライ時はフォールバックモデルを使用
        primary_model = self.settings.section_extraction_model
        retry_model = self.settings.retry_model
        
        for attempt in range(max_retries + 1):
            try:
                # リトライ時はフォールバックモデルを使用
                model = retry_model if attempt > 0 else primary_model
                
                if attempt > 0:
                    logger.warning(
                        f"セクション情報抽出リトライ ({section_name}): "
                        f"試行 {attempt + 1}/{max_retries + 1}, モデル: {model}"
                    )
                    time.sleep(retry_delay)
                
                # LLM呼び出し
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "あなたは企業開示資料から情報を抽出するエキスパートです。要約せず、原文の情報を可能な限り保持してください。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                )
                
                result = json.loads(response.choices[0].message.content)
                
                # 結果を検証
                extracted_content = {
                    "financial_data": result.get("financial_data", []),
                    "accounting_notes": result.get("accounting_notes", []),
                    "factual_info": result.get("factual_info", []),
                    "messages": result.get("messages", []),
                    "kpi_time_series": result.get("kpi_time_series", []),
                    "logical_relationships": result.get("logical_relationships", []),
                    "segment_time_series": result.get("segment_time_series", []),
                }
                
                if attempt > 0:
                    logger.info(f"セクション情報抽出リトライ成功 ({section_name}): モデル {model} で処理完了")
                
                return extracted_content
                
            except Exception as exc:
                if attempt < max_retries:
                    logger.warning(
                        f"セクション情報抽出でエラー ({section_name}): {exc}, "
                        f"リトライします（残り {max_retries - attempt} 回）"
                    )
                    continue
                else:
                    logger.error(
                        f"セクション情報抽出でエラー ({section_name}): {exc}, "
                        f"最大リトライ回数に達しました",
                        exc_info=True
                    )
                    return None
        
        return None
    
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
        for i, table in enumerate(tables[:10]):  # 最大10個のテーブル
            data = table.get("data", [])
            row_count = len(data)
            col_count = len(data[0]) if data else 0
            
            # 最初の数行を抽出
            preview_rows = data[:5]
            preview = "\n".join([" | ".join(str(cell) for cell in row) for row in preview_rows])
            
            page_display = table.get("page_number", table.get("page", "?"))
            summaries.append(
                f"テーブル{i+1} (ページ{page_display}): "
                f"{row_count}行 x {col_count}列\n{preview}"
            )
            
            if row_count > 5:
                summaries.append(f"  ... 他 {row_count - 5} 行")
        
        if len(tables) > 10:
            summaries.append(f"\n... 他 {len(tables) - 10} 個のテーブル")
        
        return "\n\n".join(summaries)
    
    def _build_extraction_prompt(
        self,
        section_name: str,
        section_text: str,
        tables_summary: str,
    ) -> str:
        """
        情報抽出用のプロンプトを構築
        
        Args:
            section_name: セクション名
            section_text: セクションのテキスト
            tables_summary: テーブルのサマリー
            
        Returns:
            プロンプト文字列
        """
        # テキストを最大10000文字に制限（大規模セクション対応）
        text_preview = section_text[:10000]
        if len(section_text) > 10000:
            text_preview += "\n\n... （以下略）"
        
        prompt = f"""
以下は企業開示資料の「{section_name}」セクションです。
このセクションから構造化情報を抽出してください。

【重要な指示】
- 要約せず、原文の表現をできるだけそのまま保持してください
- 数値は必ず単位と期間を含めて抽出してください
- 長い文章でも省略せず、重要な情報は全て含めてください

【セクションテキスト】
{text_preview}

【テーブルデータ】
{tables_summary}

【抽出タスク】
以下の7種類の情報を抽出してください：

1. **財務指標・数値情報** (financial_data) - 既存
   - 売上高、利益、資産、負債、キャッシュフローなどの財務数値
   - 各数値には、項目名(item)、数値(value)、単位(unit)、期間(period)、文脈(context)を含める
   - 前年比、増減率、予測値なども文脈に含める
   - 例: {{"item": "売上高", "value": 1234567, "unit": "百万円", "period": "2024年3月期", "context": "前年同期比10%増加"}}

2. **会計処理上のコメント** (accounting_notes) - 既存
   - 会計方針、会計基準の変更、注記、重要な会計上の見積もりなど
   - トピック(topic)、内容(content)、種類(type)を含める
   - 原文の表現をできるだけそのまま記載
   - 例: {{"topic": "収益認識", "content": "当社は、IFRS第15号...", "type": "会計方針"}}

3. **事実情報** (factual_info) - 既存
   - 会社基本情報（本社所在地、設立日、資本金、従業員数など）
   - 組織情報（役員、部門、子会社など）
   - 事業内容、製品・サービス、市場
   - 日付、期間、固有名詞
   - カテゴリ(category)、項目(item)、値(value)を含める
   - 例: {{"category": "会社基本情報", "item": "本社所在地", "value": "東京都千代田区..."}}

4. **主張・メッセージ** (messages) - 既存
   - 経営方針、戦略、ビジョン、目標
   - リスク認識とその対応策
   - 市場認識、機会、課題
   - ステークホルダーへのメッセージ
   - 種類(type)、内容(content)、トーン(tone: positive/neutral/negative)を含める
   - 原文の表現をできるだけそのまま記載（要約禁止）
   - 例: {{"type": "戦略", "content": "当社は、デジタルトランスフォーメーション...", "tone": "positive"}}

5. **時系列財務データ** (kpi_time_series) - 新規
   - 複数年度（通常5年分）の財務指標の推移を**原文に記載されているまま**抽出
   - 各指標には、指標名(indicator)、単位(unit)、時系列データ(time_series)を含める
   - **重要**: CAGR、トレンド、目標値は**原文に明記されている場合のみ**抽出（自動計算禁止）
   - 原文のコメントや注記もそのまま記載
   - time_seriesには各期間のperiod、value、noteを含める
   - stated_metricsには原文に記載されているCAGR、トレンド、コメントのみを含める（自動計算禁止）
   - target_statedには原文に記載されている目標値のみを含める（自動計算禁止）
   - 例: {{"indicator": "売上高", "unit": "百万円", "time_series": [{{"period": "2020年3月期", "value": 1000000, "note": null}}, {{"period": "2021年3月期", "value": 1050000, "note": null}}], "stated_metrics": {{"cagr_stated": "年平均成長率7.2%（原文に記載がある場合のみ）", "trend_stated": "増加傾向（原文に記載がある場合のみ）", "comment": "原文のコメントをそのまま記載"}}, "target_stated": {{"target_description": "2025年度に1,400億円を目指す（原文の表現をそのまま）", "target_value": 1400000, "target_period": "2025年3月期"}}}}

6. **論理関係** (logical_relationships) - 新規
   - 因果関係（causality）: 結果とその原因（**原文に明記されている因果関係のみ**）
   - 条件-結果（condition_consequence）: 前提条件と結果（**原文に明記されている条件のみ**）
   - 問題-解決（problem_solution）: 問題とその対応策（**原文に明記されている対応策のみ**）
   - 前提-結論（premise_conclusion）: 前提と結論（**原文に明記されている論理のみ**）
   - **重要**: 推測や解釈は行わず、原文の表現をそのまま抽出
   - 必ず原文の該当箇所を引用（original_text）し、source_sectionを記載
   - relationship_typeに応じて適切なフィールドを含める（subject/reason、condition/consequence、problem/solution、premise/conclusion等）
   - confidenceはhigh/medium/lowで評価（original_textとevidenceの有無に基づく）
   - 例（因果関係）: {{"relationship_type": "causality", "subject": "売上高の増加", "subject_category": "financial_result", "reason": "新製品の販売好調および海外市場での拡販", "reason_category": "business_driver", "evidence": "新製品Aの売上高が前年比150%、北米市場での売上が同120%", "original_text": "売上高が前年比10%増加したのは、新製品Aの販売が好調だったことと、海外市場での拡販が進んだことが主な要因です。", "confidence": "high", "source_section": "事業の状況 - 経営成績の分析"}}
   - 例（条件-結果）: {{"relationship_type": "condition_consequence", "condition": "為替相場が1ドル=140円を超える円安で推移", "condition_category": "external_factor", "consequence": "営業利益が約30億円増加する見込み", "consequence_category": "financial_impact", "original_text": "為替相場が1ドル=140円を超える円安で推移した場合、営業利益が約30億円増加する見込みです。", "confidence": "medium", "source_section": "事業の状況 - 経営成績の分析"}}
   - 例（問題-解決）: {{"relationship_type": "problem_solution", "problem": "サイバーセキュリティリスクの高まり", "problem_category": "risk", "solution": "CSIRT体制の構築と多層防御の実施", "solution_category": "mitigation_measure", "effectiveness": "リスクレベルを中程度に低減（原文に記載がある場合のみ）", "original_text": "サイバーセキュリティリスクに対応するため、当社はCSIRT体制を構築し、多層防御を実施しています。", "source_section": "事業の状況 - 事業等のリスク"}}
   - 例（前提-結論）: {{"relationship_type": "premise_conclusion", "premise": "中長期的な企業価値向上を目指す", "premise_category": "management_policy", "conclusion": "ROE 10%以上を目標とする", "conclusion_category": "target_indicator", "reasoning": "株主資本の効率的活用と持続的成長の両立", "original_text": "中長期的な企業価値向上を目指し、株主資本の効率的活用と持続的成長の両立を図るため、ROE 10%以上を目標としています。", "source_section": "事業の状況 - 経営方針"}}

7. **セグメント別時系列データ** (segment_time_series) - 新規
   - セグメントごとの財務指標の推移（通常5年分）を**原文に記載されているまま**抽出
   - セグメント名(segment_name)、指標の時系列(time_series)を含める
   - **重要**: 構成比、成長率等は**原文に記載がある場合のみ**抽出（自動計算禁止）
   - revenue_time_series、profit_time_series等、原文に記載されている指標ごとに時系列データを含める
   - stated_metricsには原文に記載されている構成比、成長率、コメントのみを含める（自動計算禁止）
   - 例: {{"segment_name": "医薬品事業", "revenue_time_series": [{{"period": "2020年3月期", "value": 400000}}, {{"period": "2021年3月期", "value": 420000}}], "profit_time_series": [{{"period": "2020年3月期", "value": 60000}}, {{"period": "2021年3月期", "value": 65000}}], "stated_metrics": {{"revenue_composition_stated": "売上構成比37.9%（原文に記載がある場合のみ）", "growth_rate_stated": "前年比4.2%増（原文に記載がある場合のみ）", "comment": "原文のコメントをそのまま記載"}}}}

【出力形式】
JSON形式で以下のように回答してください：
{{
  "financial_data": [
    {{
      "item": "項目名",
      "value": 数値,
      "unit": "単位",
      "period": "期間",
      "context": "文脈・補足情報"
    }}
  ],
  "accounting_notes": [
    {{
      "topic": "トピック",
      "content": "原文の内容をそのまま",
      "type": "会計方針/変更点/注記/見積もり"
    }}
  ],
  "factual_info": [
    {{
      "category": "カテゴリ",
      "item": "項目名",
      "value": "値"
    }}
  ],
  "messages": [
    {{
      "type": "戦略/方針/リスク/目標/市場認識",
      "content": "原文の内容をそのまま",
      "tone": "positive/neutral/negative"
    }}
  ],
  "kpi_time_series": [
    {{
      "indicator": "指標名",
      "unit": "単位",
      "time_series": [
        {{"period": "期間", "value": 数値, "note": "注記（任意）"}}
      ],
      "stated_metrics": {{
        "cagr_stated": "原文に記載がある場合のみ（自動計算禁止）",
        "trend_stated": "原文に記載がある場合のみ（自動計算禁止）",
        "comment": "原文のコメントをそのまま"
      }},
      "target_stated": {{
        "target_description": "原文の表現をそのまま",
        "target_value": 数値,
        "target_period": "期間"
      }}
    }}
  ],
  "logical_relationships": [
    {{
      "relationship_type": "causality/condition_consequence/problem_solution/premise_conclusion",
      "original_text": "原文の該当箇所をそのまま引用（必須）",
      "source_section": "セクション名",
      "confidence": "high/medium/low",
      ...（relationship_typeに応じたフィールド）
    }}
  ],
  "segment_time_series": [
    {{
      "segment_name": "セグメント名",
      "revenue_time_series": [
        {{"period": "期間", "value": 数値}}
      ],
      "profit_time_series": [
        {{"period": "期間", "value": 数値}}
      ],
      "stated_metrics": {{
        "revenue_composition_stated": "原文に記載がある場合のみ（自動計算禁止）",
        "growth_rate_stated": "原文に記載がある場合のみ（自動計算禁止）",
        "comment": "原文のコメントをそのまま"
      }}
    }}
  ]
}}

【抽出の基本原則】★最重要★
- **要約禁止**: 原文の表現をできるだけそのまま保持してください
- **推測禁止**: 記載されていない情報を推測しないでください
- **計算禁止**: 成長率、構成比、達成率等の自動計算は行わないでください
- **引用重視**: 論理関係は必ず原文の該当箇所を引用（original_text）してください
- **記載のみ**: 原文に記載されている情報のみを抽出してください

【注意事項】
- 該当する情報がない場合は、空の配列 [] を返してください
- 要約せず、原文の表現を可能な限り保持してください
- 数値情報は必ず単位と期間を明記してください
- 長い文章でも省略せず、重要な情報は全て含めてください
- kpi_time_series、logical_relationships、segment_time_seriesが存在しない場合は空配列を返してください
"""
        return prompt


def create_embedding_text(section_name: str, extracted_content: dict) -> str:
    """
    ベクトル化用のテキストを作成
    
    セクション名と抽出された情報を組み合わせて、
    意味的マッピング用のテキストを生成する。
    
    Args:
        section_name: セクション名
        extracted_content: 抽出された情報
        
    Returns:
        ベクトル化用のテキスト
    """
    parts = [f"セクション名: {section_name}"]
    
    # 財務データのサマリー
    financial_data = extracted_content.get("financial_data", [])
    if financial_data:
        financial_items = [item.get("item", "") for item in financial_data[:10]]
        parts.append(f"財務指標: {', '.join(financial_items)}")
    
    # 会計コメントのトピック
    accounting_notes = extracted_content.get("accounting_notes", [])
    if accounting_notes:
        topics = [note.get("topic", "") for note in accounting_notes[:5]]
        parts.append(f"会計トピック: {', '.join(topics)}")
    
    # 事実情報のカテゴリとアイテム
    factual_info = extracted_content.get("factual_info", [])
    if factual_info:
        facts = [
            f"{item.get('category', '')}: {item.get('item', '')}"
            for item in factual_info[:10]
        ]
        parts.append(f"事実情報: {', '.join(facts)}")
    
    # メッセージの種類
    messages = extracted_content.get("messages", [])
    if messages:
        message_types = [msg.get("type", "") for msg in messages[:10]]
        # メッセージの内容の冒頭部分も含める
        message_previews = [
            msg.get("content", "")[:100] for msg in messages[:3]
        ]
        parts.append(f"メッセージ種類: {', '.join(message_types)}")
        if message_previews:
            parts.append(f"メッセージ内容: {' | '.join(message_previews)}")
    
    return "\n".join(parts)

