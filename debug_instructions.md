# 詳細比較情報が表示されない問題のデバッグ手順

## 確認事項

### 1. ブラウザの開発者ツール（F12）を開く

### 2. コンソールタブを確認
- エラーメッセージが表示されていないか確認

### 3. ネットワークタブを確認
1. ページをリロード
2. `/api/comparisons/{comparison_id}` のリクエストを見つける
3. レスポンスタブを開いて、以下を確認：
   - `section_detailed_comparisons` が存在するか
   - 配列の要素数（17個あるはず）
   - 各要素に `section_name`, `summary`, `importance` などのフィールドがあるか

### 4. Elements タブで DOM を確認
1. ページ上で「Detailed Comparisons」というテキストを検索
2. その親要素を確認
3. その下に `<div className="mt-4 space-y-3">` というdiv要素があるか
4. その中に個別のセクション要素（`<div key={idx} className="rounded-lg..."`）があるか

### 5. 比較結果のJSONファイルを直接確認
Docker コンテナ内の最新ファイルを確認：
```powershell
docker exec disclosure_backend cat /app/storage/comparisons/71a751f4-784e-43a0-a6fc-1100ff2ebaed.json | ConvertFrom-Json | Select-Object -ExpandProperty section_detailed_comparisons | Measure-Object
```

## 考えられる原因

1. **フィルタリングの問題**: `importanceFilter` または `searchQuery` の状態が意図しない値になっている
2. **レンダリングの問題**: 要素は生成されているがCSSで非表示になっている
3. **データ変換の問題**: APIレスポンスからコンポーネントへのデータ受け渡しで問題が発生している

## 次のステップ

上記の確認結果を教えていただければ、より正確に原因を特定できます。

