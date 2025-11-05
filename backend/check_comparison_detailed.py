"""比較結果の詳細確認"""
import json
from pathlib import Path

comparison_id = "c462c49a-1a59-41f1-9849-db77e3649891"
result_path = Path(f"storage/comparisons/{comparison_id}.json")

with open(result_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("📊 詳細比較結果の全体確認")
print("=" * 80)

comparisons = data.get('section_detailed_comparisons', [])

# 重要度別カウント
importance_counts = {'high': 0, 'medium': 0, 'low': 0}
contradictions_total = 0
normal_diff_total = 0
complementary_total = 0

for comp in comparisons:
    importance = comp.get('importance', 'unknown')
    if importance in importance_counts:
        importance_counts[importance] += 1
    
    text_changes = comp.get('text_changes', {})
    contradictions_total += len(text_changes.get('contradictions', []))
    normal_diff_total += len(text_changes.get('normal_differences', []))
    complementary_total += len(text_changes.get('complementary_info', []))

print(f"\n📈 重要度別セクション数:")
print(f"   High: {importance_counts['high']}件")
print(f"   Medium: {importance_counts['medium']}件")
print(f"   Low: {importance_counts['low']}件")

print(f"\n📋 検出内容の合計:")
print(f"   矛盾 (contradictions): {contradictions_total}件")
print(f"   通常の差異 (normal_differences): {normal_diff_total}件")
print(f"   補完情報 (complementary_info): {complementary_total}件")

# 矛盾を含むセクションの重要度を確認
print(f"\n⚠️  矛盾を含むセクション:")
for comp in comparisons:
    text_changes = comp.get('text_changes', {})
    contradictions = text_changes.get('contradictions', [])
    if contradictions:
        print(f"\n   セクション: {comp.get('section_name')}")
        print(f"   重要度: {comp.get('importance')} ← ★ 重要！")
        print(f"   矛盾数: {len(contradictions)}件")
        print(f"   サマリー: {comp.get('summary', '')[:150]}...")
        for i, cont in enumerate(contradictions, 1):
            print(f"\n   [{i}] {cont.get('type', 'N/A')}")
            print(f"       {cont.get('description', 'N/A')[:200]}...")

# 全セクションのフィールド構造を確認
print(f"\n\n📦 セクション詳細比較のフィールド構造（1件目）:")
if comparisons:
    first = comparisons[0]
    print(json.dumps(first, indent=2, ensure_ascii=False)[:2000])
    print("...")

print("\n" + "=" * 80)

