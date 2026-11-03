@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title R1 lab - start

echo ============================================================
echo   R1 lab (RuoYi 4.5.1)
echo ============================================================
echo.
echo   URL   : http://127.0.0.1:19101
echo   Login : admin / admin123
echo.
echo   First start takes ~25s (MySQL + Redis + Nginx first)
echo ============================================================
echo.

rem If 19101 is already listening, skip start and just open the browser.
python -c "import socket,sys; s=socket.socket(); s.settimeout(0.5); sys.exit(0 if s.connect_ex(('127.0.0.1',19101))==0 else 1)" 2>nul
if not errorlevel 1 (
    echo [INFO] Port 19101 already listening - R1 may already be running.
    echo        Opening browser. If the page is a 502, use STOP-R1.bat first.
    echo.
    start "" "http://127.0.0.1:19101"
    pause
    exit /b 0
)

python scripts\lab.py up R1
if errorlevel 1 (
    echo.
    echo [FAIL] Start failed - see the output above.
    echo.
    echo Common causes:
    echo   1. Python not installed or not in PATH
    echo   2. jar not built - run scripts\00_probe.bat to check the environment
    echo   3. port already taken by another program
    echo.
    pause
    exit /b 1
)

echo.
echo   R1 is ready. Opening browser...
start "" "http://127.0.0.1:19101"

echo.
echo   Closing this window does NOT stop the lab.
echo   Double-click STOP-R1.bat when you are done.
echo.
pause
