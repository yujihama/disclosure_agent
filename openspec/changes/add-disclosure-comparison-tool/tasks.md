# 実装タスク

## 0. 基本セットアップと初期実装（完了）
- [x] 0.1 バックエンド構造とFastAPIアプリケーションのセットアップ（`backend/app/main.py`、`backend/app/core/config.py`）
- [x] 0.2 フロントエンドNext.jsアプリケーションのセットアップ（`frontend/`）
- [x] 0.3 PDFアップロードAPI実装（`backend/app/api/routes/uploads.py`）
- [x] 0.4 書類種別分類器の実装（テンプレート + LLM）（`backend/app/services/classifier.py`）
- [x] 0.5 PyMuPDFによるPDFテキスト抽出（`backend/app/services/document_upload.py`）
- [x] 0.6 メタデータストアの実装（`backend/app/services/metadata_store.py`）
- [x] 0.7 基本的なアップロードUIの実装（`frontend/app/page.tsx`）
- [x] 0.8 CORS設定と依存関係のセットアップ（`backend/app/main.py`、`backend/pyproject.toml`）

## 1. ドキュメントアップロードと分類の強化
- [x] 1.1 `/api/documents/` 向け正常系・バリデーションエラー・手動オーバーライドを網羅するAPIレベルのテストを追加する（`backend/tests/test_api_documents.py`）。
- [x] 1.2 アップロードバッチおよびドキュメントメタデータを取得できる読み取り専用エンドポイントを公開する（`backend/app/api/routes/uploads.py`、`backend/app/services/metadata_store.py`）。
- [x] 1.3 手動オーバーライドAPI（`PATCH /api/documents/{document_id}`）が正常に動作することをテストし、必要に応じて修正する（`frontend/lib/api.ts`修正済み）。
- [x] 1.4 新しいステータスエンドポイントをポーリングしてファイル単位の進捗を取得し、UIに表示する（`frontend/app/page.tsx`にuseEffect追加）。
- [x] 1.5 バッチ完了または期限切れ時に保存済みPDFとメタデータを削除し、保持ポリシーを徹底する（`backend/app/services/metadata_store.py`、`backend/app/workers/tasks.py`にクリーンアップ機能追加）。
- [x] 1.6 RedisとCeleryワーカーのセットアップとタスクキューイングの有効化（`docker-compose.yml`、`Dockerfile`作成、`README.md`追加、Celeryタスク有効化）。

## 2. ドキュメント構造化パイプラインの実装

**⚠️ セクション2を開始する前に実施:**
- [x] 2.0.1 RedisをDockerで起動する（`docker run -d -p 6379:6379 redis:latest` または `docker compose up redis -d`）
- [x] 2.0.2 `backend/app/api/routes/uploads.py` の110-121行目のCeleryタスクキューイングのコメントを解除する
- [x] 2.0.3 Celeryワーカーを起動する（`cd backend; celery -A app.workers.celery_app worker --loglevel=info --pool=solo`）
- [x] 2.0.4 アップロード→バックグラウンド処理→ステータス更新の完全なフローをテストする（.envファイル作成、サービス再起動が必要）

**構造化機能の実装:**
- [x] 2.1 PyMuPDFでテキストを抽出する `DocumentStructuringService` を実装する（`backend/app/services/structuring/text_extractor.py`）。
- [x] 2.2 pdf2image + Vision API を用いた画像ベースのフォールバックを追加し、スキャンPDFに対応する（`backend/app/services/structuring/vision_extractor.py`）。
- [x] 2.3 pdfplumberで表データを抽出し、構造化テーブルとして永続化する（`backend/app/services/structuring/table_extractor.py`）。
- [x] 2.4 メタデータストアを拡張し、構造化出力と進捗チェックポイントを保存できるようにする（`backend/app/services/metadata_store.py`）。
- [x] 2.5 Celeryワーカーを更新して構造化処理ステップを編成し、進捗更新を発行させる（`backend/app/workers/tasks.py`）。
- [x] 2.6 構造化パイプライン向けの単体／統合テストを追加し、エラーフォールバックを含めて検証する（`backend/tests/test_structuring.py`）。
- [x] 2.7 新しいテンプレートキーや要件があれば `backend/templates/README.md` に追記する。
- [x] 2.8 フロントエンドUIに構造化データの詳細表示機能を追加し、折りたたみ可能なセクションで実装する（`frontend/app/page.tsx`、`frontend/lib/types.ts`）。
- [x] 2.9 書類種別に応じたLLMベースのセクション検出機能を実装する（`backend/app/services/structuring/section_detector.py`）。
  - [x] 2.9.1 20ページごとのバッチ処理でセクションを検出する `SectionDetector` クラスを実装する。
  - [x] 2.9.2 書類種別のテンプレート（YAML）から期待セクションリストを動的に取得する機能を実装する。
  - [x] 2.9.3 前回のバッチ検出結果を引き継ぎながら処理し、ページ跨ぎセクションに対応する。
  - [x] 2.9.4 検出結果（セクション名、ページ範囲、信頼度）を構造化データの `sections` フィールドに保存する。
  - [x] 2.9.5 Celeryワーカーの構造化タスク（`backend/app/workers/tasks.py`）にセクション検出ステップを統合する。
  - [x] 2.9.6 セクション検出結果をUIで確認できるよう表示機能を追加する（オプション、`frontend/app/page.tsx`）。

