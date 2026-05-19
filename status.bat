@echo off
chcp 65001 >nul
title MicroBubble Agent - 状态

echo ========================================
echo   MicroBubble Agent 服务状态
echo ========================================
echo.

:: Docker 状态
echo [Docker Desktop]
docker info >nul 2>&1
if errorlevel 1 (
    echo   状态: 未运行
) else (
    echo   状态: 运行中
)

:: Docker 服务状态
echo.
echo [Docker 服务]
cd /d "%~dp0"
docker compose ps --format "  {{.Name}}: {{.Status}}" 2>nul | findstr /v "time="

:: FRP 状态
echo.
echo [FRP 内网穿透]
tasklist /fi "imagename eq frpc.exe" 2>nul | find /i "frpc.exe" >nul
if not errorlevel 1 (
    echo   状态: 运行中
) else (
    echo   状态: 未运行
)

echo.
echo ========================================
pause
