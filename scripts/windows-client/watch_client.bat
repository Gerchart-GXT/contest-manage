@echo off
setlocal

set "CLIENT_ROOT=C:\lanqiao\client"
set "CLIENT_EXE=%CLIENT_ROOT%\lanqiao_client.exe"

if not exist "%CLIENT_EXE%" (
    echo [ERROR] Client exe not found: %CLIENT_EXE%
    exit /b 1
)

tasklist | find /i "lanqiao_client.exe" >nul
if errorlevel 1 (
    cd /d "%CLIENT_ROOT%"
    start "" "%CLIENT_EXE%"
    echo [INFO] Client restarted at %date% %time%.
)
exit /b 0
