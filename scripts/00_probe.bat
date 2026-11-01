@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0.."

set "OUT=%CD%\toolchain.md"
set "TMPV=%TEMP%\ruoyi_probe_%RANDOM%%RANDOM%.txt"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do set "NOW=%%T"

> "%OUT%" echo # Toolchain Probe Result
>> "%OUT%" echo.
>> "%OUT%" echo - Probe time: !NOW!
>> "%OUT%" echo - Probe script: scripts\00_probe.bat
>> "%OUT%" echo - Note: versions below come from actual `-version` / `-v` output, not from directory names.
>> "%OUT%" echo.
>> "%OUT%" echo Component ^| Status ^| Absolute path ^| Version ^| Requirement ^| Note
>> "%OUT%" echo --- ^| --- ^| --- ^| --- ^| --- ^| ---

call :probe_jdk8
call :probe_jdk17
call :probe_maven
call :probe_node
call :probe_mysql
call :probe_redis
call :probe_nginx

>> "%OUT%" echo.
>> "%OUT%" echo ## Status legend
>> "%OUT%" echo.
>> "%OUT%" echo - `MISSING`: component not found on this machine. Per the spec, do not download or install it automatically; ask for confirmation first.
>> "%OUT%" echo - `LOW` / `MISMATCH`: executable found, but the actual version does not meet the deployment spec under `docs/`.
>> "%OUT%" echo - JDK detection is based on the major version printed by an actual `java -version` run; Maven detection uses `mvn.cmd` on Windows.
>> "%OUT%" echo.

rem Convert the GBK-encoded cmd output to UTF-8 so Chinese paths remain readable.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:OUT; $t=[IO.File]::ReadAllText($p,[Text.Encoding]::GetEncoding(936)); [IO.File]::WriteAllText($p,$t,[Text.UTF8Encoding]::new($false))"

del "%TMPV%" >nul 2>&1
echo.
echo Probe finished. Result written to:
echo   %OUT%
exit /b 0

rem ============================================================
rem JDK 8
rem ============================================================
:probe_jdk8
set "FOUND="
set "TPATH="
set "TLINE="
set "TVER="
if exist "D:\develop\java-se-8u44-ri\bin\java.exe" call :try_java "D:\develop\java-se-8u44-ri\bin\java.exe" "1.8."
if not defined FOUND if defined JAVA_HOME call :try_java "%JAVA_HOME%\bin\java.exe" "1.8."
if not defined FOUND for /f "delims=" %%J in ('where java.exe 2^>nul') do if not defined FOUND call :try_java "%%J" "1.8."
if not defined FOUND for /d %%D in ("D:\develop\jdk1.8*" "D:\develop\java-se-8u*" "C:\Program Files\Java\jdk1.8*" "C:\Program Files\Java\jdk-8*" "D:\Program Files\Java\jdk1.8*") do if not defined FOUND call :try_java "%%~fD\bin\java.exe" "1.8."
if defined FOUND (
  for /f "tokens=3" %%V in ("!TLINE!") do set "TVER=%%~V"
  set "J8STATUS=OK"
  set "J8NOTE=meets 8u44+"
  set "UPD=!TVER:*_=!"
  if not "!UPD!"=="" if !UPD! LSS 44 (
    set "J8STATUS=LOW"
    set "J8NOTE=below 8u44+"
  )
  >> "%OUT%" echo JDK 8 ^| !J8STATUS! ^| !TPATH! ^| !TVER! ^| 8u44+ ^| !J8NOTE!
) else (
  >> "%OUT%" echo JDK 8 ^| MISSING ^| - ^| - ^| 8u44+ ^| not found; java -version did not print 1.8.
)
exit /b 0

