# Project Context

## Purpose
企業の開示資料（有価証券報告書、統合報告書、決算短信等）を複数アップロードし、AIを活用して記載内容の整合性検証と差分分析を自動で行うツール。開示情報の品質向上、作成工数の削減、競合他社分析の高度化を実現する。

## Tech Stack

### フロントエンド
- Next.js 14+
- React 18+
- TypeScript 5+
- Tailwind CSS（スタイリング）
- shadcn/ui（UIコンポーネント）

### バックエンド
- Python 3.11+
- FastAPI（Webフレームワーク）
- Celery（非同期タスク処理）
- Redis（キャッシュ、タスクキュー）
- PyMuPDF（PDFテキスト抽出）
- pdfplumber（表データ抽出）
- pdf2image（画像変換）
- sentence-transformers（テキスト類似度分析）

### AI/LLM
- OpenAI gpt-5（書類判定、項目抽出、テキスト分析）

### インフラ
- Docker & Docker Compose
- PostgreSQL（将来的なデータ永続化用）

## Project Conventions

### Code Style
- **Python**: PEP 8準拠、Black（自動フォーマット）、isort（インポート整理）
- **TypeScript**: ESLint + Prettier、Airbnb スタイルガイドベース
- **命名規則**:
  - ファイル名: kebab-case（例: document-upload.ts）
  - クラス名: PascalCase
  - 関数名: camelCase（TS）、snake_case（Python）
  - 定数: UPPER_SNAKE_CASE

### Architecture Patterns
- **フロントエンド**: コンポーネントベースアーキテクチャ、hooks優先
- **バックエンド**: レイヤードアーキテクチャ（API層、サービス層、データ層）
- **非同期処理**: Celeryによるタスクキュー、長時間処理は必ず非同期化
- **エラーハンドリング**: 全APIエンドポイントで統一されたエラーレスポンス形式

### Testing Strategy
- **ユニットテスト**: 各関数・クラスに対してテスト作成（pytest、Jest）
- **統合テスト**: API エンドポイントのテスト（pytest + httpx）
- **E2Eテスト**: ユーザーフロー全体のテスト（Playwright）
- **カバレッジ目標**: 80%以上

### Git Workflow
- **ブランチ戦略**: Git Flow
  - main: 本番環境
  - develop: 開発環境
  - feature/*: 新機能開発
  - fix/*: バグ修正
- **コミットメッセージ**: Conventional Commits形式
  - feat: 新機能
  - fix: バグ修正
  - docs: ドキュメント
  - refactor: リファクタリング
  - test: テスト追加

## Domain Context

### 開示資料の種類
- **有価証券報告書**: 法定開示資料、詳細な財務情報と事業内容を記載
- **統合報告書**: 任意開示、財務・非財務情報を統合的に報告
- **決算短信**: 四半期・年次決算の速報、簡潔な財務サマリー
- **計算書類**: 株主総会用の財務諸表

### 重要な項目
- **事業等のリスク**: 企業が直面するリスク要因の記述
- **MD&A**: 経営者による財政状態・経営成績の分析
- **財務諸表**: 貸借対照表、損益計算書、キャッシュフロー計算書等

## Important Constraints

### セキュリティ
- アップロードされたPDFはセッション終了後に即座に削除
- 個人情報や機密情報の取り扱いに注意
- API キーは環境変数で管理、リポジトリにコミットしない

### コスト制約
- OpenAI API のコスト管理
- 画像処理は必要最小限に（解像度最適化）
- キャッシュ機構で重複処理を削減

### パフォーマンス
- 大規模PDF（100ページ以上）でも5分以内に処理完了
- フロントエンドのレスポンシブ性能（初期表示3秒以内）

### 法規制
- 開示資料は金融商品取引法等の法規制対象
- 分析結果はあくまで参考情報であり、最終判断は人間が行う

## External Dependencies

### OpenAI API
- gpt-5: 書類判定、項目抽出、テキスト比較・分析
- Vision API: 画像ベースPDFの処理
- レート制限: リクエスト数とトークン数に注意

### PDF処理ライブラリ
- PyMuPDF (fitz): テキスト抽出の主要ライブラリ
- pdfplumber: 表データ抽出に特化
- pdf2image: PDF → 画像変換（Poppler依存）

### Redis
- Celeryのメッセージブローカー
- キャッシュストア
