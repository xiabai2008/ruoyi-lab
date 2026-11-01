@echo off
cd /d "%~dp0"

echo ============================================
echo   RuoYi-Scan Demo Environment Restore (R9)
echo ============================================
echo.

if not exist "D:\tools\Python 3.12.9\python.exe" (
    echo [ERROR] Python not found at D:\tools\Python 3.12.9\python.exe
    echo [ERROR] Edit this bat file and change the path.
    goto end
)

echo Starting MySQL / Redis / Backend / Nginx, please wait...
echo.

"D:\tools\Python 3.12.9\python.exe" scripts\restore_demo.py R9
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [OK] Restore finished.
    echo      Open http://127.0.0.1:19109   admin / admin123
) else (
    echo [FAIL] restore_demo.py exited with code %RC%
    echo        See the messages above.
)

:end
echo.
pause
