@echo off
chcp 65001 >nul
title MicroBubble Agent - 停止

echo ========================================
echo   MicroBubble Agent 停止服务
echo ========================================
echo.

:: 1. 停止 Docker 服务
echo [1/2] 停止 Docker 服务...
cd /d "%~dp0"
docker compose down 2>nul
if errorlevel 1 (
    echo [!] Docker 服务停止失败（可能 Docker Desktop 未运行）
) else (
    echo [+] Docker 服务已停止（7个容器）
)

:: 2. 停止 FRP 客户端
echo.
echo [2/2] 停止 FRP 客户端...
tasklist /fi "imagename eq frpc.exe" 2>nul | find /i "frpc.exe" >nul
if not errorlevel 1 (
    taskkill /f /im frpc.exe >nul 2>&1
    echo [+] FRP 客户端已停止
) else (
    echo [=] FRP 客户端未运行
)

echo.
echo [+] 全部服务已停止
echo.
echo 提示: Docker Desktop 仍在运行，如需关闭请手动退出
echo.
pause
