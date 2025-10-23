# Celeryキュー管理ガイド

## 問題: 起動時に自動的にタスクが実行される

### 症状
`restart_services.ps1`でCeleryワーカーを起動した瞬間に、ボタンを押していないのに以前の比較タスクが自動的に実行される。

### 原因
Celeryは**永続的なメッセージキュー（Redis）**を使用しているため、以下の流れで問題が発生します：

1. フロントエンドから比較リクエストが送信される
2. Celeryワーカーが処理する前に停止（`Ctrl+C`でスクリプトを終了など）
3. タスクがRedisキュー内に残ったまま
4. ワーカーを再起動すると、残っているタスクが即座に処理される

これはCeleryの**正常な動作**であり、本番環境では望ましい挙動です（タスクの永続性を保証）。しかし、開発中は混乱を招く可能性があります。

## 解決策

### 方法1: 起動時に選択的にクリア（推奨）

標準の起動スクリプトを使用：

```powershell
.\backend\restart_services.ps1
```

起動時に以下のプロンプトが表示されます：

```
Redisキューをクリアしますか？ (前回の未処理タスクを削除)
  [Y] はい (推奨: 開発時)
  [N] いいえ (本番環境用: タスクを保持)
選択してください [Y/N]:
```

- **開発時**: `Y` を選択してキューをクリア
- **本番環境**: `N` を選択してタスクを保持

### 方法2: 常に自動クリア（開発専用）

確認なしで常にキューをクリアする起動スクリプト：

```powershell
.\backend\restart_services_clean.ps1
```

このスクリプトは起動時に必ずキューをクリアします（開発専用）。

### 方法3: 手動でキューをクリア

サービスを起動せずにキューだけをクリアする場合：

```powershell
.\backend\clear_queue.ps1
```

### 方法4: Celeryコマンドを直接使用

```powershell
# 仮想環境をアクティブ化
.\.venv\Scripts\Activate.ps1

# キューをクリア
celery -A backend.app.workers.celery_app purge -f
```

## 本番環境での注意事項

**本番環境ではキューをクリアしないでください！**

- 未処理のタスクは意図的にキューに保存されています
- ワーカーが一時的にダウンしても、再起動後にタスクを処理できます
- タスクの永続性は重要なフォールトトレランス機能です

## Celery設定の詳細

### タスク有効期限

`backend/app/workers/celery_app.py`で以下の設定が行われています：

```python
app.conf.update(
    result_expires=3600,  # 結果の有効期限: 1時間
    task_reject_on_worker_lost=True,  # ワーカーロスト時にタスクを拒否
    task_acks_late=True,  # タスク完了後にACKを送信
)
```

- **result_expires**: タスク結果（Redis内）は1時間後に自動削除されます
- **task_acks_late**: タスクが完全に完了するまでキューから削除されません
- **task_reject_on_worker_lost**: ワーカーがクラッシュした場合、タスクは再キューイングされます

### キューの確認

Redisに接続してキューの状態を確認：

```powershell
# Redisクライアントで接続
docker exec -it <redis-container> redis-cli

# キューの長さを確認
LLEN celery

# キューの内容を確認（最初の10件）
LRANGE celery 0 9

# すべてのキーを表示
KEYS *
```

## トラブルシューティング

### キューのクリアに失敗する

**症状**: `celery purge`コマンドが失敗する

**原因**: Redisが起動していない

**解決策**:
```powershell
# Redisを起動（Docker使用の場合）
docker run -d -p 6379:6379 redis:7-alpine

# またはdocker-composeで
docker compose up -d redis
```

### タスクが重複して実行される

**症状**: 同じタスクが複数回実行される

**原因**: 
- 複数のワーカーが起動している
- `task_acks_late=True`により、タスクが再試行されている

**解決策**:
```powershell
# すべてのCeleryプロセスを確認
Get-Process | Where-Object {$_.ProcessName -like "*celery*"}

# 不要なワーカーを停止
Stop-Process -Name celery -Force
```

### キューに大量のタスクが溜まっている

**症状**: キューに数百〜数千のタスクがある

**解決策**:
```powershell
# キューをパージ（すべて削除）
celery -A backend.app.workers.celery_app purge -f

# またはRedisを完全にリセット
docker restart <redis-container>
```

## ベストプラクティス

### 開発時

1. ✅ `restart_services.ps1`起動時に`Y`を選択してキューをクリア
2. ✅ または`restart_services_clean.ps1`を使用
3. ✅ 作業終了時は`Ctrl+C`で正しく終了

### テスト時

1. ✅ テスト前にキューをクリア
2. ✅ テスト後に結果を確認
3. ✅ テスト用データは定期的に削除

### 本番環境

1. ❌ キューをクリアしない
2. ✅ タスクの永続性を活用
3. ✅ ワーカーの監視とロギングを設定
4. ✅ タスクのタイムアウトと再試行ポリシーを設定

## 参考リンク

- [Celery公式ドキュメント](https://docs.celeryq.dev/)
- [Redis公式ドキュメント](https://redis.io/documentation)
- [プロジェクトの開発ガイド](../openspec/project.md)

