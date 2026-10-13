# 修 MicroBubble-Auto-Recovery 计划任务的触发器与 Action。
#
# ⚠️ **需要管理员身份运行**（Set-ScheduledTask 会返回 0x80070005 拒绝访问）。
#     在普通权限的 PowerShell 里跑会失败，且**失败发生在生效之前，任务定义不会被半改**。
#
#     以管理员打开 PowerShell 后执行：
#         powershell -NoProfile -ExecutionPolicy Bypass -File scripts\ci\fix-autorecovery-task.ps1
#
# ## 本脚本修什么（2026-10-13 实测，三层里只修过一层）
#
# | 层 | CLAUDE.md 声称 | 实测                                              |
# |---|---|---|
# | ① 触发器改 AtStartup | 已修 | ❌ 仍是 Winlogon EventID=7002 事件订阅 |
# | ② Action 补解释器   | 已修 | ❌ Execute 直接指向 .ps1，无 powershell.exe |
# | ③ alembic 断言改不变量 | 已修 | ✅ 确已修（脚本 94-103 行两条不变量）|
#
# ①②叠加 ⇒ **这个任务从未自动执行过一次**。判据不是状态字段而是**副作用产物**：
# `logs/auto-recovery/` 下只有 `auto-recovery-20260804.log` 与
# `auto-recovery-20261009.log`，之后再无新文件；`LastRunTime` 也停在 2026-10-09。
#
# ## 本脚本**不做**什么
#
# **绝不触发执行。** `auto-recovery-eventlog.ps1` 的主流程第 3 步会跑 bash 恢复
# 脚本（重启容器栈），失败兜底还会 `Stop-Process -Force` 杀 Docker Desktop ——
# 触发它 = 一次停掉全部生产容器。验证必须由主指挥另行决定时机。
#
# **幂等**：重复执行结果一致，可安全重跑。
$ErrorActionPreference = 'Stop'

$taskName    = 'MicroBubble-Auto-Recovery'
$repoRoot    = 'E:\microbubble-agent'
$scriptPath  = Join-Path $repoRoot 'scripts\auto-recovery-eventlog.ps1'
$psExe       = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Show-State([string]$label) {
    $t = Get-ScheduledTask -TaskName $taskName
    Write-Host "=== $label ==="
    Write-Host ("  trigger : " + (($t.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ', '))
    Write-Host ("  delay   : " + (($t.Triggers | ForEach-Object { $_.Delay }) -join ', '))
    Write-Host ("  execute : " + $t.Actions[0].Execute)
    Write-Host ("  args    : " + $t.Actions[0].Arguments)
    Write-Host ("  workdir : " + $t.Actions[0].WorkingDirectory)
    Write-Host ("  user    : " + $t.Principal.UserId + " / " + $t.Principal.LogonType)
    Write-Host ("  state   : " + $t.State)
}

# ---- 前置检查：fail loud，不要半途才炸 ----
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "需要管理员身份。请以管理员打开 PowerShell 后重跑本脚本。"
    exit 1
}
if (-not (Test-Path $scriptPath)) { throw "恢复脚本不存在: $scriptPath" }
if (-not (Test-Path $psExe))       { throw "powershell.exe 不存在: $psExe" }

# 恢复脚本含中文却缺 BOM 时，PS 5.1 会按 GBK 解码 => 解析错误（第 4 层，2026-10-13 一并修）
$head3 = [System.IO.File]::ReadAllBytes($scriptPath)[0..2]
$hasBom = ($head3[0] -eq 0xEF -and $head3[1] -eq 0xBB -and $head3[2] -eq 0xBF)
Write-Host ("恢复脚本 UTF-8 BOM: " + $(if ($hasBom) { '有' } else { '**无 —— PS 5.1 会按 GBK 解码, 建议先补 BOM**' }))
Write-Host ""

Show-State 'BEFORE'

# ---- ① 触发器：AtStartup + 2 分钟延迟 ----
# EventID=7002 (Winlogon) 在新版 Windows 已不再产生 ⇒ 事件触发器永不触发。
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = 'PT2M'

# ---- ② Action：.ps1 必须挂 powershell.exe ----
# 任务计划程序不把 .ps1 当可执行文件，进程**从未启动**；而它仍会上报 LastTaskResult。
$argString = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $scriptPath
$action = New-ScheduledTaskAction -Execute $psExe -Argument $argString -WorkingDirectory $repoRoot

# 只传 -Trigger / -Action —— Principal 与 Settings 保持不变
Set-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action | Out-Null

Write-Host ""
Show-State 'AFTER'

# ---- 回读断言：不信"没报错"，只信读回来的值（类 20.220）----
$after = Get-ScheduledTask -TaskName $taskName
$problems = @()
if ($after.Triggers.CimClass.CimClassName -notcontains 'MSFT_TaskBootTrigger') {
    $problems += '触发器仍不是 AtStartup'
}
if (-not $after.Actions[0].Execute.ToLower().EndsWith('powershell.exe')) {
    $problems += 'Execute 未指向 powershell.exe'
}
if ($after.Actions[0].Arguments -notmatch [regex]::Escape($scriptPath)) {
    $problems += 'Arguments 未指向恢复脚本'
}
# 注册后回读必查控制字符（类 20.216 第 1 形态）
foreach ($f in @('Execute', 'Arguments', 'WorkingDirectory')) {
    $v = [string]$after.Actions[0].$f
    if ($v -match '[\x00-\x08\x0B\x0C\x0E-\x1F]') {
        $problems += "$f 含控制字符（路径被转义吞掉）"
    }
}

Write-Host ""
if ($problems.Count -eq 0) {
    Write-Host "[OK] 触发器与 Action 均已修正, 且控制字符检查通过。" -ForegroundColor Green
    Write-Host "[注意] **本脚本没有执行任务**。首次真实执行将在下次开机 +2 分钟时发生;"
    Write-Host "       那将是该任务史上第一次自动运行, 行为未经验证。"
    Write-Host "       副作用产物应出现在 logs\auto-recovery\auto-recovery-<日期>.log"
} else {
    Write-Host "[FAIL] 回读校验未通过:" -ForegroundColor Red
    $problems | ForEach-Object { Write-Host ("  - " + $_) }
    exit 1
}
