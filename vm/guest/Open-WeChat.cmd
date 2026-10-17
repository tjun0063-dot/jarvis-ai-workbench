@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"%~dp0workbench\.wechat-venv\Scripts\python.exe" -I "%~dp0launch_wechat.py"
pause
