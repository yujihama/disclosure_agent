#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
どのセクションが処理され、どのセクションがスキップされたかを確認
"""
import json

# 最新の比較結果を読み込み
comparison_id = "4c0c1577-ee65-406b-bd21-348e03364639"
with open(f'backend/storage/comparisons/{comparison_id}.json', 'r', encoding='utf-8') as f:
    comp = json.load(f)

# ドキュメントのメタデータを読み込み
doc1_id = comp['doc1_info']['document_id']
doc2_id = comp['doc2_info']['document_id']

with open(f'backend/storage/metadata/{doc1_id}.json', 'r', encoding='utf-8') as f:
    doc1_data = json.load(f)

with open(f'backend/storage/metadata/{doc2_id}.json', 'r', encoding='utf-8') as f:
    doc2_data = json.load(f)

# セクション情報を取得
sections1 = doc1_data['structured_data']['sections']
sections2 = doc2_data['structured_data']['sections']
common_sections = set(sections1.keys()) & set(sections2.keys())

# 処理されたセクション
processed_sections = {d['section_name'] for d in comp['section_detailed_comparisons']}

# 比較
print(f"共通セクション数: {len(common_sections)}")
print(f"処理されたセクション数: {len(processed_sections)}")
print()

print("【処理されたセクション】")
for i, section in enumerate(sorted(processed_sections), 1):
    print(f"{i}. {section}")

print(f"\n【処理されなかった共通セクション】")
skipped = common_sections - processed_sections
for i, section in enumerate(sorted(skipped), 1):
    print(f"{i}. {section}")

print(f"\n【分析】")
print(f"合計: {len(common_sections)} 共通セクション")
print(f"処理済み: {len(processed_sections)} セクション")
print(f"スキップ: {len(skipped)} セクション")

if skipped:
    print(f"\n【原因調査】")
    print("スキップされたセクションの情報:")
    for section in list(skipped)[:3]:  # 最初の3つを確認
        if section in sections1 and section in sections2:
            s1 = sections1[section]
            s2 = sections2[section]
            print(f"\n- {section}")
            print(f"  Doc1: ページ{s1.get('start_page')}-{s1.get('end_page')}, pages={s1.get('pages')}")
            print(f"  Doc2: ページ{s2.get('start_page')}-{s2.get('end_page')}, pages={s2.get('pages')}")
            print(f"  Doc1が空: {not s1}")
            print(f"  Doc2が空: {not s2}")

