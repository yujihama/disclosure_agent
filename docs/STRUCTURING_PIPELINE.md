# ドキュメント構造化パイプライン

## 概要

PDFファイルから構造化データを抽出し、後続の比較処理で利用可能な形式に変換するパイプラインです。

## アーキテクチャ

```
┌─────────────────┐
│ PDFアップロード  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 書類種別判定    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Celeryタスク     │ Task ID: xxx
│ キューイング    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 構造化処理（Celeryワーカー）         │
├─────────────────────────────────────┤
│ 1. テキスト抽出（PyMuPDF）          │
│    ├─ 成功: 次へ                    │
│    └─ 失敗: Vision APIへ            │
│                                      │
│ 2. Vision抽出（フォールバック）     │
│    └─ スキャンPDF対応               │
│                                      │
│ 3. テーブル抽出（pdfplumber）       │
│    └─ 表データを構造化              │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ 構造化データ保存 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ UIに表示        │
└─────────────────┘
```

## コンポーネント

### 1. TextExtractor (`backend/app/services/structuring/text_extractor.py`)

**責務**: PDFからテキストを直接抽出

**実装**:
```python
from app.services.structuring import TextExtractor

extractor = TextExtractor(min_text_threshold=50)
result = extractor.extract(pdf_path)

if result.success:
    print(f"Extracted {result.page_count} pages")
    print(f"Total text: {len(result.text)} chars")
```

**特徴**:
- 平均50文字/ページ以上で成功と判定
- ページ単位のメタデータ（文字数、画像有無）
- 高速処理（234ページを約2秒）

### 2. VisionExtractor (`backend/app/services/structuring/vision_extractor.py`)

**責務**: スキャンPDFや画像ベースPDFからテキストを抽出

**実装**:
```python
from app.services.structuring import VisionExtractor

extractor = VisionExtractor(
    api_key=settings.openai_api_key,
    model="gpt-5",
    image_resolution=150,
    batch_size=10,        # 10ページずつバッチ処理
    max_workers=10,       # 最大10スレッド並列実行
)
result = extractor.extract(pdf_path)

if result.success:
    print(f"Tokens used: {result.tokens_used}")
```

**特徴**:
- OpenAI Vision API使用
- **10ページごとのバッチ並列処理**（最大10倍高速化）
- ページを画像化してOCR処理
- 前バッチの文脈を次バッチに引き継ぎ
- トークン使用量を記録

### 3. TableExtractor (`backend/app/services/structuring/table_extractor.py`)

**責務**: PDFから表データを抽出して構造化

**実装**:
```python
from app.services.structuring import TableExtractor

extractor = TableExtractor()
result = extractor.extract(pdf_path)

for table in result.tables:
    print(f"Page {table['page_number']}: {table['row_count']} rows")
    print(f"Header: {table['header']}")
```

**特徴**:
- ヘッダー行の自動検出
- データ行を辞書形式に変換
- 数値テーブルの識別（30%以上が数値セル）

### 4. DocumentMetadataStore 拡張

**新規フィールド**:
```python
@dataclass
class DocumentMetadata:
    # ... 既存フィールド ...
    
    # 構造化データ関連フィールド
    structured_data: Optional[dict[str, Any]] = None
    extraction_method: Optional[str] = None  # "text", "vision", "hybrid"
    extraction_metadata: Optional[dict[str, Any]] = None
```

**新規メソッド**:
- `save_structured_data()`: 構造化データを保存
- `get_structured_data()`: 構造化データを取得

### 5. SectionDetector (`backend/app/services/structuring/section_detector.py`)

**責務**: ドキュメントのセクション構造を検出

**実装**:
```python
from app.services.structuring.section_detector import SectionDetector

detector = SectionDetector(
    openai_client=openai_client,
    document_type="securities_report",
    batch_size=10,        # 10ページずつバッチ処理
    max_workers=5,        # 最大5バッチを並列実行
)
sections = detector.detect_sections(pages)
```

**特徴**:
- **10ページごとのバッチ並列処理**（最大5倍高速化）
- LLMでセクション構造を検出
- テンプレートと照合して標準化
- ページ跨ぎのセクションに対応

### 6. Celeryタスク統合

**新規タスク**: `documents.structure`, `documents.process`

**処理フロー（単一ドキュメント）**:
```python
@celery_app.task(name="documents.structure")
def structure_document_task(document_id: str):
    # 1. テキスト抽出
    text_result = text_extractor.extract(pdf_path)
    
    # 2. Vision抽出（フォールバック）
    if not text_result.success:
        vision_result = vision_extractor.extract(pdf_path)
    
    # 3. テーブル抽出
    table_result = table_extractor.extract(pdf_path)
    
    # 4. セクション検出
    sections = section_detector.detect_sections(text_result.pages)
    
    # 5. 保存
    metadata_store.save_structured_data(...)
```

**処理フロー（複数ドキュメント）**:
```python
@celery_app.task(name="documents.process")
def process_documents_task(document_ids: list[str]):
    # 各ドキュメントを順次処理
    # （各ドキュメント内のVision APIとセクション検出は並列化されている）
    for document_id in document_ids:
        result = structure_document_task(document_id)
```

