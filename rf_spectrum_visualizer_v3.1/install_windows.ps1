# RF Spectrum Visualizer v3.1 - Windows Installation Script
# Installs dependencies and prepares the application for use.
#
# Usage (PowerShell):
#   .\install_windows.ps1
#
# Requirements: Windows 10/11, Python 3.10+

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $PROJECT_ROOT

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "RF Spectrum Visualizer v3.1 - Windows Setup" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "[1/4] Checking Python..."
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://python.org" -ForegroundColor Yellow
    exit 1
}
Write-Host "Found: $pythonVersion" -ForegroundColor Green

# Verify src package exists
Write-Host ""
Write-Host "[2/4] Verifying project files..."
if (-not (Test-Path "src\rf_spectrum_visualizer\__init__.py")) {
    Write-Host "ERROR: src/rf_spectrum_visualizer package not found." -ForegroundColor Red
    Write-Host "Run this script from the rf_spectrum_visualizer_v3.1 directory." -ForegroundColor Yellow
    exit 1
}
Write-Host "Project files verified." -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "[3/4] Installing Python dependencies (matplotlib, pytest)..."
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: pip install failed. You may need to install dependencies manually:" -ForegroundColor Yellow
    Write-Host "  python -m pip install -r requirements.txt" -ForegroundColor Yellow
} else {
    Write-Host "Dependencies installed successfully." -ForegroundColor Green
}

# Complete
Write-Host ""
Write-Host "[4/4] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To launch the application:" -ForegroundColor Cyan
Write-Host "  Double-click: run_windows.bat" -ForegroundColor Cyan
Write-Host "  Or:           python main.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run tests:" -ForegroundColor Cyan
Write-Host "  pytest tests/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Hardware mode (nRF24L01+ on Raspberry Pi) requires pyrf24 and SPI."
Write-Host "See docs/HARDWARE_SETUP.md for details." -ForegroundColor Yellow
Write-Host ""
