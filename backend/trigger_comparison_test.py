"""新しい比較をトリガーしてテスト"""
import requests
import json
import time

# ドキュメントIDを指定
doc_id_1 = "151fc1d0-86f4-4ea4-8b1c-921d74b42cd7"  # fh_2025_allj_a4.pdf (統合報告書)
doc_id_2 = "cfd11ff5-298a-4d22-bfb3-34c99247250c"  # 富士フィルム_有価証券報告書.pdf

# 比較リクエストを送信
print("🚀 新しい比較をトリガーします...")
print(f"   Doc1: {doc_id_1}")
print(f"   Doc2: {doc_id_2}")
print(f"   Mode: consistency_check\n")

response = requests.post(
    "http://localhost:8002/api/comparisons",
    json={
        "document_ids": [doc_id_1, doc_id_2],
        "comparison_mode": "consistency_check"
    }
)

if response.status_code in [200, 202]:
    result = response.json()
    comp_id = result['comparison_id']
    print(f"✅ 比較がトリガーされました！")
    print(f"   Comparison ID: {comp_id}\n")
    
    # 完了を待つ
    print("⏳ 比較処理が完了するまで待機中...")
    for i in range(60):  # 最大5分待機
        time.sleep(5)
        
        # 結果ファイルが生成されたか確認
        import glob
        from pathlib import Path
        comp_files = sorted(glob.glob("backend/storage/comparisons/*.json"), key=lambda x: Path(x).stat().st_mtime, reverse=True)
        
        if comp_files:
            latest_file = comp_files[0]
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if data.get('comparison_id') == comp_id:
                print(f"\n✅ 比較が完了しました！ ({i * 5}秒)")
                
                # 矛盾検出セクションの重要度を確認
                sections_with_contradictions = [
                    s for s in data['section_detailed_comparisons']
                    if s['text_changes'].get('contradictions')
                ]
                
                print(f"\n📊 結果サマリ:")
                print(f"   矛盾検出セクション: {len(sections_with_contradictions)}件")
                
                high_count = sum(1 for s in sections_with_contradictions if s['importance'] == 'high')
                medium_count = sum(1 for s in sections_with_contradictions if s['importance'] == 'medium')
                
                print(f"   - High重要度: {high_count}件")
                print(f"   - Medium重要度: {medium_count}件")
                
                if high_count == len(sections_with_contradictions):
                    print(f"\n🎉 成功！すべての矛盾検出セクションがHigh重要度に設定されています！")
                else:
                    print(f"\n⚠️  問題あり：一部のセクションがMedium重要度のままです")
                    
                    # 詳細表示
                    print(f"\n矛盾検出セクション詳細:")
                    for s in sections_with_contradictions[:3]:
                        print(f"  - {s['section_name']}")
                        print(f"    重要度: {s['importance']}")
                        print(f"    矛盾数: {len(s['text_changes'].get('contradictions', []))}件")
                        print(f"    理由: {s.get('importance_reason', '')[:100]}...")
                        print()
                
                break
        
        if (i + 1) % 6 == 0:
            print(f"   {(i + 1) * 5}秒経過...")
    else:
        print(f"\n⏰ タイムアウト: 5分以内に完了しませんでした")
        
else:
    print(f"❌ エラー: {response.status_code}")
    print(response.text)

