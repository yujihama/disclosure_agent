"""extracted_contentの実際の構造を確認"""
import json
from pathlib import Path

doc_id = "cfd11ff5-298a-4d22-bfb3-34c99247250c"
meta_path = Path(f"storage/metadata/{doc_id}.json")

with open(meta_path, 'r', encoding='utf-8') as f:
    meta = json.load(f)

sections = meta.get('structured_data', {}).get('sections', {})

print("=" * 80)
print("🔍 extracted_content の実際の構造")
print("=" * 80)

# extracted_contentを持つセクションを探す
sections_with_content = []
for section_name, section_info in sections.items():
    if 'extracted_content' in section_info:
        sections_with_content.append(section_name)

print(f"\nextracted_contentを持つセクション数: {len(sections_with_content)}")

if sections_with_content:
    # 最初のセクションの構造を詳細確認
    first_section_name = sections_with_content[0]
    first_section = sections[first_section_name]
    extracted = first_section['extracted_content']
    
    print(f"\n📊 サンプルセクション: {first_section_name}")
    print(f"\nextracted_content のキー:")
    for key, value in extracted.items():
        print(f"   - {key}: {type(value).__name__}")
        
        if isinstance(value, list):
            print(f"      → 配列 (長さ: {len(value)})")
            if value and len(value) > 0:
                print(f"      → 最初の要素の型: {type(value[0]).__name__}")
                if isinstance(value[0], dict):
                    print(f"      → 最初の要素のキー: {list(value[0].keys())}")
        elif isinstance(value, dict):
            print(f"      → 辞書 (キー: {list(value.keys())})")
            print(f"      ⚠️ これが問題！配列として扱おうとしている")
    
    # financial_dataの詳細を確認
    if 'financial_data' in extracted:
        print(f"\n🔍 financial_data の詳細:")
        financial = extracted['financial_data']
        print(f"   型: {type(financial).__name__}")
        print(f"   内容: {json.dumps(financial, ensure_ascii=False, indent=4)[:500]}")
    
    # factual_infoの詳細を確認
    if 'factual_info' in extracted:
        print(f"\n🔍 factual_info の詳細:")
        factual = extracted['factual_info']
        print(f"   型: {type(factual).__name__}")
        print(f"   内容: {json.dumps(factual, ensure_ascii=False, indent=4)[:500]}")

print("\n" + "=" * 80)

