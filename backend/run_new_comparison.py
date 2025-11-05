"""新しい比較を実行して修正を確認"""
import requests
import json
import time

doc_ids = [
    '151fc1d0-86f4-4ea4-8b1c-921d74b42cd7',  # 統合報告書
    'cfd11ff5-298a-4d22-bfb3-34c99247250c',  # 有価証券報告書
]

print("=" * 80)
print("🔄 新しい比較処理を実行（修正を確認）")
print("=" * 80)
print()

# 比較リクエスト
response = requests.post(
    "http://localhost:8002/api/comparisons",
    json={"document_ids": doc_ids},
    timeout=10
)

if response.status_code == 202:
    result = response.json()
    comparison_id = result.get("comparison_id")
    print(f"✅ 比較処理が開始されました")
    print(f"   比較ID: {comparison_id}")
    print()
    
    # ステータス確認
    print("⏳ 処理完了を待機中...")
    for i in range(60):  # 最大5分待機
        time.sleep(5)
        status_response = requests.get(
            f"http://localhost:8002/api/comparisons/{comparison_id}/status",
            timeout=5
        )
        
        if status_response.status_code == 200:
            status_data = status_response.json()
            status = status_data.get("status")
            
            if status == "completed":
                print(f"\n✅ 処理完了！")
                
                # 結果を取得
                result_response = requests.get(
                    f"http://localhost:8002/api/comparisons/{comparison_id}",
                    timeout=10
                )
                
                if result_response.status_code == 200:
                    comparison_data = result_response.json()
                    
                    # 重要度カウント
                    comparisons = comparison_data.get('section_detailed_comparisons', [])
                    high_count = sum(1 for c in comparisons if c.get('importance') == 'high')
                    medium_count = sum(1 for c in comparisons if c.get('importance') == 'medium')
                    low_count = sum(1 for c in comparisons if c.get('importance') == 'low')
                    
                    print()
                    print("=" * 80)
                    print("📊 重要度別セクション数（修正後）")
                    print("=" * 80)
                    print(f"   🔴 High: {high_count}件")
                    print(f"   🟡 Medium: {medium_count}件")
                    print(f"   ⚪ Low: {low_count}件")
                    print()
                    
                    # 矛盾を含むセクション
                    sections_with_contradictions = []
                    for comp in comparisons:
                        contradictions = comp.get('text_changes', {}).get('contradictions', [])
                        if contradictions:
                            sections_with_contradictions.append({
                                'name': comp.get('section_name'),
                                'importance': comp.get('importance'),
                                'contradictions_count': len(contradictions)
                            })
                    
                    if sections_with_contradictions:
                        print("⚠️  矛盾を含むセクション:")
                        for section in sections_with_contradictions:
                            print(f"   • {section['name']}")
                            print(f"     重要度: {section['importance']} (矛盾: {section['contradictions_count']}件)")
                    
                    print()
                    print("=" * 80)
                    print("✅ 修正確認完了")
                    print("=" * 80)
                    print()
                    print(f"📌 UIで確認:")
                    print(f"   1. ブラウザをリロード（Ctrl+R / Cmd+R）")
                    print(f"   2. Detailed Comparisons セクションで")
                    print(f"      「High」フィルターをクリック → {high_count}件表示されるはず")
                    print(f"   3. 各セクションの詳細を展開して確認")
                    
                break
            
            elif status == "failed":
                print(f"\n⚠️  処理失敗")
                break
            
            elif i % 6 == 0:  # 30秒ごとに表示
                print(f"   [{i*5}秒] ステータス: {status}")
    
    else:
        print("\n⏱️ タイムアウト（5分）")
else:
    print(f"⚠️  エラー: {response.status_code}")
    print(response.text)

