"""
セクション検出サービス

LLMを使用してドキュメントのセクション構造を検出し、
各セクションのページ範囲を特定する。
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SectionDetector:
    """
    書類種別に応じたセクション検出を行うクラス
    
    10ページごとのバッチ処理で、前回の検出結果を引き継ぎながら
    ページ跨ぎのセクションにも対応する。
    """
    
    def __init__(
        self, 
        openai_client, 
        document_type: str, 
        batch_size: int = 10,
        max_workers: int = 5
    ):
        """
        Args:
            openai_client: OpenAIクライアント
            document_type: 書類種別（例: "securities_report"）
            batch_size: 1回に処理するページ数（デフォルト10）
            max_workers: 並列実行する最大ワーカー数（デフォルト5）
        """
        self.openai_client = openai_client
        self.document_type = document_type
        self.batch_size = batch_size
        self.max_workers = max_workers
        
        # テンプレートを読み込み
        from ..templates import load_template
        try:
            self.template = load_template(document_type)
        except FileNotFoundError:
            logger.warning(f"テンプレートが見つかりません: {document_type}")
            self.template = {}
    
    def detect_sections(self, pages: list[dict]) -> dict[str, dict]:
        """
        全ページを処理してセクションを検出（並列処理対応）
        
        Args:
            pages: ページデータのリスト（各要素は page_number, text などを含む辞書）
            
        Returns:
            セクション名をキーとする辞書
            {
                "表紙": {
                    "start_page": 1,
                    "end_page": 1,
                    "pages": [1],
                    "confidence": 1.0,
                    "char_count": 1500
                },
                ...
            }
        """
        if not self.openai_client:
            logger.warning("OpenAIクライアントが設定されていないため、セクション検出をスキップします")
            return {}
        
        if not pages:
            logger.warning("ページデータが空のため、セクション検出をスキップします")
            return {}
        
        all_sections = {}
        
        logger.info(f"セクション検出開始: {len(pages)}ページを{self.batch_size}ページずつ並列処理")
        
        # バッチ情報を準備
        batch_info_list = []
        for i in range(0, len(pages), self.batch_size):
            batch = pages[i:i + self.batch_size]
            batch_start = i + 1
            batch_end = min(i + self.batch_size, len(pages))
            batch_info_list.append({
                'batch': batch,
                'batch_start': batch_start,
                'batch_end': batch_end,
                'batch_index': i // self.batch_size
            })
        
        # バッチを並列処理
        batch_results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # すべてのバッチをサブミット
            future_to_batch = {
                executor.submit(
                    self._detect_batch_wrapper,
                    batch_info
                ): batch_info
                for batch_info in batch_info_list
            }
            
            # 完了したバッチを収集
            for future in as_completed(future_to_batch):
                batch_info = future_to_batch[future]
                batch_index = batch_info['batch_index']
                batch_start = batch_info['batch_start']
                batch_end = batch_info['batch_end']
                
                try:
                    batch_sections = future.result()
                    batch_results[batch_index] = {
                        'sections': batch_sections,
                        'batch_start': batch_start,
                        'batch_end': batch_end
                    }
                    logger.info(f"バッチ{batch_start}-{batch_end}の処理完了")
                except Exception as exc:
                    logger.error(
                        f"バッチ{batch_start}-{batch_end}の処理に失敗: {exc}", 
                        exc_info=True
                    )
                    continue
        
        # バッチ結果を順番にマージ（前後の文脈を考慮するため）
        previous_context = None
        for batch_index in sorted(batch_results.keys()):
            result = batch_results[batch_index]
            batch_sections = result['sections']
            
            # 結果をマージ
            self._merge_sections(all_sections, batch_sections, pages)
            
            # 次のバッチのためのコンテキストを作成
            previous_context = self._create_context(
                batch_sections, 
                result['batch_end']
            )
        
        logger.info(f"セクション検出完了: {len(all_sections)}個のセクションを検出")
        return all_sections
    
    def _detect_batch_wrapper(self, batch_info: dict) -> dict:
        """
        バッチ処理のラッパー（並列実行用）
        
        Args:
            batch_info: バッチ情報を含む辞書
            
        Returns:
            検出結果の辞書
        """
        return self._detect_batch(
            batch=batch_info['batch'],
            batch_start=batch_info['batch_start'],
            batch_end=batch_info['batch_end'],
            previous_context=None  # 並列処理時は前のコンテキストなし
        )
    
    def _detect_batch(
        self,
        batch: list[dict],
        batch_start: int,
        batch_end: int,
        previous_context: Optional[dict]
    ) -> dict:
        """
        1バッチ（最大10ページ）のセクション検出
        
        Args:
            batch: ページデータのリスト
            batch_start: バッチの開始ページ番号
            batch_end: バッチの終了ページ番号
            previous_context: 前回のバッチで検出された情報
            
        Returns:
            検出結果の辞書
        """
        # 期待されるセクション名リストを取得
        expected_sections = self._get_section_names_from_template()
        
        # バッチのテキストを整形
        batch_text = self._format_batch_text(batch, batch_start)
        
        # プロンプトを構築
        prompt = self._build_detection_prompt(
            batch_text=batch_text,
            batch_start=batch_start,
            batch_end=batch_end,
            expected_sections=expected_sections,
            previous_context=previous_context
        )
        
        # LLM呼び出し
        response = self.openai_client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "あなたは企業開示資料のセクション検出エキスパートです。"},
                {"role": "user", "content": prompt}
            ],
            
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    def _get_section_names_from_template(self) -> list[str]:
        """テンプレートから期待セクション名を抽出（階層を結合したフラット形式）"""
        sections = []
        
        for section in self.template.get("sections", []):
            section_name = section.get("name")
            if section_name:
                # 親セクション名を追加
                sections.append(section_name)
                
                # サブセクション、items、さらに深い階層を再帰的に処理
                self._extract_nested_sections(section, section_name, sections)
        
        return sections
    
    def _build_tree_structure_from_template(self) -> str:
        """テンプレートから木構造形式のセクション構成を生成"""
        tree_lines = []
        
        def format_section(section: dict, indent: int = 0):
            """セクションを木構造形式でフォーマット"""
            prefix = "  " * indent
            name = section.get("name")
            if name:
                # 必須マークを追加
                required_mark = " ⭐" if section.get("required") else ""
                tree_lines.append(f"{prefix}- {name}{required_mark}")
                
                # subsections（サブセクション）を処理
                for subsection in section.get("subsections", []):
                    format_section(subsection, indent + 1)
                
                # items（項目）を処理
                for item in section.get("items", []):
                    format_section(item, indent + 1)
        
        # 全セクションを処理
        for section in self.template.get("sections", []):
            format_section(section)
        
        return "\n".join(tree_lines)
    
    def _extract_nested_sections(
        self, 
        parent: dict, 
        parent_path: str, 
        sections: list[str]
    ) -> None:
        """
        ネストされたセクションを再帰的に抽出
        
        Args:
            parent: 親セクションの辞書
            parent_path: これまでの階層パス（例: "企業情報 - 企業の概況"）
            sections: セクション名を追加するリスト
        """
        # subsections（サブセクション）を処理
        for subsection in parent.get("subsections", []):
            subsection_name = subsection.get("name")
            if subsection_name:
                # 親階層と結合
                combined_path = f"{parent_path} - {subsection_name}"
                sections.append(combined_path)
                
                # さらに深い階層を再帰的に処理
                self._extract_nested_sections(subsection, combined_path, sections)
        
        # items（項目）を処理
        for item in parent.get("items", []):
            item_name = item.get("name")
            if item_name:
                # 親階層と結合
                combined_path = f"{parent_path} - {item_name}"
                sections.append(combined_path)
                
                # itemsの中にさらにサブセクションがある場合も処理
                self._extract_nested_sections(item, combined_path, sections)
    
    def _format_batch_text(self, batch: list[dict], batch_start: int) -> str:
        """バッチのテキストをページ番号付きで整形"""
        formatted = []
        
        for i, page in enumerate(batch):
            page_num = batch_start + i
            text = page.get("text", "")[:2000]  # 各ページ最大2000文字
            formatted.append(f"=== ページ {page_num} ===\n{text}\n")
        
        return "\n".join(formatted)
    
    def _build_detection_prompt(
        self,
        batch_text: str,
        batch_start: int,
        batch_end: int,
        expected_sections: list[str],
        previous_context: Optional[dict]
    ) -> str:
        """セクション検出用のプロンプトを構築"""
        
        # 書類種別の表示名を取得
        doc_type_label = self.template.get("display_name", self.document_type)
        
        # 前回のコンテキスト情報
        context_info = ""
        if previous_context:
            context_info = f"""
