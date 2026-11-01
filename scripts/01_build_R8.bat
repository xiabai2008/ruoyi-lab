@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "JAVA_HOME=D:\develop\jdk-17.0.0.1"
set "PATH=%JAVA_HOME%\bin;%PATH%"
set "MVN=D:\tools\apache-maven-3.9.12\bin\mvn.cmd"
set "ROOT=%CD%"
if not exist "%ROOT%\build\R8" mkdir "%ROOT%\build\R8"
call "%MVN%" -s "%ROOT%\maven-settings.xml" -Dmaven.repo.local=%ROOT%\.m2 -f "%ROOT%\src\R8\pom.xml" clean package -DskipTests -B > "%ROOT%\build\R8\mvn-build.log" 2>&1
set "RC=%ERRORLEVEL%"
echo MVN_EXIT=%RC%
exit /b %RC%
