@echo off
REM Passive Agent Startup Script for Windows
REM This script starts the passive agent and registers it with the Job Scheduler

setlocal

REM Configuration - Modify these values for your environment
set SCHEDULER_URL=http://127.0.0.1:5000
set AGENT_ID=passive-agent-%COMPUTERNAME%
set AGENT_NAME=Passive Agent - %COMPUTERNAME%
set AGENT_POOL=default
set AGENT_PORT=8080
set HEARTBEAT_INTERVAL=30
set LOG_LEVEL=INFO
set WORK_DIR=%~dp0..\agent_workspace

REM Create work directory if it doesn't exist
if not exist "%WORK_DIR%" (
    mkdir "%WORK_DIR%"
    echo Created work directory: %WORK_DIR%
)

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

REM Check if required packages are installed
echo Checking required Python packages...
python -c "import requests, pyyaml, psutil, flask" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing required packages...
    pip install requests pyyaml psutil flask
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to install required packages
        pause
        exit /b 1
    )
)

REM Display configuration
echo.
echo ====================================
echo  Passive Agent Configuration
echo ====================================
echo Scheduler URL: %SCHEDULER_URL%
echo Agent ID: %AGENT_ID%
echo Agent Name: %AGENT_NAME%
echo Agent Pool: %AGENT_POOL%
echo Agent Port: %AGENT_PORT%
echo Work Directory: %WORK_DIR%
echo Log Level: %LOG_LEVEL%
echo ====================================
echo.

REM Start the passive agent
echo Starting Passive Agent...
python "%~dp0..\docs\PassiveAgentSetup.py" ^
    --scheduler-url "%SCHEDULER_URL%" ^
    --agent-id "%AGENT_ID%" ^
    --agent-name "%AGENT_NAME%" ^
    --agent-pool "%AGENT_POOL%" ^
    --agent-port %AGENT_PORT% ^
    --heartbeat-interval %HEARTBEAT_INTERVAL% ^
    --log-level %LOG_LEVEL% ^
    --work-dir "%WORK_DIR%"

echo.
echo Passive Agent has stopped.
pause