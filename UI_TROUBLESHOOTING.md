# UI表示トラブルシューティング

## 問題の症状
- ドキュメント詳細に「Detected Sections」が表示されない
- Detailed Comparisonsで各カードに詳細ボタンが表示されない
- `<details>`タグで展開できるはずの内容が表示されない

## 原因
Next.js開発サーバーが古いコードをキャッシュしている

## 解決方法

### 1. フロントエンドDockerコンテナを再起動 ✅

```bash
docker compose restart frontend
```

### 2. ブラウザで強制リロード

**Windows/Linux:**
- `Ctrl + Shift + R`

**Mac:**
- `Cmd + Shift + R`

または、ブラウザの開発者ツール(F12)を開いた状態で：
- リロードボタンを右クリック
- 「キャッシュの消去とハード再読み込み」を選択

### 3. ブラウザのキャッシュをクリア

**Chrome/Edge:**
1. F12で開発者ツールを開く
2. Networkタブを選択
3. 「Disable cache」にチェック
4. ページをリロード

### 4. 確認事項

#### a) フロントエンドが起動しているか
```bash
docker ps | grep frontend
```

#### b) フロントエンドのログを確認
```bash
docker compose logs frontend --tail 50
```

起動メッセージ例:
```
✓ Ready in 2.5s
○ Local:        http://localhost:3000
```

#### c) ブラウザのJavaScriptコンソールを確認
1. F12で開発者ツールを開く
2. Consoleタブでエラーがないか確認
3. エラーがある場合は内容をコピー

#### d) APIから正しいデータが返されているか

ブラウザのNetworkタブで確認:
1. F12で開発者ツールを開く
2. Networkタブを選択
3. 比較結果を開く
4. `comparisons` APIリクエストを探す
5. Responseタブで `section_detailed_comparisons[0].text_changes` を確認

期待される構造:
```json
{
  "text_changes": {
    "contradictions": [...],
    "normal_differences": [...],
    "complementary_info": [...]
  }
}
```

## 表示されるべき内容

### ドキュメント詳細ページ

「Detected Sections」セクションで各セクション名をクリックすると:
```
💰 財務指標・数値情報 (X件)
📝 会計処理上のコメント (X件)
📊 事実情報 (X件)
💬 主張・メッセージ (X件)
```

### 比較結果ページ

各セクションカードのサマリーの下に以下のボタンが表示される:
```
⚠️ 矛盾・不整合 (X)
📋 書類の性質による正常な違い (X)
🔄 相互補完関係 (X)
```

クリックすると詳細が展開されます。

## まだ表示されない場合

### 完全リセット

```bash
# 1. フロントエンドのnode_modulesを削除
docker compose down frontend
docker compose up -d frontend

# 2. ブラウザのすべてのキャッシュをクリア
# 設定 > プライバシーとセキュリティ > 閲覧履歴データの削除
# 「キャッシュされた画像とファイル」を選択

# 3. ブラウザを完全に閉じて再起動

# 4. http://localhost:3000 を開く
```

### デバッグ情報の取得

```bash
# フロントエンドのログを取得
docker compose logs frontend > frontend_logs.txt

# バックエンドのログを取得
docker compose logs backend > backend_logs.txt

# コンテナの状態を確認
docker ps > containers_status.txt
```

## 確認済みの事項

- ✅ バックエンドのコードは正しく修正されている
- ✅ フロントエンドのコードは正しく修正されている
- ✅ データ構造は正しい (contradictions等のフィールドが存在)
- ✅ バックエンドは再起動済み
- 🔄 フロントエンドを再起動中...

