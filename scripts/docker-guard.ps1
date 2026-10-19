# MicroBubble Docker Desktop 守护 —— 开机自愈
#
# 背景 (2026-10-19 实战)
# ----------------------
# 机器重启后 Docker Desktop **自启是正常的** (HKCU\...\Run 里本来就有该项,
# 实测 14:15:10 开机 -> 14:16:09 Docker 进程起来), 但它**起来后自己崩了**:
#
#   1) main\ext4.vhdx 的 ACL 缺当前 WSL VM 的 SID (只有 1 个 S-1-5-83-1-*,
#      正常的数据盘有 21 个) => Docker 4.95 的 wslmigrate 挂载失败:
#      Wsl/Service/CreateInstance/MountDisk/HCS/E_ACCESSDENIED
#      => Ingest server 起不来 => backend crashed
#   2) 后果是**连锁的**: MicroBubble-Auto-Recovery 卡在 "Step 1: waiting for
#      Docker daemon" 耗满 300s 被杀 (LastResult 0xC000013A), 本机 13 个
#      容器全起不来, 本地 API 不可用。
#
# 本脚本的职责: **Docker daemon 不可用时自愈**。
# 分三级 (逐级加重, 前一级便宜且无副作用):
#   L1 清理 Docker run/ 下的 *.stale* 残留 (Docker 每次启动给旧 socket 加
#      .stale 后缀却从不清, 累积后会干扰 unix socket 绑定)
#   L2 重启 Docker Desktop (进程)
#   L3 重建 docker-desktop 发行版 (wsl --unregister + 让 Docker 重新 bootstrap)
#      ⚠️ L3 只动 main/ (96MB 系统发行版), **用户数据在 disk/docker_data.vhdx
#         (60GB), 不受影响** —— 2026-10-19 实测注销后该文件大小/mtime 不变。
#
# 与 local-watchdog.ps1 的分工: 那个是**服务健康告警**(容器 unhealthy 等),
# 语义不同不合并; 本脚本只管 Docker 本身能不能用。
#
# 幂等: 每 5 分钟跑一次, Docker 正常时立即退出(零副作用)。

param(
    [switch]$Quiet = $false,
    # ⚠️ PowerShell 的 param() 块里, 逗号必须写在行尾注释**之前** ——
    #    否则注释会把逗号吃掉, 报 "MissingEndParenthesisInFunctionParameterList"。
    [int]$BootGraceMinutes = 3,          # 开机后多久内不判定 Docker 死亡 (Docker 冷启动实测 59 秒)
    [int]$JustFailedGraceMinutes = 2     # 从「刚确认正常」掉下来的宽限期 (给它自愈的时间)
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs\docker-guard"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ("docker-guard-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$StateFile = Join-Path $LogDir "state.json"

$DOCKER_EXE = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$RUN_DIR    = Join-Path $env:LOCALAPPDATA "Docker\run"

function Write-Log {
    param([string]$Level, [string]$Message, [hashtable]$Extra = @{})
    if ($Extra.Count -eq 0) { $Extra = @{} }
    $entry = [ordered]@{
        timestamp = Get-Date -Format "o"
        level     = $Level
        script    = "docker-guard"
        message   = $Message
    }
    foreach ($k in $Extra.Keys) { $entry[$k] = $Extra[$k] }
    Add-Content -Path $LogFile -Value ($entry | ConvertTo-Json -Compress) -Encoding UTF8
}

function Get-State {
    if (Test-Path $StateFile) {
        try { return (Get-Content $StateFile -Raw | ConvertFrom-Json) } catch { return $null }
    }
    return $null
}

function Set-State {
    param([hashtable]$Data)
    # 合并而非覆盖: last_ok_at / last_l3 是跨次运行的基准, 覆盖会丢
    $old = Get-State
    $merged = @{}
    if ($old) {
        foreach ($p in $old.PSObject.Properties) { $merged[$p.Name] = $p.Value }
    }
    foreach ($k in $Data.Keys) { $merged[$k] = $Data[$k] }
    if ($merged.level -eq "OK" -and -not $Data.ContainsKey("last_ok_at")) {
        $merged.last_ok_at = Get-Date -Format "o"
    }
    $merged | ConvertTo-Json -Compress | Set-Content -Path $StateFile -Encoding UTF8
}

function Test-DockerUp {
    docker info 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Get-BootTime {
    try { return (Get-CimInstance Win32_OperatingSystem).LastBootUpTime } catch { return $null }
}

# ---------------------------------------------------------------- 正常路径
if (Test-DockerUp) {
    $st = Get-State
    if ($st -and $st.level -and $st.level -ne "OK") {
        Write-Log "INFO" "Docker recovered" @{ from = $st.level; uptime_s = $st.uptime_s }
    }
    Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                last_ok_at = (Get-Date -Format "o") }
    exit 0
}

# ---------------------------------------------------------------- 宽限期
# ⚠️ 判据不能用「距开机多久」单条 —— 本任务每 5 分钟才跑一次, 开机后第一次跑可能
#    正好落在宽限期边界上被跳过, 于是真故障也判不出来。
#    改用「距上次确认 Docker 正常过了多久」:
#      · 刚从正常态掉下来 (last_ok_at 很近) ⇒ 给一点恢复时间再判
#      · 从未正常过 (刚开机) ⇒ 用开机宽限期
$st = Get-State
$boot = Get-BootTime
$sinceLastOk = $null
if ($st -and $st.last_ok_at) {
    try { $sinceLastOk = ((Get-Date) - [datetime]$st.last_ok_at).TotalMinutes } catch { $sinceLastOk = $null }
}
$sinceBoot = if ($boot) { ((Get-Date) - $boot).TotalMinutes } else { $null }

$withinGrace = $false
$graceReason = ""
if ($null -ne $sinceLastOk -and $sinceLastOk -lt $JustFailedGraceMinutes) {
    $withinGrace = $true
    $graceReason = "just-failed"
} elseif ($null -ne $sinceBoot -and $sinceBoot -lt $BootGraceMinutes) {
    $withinGrace = $true
    $graceReason = "boot"
}
if ($withinGrace) {
    Write-Log "INFO" "Docker not up yet, within grace period" @{
        reason = $graceReason
        minutes_since_last_ok = if ($null -ne $sinceLastOk) { [math]::Round($sinceLastOk, 1) } else { $null }
        minutes_since_boot = if ($null -ne $sinceBoot) { [math]::Round($sinceBoot, 1) } else { $null }
    }
    exit 0
}

$level = if ($st -and $st.level) { $st.level } else { "L1" }
Write-Log "WARN" "Docker daemon unavailable, escalating" @{
    from_level = $level
    boot_minutes = if ($boot) { [math]::Round(((Get-Date) - $boot).TotalMinutes, 1) } else { $null }
}

# ---------------------------------------------------------------- L1: 清 .stale
try {
    $stale = @(Get-ChildItem $RUN_DIR -Force -EA SilentlyContinue | Where-Object { $_.Name -like "*.stale*" })
    if ($stale.Count -gt 0) {
        $stale | Remove-Item -Force -EA SilentlyContinue
        Write-Log "INFO" "L1 removed stale socket files" @{ count = $stale.Count }
    }
} catch {
    Write-Log "WARN" "L1 cleanup failed" @{ error = $_.Exception.Message }
}
Set-State @{ level = "L2"; checked_at = (Get-Date -Format "o"); uptime_s = 0 }

# 给了 Docker 一点时间自己起来 (有时它只是在慢启动)
Start-Sleep -Seconds 20
if (Test-DockerUp) {
    Write-Log "INFO" "Docker came up after L1 cleanup" @{}
    Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0 }
    exit 0
}

