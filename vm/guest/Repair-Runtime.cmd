@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"C:\Jarvis\python\python.exe" -I "%~dp0repair_runtime.py"
if errorlevel 3010 (
  echo Restart only the Jarvis VM, log into WeChat, then run Start-Agent.cmd.
  pause
  exit /b 3010
)
if errorlevel 1 (
  echo RUNTIME REPAIR FAILED. Please report Runtime-repair-result.txt.
  pause
  exit /b 1
)
echo Runtime check passed. Starting the connector.
call "C:\Jarvis\Start-Agent.cmd"
