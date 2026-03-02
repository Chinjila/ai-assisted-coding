# startup.ps1 - GenAIsummarizer PowerShell startup script
# Run from the repository root: .\startup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Activating virtual environment ===" -ForegroundColor Cyan
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

Write-Host "=== Changing to summarizer-app directory ===" -ForegroundColor Cyan
Set-Location "$PSScriptRoot\summarizer-app"

Write-Host "=== Installing Python dependencies ===" -ForegroundColor Cyan
if (Test-Path ".\requirements.txt") {
    pip install -r .\requirements.txt
} else {
    Write-Host "No requirements.txt found, skipping pip install." -ForegroundColor Yellow
}

Write-Host "=== Starting the app ===" -ForegroundColor Cyan
python .\run.py
