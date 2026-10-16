@echo off
chcp 65001 >nul
title Writer AI Studio - Console
cd /d "%~dp0"

set PORT=8013

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

REM ── Проверка занятости порта ─────────────────────────
set "FOUND_PID="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%PORT%" ^| findstr LISTENING') do set "FOUND_PID=%%a"

if defined FOUND_PID (
    echo.
    echo WARNING: Порт %PORT% занят процессом PID %FOUND_PID%.
    echo Возможно, приложение уже запущено в фоне ^(start.bat^).
    echo.
    choice /c YN /n /m "Завершить этот процесс и продолжить? [Y/N] "
    if errorlevel 2 (
        echo Выход.
        pause
        exit /b 1
    )
    taskkill /F /PID %FOUND_PID% >nul 2>&1
    timeout /t 1 /nobreak >nul
)

echo.
echo ────────────────────────────────────────────────
echo Запускаю uvicorn на порту %PORT%...
echo ────────────────────────────────────────────────
echo.

call .venv\Scripts\activate.bat

start "" _openbrowser.vbs

python -m uvicorn app:app --host 127.0.0.1 --port %PORT%

echo.
echo ────────────────────────────────────────────────
echo Uvicorn завершился.
echo ────────────────────────────────────────────────
echo.
pause >nul