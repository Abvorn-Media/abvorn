@echo off
title Abvorn Daemon
cd /d "%~dp0"
echo ========================================
echo   Abvorn Autonomous Affiliate Network
echo   Starting daemon...
echo ========================================
echo.

if not exist venv\Scripts\activate (
    echo [ERROR] Virtual environment not found. Run: python -m venv venv
    pause
    exit /b 1
)

call venv\Scripts\activate

echo [1/3] Checking secrets...
python -c "from abvorn.core.secrets import load_secrets; s=load_secrets(); print('  OK - %d keys loaded' %% len(s))" 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARN] Secrets issue - check ~/.abvorn/boardroom/secrets.json
)

echo [2/3] Checking migration...
python -m abvorn migrate 2>&1

echo [3/3] Starting daemon...
echo.
echo Press Ctrl+C to stop
echo.

:loop
python -m abvorn daemon
echo [INFO] Daemon stopped. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
