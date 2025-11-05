"""修正が正しく動作しているか確認"""
import json

# 新しい比較結果ファイルを確認
file_path = "backend/storage/comparisons/51c58dbf-0a2f-418c-9135-c660f6b643fe.json"

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("🔍 新しい比較結果の検証")
print("=" * 70)
print(f"\nComparison ID: {data['comparison_id']}")
print(f"作成日時: {data['created_at']}")
print(f"総セクション数: {len(data['section_detailed_comparisons'])}\n")

# 矛盾を含むセクションを抽出
sections_with_contradictions = [
    s for s in data['section_detailed_comparisons']
    if s['text_changes'].get('contradictions')
]

print(f"✅ 矛盾検出セクション数: {len(sections_with_contradictions)}\n")

# 重要度の分布を確認
high_count = 0
medium_count = 0
low_count = 0

for s in sections_with_contradictions:
    if s['importance'] == 'high':
        high_count += 1
    elif s['importance'] == 'medium':
        medium_count += 1
    else:
        low_count += 1

print("重要度の分布:")
print(f"  🔴 High: {high_count}件")
print(f"  🟡 Medium: {medium_count}件")
print(f"  🟢 Low: {low_count}件\n")

if high_count == len(sections_with_contradictions):
    print("🎉 成功！すべての矛盾検出セクションがHigh重要度に設定されています！\n")
else:
    print(f"⚠️ 一部のセクションがMedium/Low重要度のままです\n")

# 詳細表示
print("=" * 70)
print("矛盾検出セクション詳細:")
print("=" * 70)

for i, s in enumerate(sections_with_contradictions, 1):
    print(f"\n[{i}] {s['section_name']}")
    print(f"    重要度: {s['importance']}")
    print(f"    矛盾数: {len(s['text_changes'].get('contradictions', []))}件")
    print(f"    理由: {s.get('importance_reason', 'なし')[:150]}...")

# 全体サマリ
print("\n" + "=" * 70)
print("全体サマリ:")
print("=" * 70)

all_sections = data['section_detailed_comparisons']
all_high = sum(1 for s in all_sections if s['importance'] == 'high')
all_medium = sum(1 for s in all_sections if s['importance'] == 'medium')
all_low = sum(1 for s in all_sections if s['importance'] == 'low')

print(f"総セクション数: {len(all_sections)}")
print(f"  High: {all_high}件")
print(f"  Medium: {all_medium}件")
print(f"  Low: {all_low}件")
print("=" * 70)

