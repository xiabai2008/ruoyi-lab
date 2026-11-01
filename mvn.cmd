@echo off
setlocal
set "JAVA_HOME=D:\develop\jdk-17.0.0.1"
"D:\tools\apache-maven-3.9.12\bin\mvn.cmd" %*
exit /b %ERRORLEVEL%
