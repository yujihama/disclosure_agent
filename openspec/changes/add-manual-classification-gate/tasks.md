# 実装タスク

## 1. バックエンド: 書類種別判定ロジックと根拠の保存
- [x] 1.1 `ClassificationResult` データクラスに `reason: Optional[str]` フィールドを追加する（`backend/app/services/classifier.py`）
- [x] 1.2 LLM判定時に返される `reason` をパースして `ClassificationResult.reason` に格納する（`backend/app/services/classifier.py`）
- [x] 1.3 メタデータストアに `detection_reason` フィールドを追加し、分類結果と共に永続化する（`backend/app/services/metadata_store.py`）
- [x] 1.4 `DocumentUploadResult` スキーマに `detection_reason: Optional[str]` フィールドを追加する（`backend/app/schemas/documents.py`）
- [x] 1.5 `_metadata_to_result` 関数で `detection_reason` をAPIレスポンスに含める（`backend/app/api/routes/uploads.py`）

## 2. バックエンド: 構造化処理のゲート制御
- [x] 2.1 `/api/documents/` (POST) のタスクキューイングロジックに、書類種別が「unknown」または未選択の場合はキューイングしないガード条件を追加する（`backend/app/api/routes/uploads.py`）
- [x] 2.2 `/api/documents/{document_id}` (PATCH) 実行時に、書類種別が有効になった場合は構造化タスクを新たにキューイングする（`backend/app/api/routes/uploads.py`）
- [x] 2.3 Celeryワーカーの `process_documents_task` 内で、書類種別が「unknown」の場合は構造化処理をスキップするロジックを追加する（`backend/app/workers/tasks.py`）
- [x] 2.4 構造化処理がスキップされた場合、ステータスを `pending_classification` に更新する（`backend/app/workers/tasks.py`、`backend/app/api/routes/uploads.py`、`backend/app/schemas/documents.py`）

## 3. フロントエンド: 判定根拠の表示とマッチキーワードの非表示
- [x] 3.1 `DocumentUploadResult` 型定義に `detection_reason?: string` を追加する（`frontend/lib/types.ts`）
- [x] 3.2 アップロード済み書類リストUIに「判定根拠」を表示する領域を追加し、`detection_reason` を表示する（`frontend/app/page.tsx`）
- [x] 3.3 マッチキーワード（`matched_keywords`）の表示をUIから削除する（`frontend/app/page.tsx`）
- [x] 3.4 書類種別が「未判定」の場合、プルダウンで選択するよう促すメッセージを表示する（`frontend/app/page.tsx`）
- [x] 3.5 `pending_classification` ステータスのラベルを追加し、処理ステータス表示に反映する（`frontend/app/page.tsx`）

## 4. テスト
- [ ] 4.1 書類種別が「unknown」の場合に構造化タスクがキューイングされないことを確認するAPIテストを追加（`backend/tests/test_api_documents.py`）
- [ ] 4.2 書類種別を手動選択後に構造化タスクがキューイングされることを確認するAPIテストを追加（`backend/tests/test_api_documents.py`）
- [ ] 4.3 Celeryワーカーが「unknown」書類をスキップすることを確認する単体テストを追加（`backend/tests/test_classifier.py` または `backend/tests/test_structuring.py`）
- [ ] 4.4 `detection_reason` がAPIレスポンスに含まれることを確認する統合テストを追加（`backend/tests/test_api_documents.py`）

## 5. バリデーション
- [x] 5.1 `openspec validate add-manual-classification-gate --strict` を実行し、すべての検証をパスすることを確認
- [ ] 5.2 実際のPDFを使ったEnd-to-Endフローで動作確認（未判定 → 手動選択 → 構造化開始）