rem ============================================================
rem JDK 17
rem ============================================================
:probe_jdk17
set "FOUND="
set "TPATH="
set "TLINE="
set "TVER="
if exist "D:\develop\jdk-17.0.0.1\bin\java.exe" call :try_java "D:\develop\jdk-17.0.0.1\bin\java.exe" "17."
if not defined FOUND if defined JAVA_HOME call :try_java "%JAVA_HOME%\bin\java.exe" "17."
if not defined FOUND for /f "delims=" %%J in ('where java.exe 2^>nul') do if not defined FOUND call :try_java "%%J" "17."
if not defined FOUND for /d %%D in ("D:\develop\jdk-17*" "D:\develop\jdk17*" "C:\Program Files\Java\jdk-17*" "C:\Program Files\Java\jdk17*" "D:\Program Files\Java\jdk-17*") do if not defined FOUND call :try_java "%%~fD\bin\java.exe" "17."
if defined FOUND (
  for /f "tokens=3" %%V in ("!TLINE!") do set "TVER=%%~V"
  for /f "tokens=1 delims=." %%A in ("!TVER!") do set "J17MAJOR=%%A"
  set "J17STATUS=OK"
  set "J17NOTE=major version 17"
  if not "!J17MAJOR!"=="17" (
    set "J17STATUS=MISMATCH"
    set "J17NOTE=major version is not 17"
  )
  >> "%OUT%" echo JDK 17 ^| !J17STATUS! ^| !TPATH! ^| !TVER! ^| 17.0.x ^| !J17NOTE!
) else (
  >> "%OUT%" echo JDK 17 ^| MISSING ^| - ^| - ^| 17.0.x ^| not found; java -version did not print 17.
)
exit /b 0

rem ============================================================
rem Maven
rem ============================================================
:probe_maven
set "FOUND="
set "TPATH="
set "TLINE="
set "TVER="
if defined MAVEN_HOME call :try_tool "%MAVEN_HOME%\bin\mvn.cmd" "-v" "Apache Maven"
if not defined FOUND if defined M2_HOME call :try_tool "%M2_HOME%\bin\mvn.cmd" "-v" "Apache Maven"
if not defined FOUND for /f "delims=" %%M in ('where mvn.cmd 2^>nul') do if not defined FOUND call :try_tool "%%M" "-v" "Apache Maven"
if not defined FOUND for /d %%D in ("D:\tools\apache-maven-*" "D:\develop\apache-maven-*" "C:\Program Files\apache-maven-*" "D:\Program Files\apache-maven-*" "C:\apache-maven-*" "D:\apache-maven-*") do if not defined FOUND call :try_tool "%%~fD\bin\mvn.cmd" "-v" "Apache Maven"
if defined FOUND (
  for /f "tokens=3" %%V in ("!TLINE!") do set "TVER=%%V"
  set "MSTATUS=OK"
  set "MNOTE=meets 3.6+"
  for /f "tokens=1,2 delims=." %%A in ("!TVER!") do (
    set "MMA=%%A"
    set "MMI=%%B"
  )
  if !MMA! LSS 3 (
    set "MSTATUS=LOW"
    set "MNOTE=below 3.6"
  )
  if !MMA! EQU 3 if !MMI! LSS 6 (
    set "MSTATUS=LOW"
    set "MNOTE=below 3.6"
  )
  >> "%OUT%" echo Maven ^| !MSTATUS! ^| !TPATH! ^| !TVER! ^| 3.6+ ^| !MNOTE!
) else (
  >> "%OUT%" echo Maven ^| MISSING ^| - ^| - ^| 3.6+ ^| mvn.cmd not found
)
exit /b 0

