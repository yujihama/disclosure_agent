# 開示情報比較ツール (Disclosure Comparison Tool)

企業の開示資料（有価証券報告書、統合報告書、決算短信、計算書類）の自動判定、構造化、比較分析を行うAIベースのツールです。

## 機能

### ✅ 実装済み

- **PDFファイルの複数同時アップロード**
  - ドラッグ&ドロップ対応UI
  - 最大5ファイル、50MB/ファイル
  
- **書類種別の自動判定**
  - テンプレートベースのキーワードマッチング
  - gpt-5による高精度判定
  - 手動オーバーライド機能

- **ドキュメント構造化パイプライン**
  - テキスト抽出（PyMuPDF）
  - 画像ベース抽出（OpenAI Vision API）
  - テーブル抽出（pdfplumber）
  - セクション検出と自動マッピング
  - 234ページ、130テーブルを約5秒で処理
  
- **構造化データのUI表示**
  - 折りたたみ可能なセクション表示
  - ページ詳細（テキストプレビュー付き）
  - テーブル詳細（表形式で表示）
  - セクションマッピング結果の表示
  - 抽出メタデータ
  
- **比較・差分分析エンジン** ← NEW!
  - 会社・年度メタデータの自動抽出
  - 比較モード自動選択（整合性チェック／差分分析）
  - セクション間マッピング（信頼度スコア付き）
  - LLMベースの統合的差分分析
    - 数値データ比較（単位正規化、許容誤差）
    - テキスト・意味・トーン分析
    - トピック抽出と比較
    - 重要度判定と推奨アクション生成
  - セクション別詳細差分レポート
  
- **比較結果の基本表示** ← NEW!
  - 比較サマリー（モード、ステータス、進捗）
  - セクション別差分件数と重要度分布
  - 詳細差分レポートの構造化表示
  
- **バックグラウンド処理**
  - Celery + Redis
  - リアルタイムステータス更新
  - 自動クリーンアップ（24時間保持）

### 🚧 開発中

- 高度なレポーティングUI（セクション4）
  - サイドバイサイドビューア
  - 差分リスト・フィルタ機能
  - レポートエクスポート（PDF/Excel）
- E2Eテスト、CI/CD（セクション5）

## クイックスタート

### 方法1: Docker Compose（推奨・最速）

すべてのサービスをDockerで起動する方法：

```powershell
# 1. リポジトリをクローン
git clone <repository-url>
cd disclosure_agent

# 2. 環境変数を設定
# .env ファイルを作成してOpenAI APIキーを設定（最低限これだけでOK）
@"
APP_OPENAI_API_KEY=your-openai-api-key-here
APP_OPENAI_MODEL=gpt-5
# Azure OpenAI を利用する場合は以下も設定
# APP_OPENAI_PROVIDER=azure
# APP_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# APP_AZURE_OPENAI_API_VERSION=2024-02-15-preview
"@ | Out-File -FilePath .env -Encoding utf8

# 3. すべてのサービスを起動（初回はビルドに数分かかります）
docker compose up --build

# または、バックグラウンドで起動
docker compose up -d --build

# 4. ブラウザで開く
# フロントエンド: http://localhost:3001
# API: http://localhost:8000/api/docs

# ログを確認（バックグラウンド起動の場合）
docker compose logs -f

# サービスを停止
docker compose down
```

**起動するサービス:**
- Redis（ポート6379）
- バックエンドAPI（ポート8000）
- Celeryワーカー
- フロントエンド（ポート3001）

### 方法2: ローカル開発

開発時にコードの変更を即座に反映したい場合：

