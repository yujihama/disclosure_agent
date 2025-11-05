"""エンドポイント確認"""
import requests

endpoints = [
    "http://localhost:8000/",
    "http://localhost:8000/api/",
    "http://localhost:8000/api/documents",
    "http://localhost:8000/api/comparisons",
    "http://localhost:8000/api/health",
]

print("エンドポイント確認:")
for ep in endpoints:
    try:
        r = requests.get(ep, timeout=2)
        print(f"{ep}: {r.status_code}")
    except Exception as e:
        print(f"{ep}: エラー - {e}")

