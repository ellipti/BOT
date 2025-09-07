@echo off
REM ==============================================================================
REM Trading Bot Startup Script for Windows
REM ==============================================================================
REM This script is designed to be run by Windows Task Scheduler or NSSM service
REM It handles environment setup, error checking, and graceful startup/shutdown

echo [%date% %time%] ===== Trading Bot Startup =====

REM Change to the bot directory
cd /d "%~dp0"
echo [%date% %time%] Working directory: %CD%

REM Verify virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [%date% %time%] ERROR: Virtual environment not found
    echo [%date% %time%] Please run: python -m venv .venv
    exit /b 1
)

REM Activate virtual environment
echo [%date% %time%] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Verify Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: Python not available in virtual environment
    exit /b 1
)
echo [%date% %time%] Python version:
python --version

REM Verify .env file exists
if not exist ".env" (
    echo [%date% %time%] ERROR: .env configuration file not found
    echo [%date% %time%] Please copy .env.example to .env and configure
    exit /b 1
)

REM Check if MT5 terminal is running (for attach mode)
tasklist /fi "imagename eq terminal64.exe" | find "terminal64.exe" >nul
if errorlevel 1 (
    echo [%date% %time%] WARNING: MetaTrader 5 terminal not detected
    echo [%date% %time%] If using ATTACH_MODE=true, please start MT5 first
) else (
    echo [%date% %time%] MetaTrader 5 terminal detected
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Check available disk space (minimum 1GB)
for /f "tokens=3" %%a in ('dir /-c %CD% ^| find "bytes free"') do set free=%%a
if %free% LSS 1073741824 (
    echo [%date% %time%] WARNING: Low disk space detected: %free% bytes
)

REM Start the trading bot
echo [%date% %time%] Starting Trading Bot...
echo [%date% %time%] Configuration: .env
echo [%date% %time%] Logs: logs\trading_bot.log

REM Run with error handling
python app.py
set EXIT_CODE=%errorlevel%

echo [%date% %time%] Trading Bot exited with code: %EXIT_CODE%

REM Handle exit codes
if %EXIT_CODE% EQU 0 (
    echo [%date% %time%] Trading Bot completed successfully
) else if %EXIT_CODE% EQU 1 (
    echo [%date% %time%] Trading Bot exited with general error
) else if %EXIT_CODE% EQU 2 (
    echo [%date% %time%] Trading Bot exited due to configuration error
) else if %EXIT_CODE% EQU 3 (
    echo [%date% %time%] Trading Bot exited due to connection error
) else (
    echo [%date% %time%] Trading Bot exited with unknown error code: %EXIT_CODE%
)

echo [%date% %time%] ===== Trading Bot Session Ended =====
exit /b %EXIT_CODE%
