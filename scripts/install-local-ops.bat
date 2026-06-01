@echo off
chcp 65001 >nul
title MicroBubble Local Ops Installer

echo ========================================
echo   MicroBubble 本地运维定时任务注册
echo ========================================
echo.

:: 0. 检查管理员权限（schtasks 注册可选，普通用户也可用）
net session >nul 2>&1
if errorlevel 1 (
    echo [!] 当前不是管理员，部分任务可能注册失败
    echo [!] 建议右键以管理员身份运行本脚本
    echo.
)

:: 1. 健康检查 watchdog - 每 5 分钟
echo [1/3] 注册 Watchdog（每 5 分钟健康检查）...
schtasks /Create /TN "MicrobubbleWatchdog" ^
    /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"%~dp0local-watchdog.ps1\"" ^
    /SC MINUTE /MO 5 /F >nul 2>&1
if errorlevel 1 (
    echo [!] Watchdog 注册失败
) else (
    echo [+] Watchdog 已注册（每 5 分钟）
)

:: 2. 数据库备份 - 每日 02:00
echo.
echo [2/3] 注册 DB Backup（每日 02:00）...
schtasks /Create /TN "MicrobubbleDBBackup" ^
    /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"%~dp0local-backup.ps1\"" ^
    /SC DAILY /ST 02:00 /F >nul 2>&1
if errorlevel 1 (
    echo [!] DB Backup 注册失败
) else (
    echo [+] DB Backup 已注册（每日 02:00）
)

:: 3. 前端构建校验 - 手动触发（创建任务但禁用，仅供 on-demand 使用）
echo.
echo [3/3] 注册 Build Verify（手动触发）...
schtasks /Create /TN "MicrobubbleBuildVerify" ^
    /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"%~dp0local-build-verify.ps1\"" ^
    /SC ONCE /TN MicrobubbleBuildVerify /ST 00:00 /F >nul 2>&1
if errorlevel 1 (
    echo [!] Build Verify 注册失败
) else (
    echo [+] Build Verify 已注册（手动: schtasks /Run /TN MicrobubbleBuildVerify）
)

echo.
echo ========================================
echo   验证注册结果：
echo ========================================
schtasks /Query /TN "MicrobubbleWatchdog" /V /FO LIST 2>nul | findstr /C:"Task Name" /C:"Run As User" /C:"Schedule" /C:"Next Run Time"
echo ---
schtasks /Query /TN "MicrobubbleDBBackup" /V /FO LIST 2>nul | findstr /C:"Task Name" /C:"Run As User" /C:"Schedule" /C:"Next Run Time"
echo.
echo ========================================
echo   立即手动跑一次试试：
echo ========================================
echo   schtasks /Run /TN "MicrobubbleWatchdog"
echo   schtasks /Run /TN "MicrobubbleDBBackup"
echo   schtasks /Run /TN "MicrobubbleBuildVerify"
echo.
echo   或直接：
echo   powershell %~dp0local-watchdog.ps1
echo   powershell %~dp0local-backup.ps1
echo   powershell %~dp0local-build-verify.ps1
echo.
echo   卸载任务（如果需要）：
echo   schtasks /Delete /TN "MicrobubbleWatchdog" /F
echo   schtasks /Delete /TN "MicrobubbleDBBackup" /F
echo   schtasks /Delete /TN "MicrobubbleBuildVerify" /F
echo.
pause
