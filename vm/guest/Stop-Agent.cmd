@echo off
chcp 65001 >nul
"%~dp0workbench\.wechat-venv\Scripts\python.exe" -I "%~dp0background_agent.py" stop
pause
