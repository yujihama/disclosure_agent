"""セクション情報抽出の監視スクリプト（リアルタイム更新）"""
import time
import re
import json
from pathlib import Path
from datetime import datetime

doc_id1 = "151fc1d0-86f4-4ea4-8b1c-921d74b42cd7"
doc_id2 = "cfd11ff5-298a-4d22-bfb3-34c99247250c"

print("=" * 80)
print("📊 セクション情報抽出 - リアルタイム監視")
print("=" * 80)
print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"ドキュメント1: {doc_id1}")
print(f"ドキュメント2: {doc_id2}")
print("=" * 80)
print()

last_progress = None
last_message = None
check_count = 0
start_time = time.time()

try:
    while True:
        check_count += 1
        elapsed = time.time() - start_time
        
        # Dockerログから進捗を取得（エラーハンドリング付き）
        import subprocess
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", "10", "disclosure_celery_worker"],
                capture_output=True,
                timeout=5
            )
            
            # バイナリデータをデコード（エラーを無視）
            logs = result.stdout.decode('utf-8', errors='ignore') + \
                   result.stderr.decode('utf-8', errors='ignore')
            
            # 進捗パターンを検索
            progress_matches = re.findall(r'\[(\d+)/(\d+)\]', logs)
            
            if progress_matches:
                current, total = progress_matches[-1]
                current = int(current)
                total = int(total)
                progress_text = f"{current}/{total}"
                
                if progress_text != last_progress:
                    progress_pct = (current / total) * 100
                    
                    # 推定残り時間
                    if current > 0:
                        avg_time = elapsed / current
                        remaining = avg_time * (total - current)
                        remaining_min = remaining / 60
                        
                        print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] "
                              f"進捗: {current}/{total} ({progress_pct:.1f}%) | "
                              f"経過: {elapsed/60:.1f}分 | "
                              f"推定残り: {remaining_min:.1f}分")
                    
                    last_progress = progress_text
            
            # 完了メッセージを検索
            if "Section content extraction completed" in logs:
                print(f"\n✅ セクション情報抽出が完了しました！（経過時間: {elapsed/60:.1f}分）")
                break
            
            # エラーメッセージを検索
            error_matches = re.findall(r'ERROR.*', logs)
            for error in error_matches:
                if error != last_message:
                    print(f"⚠️  エラー検出: {error[:100]}")
                    last_message = error
        
        except subprocess.TimeoutExpired:
            print(f"[{check_count}] Dockerログ取得タイムアウト...")
        except Exception as e:
            print(f"[{check_count}] ログ取得エラー: {e}")
        
        # 5秒ごとにチェック
        time.sleep(5)
        
        # 最大30分でタイムアウト
        if elapsed > 1800:
            print("\n⏱️ タイムアウト（30分）")
            break

except KeyboardInterrupt:
    print("\n\n⚠️ 監視を中断しました")
    print(f"経過時間: {elapsed/60:.1f}分")

print("\n" + "=" * 80)
print("📁 ファイル作成状況を確認中...")
print("=" * 80)

# ファイルの存在確認
for i, doc_id in enumerate([doc_id1, doc_id2], 1):
    meta_path = Path(f"storage/metadata/{doc_id}.json")
    if meta_path.exists():
        print(f"\n✅ ドキュメント{i} - ファイル作成済み")
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            print(f"   ファイル名: {meta.get('filename', 'N/A')}")
            print(f"   ステータス: {meta.get('processing_status', 'N/A')}")
            print(f"   書類種別: {meta.get('detected_type_label', 'N/A')}")
            
            sections = meta.get('structured_data', {}).get('sections', {})
            sections_with_content = sum(
                1 for s in sections.values() if 'extracted_content' in s
            )
            
            print(f"   セクション数: {len(sections)}")
            print(f"   extracted_content: {sections_with_content}/{len(sections)} セクション")
            
        except Exception as e:
            print(f"   ⚠️ メタデータ読み込みエラー: {e}")
    else:
        print(f"\n⏳ ドキュメント{i} - ファイル未作成")

print("\n" + "=" * 80)
print("監視完了")
print("=" * 80)