```powershell
# 1. リポジトリをクローン
git clone <repository-url>
cd disclosure_agent

# 2. 環境変数を設定
# .env ファイルを作成してOpenAI APIキーを設定
@"
APP_OPENAI_API_KEY=your-openai-api-key-here
APP_OPENAI_MODEL=gpt-5
# Azure OpenAI を利用する場合は以下も設定
# APP_OPENAI_PROVIDER=azure
# APP_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# APP_AZURE_OPENAI_API_VERSION=2024-02-15-preview
APP_REDIS_URL=redis://localhost:6379/0
APP_CELERY_BROKER_URL=redis://localhost:6379/0
APP_CELERY_RESULT_BACKEND=redis://localhost:6379/0
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
"@ | Out-File -FilePath .env -Encoding utf8

# 3. Redisを起動
docker compose up redis -d

# 4. バックエンドをセットアップ（ウィンドウ1）
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload

# 5. Celeryワーカーを起動（ウィンドウ2）
cd backend
.\.venv\Scripts\activate
celery -A app.workers.celery_app worker --loglevel=info --pool=solo

# 6. フロントエンドを起動（ウィンドウ3）
cd frontend
npm install
npm run dev

# 7. ブラウザで開く
# http://localhost:3001
```

## セットアップ

### 前提条件

- Python 3.11以上
- Node.js 18以上
- Docker（推奨）
- OpenAI APIキー

### 環境変数の設定

プロジェクトルートに`.env`ファイルを作成してください：

```bash
# OpenAI API設定
APP_OPENAI_API_KEY=your-openai-api-key-here
APP_OPENAI_MODEL=gpt-5
APP_OPENAI_TIMEOUT_SECONDS=30.0
# Azure OpenAI を利用する場合
# APP_OPENAI_PROVIDER=azure
# APP_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# APP_AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Redis/Celery設定（Dockerを使用する場合）
APP_REDIS_URL=redis://redis:6379/0
APP_CELERY_BROKER_URL=redis://redis:6379/0
APP_CELERY_RESULT_BACKEND=redis://redis:6379/0

# Redis/Celery設定（ローカル開発の場合）
# APP_REDIS_URL=redis://localhost:6379/0
# APP_CELERY_BROKER_URL=redis://localhost:6379/0
# APP_CELERY_RESULT_BACKEND=redis://localhost:6379/0

# ドキュメントアップロード設定
APP_DOCUMENT_UPLOAD_MAX_FILES=5
APP_DOCUMENT_UPLOAD_MAX_FILE_SIZE_MB=50
APP_DOCUMENT_RETENTION_HOURS=24

# 分類設定
APP_DOCUMENT_CLASSIFICATION_USE_LLM=true
APP_DOCUMENT_CLASSIFICATION_MAX_PROMPT_CHARS=4000

# フロントエンド設定
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_MAX_UPLOAD_FILES=5
NEXT_PUBLIC_MAX_UPLOAD_SIZE_MB=50
```

**注意:** `APP_OPENAI_MODEL`は構造化処理で`gpt-5`を推奨します。

### Docker Composeを使用する場合（推奨）

**完全な手順:**

```powershell
# 1. 環境変数を設定（プロジェクトルートに .env ファイルを作成）
@"
# OpenAI API設定（必須）
APP_OPENAI_API_KEY=your-openai-api-key-here
APP_OPENAI_MODEL=gpt-5
APP_OPENAI_TIMEOUT_SECONDS=30.0
# Azure OpenAI を利用する場合
# APP_OPENAI_PROVIDER=azure
# APP_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# APP_AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Redis/Celery設定（Docker使用時）
APP_REDIS_URL=redis://redis:6379/0
APP_CELERY_BROKER_URL=redis://redis:6379/0
APP_CELERY_RESULT_BACKEND=redis://redis:6379/0

# ドキュメントアップロード設定
APP_DOCUMENT_UPLOAD_MAX_FILES=5
APP_DOCUMENT_UPLOAD_MAX_FILE_SIZE_MB=50
APP_DOCUMENT_RETENTION_HOURS=24

# 分類設定
APP_DOCUMENT_CLASSIFICATION_USE_LLM=true
APP_DOCUMENT_CLASSIFICATION_MAX_PROMPT_CHARS=4000

# フロントエンド設定
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_MAX_UPLOAD_FILES=5
NEXT_PUBLIC_MAX_UPLOAD_SIZE_MB=50
"@ | Out-File -FilePath .env -Encoding utf8

# 2. すべてのサービスを起動
docker compose up --build

# または、バックグラウンドで起動
docker compose up -d --build

# 3. アクセス
# フロントエンド: http://localhost:3001
# バックエンドAPI: http://localhost:8000/api/docs

# ログを確認（バックグラウンド起動の場合）
docker compose logs -f

# 特定のサービスのログのみ確認
docker compose logs -f backend
docker compose logs -f celery-worker

# サービスの状態を確認
docker compose ps

# サービスを停止
docker compose down

# ボリュームも削除する場合（アップロードファイルとRedisデータを削除）
docker compose down -v
```

