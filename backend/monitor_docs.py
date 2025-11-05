"""ドキュメント処理の監視スクリプト"""
import time
import json
from pathlib import Path

doc_ids = ['151fc1d0-86f4-4ea4-8b1c-921d74b42cd7', 'cfd11ff5-298a-4d22-bfb3-34c99247250c']
max_wait = 120  # 最大2分待機

print("📊 ドキュメント処理を監視中...")
print(f"ドキュメントID:")
for doc_id in doc_ids:
    print(f"  - {doc_id}")

start = time.time()

while time.time() - start < max_wait:
    files_exist = [Path(f'storage/metadata/{doc_id}.json').exists() for doc_id in doc_ids]
    
    if all(files_exist):
        elapsed = time.time() - start
        print(f"\n✅ 両方のファイルが作成されました！（{elapsed:.1f}秒後）")
        
        # ファイルの詳細を表示
        for i, doc_id in enumerate(doc_ids):
            try:
                with open(f'storage/metadata/{doc_id}.json', 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    print(f"\nドキュメント {i+1}:")
                    print(f"  ファイル名: {meta.get('filename', 'N/A')}")
                    print(f"  ステータス: {meta.get('processing_status', 'N/A')}")
                    print(f"  書類種別: {meta.get('detected_type', 'N/A')}")
                    
                    sections = meta.get('structured_data', {}).get('sections', {})
                    print(f"  セクション数: {len(sections)}")
                    
                    # extracted_content の確認
                    sections_with_content = sum(
                        1 for s in sections.values() if 'extracted_content' in s
                    )
                    print(f"  extracted_content あり: {sections_with_content}/{len(sections)}")
            except Exception as e:
                print(f"  エラー: {e}")
        
        break
    
    elapsed = int(time.time() - start)
    if elapsed % 10 == 0 and elapsed > 0:
        print(f"⏳ {elapsed}秒経過... ファイル1: {files_exist[0]}, ファイル2: {files_exist[1]}")
    
    time.sleep(2)
else:
    print(f"\n⏱️ タイムアウト（{max_wait}秒）")
    print("ファイルはまだ作成されていません。")

