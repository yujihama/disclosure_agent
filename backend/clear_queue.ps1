# Clear Celery Queue Script
# Run this when unprocessed tasks remain during development

Write-Host "Clearing Celery queue..." -ForegroundColor Cyan
Write-Host "Warning: All unprocessed tasks will be deleted!" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment
& .\.venv\Scripts\Activate.ps1

try {
    # Clear queue using Celery purge command
    celery -A backend.app.workers.celery_app purge -f
    Write-Host ""
    Write-Host "Celery queue cleared successfully" -ForegroundColor Green
    Write-Host "All unprocessed tasks have been deleted." -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "Failed to clear Celery queue" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure Redis is running." -ForegroundColor Yellow
    Write-Host "Start Redis: docker run -d -p 6379:6379 redis:7-alpine" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Press Enter to exit..."
Read-Host