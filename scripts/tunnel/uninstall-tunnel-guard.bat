@echo off
schtasks /Delete /TN "MicroBubble-SSH-Tunnel-Guard" /F
if %errorlevel%==0 echo [tunnel-guard] scheduled task removed
