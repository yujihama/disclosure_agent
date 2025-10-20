# 書類種別未判定時の構造化処理ゲート制御と判定根拠表示の追加

## Why

現状では書類種別が「未判定」の場合でも構造化処理が進んでしまい、適切なテンプレートが適用されないまま処理が実行されてしまう。これにより不正確な項目マッピングや無駄なLLM APIコールが発生する。また、LLM判定を導入した現在、マッチキーワードベースの判定根拠は不要となり、LLMの判定理由をユーザーに明示することで判定の透明性と信頼性を向上させる必要がある。

## What Changes

- **構造化処理のゲート制御**: 書類種別が「未判定（unknown）」または未選択の場合、構造化処理（Celeryタスク）を開始せず、ユーザーによる手動選択を待機する。
- **ユーザーによる手動選択後の処理再開**: ユーザーがプルダウンで書類種別を選択し `PATCH /api/documents/{document_id}` を実行した時点で、構造化処理を開始する。
- **判定根拠の表示**: LLM判定時の `reason` フィールドを画面上に表示し、ユーザーが判定の根拠を確認できるようにする。
- **マッチキーワードの非表示**: LLM判定ベースに移行したため、`matched_keywords` は内部ログ用にのみ保持し、UI上では表示しない。

## Impact

- **Affected specs**: 
  - `document-upload`（既存capabilityの修正）
  - `document-structuring`（既存capabilityの修正）
  
- **Affected code**:
  - `backend/app/services/classifier.py`: `ClassificationResult` に `reason` フィールドを追加
  - `backend/app/api/routes/uploads.py`: 「未判定」時にCeleryタスクをキューイングしないロジックを追加
  - `backend/app/workers/tasks.py`: 書類種別が「未判定」の場合は構造化処理をスキップするガード条件を追加
  - `backend/app/schemas/documents.py`: `DocumentUploadResult` に `detection_reason` フィールドを追加
  - `backend/app/services/metadata_store.py`: メタデータストアに `detection_reason` を永続化
  - `frontend/app/page.tsx`: 判定根拠の表示領域を追加、マッチキーワードを非表示化
  - `frontend/lib/types.ts`: TypeScript型定義に `detection_reason` を追加

## Breaking Changes

なし（既存APIのフィールド追加のみ、後方互換性あり）

## Dependencies

- 既存のOpenAI gpt-5 API（LLM判定で `reason` フィールドを返すようschema拡張済み）
- Celeryワーカーとメタデータストア（既存）

