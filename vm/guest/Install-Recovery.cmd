@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"C:\Jarvis\workbench\.wechat-venv\Scripts\python.exe" -I "%~dp0install_recovery.py"
pause
