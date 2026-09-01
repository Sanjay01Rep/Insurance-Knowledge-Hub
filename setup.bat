@echo off
setlocal
cd /d "%~dp0"

set "VENV=%LOCALAPPDATA%\MyD365LearningAssistant\.venv"

echo.
echo Setting up Insurance Learning Assistant...
echo This can take several minutes the first time. Please wait.
echo.

where python >nul 2>nul
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else (
        echo Python was not found.
        echo Install Python 3.12 from https://www.python.org/downloads/
        echo On the installer, tick "Add python.exe to PATH", then run this file again.
        echo.
        pause
        exit /b 1
    )
) else (
    set "PYTHON=python"
)

if not exist "%LOCALAPPDATA%\MyD365LearningAssistant" mkdir "%LOCALAPPDATA%\MyD365LearningAssistant"

"%PYTHON%" -m venv "%VENV%"
if errorlevel 1 (
    echo Could not create the app's private Python folder.
    echo If Python just finished installing, close this window, open a NEW terminal, and try again.
    pause
    exit /b 1
)

call "%VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Something went wrong while installing packages.
    echo Check your internet connection and run setup.bat again.
    pause
    exit /b 1
)

echo.
echo Setup finished. Next, run:  run.bat
echo.
pause