**Docker Composeで起動される4つのサービス:**

| サービス | 説明 | ポート |
|---------|------|--------|
| redis | Redisサーバー（Celeryのメッセージブローカー） | 6379 |
| backend | FastAPIバックエンド（API、アップロード処理） | 8000 |
| celery-worker | Celeryワーカー（構造化、比較処理） | - |
| frontend | Next.jsフロントエンド | 3001 |

**トラブルシューティング:**

```powershell
# コンテナを再ビルド（依存関係の変更後）
docker compose up --build --force-recreate

# 特定のサービスのみ起動
docker compose up redis backend celery-worker

# コンテナ内でコマンド実行
docker compose exec backend python -c "from app.core.config import settings; print(settings.OPENAI_API_KEY[:10])"

# すべてのコンテナとイメージを削除してクリーンアップ
docker compose down -v --rmi all
```

### ローカル開発の場合

#### バックエンド

```powershell
cd backend

# 依存関係をインストール
pip install -e .

# サーバーを起動
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### フロントエンド

```powershell
cd frontend

# 依存関係をインストール
npm install

# 開発サーバーを起動
npm run dev
```

#### Redis（ローカル開発でCeleryを使用する場合）

```powershell
# Dockerを使用してRedisを起動
docker run -d -p 6379:6379 redis:latest

# または、Windows用Redisをインストール
# https://redis.io/docs/getting-started/installation/install-redis-on-windows/
```

#### Celeryワーカー（ローカル開発でバックグラウンド処理を使用する場合）

```powershell
cd backend
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

## ドキュメント構造化パイプライン

アップロードされたPDFは、以下のパイプラインで自動的に構造化されます：

### 処理フロー

```
PDFアップロード
  ↓
書類種別判定
  ↓
Celeryタスクキューイング
  ↓
[構造化処理]
  ├→ 1. テキスト抽出（PyMuPDF）
  │    └→ 成功: 次へ / 失敗: Vision APIへ
  ├→ 2. Vision抽出（OpenAI Vision API）※フォールバック
  │    └→ スキャンPDFや画像ベースPDFに対応
  └→ 3. テーブル抽出（pdfplumber）
       └→ 表データを構造化形式で抽出
  ↓
構造化データ保存
  ↓
UIで表示
```

### 抽出されるデータ

- **全文テキスト**: 約30万文字（234ページの場合）
- **ページ単位データ**: 各ページのテキスト、文字数、画像有無
- **テーブルデータ**: ヘッダー、行データ、構造化JSON
- **メタデータ**: 抽出方法、成功/失敗情報、トークン使用量

### 処理時間

- 小規模PDF（~50ページ）: 1-2秒
- 中規模PDF（~100ページ）: 3-4秒
- 大規模PDF（~250ページ）: 5-10秒
- Vision API使用時: 上記の3-5倍

## API仕様

### エンドポイント

#### ドキュメント管理
- `GET /api/health` - ヘルスチェック
- `GET /api/documents/` - ドキュメント一覧取得
- `GET /api/documents/{document_id}` - 個別ドキュメント取得
- `POST /api/documents/` - ドキュメントアップロード
- `PATCH /api/documents/{document_id}` - 書類種別/メタデータの手動設定

