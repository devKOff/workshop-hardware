@echo off
REM RF Spectrum Visualizer v3.1 - Windows Launch Script
REM Runs the application in simulation mode (default).
REM
REM Usage: double-click this file, or run from command prompt:
REM     run_windows.bat

cd /d "%~dp0"

REM Check for Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Check that src/ directory exists
if not exist "src\rf_spectrum_visualizer\__init__.py" (
    echo ERROR: src/rf_spectrum_visualizer package not found.
    echo Please run this script from the rf_spectrum_visualizer_v3.1 directory.
    pause
    exit /b 1
)

REM Install dependencies if requirements.txt exists and pip is available
if exist "requirements.txt" (
    echo Checking dependencies...
    python -m pip install -r requirements.txt >nul 2>&1
    if errorlevel 1 (
        echo WARNING: Could not install dependencies automatically.
        echo Please run: pip install -r requirements.txt
    )
)

REM Launch the application
echo Starting RF Spectrum Visualizer v3.1 (Simulation Mode)...
python main.py

if errorlevel 1 (
    echo.
    echo The application exited with an error.
    pause
)
