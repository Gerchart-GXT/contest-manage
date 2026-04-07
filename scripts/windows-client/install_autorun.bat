@echo off
setlocal

set "CLIENT_ROOT=C:\lanqiao\client"
set "START_SCRIPT=%CLIENT_ROOT%\start_client.bat"
set "GUARD_SCRIPT=%CLIENT_ROOT%\watch_client.bat"
set "START_VBS=%CLIENT_ROOT%\start_client_hidden.vbs"
set "GUARD_VBS=%CLIENT_ROOT%\guard_client_hidden.vbs"

if not exist "%START_SCRIPT%" (
    echo [ERROR] Missing file: %START_SCRIPT%
    exit /b 1
)

if not exist "%GUARD_SCRIPT%" (
    echo [ERROR] Missing file: %GUARD_SCRIPT%
    exit /b 1
)

if not exist "%START_VBS%" (
    echo [ERROR] Missing file: %START_VBS%
    exit /b 1
)

if not exist "%GUARD_VBS%" (
    echo [ERROR] Missing file: %GUARD_VBS%
    exit /b 1
)

schtasks /delete /tn "LanqiaoClientWatch" /f >nul 2>nul

schtasks /create /tn "LanqiaoClientStart" /sc onlogon /delay 0000:30 /tr "wscript.exe \"%START_VBS%\"" /f
if errorlevel 1 (
    echo [ERROR] Failed to create LanqiaoClientStart task.
    exit /b 1
)

schtasks /create /tn "LanqiaoClientGuard" /sc minute /mo 1 /tr "wscript.exe \"%GUARD_VBS%\"" /f
if errorlevel 1 (
    echo [ERROR] Failed to create LanqiaoClientGuard task.
    exit /b 1
)

echo [INFO] Scheduled tasks created successfully.
echo [INFO] Client start task: LanqiaoClientStart
echo [INFO] Client guard task: LanqiaoClientGuard
exit /b 0
