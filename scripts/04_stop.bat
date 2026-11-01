@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "SITE=%~1"
if "%SITE%"=="" (
    rem no argument = stop all sites
    for %%S in (R1 R2 R3 R4 R5 R6 R7 R8 R9 R10 R11) do call "%~f0" %%S
    exit /b 0
)

rem R8 is a microservice site: stop Nacos + 6 services (supervisor + Windows Job Object),
rem not a single jar. scripts\start_r8_cloud.py stop kills the supervisor (children follow
rem via job object), stops the nacos-ruoyi-r8 container and removes .state\R8*.pid.
if /I "%SITE%"=="R8" goto stop_r8

set "PIDFILE=%CD%\.state\%SITE%.pid"
if not exist "%PIDFILE%" (
    echo [SKIP] %SITE%: no pid file
    exit /b 0
)

set "APPPID="
set /p APPPID=<"%PIDFILE%"
if "%APPPID%"=="" (
    echo [SKIP] %SITE%: pid file is empty
    del /f /q "%PIDFILE%" >nul 2>&1
    exit /b 0
)

tasklist /FI "PID eq %APPPID%" 2>nul | findstr /I "%APPPID%" >nul
if errorlevel 1 (
    echo [SKIP] %SITE%: pid %APPPID% not running
    del /f /q "%PIDFILE%" >nul 2>&1
    exit /b 0
)

taskkill /PID %APPPID% /F >nul 2>&1
if errorlevel 1 (
    echo [FAIL] %SITE%: could not kill pid %APPPID%
    exit /b 1
)

del /f /q "%PIDFILE%" >nul 2>&1
echo [OK] %SITE% stopped (pid %APPPID%)
exit /b 0

:stop_r8
set "PYTHON=D:\tools\Python 3.12.9\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" "%CD%\scripts\start_r8_cloud.py" stop
exit /b %ERRORLEVEL%
