"""比較結果の重要度を確認"""
import json
from pathlib import Path
import glob

# 最新の比較結果ファイルを取得
comp_files = sorted(glob.glob("backend/storage/comparisons/*.json"), key=lambda x: Path(x).stat().st_mtime, reverse=True)
if not comp_files:
    print("比較結果ファイルが見つかりません")
    exit(1)

latest_file = comp_files[0]
print(f"最新の比較結果ファイル: {Path(latest_file).name}\n")

with open(latest_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 矛盾を含むセクションを確認
sections_with_contradictions = []
for s in data['section_detailed_comparisons']:
    contradictions = s['text_changes'].get('contradictions', [])
    if contradictions:
        sections_with_contradictions.append({
            'name': s['section_name'],
            'importance': s['importance'],
            'contradictions_count': len(contradictions)
        })

print(f"矛盾を含むセクション数: {len(sections_with_contradictions)}\n")

for item in sections_with_contradictions[:5]:
    print(f"- セクション: {item['name']}")
    print(f"  重要度: {item['importance']}")
    print(f"  矛盾数: {item['contradictions_count']}件")
    print()

# サマリ
high_count = sum(1 for s in data['section_detailed_comparisons'] if s['importance'] == 'high')
medium_count = sum(1 for s in data['section_detailed_comparisons'] if s['importance'] == 'medium')
low_count = sum(1 for s in data['section_detailed_comparisons'] if s['importance'] == 'low')

print("=" * 60)
print(f"重要度サマリ:")
print(f"  High: {high_count}件")
print(f"  Medium: {medium_count}件")
print(f"  Low: {low_count}件")
print("=" * 60)

