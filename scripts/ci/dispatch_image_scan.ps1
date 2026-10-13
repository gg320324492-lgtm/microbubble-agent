<#
.SYNOPSIS
    每周兜底触发 image-scan 全量扫描（8 个镜像）。

.DESCRIPTION
    为什么需要它: `.github/workflows/image-scan.yml` 的 schedule（每周一 05:00 UTC）
    **不保证触发** —— 实测 2026-10-05 之后到 10-13 都没再触发过（同期同为周一
    schedule 的 `secret-scan.yml` 在 10-12 正常触发了，所以不是仓库级开关的问题）。

    而 `push` 触发器只覆盖 3 个**读 requirements.txt** 的镜像
    （app / commercial / voice-pipeline）；另外 5 个（db / web / funasr / whisper / mcp）
    **只在 PR / schedule / dispatch 时才跑** ⇒ schedule 漏跑 = 那 5 个镜像进入扫描盲区。

    本任务作为**兜底**：固定每周一触发一次全量。
    ⚠️ 幂等 —— 触发前先查近 7 天是否已有成功的全量 run（event=workflow_dispatch
    或 schedule），有就跳过，避免与 GitHub 自己的 schedule 重复烧配额。

    主体必须是**当前登录用户**（不是 SYSTEM）—— gh 的凭据存在用户 keyring，
    SYSTEM 读不到。CLAUDE.md 里 OSS 凭据那条是同型教训。

    计划任务: `MicroBubble-ImageScan-Full`，每周一 21:00（北京时间）。
    ⚠️ 注册后**必须回读验证**，且回读的 `Triggers[0].DaysOfWeek` 是
    **Task Scheduler 的 COM 编号**（Sun=1 Mon=2 Tue=3 ...），
    **不是** .NET 的 `DayOfWeek`（Sun=0 Mon=1 Tue=2 ...）——
    拿 .NET 枚举去解释它，会把 Monday(2) 误判成 Tuesday。2026-10-13 已踩过一次，
    连断言都跟着写错过。正确判定用 COM 接口读:
        $svc = New-Object -ComObject Schedule.Service; $svc.Connect()
        $svc.GetFolder('\').GetTask('<name>').Definition.Triggers.Item(1).DaysOfWeek

.NOTES
    用法（手动）:
        powershell -ExecutionPolicy Bypass -File scripts/ci/dispatch_image_scan.ps1
        powershell ... -Force        # 跳过幂等检查，强制触发
#>
[CmdletBinding()]
param(
    # 跳过幂等检查强制触发（调试用）
    [switch]$Force,
    # 只看会做什么，不真的触发
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = "E:\microbubble-agent"
Set-Location $RepoRoot

$LogDir = Join-Path $RepoRoot "logs\ci"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("dispatch_image_scan-{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Write-Log {
    param([string]$Level, [string]$Message)
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

Write-Log INFO "=== image-scan 全量兜底触发开始 (Force=$Force) ==="

# ---------- 0. 前置检查 ----------
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Log FATAL "找不到 gh 命令 —— 计划任务的环境 PATH 里可能没有它"
    exit 1
}

try {
    $auth = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gh 未认证: $auth" }
    Write-Log INFO "gh 认证正常"
} catch {
    Write-Log FATAL "gh 认证失败（计划任务是否用错了主体？）: $_"
    exit 1
}

# ---------- 1. 幂等检查 ----------
if (-not $Force) {
    try {
        # 最近 7 天的 image-scan run（workflow 名 = 文件名）
        $runs = gh run list --workflow=".github/workflows/image-scan.yml" --limit 20 `
            --json databaseId,event,conclusion,createdAt 2>$null | ConvertFrom-Json

        $cutoff = (Get-Date).AddDays(-7)
        $recentOk = $runs | Where-Object {
            ([datetime]$_.createdAt) -gt $cutoff -and $_.conclusion -eq "success" `
            -and ($_.event -eq "workflow_dispatch" -or $_.event -eq "schedule")
        }

        if ($recentOk) {
            $last = $recentOk | Sort-Object { [datetime]$_.createdAt } -Descending | Select-Object -First 1
            Write-Log INFO ("幂等跳过: 近 7 天已有成功的全量 run " +
                "(id={0}, event={1}, {2})" -f $last.databaseId, $last.event, $last.createdAt)
            exit 0
        }
        Write-Log INFO "近 7 天无成功的全量 run，继续触发"
    } catch {
        Write-Log WARN "幂等检查失败（不阻断）: $_"
    }
}

# ---------- 2. 触发 ----------
if ($WhatIfOnly) {
    Write-Log INFO "-WhatIfOnly: 到此为止，未真正触发"
    exit 0
}

$before = (gh run list --workflow=".github/workflows/image-scan.yml" --limit 1 `
    --json databaseId 2>$null | ConvertFrom-Json)
$beforeId = if ($before) { $before[0].databaseId } else { 0 }

Write-Log INFO "触发 gh workflow run ..."
$out = gh workflow run ".github/workflows/image-scan.yml" --ref main 2>&1
$rc = $LASTEXITCODE
Write-Log INFO "gh 退出码=$rc 输出: $out"

if ($rc -ne 0) {
    Write-Log FATAL "触发失败"
    exit 1
}

# ---------- 3. 确认真的起来了（不信退出码，类 20.220）----------
$found = $null
for ($i = 0; $i -lt 6; $i++) {
    Start-Sleep -Seconds 10
    $now = gh run list --workflow=".github/workflows/image-scan.yml" --limit 3 `
        --json databaseId,event,status,createdAt 2>$null | ConvertFrom-Json
    $found = $now | Where-Object { [long]$_.databaseId -ne $beforeId } | Select-Object -First 1
    if ($found) { break }
}

if ($found) {
    Write-Log INFO ("✅ 已确认新 run 启动: id={0} event={1} status={2}" -f `
        $found.databaseId, $found.event, $found.status)
    Write-Log INFO "URL: https://github.com/gg320324492-lgtm/microbubble-agent/actions/runs/$($found.databaseId)"
    exit 0
} else {
    Write-Log FATAL "gh 返回成功但 60 秒内没看到新 run —— 不排除被仓库级并发限制挡掉，如实记为失败"
    exit 1
}
