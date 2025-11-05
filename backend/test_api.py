"""API接続テストと比較実行"""
import requests
import json

doc_ids = [
    '151fc1d0-86f4-4ea4-8b1c-921d74b42cd7',  # 統合報告書
    'cfd11ff5-298a-4d22-bfb3-34c99247250c',  # 有価証券報告書
]

print("=" * 80)
print("📊 比較処理を実行します")
print("=" * 80)
print(f"ドキュメント1: {doc_ids[0]} (統合報告書)")
print(f"ドキュメント2: {doc_ids[1]} (有価証券報告書)")
print()

# APIサーバー稼働確認
try:
    health = requests.get("http://localhost:8000/api/health", timeout=2)
    print(f"✅ APIサーバー稼働中 ({health.status_code})")
except Exception as e:
    print(f"⚠️  APIサーバーに接続できません: {e}")
    exit(1)

# 比較リクエスト
print("\n比較処理を開始...")
try:
    response = requests.post(
        "http://localhost:8000/api/comparisons",
        json={"document_ids": doc_ids},
        timeout=10
    )
    
    print(f"ステータスコード: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if response.status_code == 202:
        comparison_id = result.get("comparison_id")
        print(f"\n✅ 比較処理が開始されました！")
        print(f"   比較ID: {comparison_id}")
        print(f"\n進捗確認: GET /api/comparisons/{comparison_id}/status")
    else:
        print("\n⚠️  エラーが発生しました")
        
except Exception as e:
    print(f"エラー: {e}")

print("=" * 80)

