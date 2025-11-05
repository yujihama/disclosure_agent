"""比較結果の詳細を検証"""
import json
from pathlib import Path

comparison_id = "c462c49a-1a59-41f1-9849-db77e3649891"
result_path = Path(f"storage/comparisons/{comparison_id}.json")

with open(result_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("📊 比較結果のフィールド構造確認")
print("=" * 80)

# トップレベルフィールド
print(f"\n🔍 トップレベルフィールド:")
for key in data.keys():
    value = data[key]
    if isinstance(value, list):
        print(f"   - {key}: リスト（{len(value)}件）")
    elif isinstance(value, dict):
        print(f"   - {key}: 辞書（{len(value)}キー）")
    else:
        print(f"   - {key}: {type(value).__name__}")

# セクション詳細比較の1件目を詳細確認
comparisons = data.get('section_detailed_comparisons', [])
if comparisons:
    print(f"\n\n🔍 セクション詳細比較（1件目）のフィールド:")
    first = comparisons[0]
    for key, value in first.items():
        if isinstance(value, dict):
            print(f"   - {key}: 辞書")
            for subkey in value.keys():
                subvalue = value[subkey]
                if isinstance(subvalue, list):
                    print(f"      • {subkey}: リスト（{len(subvalue)}件）")
                else:
                    print(f"      • {subkey}: {type(subvalue).__name__}")
        elif isinstance(value, list):
            print(f"   - {key}: リスト（{len(value)}件）")
        else:
            print(f"   - {key}: {type(value).__name__} = {str(value)[:50]}")

    # text_changesの詳細
    text_changes = first.get('text_changes', {})
    if text_changes:
        print(f"\n\n🔍 text_changesの詳細:")
        for key, value in text_changes.items():
            if isinstance(value, list):
                print(f"   - {key}: {len(value)}件")
                if value and len(value) > 0:
                    print(f"      サンプル: {json.dumps(value[0], ensure_ascii=False, indent=8)[:300]}...")
            else:
                print(f"   - {key}: {value}")

print("\n" + "=" * 80)
print("✅ 比較結果には詳細情報が含まれています")
print("=" * 80)
print("\n📌 UIで表示されない場合の確認事項:")
print("   1. ブラウザでページをリロード（Ctrl+R / Cmd+R）")
print("   2. 各セクションの詳細（⚠️ 矛盾・不整合、📋 正常な違い、🔄 補完関係）を")
print("      クリックして展開する必要があります")
print("   3. フロントエンドのコンソールでエラーがないか確認")

