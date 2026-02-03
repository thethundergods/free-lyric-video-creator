@echo off
echo ========================================
echo Building FREE Lyric Video Creator for Windows
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Build the executable
echo.
echo Building executable...
pyinstaller --onefile --windowed ^
    --name "FREE Lyric Video Creator" ^
    --icon icon.ico ^
    --add-data "icon.png;." ^
    --add-data "credentials;credentials" ^
    --hidden-import PIL._tkinter_finder ^
    main.py

echo.
echo ========================================
echo Build complete!
echo Executable is in: dist\FREE Lyric Video Creator.exe
echo ========================================
pause
