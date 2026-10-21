@echo off
REM ==============================================================================
REM Hospital POS and Billing System - PyInstaller 32-bit Build Script
REM Target Platform: Windows 7 (32-bit and 64-bit) | Python 3.8.10 (32-bit)
REM ==============================================================================

echo [1/3] Checking Python 3.8.10 (32-bit) Environment...
python --version

echo [2/3] Installing dependencies from requirements.txt...
pip install -r requirements.txt

echo [3/3] Compiling Hospital POS into standalone distribution...
pyinstaller --noconfirm --onedir --windowed ^
    --name "Hospital_POS" ^
    --add-data "ui;ui" ^
    --hidden-import "win32print" ^
    --hidden-import "win32ui" ^
    --hidden-import "win32api" ^
    --hidden-import "win32con" ^
    --hidden-import "sqlite3" ^
    --hidden-import "requests" ^
    --hidden-import "cryptography" ^
    --hidden-import "ttkbootstrap" ^
    main.py

echo ==============================================================================
echo Build Completed!
echo Standalone executable is located at: dist\Hospital_POS\Hospital_POS.exe
echo ==============================================================================
pause
