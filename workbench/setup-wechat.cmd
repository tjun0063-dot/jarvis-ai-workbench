@echo off
cd /d "%~dp0"
if exist ".wechat-venv\Scripts\python.exe" goto install
py -3.12 -m venv .wechat-venv
if errorlevel 1 (
  echo Python 3.12 is required. Install Python 3.12, then run this file again.
  pause
  exit /b 1
)
:install
.wechat-venv\Scripts\python.exe -m pip install -r requirements-wechat.txt
if errorlevel 1 (
  pause
  exit /b 1
)
echo WeChat adapter installed. Open the assistant account main window before connecting.
pause
