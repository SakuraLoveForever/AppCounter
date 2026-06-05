@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "AppCounter.exe" (
    start "" "AppCounter.exe" %*
) else (
    python main.py %*
)
