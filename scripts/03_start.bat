@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0.."

set "SITE=%~1"
if "%SITE%"=="" set "SITE=R2"

if "%LAB_JDK8%"=="" (set "JDK8=D:\develop\java-se-8u44-ri") else (set "JDK8=%LAB_JDK8%")
if "%LAB_JDK17%"=="" (set "JDK17=D:\develop\jdk-17.0.0.1") else (set "JDK17=%LAB_JDK17%")
set "PORT="
set "JAVA_HOME="

if /I "%SITE%"=="R1" set "PORT=19201"
if /I "%SITE%"=="R2" set "PORT=19202"
if /I "%SITE%"=="R3" set "PORT=19203"
if /I "%SITE%"=="R4" set "PORT=19204"
if /I "%SITE%"=="R5" set "PORT=19205"
if /I "%SITE%"=="R6" set "PORT=19206"
if /I "%SITE%"=="R7" set "PORT=19207"
if /I "%SITE%"=="R8" set "PORT=19208"
if /I "%SITE%"=="R9" set "PORT=19209"
if /I "%SITE%"=="R10" set "PORT=19210"
if /I "%SITE%"=="R11" set "PORT=19211"

if not defined PORT (
    echo [ERROR] Unknown site: %SITE%
    exit /b 1
)

rem R8 is a microservice site (RuoYi-Cloud): the backend is Nacos + 6 Spring Cloud services,
rem not a single ruoyi-admin.jar. scripts\start_r8_cloud.py brings up Nacos 8848 (+9848 gRPC),
rem then auth/system/gen/job/file and gateway 19208, then writes the gateway PID to .state\R8.pid.
if /I "%SITE%"=="R8" goto start_r8

rem JDK8 for 4.5.x-4.8.2; JDK17 for 4.8.3 and Vue3/Cloud/Plus
set "JAVA_HOME=%JDK8%"
if /I "%SITE%"=="R5" set "JAVA_HOME=%JDK17%"
if /I "%SITE%"=="R6" set "JAVA_HOME=%JDK17%"
if /I "%SITE%"=="R8" set "JAVA_HOME=%JDK17%"
if /I "%SITE%"=="R9" set "JAVA_HOME=%JDK17%"
if /I "%SITE%"=="R11" set "JAVA_HOME=%JDK17%"

set "PATH=%JAVA_HOME%\bin;%PATH%"
rem Clear inherited SERVER__PORT/SERVER_PORT so server.port from application-prod.yml is used
set "SERVER__PORT="
set "SERVER_PORT="
set "JAR=%CD%\build\%SITE%\ruoyi-admin.jar"
if /I "%SITE%"=="R10" set "JAR=%CD%\build\R10\jeecg-system-start-3.6.3.jar"
if /I "%SITE%"=="R11" set "JAR=%CD%\build\R11\internal-api.jar"
set "HEALTHPATH=/login"
if /I "%SITE%"=="R9" set "HEALTHPATH=/auth/code"
if /I "%SITE%"=="R10" set "HEALTHPATH=/jeecg-boot/"
if /I "%SITE%"=="R11" set "HEALTHPATH=/api/v1/health"
set "RUNDIR=%CD%\runtime\%SITE%"
set "LOGFILE=%RUNDIR%\run.log"
set "ERRFILE=%RUNDIR%\run.err.log"
set "PIDFILE=%CD%\.state\%SITE%.pid"
set "TMPHTML=%TEMP%\ruoyi_%SITE%_login_%RANDOM%.html"
set "TMPCODE=%TEMP%\ruoyi_%SITE%_code_%RANDOM%.txt"

if not exist "%JAR%" (
    echo [ERROR] Jar not found: %JAR%
    echo [ERROR] Build %SITE% first.
    exit /b 1
)
if not exist "%RUNDIR%" mkdir "%RUNDIR%"
if not exist "%RUNDIR%\profile" mkdir "%RUNDIR%\profile"
if not exist "%RUNDIR%\logs" mkdir "%RUNDIR%\logs"

echo [INFO] Checking port %PORT% ...
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [ERROR] Port %PORT% is already in use. Refusing to start.
    netstat -ano | findstr ":%PORT%" | findstr "LISTENING"
    exit /b 1
)

if exist "%PIDFILE%" del /f /q "%PIDFILE%" >nul 2>&1

echo [INFO] Starting %SITE% via scripts\launch.py
rem Launch through the Python launcher instead of start /B: a start /B child
rem inherits this script stdout handle, so the caller pipe never closes and the
rem caller hangs for 15+ minutes. Python subprocess uses close_fds=True.
if "%LAB_PYTHON%"=="" (set "PYTHON=D:\tools\Python 3.12.9\python.exe") else (set "PYTHON=%LAB_PYTHON%")
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" "%CD%\scripts\launch.py" %SITE%
if errorlevel 1 (
    echo [ERROR] launch failed for %SITE%.
    exit /b 1
)

set /a WAIT=0
:wait_loop
set /a WAIT+=1
curl.exe -s -o "%TMPHTML%" -w "%%{http_code}" "http://127.0.0.1:%PORT%%HEALTHPATH%" > "%TMPCODE%" 2>nul
set "HTTPCODE="
set /p HTTPCODE=<"%TMPCODE%"
if "%HTTPCODE%"=="200" goto ready
if %WAIT% GEQ 90 (
    echo [ERROR] %SITE% did not become ready within 90 seconds.
    echo [ERROR] See %LOGFILE%
    del /f /q "%TMPHTML%" "%TMPCODE%" >nul 2>&1
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait_loop

:ready
set "APPPID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do set "APPPID=%%P"
if "%APPPID%"=="" (
    echo [ERROR] Login page is reachable, but no listening PID was found on port %PORT%.
    del /f /q "%TMPHTML%" "%TMPCODE%" >nul 2>&1
    exit /b 1
)
> "%PIDFILE%" echo %APPPID%
del /f /q "%TMPHTML%" "%TMPCODE%" >nul 2>&1

echo [OK] %SITE% is ready.
echo [OK] URL: http://127.0.0.1:%PORT%/login
echo [OK] PID: %APPPID% (written to .state\%SITE%.pid)
exit /b 0

:start_r8
echo [INFO] Starting R8 cloud stack (Nacos + 6 microservices) via scripts\start_r8_cloud.py
if "%LAB_PYTHON%"=="" (set "PYTHON=D:\tools\Python 3.12.9\python.exe") else (set "PYTHON=%LAB_PYTHON%")
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" "%CD%\scripts\start_r8_cloud.py" start
if errorlevel 1 (
    echo [ERROR] R8 cloud stack failed to start. See runtime\R8\logs\
    exit /b 1
)
echo [OK] R8 is ready.
echo [OK] URL: http://127.0.0.1:19108/login  (gateway http://127.0.0.1:19208/)
exit /b 0
