# Celeryワーカーを再起動するスクリプト

Write-Host "既存のCeleryワーカープロセスを停止しています..." -ForegroundColor Yellow

# Celeryプロセスを探して停止
$celeryProcesses = Get-Process | Where-Object { 
    $_.ProcessName -eq "python" -and 
    $_.CommandLine -like "*celery*worker*" 
}

if ($celeryProcesses) {
    $celeryProcesses | Stop-Process -Force
    Write-Host "Celeryワーカーを停止しました" -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "実行中のCeleryワーカーが見つかりませんでした" -ForegroundColor Yellow
}

Write-Host "`n仮想環境をアクティブ化しています..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host "`nCeleryワーカーを起動しています..." -ForegroundColor Cyan
Write-Host "終了するには Ctrl+C を押してください`n" -ForegroundColor Yellow

cd backend
celery -A app.workers.celery_app worker --loglevel=info --pool=solo

