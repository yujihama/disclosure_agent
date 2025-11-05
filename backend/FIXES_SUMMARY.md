# UI修正サマリー

## 修正内容

### 1. 矛盾検出時の重要度判定修正 ✅

**問題**: 矛盾が5件検出されているのに、全て`medium`で、`high`が0件

**修正箇所**: `backend/app/services/comparison_engine.py` (行1734-1746)

```python
# 重要度の判定（矛盾がある場合は自動的にhighに昇格）
importance = result.get("importance", "medium")
importance_reason = result.get("importance_reason", "")

# 矛盾検出時は必ずhigh importanceに設定
contradictions = text_changes.get("contradictions", [])
if contradictions and len(contradictions) > 0:
    importance = "high"
    if not importance_reason:
        importance_reason = f"矛盾が{len(contradictions)}件検出されました"
    else:
        importance_reason = f"矛盾が{len(contradictions)}件検出されました。{importance_reason}"
```

**効果**: 矛盾を含むセクションは自動的に`high`重要度に設定されるため、UIの"High Priority"フィルターで正しく表示されます。

---

### 2. extracted_contentの表示追加 ✅

**問題**: UI上でextracted_contentが表示されていない

**修正箇所**: `frontend/app/page.tsx` (行99-190)

**追加機能**:
- 各セクションをクリックすると、抽出された構造化情報が表示される
- **財務指標・数値情報** 💰 (financial_data)
  - 項目名、数値、単位、期間
- **会計処理上のコメント** 📝 (accounting_notes)
  - トピック、内容
- **事実情報** 📊 (factual_info)
  - カテゴリ、項目、値
- **主張・メッセージ** 💬 (messages)
  - メッセージタイプ、内容

**効果**: ドキュメント詳細画面の「Detected Sections」セクションで、各セクションをクリックするとextracted_contentが表示されます。

---

### 3. processing_statusスキーマ修正 ✅

**問題**: Pydanticバリデーションエラー（`extracting_section_content`が定義されていない）

**修正箇所**: 
- `backend/app/schemas/documents.py` (行50)
- `frontend/app/page.tsx` (行287)

**追加内容**:
- バックエンドスキーマに`"extracting_section_content"`を追加
- フロントエンドに日本語ラベル「セクション情報抽出中」を追加

**効果**: ドキュメント処理中のステータスが正しく表示されます。

---

## 比較結果の詳細表示について

**現状**: 比較結果のUI（Detailed Comparisons）には、すでに以下の情報が実装されています：

### 整合性チェック(consistency_check)モードの場合:
1. **⚠️ 矛盾・不整合** (contradictions)
   - 種類(type)
   - 説明(description)
   - 影響(impact)

2. **📋 書類の性質による正常な違い** (normal_differences)
   - 側面(aspect)
   - 書類1のアプローチ(doc1_approach)
   - 書類2のアプローチ(doc2_approach)
   - 理由(reason)

3. **🔄 相互補完関係** (complementary_info)
   - トピック(topic)
   - 書類1の貢献(doc1_contribution)
   - 書類2の貢献(doc2_contribution)
   - 関係性(relationship)

これらの情報は`<details>`タグで折りたたまれているため、**セクションをクリックして展開する必要があります**。

---

## 適用方法

1. Dockerコンテナを再起動:
```bash
docker compose restart backend
```

2. 既存の比較結果を再実行:
```bash
# 既存の比較結果には修正が反映されないため、再度比較を実行
```

3. ブラウザでページをリロード（Ctrl+R / Cmd+R）

---

## 確認事項

### バックエンド
- [x] 矛盾検出時の重要度判定を修正
- [x] processing_statusスキーマを更新

### フロントエンド
- [x] extracted_contentの表示機能を追加
- [x] processing_statusラベルを追加

### 次回の比較処理で確認
- [ ] High Priority = 矛盾を含むセクション数（5件）
- [ ] ドキュメント詳細でextracted_contentが表示される
- [ ] 比較詳細で矛盾・差異・補完情報が表示される（展開必要）