【前回の処理結果】
- 前回の最終ページ（{previous_context['last_page']}）で検出されていたセクション: {previous_context['last_section']}
- 継続中のセクション: {', '.join(previous_context.get('ongoing_sections', []))}
"""
        
        # 木構造形式のセクション構成を取得
        tree_structure = self._build_tree_structure_from_template()
        
        prompt = f"""
以下は「{doc_type_label}」のページ{batch_start}～{batch_end}のテキストです。
各ページがどのセクションに属するか判定してください。

{context_info}

【{doc_type_label}の標準的なセクション構成】
（⭐は必須セクションを示します）

{tree_structure}

【セクション名の指定方法】
- 階層構造の場合は「親セクション - 子セクション」形式で指定してください
  例: "企業情報 - 企業の概況"
  例: "企業情報 - 企業の概況 - 主要な経営指標等の推移"
- トップレベルのセクションはそのまま指定してください
  例: "表紙"、"企業情報"

【ページテキスト】
{batch_text[:15000]}

【出力形式】
以下のJSON形式で回答してください：
{{
  "sections": [
    {{
      "section_name": "表紙",
      "start_page": 1,
      "end_page": 1,
      "confidence": 1.0,
      "is_continuing": false
    }},
    {{
      "section_name": "企業情報 - 企業の概況",
      "start_page": 2,
      "end_page": 15,
      "confidence": 0.95,
      "is_continuing": false
    }}
  ],
  "notes": "特記事項があれば記載"
}}

