@echo off
rem ============================================================================
rem  find-Python.bat -- locate a WORKING python and put its path in PYEXE
rem
rem  Why this exists
rem  ---------------
rem  Typing `python` on Windows is unreliable. Measured on 2026-11-04:
rem
rem    cmd> where python
rem      C:\Users\HZR\AppData\Local\Microsoft\WindowsApps\python.exe   <- store stub
rem      D:\tools\Python 3.12.9\python.exe                             <- the real one
rem
rem  The WindowsApps one is a 0-byte forwarder. When the Store version is not
rem  installed it just fails with:
rem      The system cannot find the file C:\...\WindowsApps\python.exe.
rem  and it sits FIRST in PATH, so plain `python foo.py` dies.
rem
rem  The `py` launcher can be broken too (this machine: points at a Python 3.14
rem  that does not exist).
rem
rem  Strategy: try each candidate by actually running `-c "import sys"`.
rem  Only a candidate that RUNS gets used. Result is cached in
rem  .state\python-path.txt so later runs skip the probing.
rem
rem  NOTE: comments are English on purpose -- Chinese in a .bat gets mangled
rem  depending on the active code page and can even be executed as a command.
rem
rem  Usage: call scripts\find-Python.bat
rem         On success %PYEXE% holds the interpreter path; on failure it is empty.
rem ============================================================================

setlocal EnableExtensions EnableDelayedExpansion
set "PYEXE="
set "ROOT=%~dp0.."
set "CACHE=%ROOT%\.state\python-path.txt"

rem ---- 1. cached path (still verify it runs; the user may have uninstalled it)
if exist "%CACHE%" (
    set /p CACHED=<"%CACHE%"
    if defined CACHED (
        "%CACHED%" -c "import sys" >nul 2>&1
        if not errorlevel 1 (
            endlocal & set "PYEXE=%CACHED%"
            goto :eof
        )
    )
)

rem ---- 2. explicit path from lab.local.json wins
set "CFG=%ROOT%\lab.local.json"
if exist "%CFG%" (
    for /f "usebackq tokens=2 delims=:" %%A in (`findstr /i "\"PYTHON\"" "%CFG%"`) do (
        set "CAND=%%A"
        set "CAND=!CAND:,=!"
        set "CAND=!CAND:"=!"
        for /f "tokens=* delims= " %%B in ("!CAND!") do set "CAND=%%B"
        if defined CAND if exist "!CAND!" (
            "!CAND!" -c "import sys" >nul 2>&1
            if not errorlevel 1 call :Save "!CAND!"
        )
    )
)
if defined PYEXE goto :done

rem ---- 3. common install locations (python.org installer defaults)
for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python313"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "D:\tools\Python 3.12.9"
    "C:\Python312"
    "C:\Python311"
) do (
    if exist "%%~D\python.exe" (
        "%%~D\python.exe" -c "import sys" >nul 2>&1
        if not errorlevel 1 call :Save "%%~D\python.exe"
    )
)
if defined PYEXE goto :done

rem ---- 4. last resort: PATH entries, but skip the WindowsApps stub and verify
for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        "%%P" -c "import sys" >nul 2>&1
        if not errorlevel 1 call :Save "%%P"
    )
)
if defined PYEXE goto :done

:done
endlocal & set "PYEXE=%PYEXE%"
goto :eof

:Save
set "PYEXE=%~1"
if not exist "%ROOT%\.state" mkdir "%ROOT%\.state" >nul 2>&1
> "%CACHE%" echo %~1
goto :eof
