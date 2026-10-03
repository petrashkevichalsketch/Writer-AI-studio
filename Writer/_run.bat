bat
@echo off
chcp 65001 >nul
cd /d %~dp0

if not exist logs mkdir logs
set LOGFILE=logs\app.log

echo. >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"
echo Запуск %date% %time% >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

REM ── Проверка Python ────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo Python не найден. Установите Python 3.10+ >> "%LOGFILE%"
    powershell -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Python не найден. Установите Python 3.10+ и добавьте в PATH.','AI Романист — ошибка')"
    exit /b 1
)

REM ── Venv ───────────────────────────────────────────
if not exist .venv (
    echo Создаю окружение... >> "%LOGFILE%"
    python -m venv .venv >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        powershell -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Не удалось создать окружение. Смотрите logs\app.log.','AI Романист — ошибка')"
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

REM ── Зависимости (только если менялся requirements.txt) ──
set "SNAPSHOT=.venv\.req_snapshot"
set NEED_INSTALL=0
if not exist "%SNAPSHOT%" (
    set NEED_INSTALL=1
) else (
    fc /b requirements.txt "%SNAPSHOT%" >nul 2>&1
    if errorlevel 1 set NEED_INSTALL=1
)

if "%NEED_INSTALL%"=="1" (
    echo Устанавливаю зависимости... >> "%LOGFILE%"
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install -r requirements.txt --quiet --disable-pip-version-check >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        powershell -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Не удалось установить зависимости. Проверьте интернет. Подробности в logs\app.log.','AI Романист — ошибка')"
        exit /b 1
    )
    copy /y requirements.txt "%SNAPSHOT%" >nul
    echo Зависимости установлены. >> "%LOGFILE%"
)

REM ── Открыть браузер ────────────────────────────────
start "" _openbrowser.vbs

REM ── Запуск uvicorn ─────────────────────────────────
echo Запускаю uvicorn... >> "%LOGFILE%"
python -m uvicorn app:app --host 127.0.0.1 --port 8013 --log-level warning >> "%LOGFILE%" 2>&1

REM ── Если uvicorn упал ──────────────────────────────
echo uvicorn завершился. >> "%LOGFILE%"
powershell -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Приложение остановлено. Если это было неожиданно — запустите start_debug.bat и смотрите ошибку.','AI Романист')"