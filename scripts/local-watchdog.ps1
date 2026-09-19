# MicroBubble Local Watchdog - Docker Service Health Monitor
# Usage: powershell scripts/local-watchdog.ps1 [-Quiet]
# Recommended: Task Scheduler every 5 minutes

param(
    [switch]$Quiet = $false
)

$ErrorActionPreference = "Continue"  # Don't throw on native stderr (e.g. docker warnings)
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs\watchdog"
$LogFile = Join-Path $LogDir ("watchdog-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$StateFile = Join-Path $LogDir "last-state.json"

# Expected services (W100 +N updated: 13 containers)
# 2026-09-18: pg-exporter-dev-1 → pg-exporter-1 (实际容器名, -dev 是陈旧名单导致永久误报 missing)
$ExpectedServices = @(
    "microbubble-agent-app-1",
    "microbubble-agent-db-1",
    "microbubble-agent-redis-1",
    "microbubble-agent-minio-1",
    "microbubble-agent-celery-worker-1",
    "microbubble-agent-celery-beat-1",
    "microbubble-agent-celery-meeting-worker-1",
    "microbubble-agent-neo4j-1",
    "microbubble-agent-ollama-1",
    "microbubble-agent-sensevoice-1",
    "microbubble-agent-vision-mcp-1",
    "microbubble-agent-pg-exporter-1",
    "microbubble-agent-langfuse-1"
)

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# Structured logging (JSON one-line per entry)
function Write-Log {
    param([string]$Level, [string]$Message, [hashtable]$Extra)
    if ($Extra -eq $null) { $Extra = @{} }
    $entry = [ordered]@{
        timestamp = Get-Date -Format "o"
        level = $Level
        script = "local-watchdog"
        message = $Message
    }
    foreach ($k in $Extra.Keys) { $entry[$k] = $Extra[$k] }
    $json = $entry | ConvertTo-Json -Compress
    Add-Content -Path $LogFile -Value $json -Encoding UTF8
}

# TTS alert (use Chinese voice if available)
function Send-Alert {
    param([string]$Message)
    if ($Quiet) { return }
    try {
        Add-Type -AssemblyName System.Speech -ErrorAction Stop
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        try { $synth.SelectVoice("Microsoft Huihui Desktop") } catch {}
        $synth.Volume = 100
        $synth.Rate = -1
        $synth.Speak($Message)
        $synth.Dispose()
    } catch {
        Write-Log "WARN" "TTS failed" @{ error = $_.Exception.Message }
    }
}

# Main
try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR" "Docker Desktop not running" @{}
        Send-Alert "Warning: Docker Desktop not running, MicroBubble services unavailable"
        exit 1
    }

    $running = docker compose ps --format "{{.Name}}|{{.State}}|{{.Status}}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR" "docker compose ps failed" @{ output = ($running -join "; ") }
        exit 2
    }

    $statusMap = @{}
    foreach ($line in $running) {
        $parts = $line -split "\|"
        if ($parts.Count -ge 3) {
            $statusMap[$parts[0]] = @{ State = $parts[1]; Status = $parts[2] }
        }
    }

    $downServices = @()
    $unhealthyServices = @()
    foreach ($svc in $ExpectedServices) {
        # 2026-09-18: 孤儿 compose run 的容器带随机 hex 前缀 (如 6010d5393430_microbubble-agent-...),
        # 精确匹配永久 missing → 状态文件常驻 hasIssue=true → 状态转换告警永不触发 (watchdog 变哑).
        # 改后缀匹配. 前缀是 compose project hash, 硬编码不可靠.
        $entry = $null
        foreach ($key in $statusMap.Keys) {
            if ($key -like "*$svc") { $entry = $statusMap[$key]; break }
        }
        if (-not $entry) {
            $downServices += "$svc (missing)"
        } elseif ($entry.State -ne "running") {
            $downServices += "$svc ($($entry.State))"
        } elseif ($entry.Status -match "unhealthy|restarting|exited") {
            $unhealthyServices += "$svc ($($entry.Status))"
        }
    }

    # 2026-09-18 GPU services check - Windows NVIDIA driver update without WSL restart
    # silently breaks CUDA context inside containers:
    #   ollama:     "ggml_cuda_init: failed" (CPU fallback, 17GB model loads 3.5min+)
    #   sensevoice: "GPU-FALLBACK" / "CUDA error" (server auto-falls-back to CPU)
    # Symptoms only appear on real inference, so we scan container log signatures.
    # Fix = wsl --shutdown + restart Docker Desktop.
    # Note: ASCII-only patterns (Chinese garbles under PowerShell cp936).
    $gpuIssues = @()
    $gpuLogChecks = @(
        @{ Name = "microbubble-agent-ollama-1";     Pattern = "ggml_cuda_init: failed" },
        @{ Name = "microbubble-agent-sensevoice-1"; Pattern = "GPU-FALLBACK|CUDA error|CUDA initialization" }
    )
    foreach ($chk in $gpuLogChecks) {
        $fullName = $null
        foreach ($key in $statusMap.Keys) {
            if ($key -like ("*" + $chk.Name)) { $fullName = $key; break }
        }
        if (-not $fullName) { continue }  # container missing already reported above
        $failLines = docker logs --since 24h $fullName 2>&1 | Select-String -Pattern $chk.Pattern
        if ($failLines) {
            $gpuIssues += "$($chk.Name): CUDA broken, needs WSL + Docker Desktop restart"
        }
    }
    $cudaBroken = ($gpuIssues.Count -gt 0)

    # 2026-09-19: MinIO port-publish zombie check. After a WSL/Docker Desktop
    # restart, vpnkit port forwards can go half-dead (TCP accepts, HTTP never
    # answers) -> cloud nginx serves 502 for ALL avatars/files (09-18 incident,
    # minio 9000 + earlier ollama 11434). HTTP-level probe required; a TCP
    # connect test is NOT sufficient. Fix = force-recreate the container.
    $minioDown = $false
    try {
        $minioResp = Invoke-WebRequest -Uri "http://127.0.0.1:9000/minio/health/live" -UseBasicParsing -TimeoutSec 5
        if ($minioResp.StatusCode -ne 200) { $minioDown = $true }
    } catch {
        $minioDown = $true
    }
    if ($minioDown) {
        $gpuIssues += "MinIO port 9000 unreachable from host (port-publish zombie; fix: docker compose up -d --force-recreate minio)"
    }

    # Read last state (avoid repeat alerts)
    $lastHasIssue = $false
    if (Test-Path $StateFile) {
        try {
            $lastState = Get-Content $StateFile -Raw | ConvertFrom-Json
            $lastHasIssue = $lastState.hasIssue
        } catch { $lastHasIssue = $false }
    }

    $hasIssue = ($downServices.Count -gt 0) -or ($unhealthyServices.Count -gt 0) -or $cudaBroken -or $minioDown

    if (-not $hasIssue) {
        Write-Log "INFO" "All services healthy" @{ service_count = $ExpectedServices.Count }
        if ($lastHasIssue) {
            Send-Alert "MicroBubble all services restored to healthy"
        }
        $stateObj = [ordered]@{ hasIssue = $false; timestamp = Get-Date -Format "o" }
        $stateObj | ConvertTo-Json | Set-Content $StateFile -Encoding UTF8
        exit 0
    }

    # Has issue
    $alertMsg = ""
    if ($downServices.Count -gt 0) { $alertMsg += "Stopped: " + ($downServices -join ", ") + ". " }
    if ($unhealthyServices.Count -gt 0) { $alertMsg += "Unhealthy: " + ($unhealthyServices -join ", ") + "." }
    if ($cudaBroken -or $minioDown) { $alertMsg += ($gpuIssues -join "; ") + ". " }

    Write-Log "ERROR" "Service anomaly detected" @{
        down = $downServices
        unhealthy = $unhealthyServices
        cudaBroken = $cudaBroken
        minioDown = $minioDown
        gpuIssues = $gpuIssues
        alert = $alertMsg
    }

    # Only alert on state transition (normal -> issue)
    if (-not $lastHasIssue) {
        Send-Alert ("Warning: MicroBubble service anomaly. {0} Please check Docker Desktop." -f $alertMsg)
    }

    $stateObj = [ordered]@{
        hasIssue = $true
        timestamp = Get-Date -Format "o"
        down = $downServices
        unhealthy = $unhealthyServices
        cudaBroken = $cudaBroken
        minioDown = $minioDown
        gpuIssues = $gpuIssues
    }
    $stateObj | ConvertTo-Json | Set-Content $StateFile -Encoding UTF8
    exit 1
}
catch {
    Write-Log "ERROR" "Watchdog crashed" @{ error = $_.Exception.Message; stack = $_.ScriptStackTrace }
    Send-Alert "Warning: MicroBubble watchdog itself errored, please check manually"
    exit 99
}
