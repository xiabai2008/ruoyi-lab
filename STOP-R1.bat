@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title R1 lab - stop

echo ============================================================
echo   Stopping R1 lab
echo ============================================================
echo.

rem Same python resolution as START-R1.bat - plain `python` may be the broken
rem WindowsApps stub (see scripts\find-Python.bat).
call "%~dp0scripts\find-Python.bat"
if not defined PYEXE (
    echo [FAIL] No working Python found, cannot stop via scripts.
    echo        Find the java process yourself:
    echo           netstat -ano ^| findstr :19201
    echo        then: taskkill /PID ^<pid^> /F
    echo.
    pause
    exit /b 1
)

"%PYEXE%" scripts\lab.py down R1

echo.
echo   R1 stopped. MySQL / Redis / Nginx are left running so other
echo   labs are not disturbed. To stop everything:
echo       python scripts\demo.py down
echo       python scripts\lab.py down infra
echo.
pause
