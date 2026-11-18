@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem 面板放在 tools\panel，靶场根目录是上两级。
cd /d "%~dp0..\.."
title RuoYi lab panel

set "PORT=19500"
if not "%~1"=="" set "PORT=%~1"
set "NOBROWSER="
if /I "%~2"=="--no-browser" set "NOBROWSER=--no-browser"

call "scripts\find-Python.bat"
if not defined PYEXE (
    echo [FAIL] 没有找到可用的 Python。
    echo        请安装 Python 3.9+，或检查 lab.local.json 里的 PYTHON。
    pause
    exit /b 1
)

"%PYEXE%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo [FAIL] 当前 Python 缺少 fastapi / uvicorn：
    echo        %PYEXE%
    echo.
    echo        安装命令：
    echo        "%PYEXE%" -m pip install -r tools\panel\requirements.txt
    pause
    exit /b 1
)

echo ============================================================
echo   若依靶场 Web 管理平台
echo ============================================================
echo   Python : %PYEXE%
echo   地址   : http://127.0.0.1:%PORT%
echo.
echo   关闭本窗口只会停止面板，不会停止已启动的靶场。
echo ============================================================
echo.

"%PYEXE%" -m tools.panel.run --port %PORT% %NOBROWSER%
pause
