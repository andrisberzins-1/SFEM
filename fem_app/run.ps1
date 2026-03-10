# -----------------------------------------------
# run.ps1 — Launch both Streamlit and FastAPI servers
#
# Usage: .\run.ps1
#   Streamlit: http://localhost:8501
#   FastAPI:   http://localhost:8502
#   API docs:  http://localhost:8502/docs
# -----------------------------------------------

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  2D FEM Web Application"                  -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Starting servers..."
Write-Host "    Streamlit UI:  " -NoNewline; Write-Host "http://localhost:8501" -ForegroundColor Green
Write-Host "    FastAPI:       " -NoNewline; Write-Host "http://localhost:8502" -ForegroundColor Green
Write-Host "    API docs:      " -NoNewline; Write-Host "http://localhost:8502/docs" -ForegroundColor Green
Write-Host ""

# Find Python
$py = $null
foreach ($cmd in @("python", "python3", "py")) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found -and (& $cmd --version 2>&1) -match "Python 3") {
        $py = $cmd
        break
    }
}
if (-not $py) {
    Write-Host "ERROR: Python 3 not found." -ForegroundColor Red
    exit 1
}
Write-Host "  Using: $py ($(& $py --version 2>&1))"

# Start FastAPI in background
$apiJob = Start-Process -NoNewWindow -PassThru -FilePath $py `
    -ArgumentList "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8502"
Write-Host "  FastAPI started (PID: $($apiJob.Id))"

# Start Streamlit in background
$stJob = Start-Process -NoNewWindow -PassThru -FilePath $py `
    -ArgumentList "-m", "streamlit", "run", "app.py", "--server.port", "8501", "--server.headless", "true"
Write-Host "  Streamlit started (PID: $($stJob.Id))"

Write-Host ""
Write-Host "  Press Ctrl+C to stop both servers."
Write-Host "==========================================" -ForegroundColor Cyan

# Wait and clean up on exit
try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Write-Host ""
    Write-Host "  Stopping servers..." -ForegroundColor Yellow
    if (!$apiJob.HasExited) { Stop-Process -Id $apiJob.Id -Force -ErrorAction SilentlyContinue }
    if (!$stJob.HasExited) { Stop-Process -Id $stJob.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "  Done." -ForegroundColor Green
}
