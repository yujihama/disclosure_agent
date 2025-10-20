# 開示資料テンプレート

このディレクトリには、各種開示資料の標準的な構成と記載項目を定義したテンプレートファイルが格納されています。

## テンプレートファイル一覧

### 1. 有価証券報告書（securities_report.yaml）
- **法的根拠**: 金融商品取引法
- **提出頻度**: 年1回（事業年度終了後3ヶ月以内）
- **主な記載項目**:
  - 企業の概況
  - 事業の状況（事業等のリスク、MD&A等）
  - 設備の状況
  - 提出会社の状況（株式、コーポレートガバナンス等）
  - 経理の状況（連結・個別財務諸表）

### 2. 決算短信（earnings_report.yaml）
- **法的根拠**: 東京証券取引所の適時開示規則
- **提出頻度**: 四半期ごと、年度決算後速やかに
- **主な記載項目**:
  - サマリー情報
  - 連結経営成績
  - 連結財政状態
  - 連結キャッシュ・フローの状況
  - 連結業績予想
  - 定性的情報
  - 連結財務諸表

### 3. 統合報告書（integrated_report.yaml）
- **法的根拠**: 任意開示（IIRCフレームワーク準拠）
- **提出頻度**: 年1回（任意）
- **主な記載項目**:
  - トップメッセージ
  - 価値創造プロセス
  - 経営戦略・サステナビリティ戦略
  - 事業概要
  - 財務情報
  - ESG情報（環境・社会・ガバナンス）
  - リスクと機会
  - パフォーマンス

### 4. 計算書類（financial_statements.yaml）
- **法的根拠**: 会社法
- **提出頻度**: 年1回（株主総会）
- **主な記載項目**:
  - 貸借対照表
  - 損益計算書
  - 株主資本等変動計算書
  - 個別注記表
  - 附属明細書

## テンプレート構造

各テンプレートは以下の構造を持っています：

```yaml
document_type: <書類タイプID>
display_name: <表示名>
description: <説明>

sections:
  - id: <セクションID>
    name: <セクション名>
    required: <true/false>
    alternative_names:  # 別名（オプション）
      - <別名1>
      - <別名2>
    items:  # 記載項目
      - <項目1>
      - <項目2>
    tables:  # 表データ（オプション）
      - <表1>
      - <表2>
    subsections:  # サブセクション（オプション）
      - id: <サブセクションID>
        name: <サブセクション名>
        ...

important_sections:  # 重要セクション
  - <セクションID>
  
keywords_for_detection:  # 書類判定用キーワード
  - <キーワード1>
  - <キーワード2>
```

## 使用方法

### 1. テンプレートの読み込み

```python
import yaml

def load_template(document_type: str):
    """指定した書類種別のテンプレートを読み込む"""
    template_path = f"backend/templates/{document_type}.yaml"
    with open(template_path, 'r', encoding='utf-8') as f:
        template = yaml.safe_load(f)
    return template

# 例: 有価証券報告書のテンプレートを読み込む
template = load_template('securities_report')
```

### 2. 書類種別の判定

```python
def detect_document_type(text: str, templates: dict):
    """テキストから書類種別を判定する"""
    max_score = 0
    detected_type = None
    
    for doc_type, template in templates.items():
        score = 0
        keywords = template.get('keywords_for_detection', [])
        for keyword in keywords:
            if keyword in text:
                score += 1
        
        if score > max_score:
            max_score = score
            detected_type = doc_type
    
    return detected_type, max_score
```

### 3. 項目マッピング

```python
def map_sections(pdf_text: str, template: dict):
    """PDFテキストをテンプレートに基づいて項目にマッピングする"""
    mapped_sections = {}
    
    for section in template['sections']:
        # LLMを使用してセクションの開始・終了ページを検出
        section_text = extract_section_text(pdf_text, section['name'])
        mapped_sections[section['id']] = {
            'name': section['name'],
            'text': section_text,
            'required': section.get('required', False)
        }
    
    return mapped_sections
```

## テンプレートのカスタマイズ

特定の企業や業界向けにテンプレートをカスタマイズする場合：

1. 既存のテンプレートをコピー
2. `sections`に追加項目を定義
3. `keywords_for_detection`を調整
4. カスタムテンプレートとして別ファイルに保存

