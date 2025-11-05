"""
セクション情報抽出サービス

各セクションから構造化情報（財務指標、会計コメント、事実、主張）を抽出する。
要約せず、原文の情報量を可能な限り保持する。
"""

from __future__ import annotations

import json
import logging
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
    
    def __init__(self, openai_client, max_workers: int = 3):
        """
        Args:
            openai_client: OpenAIクライアント
            max_workers: 並列実行する最大ワーカー数（デフォルト3）
        """
        self.openai_client = openai_client
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
        logger.info(f"セクション情報抽出開始: {total_sections}セクションを並列処理（最大{self.max_workers}並列）")
        
        # 各セクションの処理準備
        section_items = []
        for section_name, section_info in sections.items():
            # セクションのテキストとテーブルを抽出
            section_text = self._extract_section_text(section_info, pages)
            section_tables = self._extract_section_tables(section_info, tables)
            
            section_items.append({
                'section_name': section_name,
                'section_info': section_info,
                'section_text': section_text,
                'section_tables': section_tables,
            })
        
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
        単一セクションの情報抽出
        
        Args:
            section_name: セクション名
            section_text: セクションのテキスト
            section_tables: セクションのテーブルデータ
            
        Returns:
            抽出された情報、またはスキップ時はNone
        """
        try:
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
            
            # LLM呼び出し
            response = self.openai_client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは企業開示資料から情報を抽出するエキスパートです。要約せず、原文の情報を可能な限り保持してください。"
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # 一貫性を重視
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # 結果を検証
            extracted_content = {
                "financial_data": result.get("financial_data", []),
                "accounting_notes": result.get("accounting_notes", []),
                "factual_info": result.get("factual_info", []),
                "messages": result.get("messages", []),
            }
            
            return extracted_content
            
        except Exception as exc:
            logger.error(f"情報抽出処理でエラー ({section_name}): {exc}", exc_info=True)
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
            
            summaries.append(
                f"テーブル{i+1} (ページ{table.get('page', '?')}): "
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
以下の4種類の情報を抽出してください：

1. **財務指標・数値情報** (financial_data)
   - 売上高、利益、資産、負債、キャッシュフローなどの財務数値
   - 各数値には、項目名(item)、数値(value)、単位(unit)、期間(period)、文脈(context)を含める
   - 前年比、増減率、予測値なども文脈に含める
   - 例: {{"item": "売上高", "value": 1234567, "unit": "百万円", "period": "2024年3月期", "context": "前年同期比10%増加"}}

2. **会計処理上のコメント** (accounting_notes)
   - 会計方針、会計基準の変更、注記、重要な会計上の見積もりなど
   - トピック(topic)、内容(content)、種類(type)を含める
   - 原文の表現をできるだけそのまま記載
   - 例: {{"topic": "収益認識", "content": "当社は、IFRS第15号...", "type": "会計方針"}}

3. **事実情報** (factual_info)
   - 会社基本情報（本社所在地、設立日、資本金、従業員数など）
   - 組織情報（役員、部門、子会社など）
   - 事業内容、製品・サービス、市場
   - 日付、期間、固有名詞
   - カテゴリ(category)、項目(item)、値(value)を含める
   - 例: {{"category": "会社基本情報", "item": "本社所在地", "value": "東京都千代田区..."}}

4. **主張・メッセージ** (messages)
   - 経営方針、戦略、ビジョン、目標
   - リスク認識とその対応策
   - 市場認識、機会、課題
   - ステークホルダーへのメッセージ
   - 種類(type)、内容(content)、トーン(tone: positive/neutral/negative)を含める
   - 原文の表現をできるだけそのまま記載（要約禁止）
   - 例: {{"type": "戦略", "content": "当社は、デジタルトランスフォーメーション...", "tone": "positive"}}

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
  ]
}}

【注意事項】
- 該当する情報がない場合は、空の配列 [] を返してください
- 要約せず、原文の表現を可能な限り保持してください
- 数値情報は必ず単位と期間を明記してください
- 長い文章でも省略せず、重要な情報は全て含めてください
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

