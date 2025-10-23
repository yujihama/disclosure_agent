# Restart Celery Worker Script

Write-Host "Stopping existing Celery worker processes..." -ForegroundColor Yellow

# Find and stop Celery processes
$celeryProcesses = Get-Process | Where-Object { 
    $_.ProcessName -eq "python" -and 
    $_.CommandLine -like "*celery*worker*" 
}

if ($celeryProcesses) {
    $celeryProcesses | Stop-Process -Force
    Write-Host "Celery worker stopped" -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "No running Celery worker found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host ""
Write-Host "Starting Celery worker..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop"
Write-Host ""

cd backend
celery -A app.workers.celery_app worker --loglevel=info --pool=solo