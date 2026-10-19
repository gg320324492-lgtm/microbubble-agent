# MicroBubble Docker Guard - Scheduled Task Registration
#
# 注册 scripts/docker-guard.ps1 为计划任务: 开机后 2 分钟起跑, 之后每 5 分钟重复。
#
# 为什么需要它 (2026-10-19 实战)
# ---------------------------------
# 机器重启后 Docker Desktop **自启本来是正常的** (HKCU\...\Run 里已有该项,
# 实测 14:15:10 开机 -> 14:16:09 Docker 起来), 但它**起来后自己崩了**:
#   main\ext4.vhdx 的 ACL 缺当前 WSL VM 的 SID => Docker 4.95 挂载失败
#   (E_ACCESSDENIED) => Ingest server 起不来 => backend crashed。
# 后果连锁: Auto-Recovery 卡在等 Docker daemon 耗满 300s 被杀, 13 个容器全起不来。
#
# 本任务在 Docker 不可用时分级自愈 (L1 清 .stale / L2 重启 / L3 重建发行版),
# 详见 docker-guard.ps1 头部注释。
#
# ⚠️ 为什么不用 -Xml 注册 (踩过的坑, 别走回头路):
#   ① Register-ScheduledTask -Xml 在本机**连 Task Scheduler 自己导出的、确定能用的
#      XML 都报「XML 格式错误」** —— 该 cmdlet 的 -Xml 传参路径在此环境下有问题。
#      ⇒ 改用 cmdlet 直接构造对象, 不走 XML。
#   ② schtasks /Create /XML 报「拒绝访问」(而 /TR 简单命令成功) —— 同样绕开 XML。
#   ③ New-ScheduledTaskTrigger 的 -RepetitionInterval 收 **TimeSpan** 不是 ISO 字符串
#      (收 'PT5M' 会报「无法将 System.String 转换为 System.TimeSpan」)。
#   ④ -AtStartup 生成的 trigger 的 .Delay **是可写属性**, 直接赋值即可。
#
# 幂等: 重复执行本脚本不会产生重复任务 (先删后建)。
#
# 用法: powershell -ExecutionPolicy Bypass -File scripts/register-docker-guard-task.ps1

$ErrorActionPreference = "Stop"

$taskName   = 'MicroBubble-Docker-Guard'
$scriptPath = 'E:\microbubble-agent\scripts\docker-guard.ps1'
$runner     = 'E:\microbubble-agent\scripts\run-hidden.vbs'

if (-not (Test-Path $scriptPath)) { throw "找不到 $scriptPath" }
if (-not (Test-Path $runner))    { throw "找不到 $runner" }

Write-Host "============================================================"
Write-Host " MicroBubble Docker Guard - Task Registration"
Write-Host "============================================================"
Write-Host ""
Write-Host "  Task name : $taskName"
Write-Host "  Script    : $scriptPath"
Write-Host "  Trigger   : 开机后 2 分钟起, 每 5 分钟重复"
Write-Host "  Identity  : 当前用户 (InteractiveToken, Limited)"
Write-Host ""

# 幂等: 先删旧的
if (Get-ScheduledTask -TaskName $taskName -EA SilentlyContinue) {
    Write-Host "  已存在, 先注销..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# 动作: 用 wscript.exe 隐藏窗口跑脚本 (与既有隧道守护任务同一范式)
$action = New-ScheduledTaskAction -Execute 'wscript.exe' `
    -Argument "`"$runner`" `"$scriptPath`""

# 触发器 1: 开机后 2 分钟 (给 Docker 冷启动留时间; 脚本内另有 5 分钟宽限期)
$bootTrigger = New-ScheduledTaskTrigger -AtStartup
$bootTrigger.Delay = 'PT2M'

# 触发器 2: 每 5 分钟重复
$timeTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 8) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger @($bootTrigger, $timeTrigger) `
    -Principal $principal -Settings $settings `
    -Description "Docker Desktop unavailable - graded self-heal (L1 clean stale sockets / L2 restart / L3 rebuild docker-desktop distro)"

Write-Host "  registered OK"
Write-Host ""
Write-Host "  验证:"
Write-Host "    powershell -ExecutionPolicy Bypass -File $scriptPath"
Write-Host "    日志: E:\microbubble-agent\logs\docker-guard\docker-guard-YYYYMMDD.log"
Write-Host ""

$t = Get-ScheduledTask -TaskName $taskName
Write-Host "  当前状态: State=$($t.State)"
$t.Triggers | ForEach-Object {
    Write-Host ("  触发器: " + $_.CimClass.CimClassName + " Delay=" + $_.Delay + " Start=" + $_.StartBoundary)
}
$t.Actions | ForEach-Object { Write-Host ("  动作: " + $_.Execute + " " + $_.Arguments) }
