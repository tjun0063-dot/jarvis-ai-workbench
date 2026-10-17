@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"%~dp0bootstrap-python\python.exe" -I "%~dp0setup_guest.py"
if errorlevel 1 (
    echo INSTALLATION FAILED. Keep this window open and report the error above.
) else (
    echo INSTALLATION COMPLETED. Open C:\Jarvis\Open-WeChat.cmd next.
)
pause
