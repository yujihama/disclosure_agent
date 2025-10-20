#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
セクション名のミスマッチを調査
"""
import json

# ドキュメントのメタデータを読み込み
doc1_id = "a4fe6727-a076-421d-ac03-ae0b1996ee93"
doc2_id = "0a53a622-adbe-475c-b06e-f0f83fdc9777"

with open(f'backend/storage/metadata/{doc1_id}.json', 'r', encoding='utf-8') as f:
    doc1_data = json.load(f)

with open(f'backend/storage/metadata/{doc2_id}.json', 'r', encoding='utf-8') as f:
    doc2_data = json.load(f)

# セクション情報を取得
sections1 = doc1_data['structured_data']['sections']
sections2 = doc2_data['structured_data']['sections']

common_sections = sorted(set(sections1.keys()) & set(sections2.keys()))

print(f"【共通セクション一覧】({len(common_sections)}個)")
print()

for i, section in enumerate(common_sections, 1):
    s1 = sections1[section]
    s2 = sections2[section]
    print(f"{i}. {section}")
    print(f"   Doc1: ページ{s1['start_page']}-{s1['end_page']} ({len(s1['pages'])}ページ, {s1['char_count']}文字)")
    print(f"   Doc2: ページ{s2['start_page']}-{s2['end_page']} ({len(s2['pages'])}ページ, {s2['char_count']}文字)")
    
    # セクションが「提出会社の状況」で始まっているか確認
    if section.startswith("提出会社の状況"):
        print(f"   ★ 提出会社の状況系セクション（親なし）")
    elif "提出会社の状況" in section:
        print(f"   ★ 企業情報配下の提出会社の状況")
    
    print()

