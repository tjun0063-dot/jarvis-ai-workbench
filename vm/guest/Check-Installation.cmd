@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"%~dp0bootstrap-python\python.exe" -I "%~dp0check_installation.py"
pause
