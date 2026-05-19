@echo off
chcp 65001 >nul
title MicroBubble Agent - 启动

echo ========================================
echo   MicroBubble Agent 一键启动
echo ========================================
echo.

:: 1. 启动 Docker Desktop（如果未运行）
echo [1/3] 检查 Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
    echo [*] Docker Desktop 未运行，正在启动...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if errorlevel 1 (
        echo [*] 等待中...
        goto wait_docker
    )
    echo [+] Docker Desktop 已启动
) else (
    echo [=] Docker Desktop 已在运行
)

:: 2. 启动 Docker 服务
echo.
echo [2/3] 启动 Docker 服务（7个容器）...
cd /d "%~dp0"
docker compose up -d
if errorlevel 1 (
    echo [!] Docker 服务启动失败，请检查日志
    pause
    exit /b 1
)

:: 等待服务健康检查
echo [*] 等待服务就绪...
timeout /t 10 /nobreak >nul
docker compose ps --format "{{.Name}}: {{.Status}}" 2>nul | findstr /v "time="
echo [+] Docker 服务已启动

:: 3. 启动 FRP 客户端
echo.
echo [3/3] 启动 FRP 内网穿透...
tasklist /fi "imagename eq frpc.exe" 2>nul | find /i "frpc.exe" >nul
if not errorlevel 1 (
    echo [=] FRP 客户端已在运行，跳过
) else (
    if exist "%~dp0frp\frpc.exe" (
        start "frpc" /min "%~dp0frp\frpc.exe" -c "%~dp0frp\frpc.toml"
        echo [+] FRP 客户端已启动
    ) else (
        echo [!] FRP 客户端不存在: frp\frpc.exe
    )
)

echo.
echo ========================================
echo   启动完成！
echo   本地访问: http://localhost:8000/docs
echo   外网访问: https://agent.mnb-lab.cn
echo ========================================
echo.
pause
