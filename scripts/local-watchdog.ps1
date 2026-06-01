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

# Expected services (7 Docker services)
$ExpectedServices = @(
    "microbubble-agent-app-1",
    "microbubble-agent-db-1",
    "microbubble-agent-redis-1",
    "microbubble-agent-minio-1",
    "microbubble-agent-whisper-1",
    "microbubble-agent-celery-worker-1",
    "microbubble-agent-celery-beat-1"
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
        if (-not $statusMap.ContainsKey($svc)) {
            $downServices += "$svc (missing)"
        } elseif ($statusMap[$svc].State -ne "running") {
            $downServices += "$svc ($($statusMap[$svc].State))"
        } elseif ($statusMap[$svc].Status -match "unhealthy|restarting|exited") {
            $unhealthyServices += "$svc ($($statusMap[$svc].Status))"
        }
    }

    # Read last state (avoid repeat alerts)
    $lastHasIssue = $false
    if (Test-Path $StateFile) {
        try {
            $lastState = Get-Content $StateFile -Raw | ConvertFrom-Json
            $lastHasIssue = $lastState.hasIssue
        } catch { $lastHasIssue = $false }
    }

    $hasIssue = ($downServices.Count -gt 0) -or ($unhealthyServices.Count -gt 0)

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

    Write-Log "ERROR" "Service anomaly detected" @{
        down = $downServices
        unhealthy = $unhealthyServices
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
    }
    $stateObj | ConvertTo-Json | Set-Content $StateFile -Encoding UTF8
    exit 1
}
catch {
    Write-Log "ERROR" "Watchdog crashed" @{ error = $_.Exception.Message; stack = $_.ScriptStackTrace }
    Send-Alert "Warning: MicroBubble watchdog itself errored, please check manually"
    exit 99
}
