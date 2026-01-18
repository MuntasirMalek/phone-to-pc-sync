@echo off
REM Downloads Sync - Windows Service Installer
REM This script installs Downloads Sync to run at startup

echo.
echo =========================================
echo Downloads Sync - Windows Installer
echo =========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo Python is required but not installed.
        echo Install it from: https://www.python.org/
        pause
        exit /b 1
    )
)

REM Get script directory
set SCRIPT_DIR=%~dp0

REM Create VBS launcher for hidden window
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set VBS_FILE=%STARTUP_DIR%\DownloadsSync.vbs

echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_FILE%"
echo WshShell.Run "python ""%SCRIPT_DIR%server.py""", 0, False >> "%VBS_FILE%"

echo Service installed successfully!
echo.
echo The server will auto-start on login.
echo.
echo To start now, run: python server.py
echo.
echo To uninstall, delete:
echo   %VBS_FILE%
echo.

REM Start the server now
start "" python "%SCRIPT_DIR%server.py"

pause
