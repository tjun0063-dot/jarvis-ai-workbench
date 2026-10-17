@echo off
if /i "%~1"=="--console" goto run
start "Jarvis Material Collection Update v4" "%ComSpec%" /d /k ""%~f0" --console"
if errorlevel 1 goto launch_failed
exit /b 0
:run
title Jarvis Material Collection Update v4
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "JARVIS_LAUNCHER_REPORT=1"
set "JARVIS_LOG_DIR=%LOCALAPPDATA%\JarvisGuest"
if not exist "%JARVIS_LOG_DIR%" mkdir "%JARVIS_LOG_DIR%"
set "JARVIS_UPDATE_REPORT=%JARVIS_LOG_DIR%\Attachment-launch-result.txt"
> "%JARVIS_UPDATE_REPORT%" echo JARVIS_MATERIAL_COLLECTION_UPDATE_V4
echo Jarvis Material Collection Update v4
echo Starting the verified update. Please wait; this window will stay open.
echo Report: "%JARVIS_UPDATE_REPORT%"
if not exist "C:\Jarvis\workbench\.wechat-venv\Scripts\python.exe" goto missing_python
if not exist "%~dp0update_attachments.py" goto missing_payload
"C:\Jarvis\workbench\.wechat-venv\Scripts\python.exe" -u -I -X utf8 "%~dp0update_attachments.py" >> "%JARVIS_UPDATE_REPORT%" 2>&1
set "JARVIS_UPDATE_EXIT=%errorlevel%"
goto report
:missing_python
>> "%JARVIS_UPDATE_REPORT%" echo ERROR: Installed Python was not found at C:\Jarvis\workbench\.wechat-venv\Scripts\python.exe
set "JARVIS_UPDATE_EXIT=3"
goto report
:missing_payload
>> "%JARVIS_UPDATE_REPORT%" echo ERROR: update_attachments.py is missing from this deployment disc. Refresh the disc folder and retry.
set "JARVIS_UPDATE_EXIT=4"
:report
>> "%JARVIS_UPDATE_REPORT%" echo Update process exit code: %JARVIS_UPDATE_EXIT%
echo.
type "%JARVIS_UPDATE_REPORT%"
start "" "%SystemRoot%\System32\notepad.exe" "%JARVIS_UPDATE_REPORT%"
if not "%JARVIS_UPDATE_EXIT%"=="0" goto failed
echo UPDATE COMPLETED. Closing this console does not stop the background connector.
exit /b 0
:failed
echo UPDATE FAILED. Keep the report open and send its error text to the workbench.
exit /b %JARVIS_UPDATE_EXIT%
:launch_failed
echo Could not open the persistent console. Run this file from cmd.exe with --console.
pause
exit /b 1
