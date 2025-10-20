#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
セクションマッピングとセクション検出の状況を確認
"""
import json

# 2つのドキュメントのメタデータを読み込み
doc1_id = "a4fe6727-a076-421d-ac03-ae0b1996ee93"
doc2_id = "0a53a622-adbe-475c-b06e-f0f83fdc9777"

with open(f'backend/storage/metadata/{doc1_id}.json', 'r', encoding='utf-8') as f:
    doc1_data = json.load(f)

with open(f'backend/storage/metadata/{doc2_id}.json', 'r', encoding='utf-8') as f:
    doc2_data = json.load(f)

# セクション情報を取得
sections1 = doc1_data['structured_data']['sections']
sections2 = doc2_data['structured_data']['sections']

print(f"【ドキュメント1】{doc1_data['filename']}")
print(f"検出セクション数: {len(sections1)}")
print("\nセクション一覧:")
for i, section_name in enumerate(sections1.keys(), 1):
    print(f"{i:2d}. {section_name}")

print(f"\n{'='*80}")
print(f"\n【ドキュメント2】{doc2_data['filename']}")
print(f"検出セクション数: {len(sections2)}")
print("\nセクション一覧:")
for i, section_name in enumerate(sections2.keys(), 1):
    print(f"{i:2d}. {section_name}")

# 共通セクションを確認
common = set(sections1.keys()) & set(sections2.keys())
print(f"\n{'='*80}")
print(f"\n【両方に存在する共通セクション】")
print(f"共通セクション数: {len(common)}")
print("\n一覧:")
for i, section_name in enumerate(sorted(common), 1):
    s1 = sections1[section_name]
    s2 = sections2[section_name]
    print(f"{i:2d}. {section_name}")
    print(f"    Doc1: ページ{s1['start_page']}-{s1['end_page']} ({len(s1['pages'])}ページ), 文字数={s1['char_count']}")
    print(f"    Doc2: ページ{s2['start_page']}-{s2['end_page']} ({len(s2['pages'])}ページ), 文字数={s2['char_count']}")

# Doc1にのみ存在
only_doc1 = set(sections1.keys()) - set(sections2.keys())
print(f"\n{'='*80}")
print(f"\n【ドキュメント1にのみ存在】")
print(f"件数: {len(only_doc1)}")
if only_doc1:
    for i, section_name in enumerate(sorted(only_doc1)[:10], 1):
        print(f"{i:2d}. {section_name}")
    if len(only_doc1) > 10:
        print(f"    ... 他 {len(only_doc1) - 10} 件")

# Doc2にのみ存在
only_doc2 = set(sections2.keys()) - set(sections1.keys())
print(f"\n【ドキュメント2にのみ存在】")
print(f"件数: {len(only_doc2)}")
if only_doc2:
    for i, section_name in enumerate(sorted(only_doc2)[:10], 1):
        print(f"{i:2d}. {section_name}")
    if len(only_doc2) > 10:
        print(f"    ... 他 {len(only_doc2) - 10} 件")

print(f"\n{'='*80}")
print("\n【結論】")
print(f"セクション別詳細差分の対象になるのは: {len(common)} セクション")
print("（両方のドキュメントに存在する共通セクションのみ）")

