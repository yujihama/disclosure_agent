"""比較処理の監視"""
import time
import requests
import json
from datetime import datetime

comparison_id = "c462c49a-1a59-41f1-9849-db77e3649891"
base_url = "http://localhost:8002/api"

print("=" * 80)
print("📊 比較処理の進捗を監視中")
print("=" * 80)
print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"比較ID: {comparison_id}")
print(f"モード: 整合性チェック（統合報告書 vs 有価証券報告書）")
print("=" * 80)
print()

last_status = None
start_time = time.time()

while True:
    elapsed = time.time() - start_time
    
    try:
        # ステータスを確認
        response = requests.get(
            f"{base_url}/comparisons/{comparison_id}/status",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            if status != last_status:
                print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] ステータス: {status}")
                
                # 進捗情報があれば表示
                if "current_section" in data:
                    print(f"   現在のセクション: {data['current_section']}")
                if "completed_sections" in data and "total_sections" in data:
                    completed = data['completed_sections']
                    total = data['total_sections']
                    pct = (completed / total * 100) if total > 0 else 0
                    print(f"   進捗: {completed}/{total} ({pct:.1f}%)")
                
                last_status = status
            
            # 完了チェック
            if status == "completed":
                print(f"\n✅ [{datetime.now().strftime('%H:%M:%S')}] 比較処理が完了しました！")
                print(f"   経過時間: {elapsed/60:.1f}分")
                
                # 結果を取得
                result_response = requests.get(
                    f"{base_url}/comparisons/{comparison_id}",
                    timeout=10
                )
                
                if result_response.status_code == 200:
                    result = result_response.json()
                    print(f"\n📊 比較結果サマリー:")
                    print(f"   比較モード: {result.get('mode')}")
                    print(f"   セクションマッピング数: {len(result.get('section_mappings', []))}")
                    print(f"   詳細比較セクション数: {len(result.get('section_detailed_comparisons', []))}")
                    
                    # extracted_content使用の確認
                    detailed = result.get('section_detailed_comparisons', [])
                    if detailed:
                        first = detailed[0]
                        print(f"\n   最初のセクション例:")
                        print(f"     セクション名: {first.get('section_name')}")
                        print(f"     重要度: {first.get('importance')}")
                        print(f"     サマリー: {first.get('summary', '')[:100]}...")
                
                break
            
            elif status == "failed":
                print(f"\n⚠️  比較処理が失敗しました")
                print(f"   エラー: {data.get('error', 'N/A')}")
                break
        
        else:
            print(f"[{elapsed:.0f}s] ステータス取得エラー: {response.status_code}")
    
    except Exception as e:
        print(f"[{elapsed:.0f}s] エラー: {e}")
    
    time.sleep(5)
    
    # 最大30分でタイムアウト
    if elapsed > 1800:
        print("\n⏱️ タイムアウト（30分）")
        break

print("\n" + "=" * 80)
print("監視完了")
print("=" * 80)

