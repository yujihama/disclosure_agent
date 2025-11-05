"""UIに表示されているデータの構造を確認"""
import json
from pathlib import Path

comparison_id = "c462c49a-1a59-41f1-9849-db77e3649891"
result_path = Path(f"storage/comparisons/{comparison_id}.json")

with open(result_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("🔍 UIに表示されているデータの確認")
print("=" * 80)

comparisons = data.get('section_detailed_comparisons', [])
first = comparisons[0] if comparisons else {}

print(f"\n📊 最初のセクション:")
print(f"   section_name: {first.get('section_name')}")
print(f"   importance: {first.get('importance')}")
print()

# text_changesの構造を確認
text_changes = first.get('text_changes', {})
print(f"🔍 text_changes フィールド:")
for key, value in text_changes.items():
    if isinstance(value, list):
        print(f"   ✓ {key}: {len(value)}件 (配列)")
    else:
        print(f"   • {key}: {type(value).__name__}")

# contradictionsが存在するか
contradictions = text_changes.get('contradictions', [])
if contradictions:
    print(f"\n✅ contradictions フィールドは存在し、{len(contradictions)}件のデータがあります")
    print(f"\nUIで表示されるべき内容:")
    print(f'   <details>')
    print(f'     <summary>⚠️ 矛盾・不整合 ({len(contradictions)})</summary>')
    print(f'     ...')
    print(f'   </details>')
else:
    print(f"\n❌ contradictions フィールドが存在しないか、空配列です")

# 他のフィールドも確認
normal_diff = text_changes.get('normal_differences', [])
complementary = text_changes.get('complementary_info', [])

print(f"\n📋 その他のフィールド:")
print(f"   normal_differences: {len(normal_diff)}件")
print(f"   complementary_info: {len(complementary)}件")

print("\n" + "=" * 80)
print("💡 確認事項")
print("=" * 80)
print("""
1. この比較結果には contradictions などのフィールドが存在します
2. UIでこれらが表示されない場合の原因:
   
   a) Next.js開発サーバーが古いコードを使用している
      → フロントエンドのターミナルで Ctrl+C で停止してから
         npm run dev で再起動
   
   b) ブラウザのキャッシュが残っている
      → Ctrl+Shift+R (Windows) または Cmd+Shift+R (Mac) で
         強制リロード
   
   c) APIから返されるデータが古い
      → バックエンドは再起動済みなので問題ないはず
   
   d) JavaScriptコンソールにエラーがある
      → ブラウザの開発者ツール (F12) でコンソールを確認
""")

