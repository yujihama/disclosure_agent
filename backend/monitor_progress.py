"""セクション情報抽出の進捗監視スクリプト"""
import time
import re
from subprocess import run, PIPE

doc_id = "cfd11ff5-298a-4d22-bfb3-34c99247250c"
print(f"📊 セクション情報抽出の進捗を監視中...")
print(f"ドキュメントID: {doc_id}\n")

last_count = 0
start_time = time.time()

while True:
    # Dockerログから最新の進捗を取得
    result = run(
        ["docker", "logs", "--tail", "5", "disclosure_celery_worker"],
        capture_output=True,
        text=True
    )
    
    logs = result.stdout + result.stderr
    
    # 進捗パターンを検索（例: [5/40]）
    matches = re.findall(r'\[(\d+)/(\d+)\]', logs)
    
    if matches:
        current, total = matches[-1]
        current = int(current)
        total = int(total)
        
        if current != last_count:
            elapsed = time.time() - start_time
            progress_pct = (current / total) * 100
            
            # 推定残り時間を計算
            if current > 0:
                avg_time_per_section = elapsed / current
                remaining_sections = total - current
                estimated_remaining = avg_time_per_section * remaining_sections
                
                print(f"⏳ 進捗: {current}/{total} ({progress_pct:.1f}%) | "
                      f"経過: {elapsed/60:.1f}分 | "
                      f"推定残り: {estimated_remaining/60:.1f}分")
            
            last_count = current
            
            if current >= total:
                print(f"\n✅ セクション情報抽出完了！（{elapsed/60:.1f}分）")
                print("次のステップ: structured_dataの保存を待機...")
                break
    
    # 完了メッセージを検索
    if "Section content extraction completed" in logs or "structured" in logs:
        print("\n✅ 処理完了の可能性あり！")
        break
    
    time.sleep(5)

print("\n処理完了を確認中...")
time.sleep(5)

# 最終確認
import json
from pathlib import Path

meta_path = Path(f"storage/metadata/{doc_id}.json")
if meta_path.exists():
    print(f"✅ メタデータファイルが作成されました！")
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
        
    sections = meta.get('structured_data', {}).get('sections', {})
    sections_with_content = sum(
        1 for s in sections.values() if 'extracted_content' in s
    )
    
    print(f"セクション数: {len(sections)}")
    print(f"extracted_content あり: {sections_with_content}/{len(sections)}")
else:
    print("⚠️ メタデータファイルがまだ作成されていません")

