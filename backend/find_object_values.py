"""オブジェクト型のvalueを持つデータを探す"""
import json
from pathlib import Path

doc_id = "cfd11ff5-298a-4d22-bfb3-34c99247250c"
meta_path = Path(f"storage/metadata/{doc_id}.json")

with open(meta_path, 'r', encoding='utf-8') as f:
    meta = json.load(f)

sections = meta.get('structured_data', {}).get('sections', {})

print("=" * 80)
print("🔍 オブジェクト型のvalueを含むデータを検索")
print("=" * 80)

found_objects = []

for section_name, section_info in sections.items():
    if 'extracted_content' not in section_info:
        continue
    
    extracted = section_info['extracted_content']
    
    # financial_data をチェック
    for item in extracted.get('financial_data', []):
        if isinstance(item.get('value'), dict):
            found_objects.append({
                'section': section_name,
                'type': 'financial_data',
                'item': item.get('item'),
                'value': item.get('value')
            })
    
    # factual_info をチェック
    for item in extracted.get('factual_info', []):
        if isinstance(item.get('value'), dict):
            found_objects.append({
                'section': section_name,
                'type': 'factual_info',
                'item': item.get('item'),
                'value': item.get('value')
            })

if found_objects:
    print(f"\n⚠️  オブジェクト型のvalueが見つかりました: {len(found_objects)}件\n")
    
    for i, obj in enumerate(found_objects[:5], 1):  # 最初の5件を表示
        print(f"[{i}] セクション: {obj['section']}")
        print(f"    種類: {obj['type']}")
        print(f"    項目: {obj['item']}")
        print(f"    値: {json.dumps(obj['value'], ensure_ascii=False, indent=4)}")
        print()
    
    if len(found_objects) > 5:
        print(f"... 他に {len(found_objects) - 5} 件")
else:
    print("\n✅ オブジェクト型のvalueは見つかりませんでした")

print("\n" + "=" * 80)
print("💡 対応状況")
print("=" * 80)
print("""
オブジェクト型のvalueが含まれる場合、修正後のコードでは:
- JSON.stringify()で文字列化して表示
- より読みやすい表示が必要な場合は、個別に整形可能
""")

