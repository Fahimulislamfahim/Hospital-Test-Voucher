@echo off
title Hospital POS Launcher
cd /d "%~dp0Hospital_POS"
echo ===================================================
echo Starting Hospital POS - Diagnostic Billing System...
echo ===================================================
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error code: %ERRORLEVEL%
    pause
)
