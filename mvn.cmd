@echo off
rem Maven wrapper.
rem
rem Sites need different JDKs (single-app 8, Spring Boot 3 series 17).
rem This wrapper builds with JDK17 (backward compatible with Java 8 sources).
rem
rem Override via environment variables instead of editing this file:
rem   set JAVA_HOME=D:\path\to\jdk-17
rem   set MVN_HOME=D:\path\to\apache-maven
setlocal

if "%JAVA_HOME%"=="" set "JAVA_HOME=D:\develop\jdk-17.0.0.1"
if "%MVN_HOME%"=="" set "MVN_HOME=D:\tools\apache-maven-3.9.12"

if not exist "%JAVA_HOME%\bin\java.exe" (
    echo [ERROR] JDK not found: %JAVA_HOME%
    echo         Set JAVA_HOME to your JDK 17 install directory.
    exit /b 1
)
if not exist "%MVN_HOME%\bin\mvn.cmd" (
    echo [ERROR] Maven not found: %MVN_HOME%
    echo         Set MVN_HOME to your Maven install directory.
    exit /b 1
)

rem Use the bundled settings.xml (Aliyun mirror) when present.
set "MVN_SETTINGS="
if exist "%~dp0maven-settings.xml" set "MVN_SETTINGS=-s "%~dp0maven-settings.xml""

call "%MVN_HOME%\bin\mvn.cmd" %MVN_SETTINGS% %*
exit /b %ERRORLEVEL%
