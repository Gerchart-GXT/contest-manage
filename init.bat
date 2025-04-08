@echo off
setlocal

set DESKTOP_DIR=C:\Users\%USERNAME%\Desktop
set LANQIAO_ENV_DIR=C:\lanqiao\env
set LANQIAO_APP_DIR=%DESKTOP_DIR%

echo Installing Python...
%LANQIAO_ENV_DIR%\python-3.8.6-amd64.exe /quiet InstallAllUsers=1 PrependPath=1
if errorlevel 1 (
    echo Python installation failed.
    exit /b 1
)

set PYTHON_BIN=C:\Program Files\Python38\
echo %PATH% | find /i "%PYTHON_BIN%" >nul
if %errorLevel% == 0 (
    echo %PYTHON_BIN% is already in PATH.
) else (
    echo Adding %PYTHON_BIN% to PATH...
    setx PATH "%PATH%;%PYTHON_BIN%" /M
    echo %PYTHON_BIN% has been added to PATH.
)

set PYTHON_SCRIPTS=C:\Program Files\Python38\Scripts\
echo %PATH% | find /i "%PYTHON_SCRIPTS%" >nul
if %errorLevel% == 0 (
    echo %PYTHON_SCRIPTS% is already in PATH.
) else (
    echo Adding %PYTHON_SCRIPTS% to PATH...
    setx PATH "%PATH%;%PYTHON_SCRIPTS%" /M
    echo %PYTHON_SCRIPTS% has been added to PATH.
)

set PYTHON_BIN_OLD=C:\Program Files\Python35\
echo %PATH% | find /i "%PYTHON_BIN_OLD%" >nul
if %errorLevel% == 0 (
    echo Removing %PYTHON_BIN_OLD% from PATH...
    for /f "delims=" %%A in ('echo %PATH%') do set "newPathVar=%%A"
    set "newPathVar=%newPathVar:;%PYTHON_BIN_OLD%=%"
    setx PATH "%newPathVar%" /M
    echo %PYTHON_BIN_OLD% has been removed from PATH.
)

set PYTHON_SCRIPTS_OLD=C:\Program Files\Python35\Scripts\
echo %PATH% | find /i "%PYTHON_SCRIPTS_OLD%" >nul
if %errorLevel% == 0 (
    echo Removing %PYTHON_SCRIPTS_OLD% from PATH...
    for /f "delims=" %%A in ('echo %PATH%') do set "newPathVar=%%A"
    set "newPathVar=%newPathVar:;%PYTHON_SCRIPTS_OLD%=%"
    setx PATH "%newPathVar%" /M
    echo %PYTHON_SCRIPTS_OLD% has been removed from PATH.
)

echo Installing Java...
%LANQIAO_ENV_DIR%\jdk-8u261-windows-x64.exe /s
if errorlevel 1 (
    echo Java installation failed.
    exit /b 1
)

set JDK_BIN=C:\Program Files\Java\jdk1.8.0_261\bin\
echo %PATH% | find /i "%JDK_BIN%" >nul
if %errorLevel% == 0 (
    echo %JDK_BIN% is already in PATH.
) else (
    echo Adding %JDK_BIN% to PATH...
    setx PATH "%PATH%;%JDK_BIN%" /M
    echo %JDK_BIN% has been added to PATH.
)

set JRE_BIN=C:\Program Files\Java\jre1.8.0_261\bin\
echo %PATH% | find /i "%JRE_BIN%" >nul
if %errorLevel% == 0 (
    echo %JRE_BIN% is already in PATH.
) else (
    echo Adding %JRE_BIN% to PATH...
    setx PATH "%PATH%;%JRE_BIN%" /M
    echo %JRE_BIN% has been added to PATH.
)

echo Installing Node.js...
msiexec /i %LANQIAO_ENV_DIR%\node-v12.14.1-x64.msi /quiet
if errorlevel 1 (
    echo Node.js installation failed.
    exit /b 1
)

echo Installing VSCode...
%LANQIAO_ENV_DIR%\VSCodeUserSetup-x64-1.61.2.exe /verysilent /suppressmsgboxes /norestart
if errorlevel 1 (
    echo VSCode installation failed.
    exit /b 1
)

taskkill /IM Code.exe /F /T

echo Installing 7-Zip...
%LANQIAO_ENV_DIR%\7z2104-x64.exe /S
if errorlevel 1 (
    echo 7-Zip installation failed.
    exit /b 1
)

echo Unzipping MinGW...
tar -xf %LANQIAO_ENV_DIR%\MinGW64.zip -C %LANQIAO_ENV_DIR%\
if errorlevel 1 (
    echo MinGW extraction failed.
    exit /b 1
)

set MINGW_BIN=%LANQIAO_ENV_DIR%\MinGW64\bin\
echo %PATH% | find /i "%MINGW_BIN%" >nul
if %errorLevel% == 0 (
    echo %MINGW_BIN% is already in PATH.
) else (
    echo Adding %MINGW_BIN% to PATH...
    setx PATH "%PATH%;%MINGW_BIN%" /M
    echo %MINGW_BIN% has been added to PATH.
)

echo Installation complete!
del %DESKTOP_DIR%\init.bat

endlocal