## 3. 比較エンジンの構築
- [x] 3.1 会社・種別メタデータに基づいてモードを選択する比較オーケストレータを実装する（`backend/app/services/comparison_engine.py`）。
- [x] 3.2 LLMで会社名・年度メタデータを抽出し、手動オーバーライド用API/UIを用意する（`backend/app/api/routes/comparisons.py`、`frontend/app`）。
- [x] 3.3 テンプレートと構造化結果を活用して書類間でセクションをマッピングし、信頼度スコアを付与する（`backend/app/services/comparison_engine.py`）。
- [x] 3.4 単位正規化と許容誤差を考慮した数値差分を実装し、異常値を永続化する（`backend/app/services/comparison_engine.py`）。
- [x] 3.5 埋め込みとLLM要約を組み合わせ、文脈・トーンの差異を分析するテキスト／意味差分を実装する（`backend/app/services/comparison_engine.py`）。
- [x] 3.6 比較結果を下流レポーティング向けの構造化レコードとして保存する（`backend/app/services/metadata_store.py`）。
- [x] 3.7 マッピングされた各セクションに対してLLMで統合的な差分分析を実行する（`backend/app/services/comparison_engine.py`）。
  - [x] 3.7.1 セクション情報（ページ範囲）から該当ページのテキストとテーブルデータを抽出するヘルパー関数を実装する。
  - [x] 3.7.2 書類種別に応じた詳細比較プロンプトを動的に構築する機能を実装する。
  - [x] 3.7.3 LLMでセクションごとの包括的な差分分析を実行する（テキスト差異、数値差異、トーン差異、重要度判定を含む）。
  - [x] 3.7.4 セクション別詳細差分レポートを構造化データとして生成・保存する。
  - [x] 3.7.5 比較結果APIレスポンスにセクション別詳細差分を含める（`backend/app/schemas/comparisons.py`更新）。
  - [x] 3.7.6 UIにセクション別詳細差分レポートを表示する機能を追加する（`frontend/app/page.tsx`）。

## 4. 結果レポーティング体験の提供
- [ ] 4.1 比較サマリーと詳細差分を取得するRESTエンドポイントを公開する（`backend/app/api/routes/results.py`）。
- [ ] 4.2 件数・グラフ・クイックフィルタを備えたサマリーダッシュボードをNext.jsで構築する（`frontend/app/(dashboard)`）。
- [ ] 4.3 差分ハイライトとナビゲーション付きのサイドバイサイドビューアを実装する（`frontend/components/SideBySideViewer.tsx`）。
- [ ] 4.4 フィルタ／ソート／キーワード検索を備えた差分リストを実装する（`frontend/app/(dashboard)/differences.tsx`）。
- [ ] 4.5 PDF／Excelレポートをエクスポートできるツールを追加する（`backend/app/services/reporting.py`、`frontend/lib/api.ts`）。

## 5. 品質・運用・ツール整備
- [ ] 5.1 アップロードから差分表示までをカバーするEnd-to-Endテスト（pytest + Playwright）を追加する（`backend/tests`、`frontend/__tests__/`）。
- [ ] 5.2 ログ／メトリクス計装と、ワーカ失敗やLLMリトライ枯渇を検知するアラートを整備する（`backend/app/core`、`backend/app/workers/tasks.py`）。
- [ ] 5.3 フルスタック用の docker-compose と環境構築ドキュメントを整備する（`docker-compose.yml`、`README.md`、`.env.example`）。
- [ ] 5.4 全パイプラインで生データと構造化出力が保持ポリシーを守るよう確認する（`backend/app/services/metadata_store.py`）。
- [ ] 5.5 CIで `openspec validate add-disclosure-comparison-tool --strict`、バックエンドテスト、フロントエンドのLint／テストを実行するよう設定する。
