# Backend Services Startup Script

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

# Redis queue clear option
Write-Host ""
Write-Host "Clear Redis queue? (Remove previous unprocessed tasks)" -ForegroundColor Yellow
Write-Host "  [Y] Yes (Recommended for development)" -ForegroundColor Green
Write-Host "  [N] No (For production: Keep tasks)" -ForegroundColor Cyan
$clearQueue = Read-Host "Select [Y/N]"

if ($clearQueue -eq "Y" -or $clearQueue -eq "y") {
    Write-Host ""
    Write-Host "Clearing Redis queue..." -ForegroundColor Cyan
    try {
        celery -A backend.app.workers.celery_app purge -f
        Write-Host "Redis queue cleared successfully" -ForegroundColor Green
    } catch {
        Write-Host "Warning: Failed to clear Redis queue" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "Continuing without clearing Redis queue" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Starting Celery worker in background..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\.venv\Scripts\Activate.ps1; celery -A backend.app.workers.celery_app worker --loglevel=info --pool=solo"

Write-Host ""
Write-Host "Waiting 5 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Starting backend server..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop"
Write-Host ""

cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000