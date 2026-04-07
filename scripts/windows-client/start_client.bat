@echo off
setlocal

set "CLIENT_ROOT=C:\lanqiao\client"
set "CLIENT_EXE=%CLIENT_ROOT%\lanqiao_client.exe"
set "START_DELAY=45"

if not exist "%CLIENT_EXE%" (
    echo [ERROR] Client exe not found: %CLIENT_EXE%
    exit /b 1
)

timeout /t %START_DELAY% /nobreak >nul

tasklist | find /i "lanqiao_client.exe" >nul
if not errorlevel 1 (
    echo [INFO] lanqiao_client.exe is already running.
    exit /b 0
)

cd /d "%CLIENT_ROOT%"
start "" "%CLIENT_EXE%"
echo [INFO] Client started.
exit /b 0