rem ============================================================
rem Node.js
rem ============================================================
:probe_node
set "FOUND="
set "TPATH="
set "TLINE="
set "TVER="
if exist "C:\Program Files\nodejs\node.exe" call :try_tool "C:\Program Files\nodejs\node.exe" "-v" "v"
if not defined FOUND for /f "delims=" %%N in ('where node.exe 2^>nul') do if not defined FOUND call :try_tool "%%N" "-v" "v"
if not defined FOUND for /d %%D in ("C:\Program Files\nodejs*" "D:\tools\node*" "D:\develop\node*") do if not defined FOUND call :try_tool "%%~fD\node.exe" "-v" "v"
if defined FOUND (
  set "TVER=!TLINE:v=!"
  for /f "tokens=1 delims=." %%A in ("!TVER!") do set "NMAJOR=%%A"
  set "NSTATUS=OK"
  set "NNOTE=meets 16.20 / 18.x"
  set "NODE_OK=0"
  if "!NMAJOR!"=="16" set "NODE_OK=1"
  if "!NMAJOR!"=="18" set "NODE_OK=1"
  if "!NODE_OK!"=="0" (
    set "NSTATUS=MISMATCH"
    set "NNOTE=outside 16.20 / 18.x"
  )
  >> "%OUT%" echo Node.js ^| !NSTATUS! ^| !TPATH! ^| !TVER! ^| 16.20 or 18.x ^| !NNOTE!
) else (
  >> "%OUT%" echo Node.js ^| MISSING ^| - ^| - ^| 16.20 or 18.x ^| node.exe not found
)
exit /b 0

rem ============================================================
rem MySQL
rem ============================================================
:probe_mysql
set "FOUND="
set "TPATH="
set "TLINE="
set "TVER="
if exist "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" call :try_tool "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" "--version" "Ver"
if not defined FOUND for /f "delims=" %%S in ('where mysqld.exe 2^>nul') do if not defined FOUND call :try_tool "%%S" "--version" "Ver"
if not defined FOUND for /d %%D in ("C:\Program Files\MySQL\MySQL Server *" "D:\develop\mysql*" "D:\tools\mysql*" "C:\phpstudy_pro\Extensions\MySQL*") do if not defined FOUND call :try_tool "%%~fD\bin\mysqld.exe" "--version" "Ver"
if defined FOUND (
  set "MYSQLVER=!TLINE:*  Ver =!"
  if "!MYSQLVER!"=="!TLINE!" set "MYSQLVER=!TLINE:*Ver =!"
  for /f "tokens=1" %%V in ("!MYSQLVER!") do set "TVER=%%V"
  set "MYSQLSTATUS=OK"
  set "MYSQLNOTE=meets 5.7 / 8.0"
  echo !TVER! | findstr /b /c:"5.7" /c:"8.0" >nul
  if errorlevel 1 (
    set "MYSQLSTATUS=MISMATCH"
    set "MYSQLNOTE=outside 5.7 / 8.0"
  )
  >> "%OUT%" echo MySQL ^| !MYSQLSTATUS! ^| !TPATH! ^| !TVER! ^| 5.7 or 8.0 ^| !MYSQLNOTE!
) else (
  >> "%OUT%" echo MySQL ^| MISSING ^| - ^| - ^| 5.7 or 8.0 ^| mysqld.exe not found
)
exit /b 0

rem ============================================================
rem Redis
rem ============================================================
:probe_redis
set "FOUND="
set "TPATH="
set "TLINE="
set "TVER="
if exist "%CD%\redis\redis-server.exe" call :try_tool "%CD%\redis\redis-server.exe" "--version" "Redis server"
if not defined FOUND for /f "delims=" %%R in ('where redis-server.exe 2^>nul') do if not defined FOUND call :try_tool "%%R" "--version" "Redis server"
if not defined FOUND for %%R in ("C:\redis\redis-server.exe" "D:\redis\redis-server.exe" "C:\Program Files\Redis\redis-server.exe" "D:\tools\redis\redis-server.exe" "D:\develop\redis\redis-server.exe") do if not defined FOUND call :try_tool "%%~R" "--version" "Redis server"
if not defined FOUND for /d %%D in ("C:\redis*" "D:\redis*" "D:\tools\redis*" "D:\develop\redis*" "C:\Program Files\Redis*") do if not defined FOUND call :try_tool "%%~fD\redis-server.exe" "--version" "Redis server"
if defined FOUND (
  for /f "tokens=1" %%V in ("!TLINE:*v==!") do set "TVER=%%V"
  set "REDISSTATUS=OK"
  set "REDISNOTE=meets 5.0+"
  for /f "tokens=1 delims=." %%A in ("!TVER!") do set "RMAJOR=%%A"
  if !RMAJOR! LSS 5 (
    set "REDISSTATUS=LOW"
    set "REDISNOTE=below 5.0"
  )
  >> "%OUT%" echo Redis ^| !REDISSTATUS! ^| !TPATH! ^| !TVER! ^| 5.0+ ^| !REDISNOTE!
) else (
  >> "%OUT%" echo Redis ^| MISSING ^| - ^| - ^| 5.0+ ^| redis-server.exe not found
)
exit /b 0

