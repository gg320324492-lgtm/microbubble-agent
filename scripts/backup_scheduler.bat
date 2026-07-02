@echo off
REM ============================================================
REM MicroBubble Daily Backup Wrapper (Windows Task Scheduler)
REM P0-2 2026-07-03 fix: rewrite with pure ASCII to avoid
REM Windows cmd.exe ANSI (CP936) encoding trap on UTF-8 .bat
REM
REM Install (admin PowerShell):
REM   schtasks /Create /TN "MicroBubble-Daily-Backup" ^
REM     /TR "\"E:\microbubble-agent\scripts\backup_scheduler.bat\"" ^
REM     /SC DAILY /ST 02:00 /F
REM
REM Remove:
REM   schtasks /Delete /TN "MicroBubble-Daily-Backup" /F
REM
REM Query:
REM   schtasks /Query /TN "MicroBubble-Daily-Backup" /V /FO LIST
REM ============================================================

setlocal

REM cd to project root (script depends on docker-compose.yml)
cd /d "E:\microbubble-agent"

REM log dir
set LOG_DIR=E:\microbubble-agent\logs\backup
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM log filename: backup_scheduler_yyyy-mm-dd.log
REM Avoid %DATE% slice (locale dependent: en=MM/DD/YYYY, zh-CN=YYYY/MM/DD)
REM Just strip / and : from %DATE% + %TIME% to keep filename safe
set TODAY=%DATE:/=-%
set LOG_FILE=%LOG_DIR%\backup_scheduler_%TODAY%.log

echo [%DATE% %TIME%] backup scheduler starting >> "%LOG_FILE%"

REM Run backup_db.sh via Git Bash
REM Use absolute path for bash.exe to avoid PATH drift
set BASH_EXE=C:\Program Files\Git\bin\bash.exe
if not exist "%BASH_EXE%" (
  echo [%DATE% %TIME%] ERROR: bash.exe not found at "%BASH_EXE%" >> "%LOG_FILE%"
  exit /b 2
)

call "%BASH_EXE%" "E:\microbubble-agent\scripts\backup_db.sh" >> "%LOG_FILE%" 2>&1
set RC=%ERRORLEVEL%

echo [%DATE% %TIME%] backup scheduler finished exit=%RC% >> "%LOG_FILE%"

REM Cleanup logs older than 7 days
forfiles /p "%LOG_DIR%" /m "backup_scheduler_*.log" /d -7 /c "cmd /c del @path" 2>>"%LOG_FILE%"

endlocal & exit /b %RC%