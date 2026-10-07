@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-stack.ps1" -Version 2
if errorlevel 1 (
    if not defined TRAVELROUTE_NO_PAUSE pause
    exit /b 1
)
