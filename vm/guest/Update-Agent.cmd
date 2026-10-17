@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"C:\Jarvis\python\python.exe" -I "%~dp0update_launcher.py" --agent
if errorlevel 1 (
  echo UPDATE FAILED. Keep this window open and report the error above.
  pause
  exit /b 1
)
echo Agent updated. Keep WeChat logged in. Starting the connector.
call "C:\Jarvis\Start-Agent.cmd"
