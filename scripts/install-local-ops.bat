@echo off
chcp 65001 >nul
title MicroBubble Local Ops Installer

echo ========================================
echo   MicroBubble Local Ops - One-Click Installer
echo ========================================
echo.

REM Check admin privileges (optional but recommended for schtasks)
net session >nul 2>&1
if errorlevel 1 (
    echo [!] Not running as administrator. Some tasks may fail.
    echo [!] Right-click and "Run as administrator" is recommended.
    echo.
)

REM Set the script directory as the working dir
set "SCRIPT_DIR=%~dp0"
set "PS_EXEC=powershell.exe -NoProfile -ExecutionPolicy Bypass -File"

REM 1. Health check watchdog - every 5 minutes
echo [1/3] Registering Watchdog (every 5 minutes)...
schtasks /Create /TN "MicrobubbleWatchdog" /TR "%PS_EXEC% \"%SCRIPT_DIR%local-watchdog.ps1\"" /SC MINUTE /MO 5 /F
if errorlevel 1 (
    echo [!] Watchdog registration FAILED
) else (
    echo [+] Watchdog registered (every 5 minutes)
)

REM 2. Database backup - daily at 02:00
echo.
echo [2/3] Registering DB Backup (daily 02:00)...
schtasks /Create /TN "MicrobubbleDBBackup" /TR "%PS_EXEC% \"%SCRIPT_DIR%local-backup.ps1\"" /SC DAILY /ST 02:00 /F
if errorlevel 1 (
    echo [!] DB Backup registration FAILED
) else (
    echo [+] DB Backup registered (daily 02:00)
)

REM 3. Build verify - manual trigger
echo.
echo [3/3] Registering Build Verify (manual trigger)...
schtasks /Create /TN "MicrobubbleBuildVerify" /TR "%PS_EXEC% \"%SCRIPT_DIR%local-build-verify.ps1\"" /SC ONCE /ST 00:00 /F
if errorlevel 1 (
    echo [!] Build Verify registration FAILED
) else (
    echo [+] Build Verify registered (manual via schtasks /Run)
)

echo.
echo ========================================
echo   Verification - listing Microbubble tasks:
echo ========================================
schtasks /Query /FO TABLE 2>nul | findstr /I "Microbubble"
echo.

echo ========================================
echo   Manual run commands (anytime):
echo ========================================
echo   schtasks /Run /TN "MicrobubbleWatchdog"
echo   schtasks /Run /TN "MicrobubbleDBBackup"
echo   schtasks /Run /TN "MicrobubbleBuildVerify"
echo.
echo   Or direct:
echo   powershell "%SCRIPT_DIR%local-watchdog.ps1"
echo   powershell "%SCRIPT_DIR%local-backup.ps1"
echo   powershell "%SCRIPT_DIR%local-build-verify.ps1"
echo.
echo   Uninstall:
echo   schtasks /Delete /TN "MicrobubbleWatchdog" /F
echo   schtasks /Delete /TN "MicrobubbleDBBackup" /F
echo   schtasks /Delete /TN "MicrobubbleBuildVerify" /F
echo.
pause
