# MicroBubble Backup Scheduler 安装脚本 (Windows Task Scheduler)
# P0-2 2026-07-03: 自动注册每日 02:00 备份任务.
# 部署: powershell -ExecutionPolicy Bypass -File scripts\install-backup-scheduler.ps1

$ErrorActionPreference = "Stop"

$TaskName = "MicroBubble-Daily-Backup"
$BatPath = "E:\microbubble-agent\scripts\backup_scheduler.bat"
$Time = "02:00"
$WorkDir = "E:\microbubble-agent"

# 校验 bat 文件存在
if (-not (Test-Path $BatPath)) {
    Write-Host "[ERROR] $BatPath 不存在" -ForegroundColor Red
    exit 1
}

# 校验 Git Bash 存在 (scheduler 依赖)
$BashPath = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path $BashPath)) {
    Write-Host "[ERROR] $BashPath 不存在, 备份调度依赖 Git Bash 跑 backup_db.sh" -ForegroundColor Red
    Write-Host "        请先安装 Git for Windows 或改用 local-backup.ps1 (PowerShell 原生版)" -ForegroundColor Yellow
    exit 2
}

# 幂等: 先删旧 task (避免 schtasks /Create 报 "already exists")
$existingTask = schtasks /Query /TN $TaskName 2>$null
if ($existingTask -and $LASTEXITCODE -eq 0) {
    Write-Host "[INFO] 检测到旧 task '$TaskName', 先删除..." -ForegroundColor Yellow
    schtasks /Delete /TN $TaskName /F | Out-Null
}

# 注册新 task
Write-Host "[INFO] 注册 Task Scheduler task '$TaskName'..." -ForegroundColor Cyan
$output = schtasks /Create /TN $TaskName `
    /TR "`"$BatPath`"" `
    /SC DAILY /ST $Time `
    /RL HIGHEST `
    /RU SYSTEM `
    /F 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] schtasks /Create 失败: $output" -ForegroundColor Red
    exit 3
}

Write-Host "[OK] Task Scheduler 任务已注册: $TaskName" -ForegroundColor Green
Write-Host "     触发时间: 每日 $Time (本地时区)"
Write-Host "     启动器: $BatPath"
Write-Host "     日志: E:\microbubble-agent\logs\backup\backup_scheduler_yyyymmdd.log"

# 验证 task 已注册
Write-Host ""
Write-Host "[INFO] Task 信息:" -ForegroundColor Cyan
schtasks /Query /TN $TaskName /V /FO LIST 2>&1 | Select-String -Pattern "Status|Time|Task Name|Run As User" | ForEach-Object { Write-Host "       $_" }