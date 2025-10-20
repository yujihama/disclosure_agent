# バックエンドサービスの起動スクリプト

Write-Host "仮想環境をアクティブ化しています..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host "`nCeleryワーカーをバックグラウンドで起動しています..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\.venv\Scripts\Activate.ps1; celery -A backend.app.workers.celery_app worker --loglevel=info --pool=solo"

Write-Host "`n5秒待機中..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "`nバックエンドサーバーを起動しています..." -ForegroundColor Cyan
Write-Host "終了するには Ctrl+C を押してください`n" -ForegroundColor Yellow

cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

