@echo off
setlocal
cd /d "%~dp0"

set "VENV=%LOCALAPPDATA%\MyD365LearningAssistant\.venv"
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set STREAMLIT_SERVER_HEADLESS=true
rem Do not keep .pyc files in this OneDrive folder — they can be older than the .py files.
set PYTHONDONTWRITEBYTECODE=1
set PYTHONUNBUFFERED=1

if not exist "%VENV%\Scripts\python.exe" (
    echo The app is not set up yet.
    echo First run:  setup.bat
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

echo.
echo Closing any old copy still using port 8501...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
ping 127.0.0.1 -n 2 >nul

if exist "%~dp0__pycache__" rd /s /q "%~dp0__pycache__" 2>nul

echo Starting Insurance Learning Assistant with a fresh copy of the code...
echo.
echo Open this address in Chrome or Edge:
echo.
echo     http://localhost:8501
echo.
echo Leave this window open while you use the app.
echo Close this window (or press Ctrl+C) to stop the app.
echo Do not use Cursor Live Preview — it will not work.
echo.

"%VENV%\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port 8501 --server.fileWatcherType poll --server.runOnSave true --browser.gatherUsageStats false