#### 比較分析
- `POST /api/comparisons/` - 比較分析の実行
- `GET /api/comparisons/{comparison_id}` - 比較結果の取得
- `GET /api/comparisons/` - 比較一覧の取得

### レスポンス例

#### ドキュメント取得（構造化完了後）
```json
{
  "document": {
    "document_id": "xxx",
    "filename": "report.pdf",
    "processing_status": "structured",
    "extraction_method": "text",
    "document_type": "securities_report",
    "company_name": "株式会社サンプル",
    "fiscal_year": "2024",
    "structured_data": {
      "full_text": "...",
      "pages": [...],
      "tables": [...],
      "sections": [
        {
          "section_name": "事業等のリスク",
          "start_page": 10,
          "end_page": 15,
          "confidence": 0.95
        }
      ]
    }
  }
}
```

#### 比較結果取得
```json
{
  "comparison_id": "yyy",
  "comparison_mode": "diff_analysis",
  "status": "completed",
  "document_ids": ["xxx-1", "xxx-2"],
  "summary": {
    "total_sections_compared": 15,
    "sections_with_differences": 8,
    "high_importance_count": 3,
    "medium_importance_count": 4,
    "low_importance_count": 1
  },
  "section_details": [
    {
      "section_name": "事業等のリスク",
      "mapping_confidence": 0.95,
      "difference_summary": "...",
      "importance_level": "high",
      "recommended_action": "..."
    }
  ]
}
```

詳細は http://localhost:8000/api/docs で確認できます。

## ドキュメント

- [開示情報比較仕様書](開示情報比較仕様書.md) - 全機能の概要と仕様
- [ドキュメント構造化パイプライン詳細](docs/STRUCTURING_PIPELINE.md) - セクション2の技術仕様
- [テンプレート仕様](backend/templates/README.md) - 書類種別テンプレートの説明
- [OpenSpec変更提案](openspec/changes/add-disclosure-comparison-tool/) - 設計ドキュメントと実装タスク

## テスト

### バックエンドテスト

```powershell
cd backend
pytest
```

### フロントエンドテスト

```powershell
cd frontend
npm test
```

## 開発状況と次のステップ

### ✅ 完了している機能（セクション0-3）

**セクション0-1: 基本機能**
- PDFアップロード（複数ファイル対応、ドラッグ&ドロップUI）
- 書類種別の自動判定（テンプレート + gpt-5）
- メタデータ管理API
- 手動オーバーライド機能
- ステータスポーリングUI
- 自動削除ポリシー（24時間保持）
- Redis + Celeryバックグラウンド処理

**セクション2: ドキュメント構造化パイプライン**
- ✅ テキスト抽出（PyMuPDF）
- ✅ Vision抽出フォールバック（OpenAI Vision API）
- ✅ テーブル抽出（pdfplumber）
- ✅ セクション検出と自動マッピング（LLMベース、20ページバッチ処理）
- ✅ 構造化データの永続化
- ✅ 進捗ステータス更新（queued → extracting_text → extracting_tables → structured）
- ✅ UIでの構造化データ表示（折りたたみ可能なセクション）
  - サマリー（抽出方法、ページ数、テーブル数、文字数、セクション数）
  - ページ詳細（最初の10ページ、テキストプレビュー）
  - テーブル詳細（最初の5テーブル、表形式表示）
  - セクションマッピング結果
  - 抽出メタデータ

**動作実績:**
- 有価証券報告書 234ページ: 約5秒で完了
- テキスト抽出: 296,499文字
- テーブル抽出: 130個

**セクション3: 比較・差分分析エンジン**
- ✅ 会社・年度メタデータの自動抽出（LLM）
- ✅ 比較モードの自動選択（整合性チェック／差分分析／多資料比較）
- ✅ セクション間マッピング（信頼度スコア付き）
- ✅ LLMベースの統合的差分分析
- ✅ セクション別詳細差分レポートの生成と保存
- ✅ 比較結果API（`POST /api/comparisons/`, `GET /api/comparisons/{id}`）
- ✅ UIでの比較結果表示（サマリー、セクション別詳細差分）

