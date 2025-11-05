"""ドキュメント2の処理監視"""
import time
import re
from datetime import datetime

doc_id = "151fc1d0-86f4-4ea4-8b1c-921d74b42cd7"

print("=" * 80)
print("📊 ドキュメント2の処理を監視中")
print("=" * 80)
print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"ドキュメントID: {doc_id}")
print("=" * 80)
print()

last_stage = None
last_progress = None
start_time = time.time()

try:
    while True:
        elapsed = time.time() - start_time
        
        import subprocess
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", "15", "disclosure_celery_worker"],
                capture_output=True,
                timeout=5
            )
            
            logs = result.stdout.decode('utf-8', errors='ignore') + \
                   result.stderr.decode('utf-8', errors='ignore')
            
            # ステージを確認
            if "Starting section detection" in logs and last_stage != "section_detection":
                print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] セクション検出を開始...")
                last_stage = "section_detection"
            
            elif "Section detection completed" in logs and last_stage != "section_completed":
                # セクション数を抽出
                match = re.search(r'(\d+) sections detected', logs)
                if match:
                    section_count = match.group(1)
                    print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] セクション検出完了: {section_count}セクション")
                last_stage = "section_completed"
            
            elif "Starting section content extraction" in logs and last_stage != "content_extraction":
                print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] セクション情報抽出を開始...")
                last_stage = "content_extraction"
            
            # 進捗を確認
            progress_matches = re.findall(r'\[(\d+)/(\d+)\]', logs)
            if progress_matches and last_stage == "content_extraction":
                current, total = progress_matches[-1]
                progress_text = f"{current}/{total}"
                
                if progress_text != last_progress:
                    current = int(current)
                    total = int(total)
                    progress_pct = (current / total) * 100
                    print(f"   📈 進捗: {current}/{total} ({progress_pct:.1f}%)")
                    last_progress = progress_text
            
            # 完了を確認
            if "Section content extraction completed" in logs and doc_id in logs:
                print(f"\n✅ [{datetime.now().strftime('%H:%M:%S')}] セクション情報抽出が完了！")
                print(f"   経過時間: {elapsed/60:.1f}分")
                
                # 統計を抽出
                stats_match = re.search(r'成功=(\d+).*スキップ=(\d+)', logs)
                if stats_match:
                    success = stats_match.group(1)
                    skipped = stats_match.group(2)
                    print(f"   成功: {success}件、スキップ: {skipped}件")
                break
            
            if "Successfully structured document" in logs and doc_id in logs:
                print(f"\n🎉 [{datetime.now().strftime('%H:%M:%S')}] ドキュメント処理が完了しました！")
                print(f"   総経過時間: {elapsed/60:.1f}分")
                break
        
        except Exception as e:
            pass
        
        time.sleep(5)
        
        # 最大30分でタイムアウト
        if elapsed > 1800:
            print("\n⏱️ タイムアウト（30分）")
            break

except KeyboardInterrupt:
    print("\n⚠️ 監視を中断しました")

print("\n" + "=" * 80)
print("監視完了")
print("=" * 80)