**ステータス遷移**:
```
queued
  ↓
processing
  ↓
extracting_text
  ↓
extracting_vision (テキスト抽出失敗時のみ)
  ↓
extracting_tables
  ↓
detecting_sections (書類種別判明時のみ)
  ↓
structured
```

## データ形式

### 構造化データのJSON形式

```json
{
  "structured_data": {
    "full_text": "PDFの全テキスト",
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
        "rows": [
          ["売上高", "100,000", "10%"],
          ["営業利益", "20,000", "15%"]
        ],
        "structured_data": [
          {"項目": "売上高", "金額": "100,000", "前期比": "10%"},
          {"項目": "営業利益", "金額": "20,000", "前期比": "15%"}
        ],
        "row_count": 2,
        "column_count": 3
      }
    ]
  },
  "extraction_method": "text",
  "extraction_metadata": {
    "text_extraction": {
      "success": true,
      "page_count": 234,
      "error": null
    },
    "table_extraction": {
      "success": true,
      "table_count": 130,
      "error": null
    }
  }
}
```

## UI表示

### 折りたたみ可能なセクション

1. **サマリー**（デフォルト: 展開）
   - 抽出方法
   - ページ数
   - テーブル数
   - 全文字数

2. **ページ詳細**（デフォルト: 折りたたみ）
   - 最初の10ページを表示
   - 各ページは個別に展開可能
   - テキストプレビュー（最初の500文字）

3. **テーブル詳細**（デフォルト: 折りたたみ）
   - 最初の5テーブルを表示
   - 表形式で表示（最初の5行）
   - ページ番号、行数×列数を表示

4. **抽出メタデータ**（デフォルト: 折りたたみ）
   - 処理詳細をJSON形式で表示

### コンポーネント構造

```tsx
<StructuredDataDisplay document={document}>
  <SummarySection />          // サマリー
  <PageDetailsSection />      // ページ詳細
  <TableDetailsSection />     // テーブル詳細
  <MetadataSection />         // メタデータ
</StructuredDataDisplay>
```

## パフォーマンス

### 処理時間実績

| PDF種別 | ページ数 | テーブル数 | 処理時間 | 抽出方法 |
|---------|----------|------------|----------|----------|
| 有価証券報告書 | 234 | 130 | 5秒 | text |
| 有価証券報告書 | 225 | 117 | 5秒 | text |

### 並列処理による高速化

#### Vision API抽出（10ページバッチ並列）

| ページ数 | 従来（順次） | 並列処理後 | 高速化率 |
|---------|------------|-----------|---------|
| 100ページ | 約5分 | 約30秒 | **10倍** |
| 200ページ | 約10分 | 約1分 | **10倍** |

#### セクション検出（5バッチ並列）

| ページ数 | 従来（順次） | 並列処理後 | 高速化率 |
|---------|------------|-----------|---------|
| 100ページ | 約50秒 | 約15秒 | **3-4倍** |
| 200ページ | 約100秒 | 約30秒 | **3-4倍** |


### 最適化のポイント

1. **テキスト優先**
   - 高速・低コスト
   - ほとんどのPDFで成功

2. **Vision APIはフォールバックのみ**
   - テキスト抽出失敗時のみ実行
   - コスト削減

3. **2段階の並列処理**
   - **レベル1**: Vision API 10ページバッチの並列処理（ThreadPool）
   - **レベル2**: セクション検出バッチの並列処理（ThreadPool）

4. **UI表示の最適化**
   - 大量データは表示数を制限
   - 折りたたみでパフォーマンス向上

## エラーハンドリング

### フォールバック戦略

```
テキスト抽出
  ├─ 成功 → 次へ
  └─ 失敗
      └─ Vision抽出
          ├─ 成功 → 次へ
          └─ 失敗
              └─ エラー記録して継続
```

### エラーの記録

各ステップの成功/失敗は`extraction_metadata`に記録：

```json
{
  "text_extraction": {
    "success": false,
    "error": "Insufficient text content detected"
  },
  "vision_extraction": {
    "success": true,
    "tokens_used": 12345
  }
}
```

## 将来の拡張

### セクション3での利用

構造化データは比較エンジンで以下のように利用されます：

1. **セクションマッピング**
   - `full_text`から各セクションを識別
   - テンプレートとマッチング

2. **数値比較**
   - `tables`から財務データを抽出
   - 正規化して比較

3. **テキスト比較**
   - `pages`から対応セクションを抽出
   - 意味的な差分を分析

### 実装済みの最適化

- ✅ **バッチ並列処理**（Vision API: 10ページ、セクション検出: 5バッチ）
- ✅ **2段階の並列処理アーキテクチャ**（ThreadPoolExecutor）

### さらなる最適化の余地

- キャッシング（同一PDFの再処理回避）
- バッチサイズの動的調整（ページ数に応じて最適化）
- Vision API解像度の動的調整（画質に応じて150-300dpi）
- 並列テーブル抽出（pdfplumberの並列実行）
- ワーカー数の自動スケーリング（負荷に応じて増減）

## 参考資料

- PyMuPDF: https://pymupdf.readthedocs.io/
- pdfplumber: https://github.com/jsvine/pdfplumber
- OpenAI Vision API: https://platform.openai.com/docs/guides/vision
- Celery: https://docs.celeryq.dev/

