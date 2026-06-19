@echo off
REM MicroBubble reprocess meeting wrapper (cmd.exe)
REM
REM Usage:
REM   scripts\run-reprocess.bat 120
REM   scripts\run-reprocess.bat 120 verify
REM   scripts\run-reprocess.bat 120 regen
REM   scripts\run-reprocess.bat 120 apply "C:\path\to\audio.m4a"
REM
REM Steps: load,extract,cluster,vote,assign,apply,regen,verify
REM   verify  - 8 fields check (no audio)
REM   regen   - regenerate summary/key_points/decisions
REM   apply   - full reprocess (extract + apply + regen, needs audio)
REM   (default) = all steps

setlocal

if "%~1"=="" goto :help
if "%~1"=="/?" goto :help
if "%~1"=="-h" goto :help
if "%~1"=="--help" goto :help

set "MEETING=%~1"
set "STEPS=%~2"
if "%STEPS%"=="" set "STEPS=load,extract,cluster,vote,assign,apply,regen,verify"
set "AUDIO=%~3"
set "CONTAINER=microbubble-agent-app-1"

if not "%AUDIO%"=="" (
    if not exist "%AUDIO%" (
        echo [ERR] audio file not found: %AUDIO%
        exit /b 1
    )
)

echo [1/5] container check
docker ps --format "{{.Names}}" > "%TEMP%\docker_ps.txt" 2>nul
findstr /B /C:"%CONTAINER%" "%TEMP%\docker_ps.txt" >nul 2>&1
if errorlevel 1 (
    echo [ERR] container %CONTAINER% not running
    type "%TEMP%\docker_ps.txt" 2>nul
    del "%TEMP%\docker_ps.txt" 2>nul
    exit /b 1
)
del "%TEMP%\docker_ps.txt" 2>nul
echo   OK  container: %CONTAINER%

echo [2/5] sync script to container
docker cp "%~dp0reprocess_meeting.py" "%CONTAINER%:/tmp/reprocess_meeting.py" >nul
if errorlevel 1 (
    echo [ERR] docker cp reprocess_meeting.py failed
    exit /b 1
)
echo   OK  /tmp/reprocess_meeting.py synced

set "DOCKER_AUDIO="
if not "%AUDIO%"=="" (
    echo [3/5] copy audio to container
    for %%F in ("%AUDIO%") do set "AUDIO_NAME=%%~nxF"
    set "DOCKER_AUDIO=/tmp/%AUDIO_NAME%"
    docker cp "%AUDIO%" "%CONTAINER%:%DOCKER_AUDIO%" >nul
    if errorlevel 1 (
        echo [ERR] docker cp audio failed
        exit /b 1
    )
    echo   OK  audio: %DOCKER_AUDIO%
) else (
    echo [3/5] skip audio copy
    echo "%STEPS%" | findstr "extract" >nul
    if not errorlevel 1 (
        echo   WARN Steps has extract but no audio arg
    )
)

echo [4/5] run reprocess
echo     Meeting: %MEETING%
echo     Steps:   %STEPS%
echo     Audio:   %DOCKER_AUDIO%
echo.

echo ------ docker exec output ------
if not "%DOCKER_AUDIO%"=="" (
    docker exec -i %CONTAINER% python /tmp/reprocess_meeting.py --meeting %MEETING% --steps %STEPS% --audio %DOCKER_AUDIO%
) else (
    docker exec -i %CONTAINER% python /tmp/reprocess_meeting.py --meeting %MEETING% --steps %STEPS%
)
set "EXIT_CODE=%ERRORLEVEL%"
echo ------ end (exit %EXIT_CODE%) ------

if not "%EXIT_CODE%"=="0" (
    echo [ERR] reprocess_meeting.py failed
    exit /b %EXIT_CODE%
)

echo [5/5] output files in container
echo     /tmp/reprocess_%MEETING%_result.json          ^(intermediate^)
echo     /tmp/reprocess_%MEETING%_new_transcript.json ^(new transcript^)
echo     /tmp/meeting_%MEETING%_backup_*.json         ^(apply backup^)
echo     /tmp/meeting_%MEETING%_summary_backup_*.json ^(regen backup^)
echo.
echo   OK  done
echo.
echo Verify in browser: hard refresh ^(Ctrl+Shift+R^)

exit /b 0

:help
echo Usage:
echo   scripts\run-reprocess.bat ^<meeting_id^>
echo   scripts\run-reprocess.bat ^<meeting_id^> ^<steps^>
echo   scripts\run-reprocess.bat ^<meeting_id^> ^<steps^> ^<audio_path^>
echo.
echo Steps: load,extract,cluster,vote,assign,apply,regen,verify
echo   verify  - 8 fields check (no audio)
echo   regen   - regenerate summary/key_points/decisions
echo   apply   - full reprocess (extract + apply + regen, needs audio)
echo   (default) = all steps
exit /b 0
