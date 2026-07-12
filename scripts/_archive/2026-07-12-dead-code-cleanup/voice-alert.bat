@echo off
REM MicroBubble Voice Alert - .bat wrapper
REM
REM Usage:
REM   scripts\voice-alert -TaskDone              # 默认仅 TTS，2 秒完成
REM   scripts\voice-alert -TaskDone -ShowToast   # 戴耳机场景：TTS + 通知
REM   scripts\voice-alert -Message "Claude completed"
REM   scripts\voice-alert -OnError "failed"
REM   scripts\voice-alert -Quiet -Message "silent log only"

setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%voice-alert.ps1"

if not exist "%PS_SCRIPT%" (
    echo ERROR: %PS_SCRIPT% not found
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
exit /b %ERRORLEVEL%