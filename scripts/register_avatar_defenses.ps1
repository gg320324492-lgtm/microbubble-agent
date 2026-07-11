# register_avatar_defenses.ps1
# 以管理员身份运行 PowerShell 后, 跑:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   & "E:\microbubble-agent\scripts\register_avatar_defenses.ps1"

$ErrorActionPreference = "Stop"

# === Defense #2: MinIO 每日全量备份 ===
$action1 = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument 'E:\microbubble-agent\scripts\backup_minio_daily.py' `
    -WorkingDirectory 'E:\microbubble-agent'

$trigger1 = New-ScheduledTaskTrigger -Daily -At "03:30"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName "MinIO_Daily_Backup" `
    -Action $action1 `
    -Trigger $trigger1 `
    -Settings $settings `
    -Description "Daily MinIO bucket backup to E:\microbubble-agent\backups\minio-daily (2026-07-11 Defense #2)" `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Force

Write-Host "[1/2] MinIO_Daily_Backup 任务注册成功 (每天 03:30)" -ForegroundColor Green

# === Defense #3: 每日 orphan avatar URL 检测 ===
$action2 = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument 'E:\microbubble-agent\scripts\check_orphan_avatars.py --alert' `
    -WorkingDirectory 'E:\microbubble-agent'

$trigger2 = New-ScheduledTaskTrigger -Daily -At "04:00"

Register-ScheduledTask `
    -TaskName "Avatar_Orphan_Check" `
    -Action $action2 `
    -Trigger $trigger2 `
    -Settings $settings `
    -Description "Daily check for orphan avatar URLs (2026-07-11 Defense #3)" `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Force

Write-Host "[2/2] Avatar_Orphan_Check 任务注册成功 (每天 04:00)" -ForegroundColor Green

Write-Host ""
Write-Host "=== 验证 ===" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object {
    $_.TaskName -eq 'MinIO_Daily_Backup' -or $_.TaskName -eq 'Avatar_Orphan_Check'
} | Format-Table TaskName, State -AutoSize

Write-Host ""
Write-Host "卸载命令:" -ForegroundColor Yellow
Write-Host "  Unregister-ScheduledTask -TaskName 'MinIO_Daily_Backup' -Confirm:`$false"
Write-Host "  Unregister-ScheduledTask -TaskName 'Avatar_Orphan_Check' -Confirm:`$false"