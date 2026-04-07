@echo off
setlocal

taskkill /IM lanqiao_client.exe /F >nul 2>nul
echo [INFO] Stop command finished.
exit /b 0
