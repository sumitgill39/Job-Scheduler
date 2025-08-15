@echo off
REM Windows Job Scheduler Startup Script

echo ================================================
echo        Windows Job Scheduler
echo ================================================

REM Check if Python is available
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if we're in a virtual environment
if "%VIRTUAL_ENV%"=="" (
    echo WARNING: Not in a virtual environment
    echo It's recommended to create and activate a virtual environment:
    echo   py -m venv venv
    echo   venv\Scripts\activate
    echo.
)

REM Install dependencies if requirements.txt is newer than installed packages
if exist requirements.txt (
    echo Installing/updating dependencies...
    py -m pip install -r requirements.txt
    py -m pip install ldap3 dnspython cryptography 
)

echo.
echo Starting Job Scheduler in web mode...
echo Web interface will be available at: http://localhost:5000
echo.
echo Press Ctrl+C to stop
echo.

REM Start the application
py main.py --mode web

pause