### 🚧 次のステップ（セクション4-5）

**セクション4: 高度なレポーティングUI**
- サイドバイサイドビューア（差分ハイライト、ページジャンプ）
- 差分リスト（フィルタ、ソート、キーワード検索）
- レポートエクスポート（PDF/Excel）
- インタラクティブなダッシュボード（グラフ、クイックフィルタ）

**セクション5: 品質・運用**
- E2Eテスト（pytest + Playwright）
- ログ／メトリクス計装とアラート
- CI/CD設定
- 保持ポリシーの全パイプライン検証

## トラブルシューティング

### 起動時に古いタスクが自動実行される場合

**症状**: `restart_services.ps1`でサービスを起動した瞬間に、ボタンを押していないのに以前のタスクが自動実行される。

**原因**: Redisキューに以前の未処理タスクが残っているため。これはCeleryの正常な動作（タスクの永続性）ですが、開発中は混乱を招く可能性があります。

**解決策**:

1. **起動時に選択的にクリア（推奨）**:
   ```powershell
   .\backend\restart_services.ps1
   # プロンプトで "Y" を選択
   ```

2. **常に自動クリア（開発専用）**:
   ```powershell
   .\backend\restart_services_clean.ps1
   ```

3. **手動でキューをクリア**:
   ```powershell
   .\backend\clear_queue.ps1
   ```

詳細は [Celeryキュー管理ガイド](backend/README_QUEUE_MANAGEMENT.md) を参照してください。

### CORSエラーが発生する場合

`backend/app/main.py`のCORS設定を確認してください。

### Celeryタスクがキューイングされない場合

1. Redisが起動しているか確認
   ```powershell
   docker ps --filter "name=redis"
   ```

2. Celeryワーカーが起動しているか確認
   ```powershell
   # タスクの登録を確認
   python -c "import sys; sys.path.insert(0, 'backend'); from app.workers.celery_app import celery_app; i = celery_app.control.inspect(); print(list(i.registered().values())[0] if i.registered() else 'None')"
   ```
   
   `['documents.process', 'documents.structure', 'documents.cleanup_expired']`が表示されればOK

3. バックエンドAPIのログで「Enqueued Celery task」が表示されるか確認

### 構造化処理が進まない（processing_status が queued のまま）

1. Celeryワーカーのログを確認
   - タスクを受信しているか（`Task documents.process[...] received`）
   - エラーが発生していないか

2. `.env`ファイルの設定を確認
   ```bash
   APP_REDIS_URL=redis://localhost:6379/0
   APP_CELERY_BROKER_URL=redis://localhost:6379/0
   APP_CELERY_RESULT_BACKEND=redis://localhost:6379/0
   ```

3. サービスを再起動して環境変数を反映
   - バックエンドAPI: `Ctrl+C` → 再起動
   - Celeryワーカー: `Ctrl+C` → 再起動

### 書類種別が「未判定」になる場合

1. OpenAI APIキーが正しく設定されているか確認
2. `APP_DOCUMENT_CLASSIFICATION_USE_LLM=true`が設定されているか確認
3. バックエンドログでエラーを確認

### 構造化データがUIに表示されない場合

1. ドキュメントの`processing_status`が`structured`になっているか確認
2. ブラウザのコンソールでJavaScriptエラーを確認
3. APIレスポンスに`structured_data`フィールドが含まれているか確認
   ```powershell
   curl http://localhost:8000/api/documents/{document_id}
   ```

### Vision API使用時のエラー

1. `APP_OPENAI_MODEL`が Vision対応モデルか確認（`gpt-5`など）
2. OpenAI APIの利用可能枠を確認
3. 画像サイズが大きすぎる場合は解像度を下げる（`vision_extractor.py`の`image_resolution`）

## ライセンス

（ライセンス情報を記載してください）

