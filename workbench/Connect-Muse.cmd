@echo off
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File "%~dp0Connect-Muse.ps1"
if errorlevel 1 pause
