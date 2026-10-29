@echo off
title BJUT Campus Login
cd /d "%~dp0"
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3 and check "Add to PATH".
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
python campus_login.py
echo.
pause
