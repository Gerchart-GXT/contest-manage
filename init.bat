@echo off
echo Clearing DataDisk
for %%d in (D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if exist %%d:\ (
        echo Cleaning drive %%d:\
        del /s /q %%d:\*.* 2>nul
        for /d %%i in (%%d:\*) do rd /s /q %%i 2>nul
    )
)

set DESKTOP_DIR=C:\Users\%USERNAME%\Desktop
set LANQIAO_ENV_DIR=C:\lanqiao-env
set LANQIAO_APP_DIR=%DESKTOP_DIR%

echo Unzipping lanqiao-env
tar -xf %DESKTOP_DIR%\lanqiao-env.zip -C %LANQIAO_ENV_DIR%
echo Unzipping lanqiao-app
tar -xf %DESKTOP_DIR%\lanqiao-app.zip -C %LANQIAO_APP_DIR%

echo Installing Python...
%LANQIAO_ENV_DIR%\python-3.8.6-amd64.exe /quiet InstallAllUsers=1 PrependPath=1

echo Installing Java...
%LANQIAO_ENV_DIR%\jdk-8u261-windows-x64.exe /s

echo Installing Node.js...
msiexec /i %LANQIAO_ENV_DIR%\node-v12.14.1-x64.msi /quiet

echo Installing VSCode...
%LANQIAO_ENV_DIR%\VSCodeUserSetup-x64-1.61.2.exe /verysilent /suppressmsgboxes /norestart

echo Installing 7-Zip...
%LANQIAO_ENV_DIR%\7z2104-x64.exe /S 
echo Installation complete!

echo Unzipping MinGW
tar -xf %LANQIAO_ENV_DIR%\MinGW64.zip -C %LANQIAO_ENV_DIR%\

echo Adding GCC Path
set MINGW_BIN=%LANQIAO_ENV_DIR%\MinGW64\bin
echo %PATH% | find /i "%MINGW_BIN%" >nul
if %errorLevel% == 0 (
    echo %MINGW_BIN% is already in PATH.
) else (
    echo Adding %MINGW_BIN% to PATH...
    setx PATH "%PATH%;%MINGW_BIN%" /M
    echo %MINGW_BIN% has been added to PATH.
)

del %DESKTOP_DIR%\lanqiao-env.zip
del %DESKTOP_DIR%\lanqiao-app.zip
del %DESKTOP_DIR%\init.bat