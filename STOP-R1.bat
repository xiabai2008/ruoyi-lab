@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title R1 lab - stop

echo ============================================================
echo   Stopping R1 lab
echo ============================================================
echo.

python scripts\lab.py down R1

echo.
echo   R1 stopped. MySQL / Redis / Nginx are left running so other
echo   labs are not disturbed. To stop everything:
echo       python scripts\demo.py down
echo       python scripts\lab.py down infra
echo.
pause