rem ============================================================
rem Nginx
rem ============================================================
:probe_nginx
set "FOUND="
set "TPATH="
set "TLINE="
set "TVER="
if exist "%CD%\nginx\nginx.exe" call :try_tool "%CD%\nginx\nginx.exe" "-v" "nginx version"
if not defined FOUND for /f "delims=" %%G in ('where nginx.exe 2^>nul') do if not defined FOUND call :try_tool "%%G" "-v" "nginx version"
if not defined FOUND for %%G in ("C:\nginx\nginx.exe" "D:\nginx\nginx.exe" "C:\Program Files\nginx\nginx.exe" "D:\tools\nginx\nginx.exe" "D:\develop\nginx\nginx.exe") do if not defined FOUND call :try_tool "%%~G" "-v" "nginx version"
if not defined FOUND for /d %%D in ("C:\nginx*" "D:\nginx*" "D:\tools\nginx*" "D:\develop\nginx*" "C:\Program Files\nginx*") do if not defined FOUND call :try_tool "%%~fD\nginx.exe" "-v" "nginx version"
if defined FOUND (
  set "TVER=!TLINE:*nginx/=!"
  set "NGINXSTATUS=OK"
  set "NGINXNOTE=meets 1.20+"
  for /f "tokens=1,2 delims=." %%A in ("!TVER!") do (
    set "NGA=%%A"
    set "NGB=%%B"
  )
  if !NGA! LSS 1 (
    set "NGINXSTATUS=LOW"
    set "NGINXNOTE=below 1.20"
  )
  if !NGA! EQU 1 if !NGB! LSS 20 (
    set "NGINXSTATUS=LOW"
    set "NGINXNOTE=below 1.20"
  )
  >> "%OUT%" echo Nginx ^| !NGINXSTATUS! ^| !TPATH! ^| !TVER! ^| 1.20+ ^| !NGINXNOTE!
) else (
  >> "%OUT%" echo Nginx ^| MISSING ^| - ^| - ^| 1.20+ ^| nginx.exe not found
)
exit /b 0

rem ============================================================
rem Helpers
rem ============================================================
:try_java
if not exist "%~1" exit /b 1
"%~1" -version > "%TMPV%" 2>&1
findstr /c:"%~2" "%TMPV%" >nul
if errorlevel 1 exit /b 1
for /f "usebackq delims=" %%L in (`findstr /c:"%~2" "%TMPV%"`) do if not defined TLINE set "TLINE=%%L"
set "TPATH=%~1"
set "FOUND=1"
exit /b 0

:try_tool
if not exist "%~1" exit /b 1
call "%~1" %~2 > "%TMPV%" 2>&1
findstr /i /c:"%~3" "%TMPV%" >nul
if errorlevel 1 exit /b 1
for /f "usebackq delims=" %%L in (`findstr /i /c:"%~3" "%TMPV%"`) do if not defined TLINE set "TLINE=%%L"
set "TPATH=%~1"
set "FOUND=1"
exit /b 0