例：
```yaml
# custom_securities_report.yaml
document_type: custom_securities_report
display_name: カスタム有価証券報告書
description: 特定業界向けカスタムテンプレート

# 既存のセクションに加えて業界固有のセクションを追加
sections:
  # ... 既存セクション ...
  - id: industry_specific
    name: 業界固有情報
    required: true
    items:
      - 特定の規制対応状況
      - 業界特有のKPI
```

## テンプレートの更新

開示資料の規則や様式が変更された場合：

1. 該当するYAMLファイルを編集
2. `sections`や`items`を追加・修正
3. バージョン管理のためgitコミット
4. テストケースを更新

## 参考資料

### 有価証券報告書
- [金融庁：有価証券報告書の記載事項](https://www.fsa.go.jp/)
- [EDINET：有価証券報告書提出者一覧](https://disclosure.edinet-fsa.go.jp/)

### 決算短信
- [東京証券取引所：決算短信・四半期決算短信](https://www.jpx.co.jp/equities/listed-co/format/summary/)

### 統合報告書
- [IIRC：国際統合報告フレームワーク](https://www.integratedreporting.org/)
- [経済産業省：価値協創ガイダンス](https://www.meti.go.jp/)

### 計算書類
- [法務省：会社法](https://elaws.e-gov.go.jp/)

## ドキュメント構造化パイプライン

### 概要

アップロードされたPDFファイルは以下のパイプラインで構造化されます：

1. **テキスト抽出** (PyMuPDF)
   - PDFからテキストを直接抽出
   - ページごとの文字数、画像の有無を記録
   - 平均50文字/ページ以上であれば成功と判定

2. **画像ベース抽出** (Vision API - フォールバック)
   - テキスト抽出が不十分な場合に実行
   - スキャンPDFや複雑なレイアウトに対応
   - 各ページを画像化してOpenAI Vision APIで解析
   - 前ページの文脈を維持しながら連続処理

3. **テーブル抽出** (pdfplumber)
   - 表データを構造化形式で抽出
   - ヘッダー行とデータ行を自動認識
   - 数値データを含む表の識別（30%以上の数値セルを含む場合）

### 構造化データ形式

構造化されたデータは以下の形式でメタデータストアに保存されます：

```json
{
  "structured_data": {
    "full_text": "抽出された全テキスト",
    "pages": [
      {
        "page_number": 1,
        "text": "ページ1のテキスト",
        "char_count": 1234,
        "has_images": true
      }
    ],
    "tables": [
      {
        "page_number": 5,
        "table_index": 0,
        "header": ["項目", "金額", "前期比"],
        "rows": [["売上高", "100,000", "10%"]],
        "structured_data": [...],
        "row_count": 10,
        "column_count": 3
      }
    ]
  },
  "extraction_method": "text|vision|hybrid",
  "extraction_metadata": {
    "text_extraction": {...},
    "vision_extraction": {...},
    "table_extraction": {...}
  }
}
```

### 構造化ステータス

処理中のドキュメントは以下のステータスを持ちます：

- `queued`: キューに追加済み
- `processing`: 処理中
- `extracting_text`: テキスト抽出中
- `extracting_vision`: Vision API処理中
- `extracting_tables`: テーブル抽出中
- `structured`: 構造化完了
- `failed`: 処理失敗

### 使用例

```python
from app.services.metadata_store import DocumentMetadataStore
from app.core.config import get_settings

settings = get_settings()
metadata_store = DocumentMetadataStore(settings)

# 構造化データの取得
structured_data = metadata_store.get_structured_data(document_id)

if structured_data:
    full_text = structured_data["full_text"]
    tables = structured_data["tables"]
    
    # テンプレートと組み合わせてセクションマッピング
    template = load_template("securities_report")
    mapped_sections = map_sections_with_structured_data(
        full_text, tables, template
    )
```

### パフォーマンス最適化

- **テキスト優先**: まずテキスト抽出を試行（高速・低コスト）
- **Vision APIフォールバック**: 必要な場合のみ実行（高精度・高コスト）
- **バッチ処理**: 複数ドキュメントを並列処理
- **キャッシング**: 同一PDFの再処理を回避

### エラーハンドリング

各抽出ステップは独立しており、一部が失敗しても他のステップは継続します。最終的な成功判定は：

- テキストまたはVisionの少なくとも一方が成功
- テーブル抽出は任意（失敗しても全体は成功扱い）


