@echo off
chcp 65001 >nul
title Writer AI Studio - Console
cd /d "%~dp0"

echo Starting Writer AI Studio in console mode.
echo All logs and tracebacks will be shown in this window.
echo Stop: Ctrl+C
echo.

if not exist .venv (
    echo ERROR: .venv folder not found.
    echo Run start.bat first to create the environment.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

start "" _openbrowser.vbs

python -m uvicorn app:app --host 127.0.0.1 --port 8013

echo.
echo Uvicorn finished. Press any key to close.
pause >nul