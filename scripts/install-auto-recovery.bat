@echo off
REM ============================================================
REM MicroBubble Auto Recovery Installer (Windows Task Scheduler)
REM W2 +N 2026-08-04: Auto-install scheduled task triggered by
REM user logon event (Winlogon EventID=7002) + DELAY 2 minutes
REM
REM Trigger: User logs in → 2 min delay → auto-recovery.ps1 runs
REM Why: Docker Desktop 通过 WSL2 backend 运行, 不写 EventLog
REM      (explored 2026-08-04, only WSL events with empty messages)
REM      Winlogon 7002 = "User logon session created" 每次 session 都触发
REM
REM Install (admin PowerShell):
REM   E:\microbubble-agent\scripts\install-auto-recovery.bat
REM
REM Or direct schtasks:
REM   schtasks /Create /TN "MicroBubble-Auto-Recovery" ^
REM     /TR "\"E:\microbubble-agent\scripts\auto-recovery-eventlog.ps1\"" ^
REM     /SC ONEVENT /EC Application ^
REM     /MO "*[System[Provider[@Name='Microsoft-Windows-Winlogon']] and EventID=7002]" ^
REM     /DELAY 0002:00 /RL HIGHEST /F
REM
REM Remove:
REM   schtasks /Delete /TN "MicroBubble-Auto-Recovery" /F
REM
REM Query:
REM   schtasks /Query /TN "MicroBubble-Auto-Recovery" /V /FO LIST
REM ============================================================

setlocal

set TASK_NAME=MicroBubble-Auto-Recovery
set SCRIPT_PATH=E:\microbubble-agent\scripts\auto-recovery-eventlog.ps1
set QUERY_XPATH=*[System[Provider[@Name='Microsoft-Windows-Winlogon']] and EventID=7002]

echo ============================================================
echo MicroBubble Auto Recovery Installer
echo ============================================================
echo.

REM Check admin privileges
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] This script requires administrator privileges.
    echo Please run from an admin PowerShell:
    echo   Start-Process "%~f0" -Verb RunAs -Wait
    exit /b 1
)

echo [1/3] Creating scheduled task: %TASK_NAME%
echo   Trigger: User logon (Winlogon EventID=7002) + 2 min delay
echo   Script:  %SCRIPT_PATH%
echo.

schtasks /Create /TN "%TASK_NAME%" ^
    /TR "\"%SCRIPT_PATH%\"" ^
    /SC ONEVENT ^
    /EC Application ^
    /MO "%QUERY_XPATH%" ^
    /DELAY 0002:00 ^
    /RL HIGHEST ^
    /F

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] schtasks /Create failed (rc=%ERRORLEVEL%)
    echo Manual command:
    echo   schtasks /Create /TN "%TASK_NAME%" /TR "\"%SCRIPT_PATH%\"" /SC ONEVENT /EC Application /MO "%QUERY_XPATH%" /DELAY 0002:00 /RL HIGHEST /F
    exit /b 2
)

echo.
echo [2/3] Verifying task registered...
schtasks /Query /TN "%TASK_NAME%" /FO LIST 2>&1 | findstr /C:"TaskName:" /C:"Run:" /C:"Delay:" /C:"Schedule:" /C:"Logon Mode:" /C:"Run As User:"
echo.

echo [3/3] Task is registered. Trigger fires on next user logon.
echo.
echo ============================================================
echo Test commands (run manually to verify):
echo ============================================================
echo   # Query task
echo   schtasks /Query /TN "%TASK_NAME%" /V /FO LIST
echo.
echo   # Trigger immediately (no need to log off/on)
echo   schtasks /Run /TN "%TASK_NAME%"
echo.
echo   # View logs after trigger
echo   type E:\microbubble-agent\logs\auto-recovery\auto-recovery-*.log
echo.
echo   # Remove task
echo   schtasks /Delete /TN "%TASK_NAME%" /F
echo ============================================================

endlocal & exit /b 0