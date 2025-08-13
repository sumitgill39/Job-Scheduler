@echo off
REM Windows Job Scheduler CLI Startup Script

echo ================================================
echo    Windows Job Scheduler - CLI Mode
echo ================================================

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Install dependencies if requirements.txt is newer than installed packages
if exist requirements.txt (
    echo Installing/updating dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting Job Scheduler in CLI mode...
echo Type 'help' for available commands
echo Type 'quit' to exit
echo.

REM Start the application in CLI mode
python main.py --mode cli

pause