# ---------------------------------------------------------------- L2: 重启 Docker Desktop
try {
    Get-Process -Name "Docker Desktop","com.docker.backend","com.docker.build" -EA SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 6
    Start-Process -FilePath $DOCKER_EXE | Out-Null
    Write-Log "INFO" "L2 restarted Docker Desktop" @{}
} catch {
    Write-Log "WARN" "L2 restart failed" @{ error = $_.Exception.Message }
}
Set-State @{ level = "L3"; checked_at = (Get-Date -Format "o"); uptime_s = 0 }

# 等它起 (Docker 冷启动到 daemon 可用约 1-3 分钟)
$deadline = (Get-Date).AddMinutes(4)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 15
    if (Test-DockerUp) {
        Write-Log "INFO" "Docker came up after L2 restart" @{}
        Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0 }
        exit 0
    }
}

# ---------------------------------------------------------------- L3: 重建 docker-desktop 发行版
# ⚠️ 只注销 docker-desktop (main/, 96MB 系统发行版); **用户数据在
#    disk/docker_data.vhdx (60GB), 不在这个路径下, 2026-10-19 实测注销后不变。
#    L3 是破坏性动作, 因此只在 L1/L2 都失败后执行, 且每 30 分钟最多一次。
$st = Get-State
$lastL3 = if ($st -and $st.last_l3) { [datetime]$st.last_l3 } else { [datetime]::MinValue }
if (((Get-Date) - $lastL3).TotalMinutes -lt 30) {
    Write-Log "INFO" "L3 skipped, ran recently" @{ last_l3 = $lastL3.ToString("o") }
    exit 1
}

Write-Log "WARN" "L3 rebuilding docker-desktop distro (user data disk untouched)" @{}
try {
    wsl --shutdown 2>$null | Out-Null
    Start-Sleep -Seconds 8
    Get-Process -Name "Docker Desktop","com.docker.backend","com.docker.build" -EA SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 5
    wsl --unregister docker-desktop 2>&1 | Out-Null
    Start-Process -FilePath $DOCKER_EXE | Out-Null
    Set-State @{ level = "L3"; checked_at = (Get-Date -Format "o"); uptime_s = 0; last_l3 = (Get-Date -Format "o") }
    Write-Log "INFO" "L3 distro unregistered, Docker Desktop relaunched" @{}
} catch {
    Write-Log "ERROR" "L3 failed" @{ error = $_.Exception.Message }
    Set-State @{ level = "L3"; checked_at = (Get-Date -Format "o"); uptime_s = 0; last_l3 = (Get-Date -Format "o") }
}
exit 1
