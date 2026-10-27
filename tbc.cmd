@echo off
rem Tinderbox CLI entry (Windows). Usage: tbc ingest PATH  /  tbc serve
setlocal
set "HERE=%~dp0"
set "ENTRY=%HERE%demo\tbc.py"

rem 1) py launcher (preferred on Windows)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%ENTRY%" %*
    exit /b %errorlevel%
)

rem 2) python on PATH, but skip the Microsoft Store stub
for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | find /i "WindowsApps" >nul
    if errorlevel 1 (
        "%%P" "%ENTRY%" %*
        exit /b %errorlevel%
    )
)

rem 3) bundled runtime used during development
set "BUNDLED=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED%" (
    "%BUNDLED%" "%ENTRY%" %*
    exit /b %errorlevel%
)

echo No usable Python found. Install Python 3.10+ or edit tbc.cmd.
exit /b 1
