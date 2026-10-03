@echo off
chcp 65001 >nul
cd /d %~dp0
echo Режим отладки. Смотрите всё в этом окне.
echo.
call _run.bat
pause