【注意事項】
1. {doc_type_label}の標準的な構成（上記の木構造）に基づいて判定
2. セクション名は階層構造を「-」で結合した形式で指定（例: "親 - 子 - 孫"）
3. セクションがこのバッチの範囲を超えて続く場合は、end_pageを{batch_end}にして is_continuing: true を設定
4. 前回の処理結果と矛盾がないように継続性を保つ
5. 見出しや書式から判断し、confidenceスコアを付与
6. ⭐マークの必須セクションは優先的に検出してください
"""
        return prompt
    
    def _merge_sections(
        self,
        all_sections: dict,
        batch_sections: dict,
        all_pages: list[dict]
    ) -> None:
        """バッチの検出結果を全体にマージ"""
        
        for section_info in batch_sections.get("sections", []):
            section_name = section_info["section_name"]
            start_page = section_info["start_page"]
            end_page = section_info["end_page"]
            confidence = section_info.get("confidence", 0.0)
            is_continuing = section_info.get("is_continuing", False)
            
            if section_name in all_sections:
                # 既存セクションの拡張（ページ跨ぎ）
                all_sections[section_name]["end_page"] = end_page
                all_sections[section_name]["pages"] = list(range(
                    all_sections[section_name]["start_page"],
                    end_page + 1
                ))
                all_sections[section_name]["is_continuing"] = is_continuing
            else:
                # 新規セクション
                all_sections[section_name] = {
                    "start_page": start_page,
                    "end_page": end_page,
                    "pages": list(range(start_page, end_page + 1)),
                    "confidence": confidence,
                    "is_continuing": is_continuing,
                    "char_count": 0  # 後で計算
                }
        
        # 文字数を計算
        for section_name, section_info in all_sections.items():
            char_count = 0
            for page_num in section_info["pages"]:
                if 1 <= page_num <= len(all_pages):
                    page_text = all_pages[page_num - 1].get("text", "")
                    char_count += len(page_text)
            section_info["char_count"] = char_count
    
    def _create_context(self, batch_sections: dict, batch_end: int) -> Optional[dict]:
        """次のバッチのためのコンテキスト情報を作成"""
        
        sections = batch_sections.get("sections", [])
        if not sections:
            return None
        
        # 最後のセクション
        last_section = sections[-1]
        
        # 継続中のセクションを収集
        ongoing = [
            s["section_name"]
            for s in sections
            if s.get("is_continuing", False)
        ]
        
        return {
            "last_section": last_section["section_name"],
            "last_page": batch_end,
            "ongoing_sections": ongoing
        }

