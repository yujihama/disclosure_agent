"""比較結果の確認"""
import json
from pathlib import Path

comparison_id = "c462c49a-1a59-41f1-9849-db77e3649891"
result_path = Path(f"storage/comparisons/{comparison_id}.json")

print("=" * 80)
print("📊 比較結果の確認")
print("=" * 80)
print(f"比較ID: {comparison_id}")
print()

if not result_path.exists():
    print("⚠️  比較結果ファイルが見つかりません")
    exit(1)

with open(result_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"✅ 比較モード: {data.get('mode')}")
print(f"✅ セクションマッピング: {len(data.get('section_mappings', []))}件")
print(f"✅ 詳細比較: {len(data.get('section_detailed_comparisons', []))}件")
print()

# ドキュメント情報
doc1_info = data.get('doc1_info', {})
doc2_info = data.get('doc2_info', {})

print("📄 ドキュメント1:")
print(f"   ファイル名: {doc1_info.get('filename')}")
print(f"   書類種別: {doc1_info.get('document_type')}")
print()

print("📄 ドキュメント2:")
print(f"   ファイル名: {doc2_info.get('filename')}")
print(f"   書類種別: {doc2_info.get('document_type')}")
print()

# セクションマッピングのサンプル
mappings = data.get('section_mappings', [])
if mappings:
    print(f"🔗 セクションマッピング例（最初の3件）:")
    for i, mapping in enumerate(mappings[:3], 1):
        print(f"\n   [{i}] セクション1: {mapping.get('section1_name')}")
        print(f"       セクション2: {mapping.get('section2_name')}")
        print(f"       類似度: {mapping.get('similarity_score', 0):.2f}")
        print(f"       マッピング理由: {mapping.get('mapping_reason', 'N/A')[:100]}...")

# 詳細比較のサンプル
comparisons = data.get('section_detailed_comparisons', [])
if comparisons:
    print(f"\n\n📊 詳細比較例（最初の1件）:")
    first = comparisons[0]
    print(f"\n   セクション名: {first.get('section_name')}")
    print(f"   重要度: {first.get('importance')}")
    print(f"   サマリー:")
    print(f"   {first.get('summary', '')[:200]}...")
    
    # text_changesの内容を確認（整合性チェックの場合）
    text_changes = first.get('text_changes', {})
    if text_changes:
        print(f"\n   テキスト変更:")
        for key in ['contradictions', 'normal_differences', 'complementary_info']:
            if key in text_changes and text_changes[key]:
                items = text_changes[key]
                print(f"   - {key}: {len(items)}件")
                if items and len(items) > 0:
                    item_text = str(items[0])
                    print(f"      例: {item_text[:150]}...")

print("\n" + "=" * 80)
print("確認完了")
print("=" * 80)

