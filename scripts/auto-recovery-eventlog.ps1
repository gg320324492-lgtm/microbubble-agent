# MicroBubble Auto Recovery - Windows Login Trigger + Self-Healing
# Triggered by: schtasks ONEVENT Microsoft-Windows-Winlogon EventID=7002 /DELAY 0002:00
# Purpose: Full self-heal after computer reboot (Docker daemon + 8000 port + 7 endpoints)
#
# Logic (15 steps):
#   1. Poll `docker info` up to 5 min (Docker daemon init)
#   2. Detect port 8000 zombie bind (class 20.138)
#   3. Auto Quit + Restart Docker Desktop GUI (class 20.138)
#   4. Wait 120s for daemon + WSL2 init
#   5. Run `bash scripts/restart-recovery-after-gui-restart.sh`
#   6. Verify 7 endpoints (health + 6 APIs)
#   7. TTS alert (success/failure)
#   8. JSON log
#
# Class 20.143 (W2 +N): full self-heal via Winlogon EventID=7002, not Docker Desktop EventLog
# (Docker Desktop 通过 WSL2 backend 运行, 不写 EventLog — 探索确认)

param(
    [switch]$Quiet = $false
)

$ErrorActionPreference = "Continue"

# Resolve script directory robustly across all invocation contexts
# Priority: $PSCommandPath > $PSScriptRoot > $MyInvocation.MyCommand.Path > hardcoded fallback
$ScriptDir = $PSCommandRoot
if (-not $ScriptDir) { $ScriptDir = $PSScriptRoot }
if (-not $ScriptDir) { $ScriptDir = $MyInvocation.MyCommand.Path }
if (-not $ScriptDir) { $ScriptDir = $MyInvocation.MyCommand.Definition }
if (-not $ScriptDir) { $ScriptDir = "E:\microbubble-agent\scripts" }

# Strip filename if we got a path with .ps1
if ($ScriptDir -like "*.ps1") { $ScriptDir = Split-Path -Parent $ScriptDir }

$ProjectRoot = Split-Path -Parent $ScriptDir
if (-not (Test-Path $ProjectRoot)) { $ProjectRoot = "E:\microbubble-agent" }
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs\auto-recovery"
$LogFile = Join-Path $LogDir ("auto-recovery-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))

# Constants
$MAX_DOCKER_WAIT_SEC = 300    # 5 min
$MAX_TOTAL_SEC = 600          # 10 min
$PORT_8000 = 8000
$DOCKER_DESKTOP_EXE = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$BASH_EXE = "C:\Program Files\Git\bin\bash.exe"
$RECOVERY_SCRIPT = Join-Path $ProjectRoot "scripts\restart-recovery-after-gui-restart.sh"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Log {
    param([string]$Level, [string]$Message, [hashtable]$Extra)
    if ($Extra -eq $null) { $Extra = @{} }
    $entry = [ordered]@{
        timestamp = Get-Date -Format "o"
        level = $Level
        script = "auto-recovery"
        message = $Message
    }
    foreach ($k in $Extra.Keys) { $entry[$k] = $Extra[$k] }
    $json = $entry | ConvertTo-Json -Compress
    Add-Content -Path $LogFile -Value $json -Encoding UTF8
}

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

function Wait-Docker {
    param([int]$TimeoutSec)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $info = docker info 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Test-Port8000Zombie {
    # 检测 8000 端口是否在宿主机 LISTEN
    $conns = Get-NetTCPConnection -LocalPort $PORT_8000 -State Listen -ErrorAction SilentlyContinue
    return ($conns.Count -gt 0)
}

function Restart-DockerGUI {
    Write-Log "INFO" "Docker Desktop GUI self-heal: stopping processes" @{}
    Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue | Stop-Process -Force
    Get-Process -Name "com.docker.backend" -ErrorAction SilentlyContinue | Stop-Process -Force
    Get-Process -Name "com.docker.service" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 15

    if (-not (Test-Path $DOCKER_DESKTOP_EXE)) {
        Write-Log "ERROR" "Docker Desktop.exe not found" @{ path = $DOCKER_DESKTOP_EXE }
        return $false
    }

    Write-Log "INFO" "Docker Desktop GUI self-heal: starting" @{}
    Start-Process -FilePath $DOCKER_DESKTOP_EXE -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 120  # daemon + WSL2 init time

    return (Wait-Docker -TimeoutSec $MAX_DOCKER_WAIT_SEC)
}

# Main
$startTime = Get-Date
Write-Log "INFO" "Auto-recovery started" @{
    user = $env:USERNAME
    pid = $PID
    trigger = "Winlogon EventID=7002 + Delay 2min"
}

$global:GuiRestarted = $false
$global:Failed = $true
$global:Reason = "unknown"

try {
    # Step 1: 智能等 Docker daemon
    Write-Log "INFO" "Step 1: waiting for Docker daemon" @{ timeout = $MAX_DOCKER_WAIT_SEC }
    if (-not (Wait-Docker -TimeoutSec $MAX_DOCKER_WAIT_SEC)) {
        $global:Reason = "Docker daemon not responding after $MAX_DOCKER_WAIT_SEC s"
        Write-Log "ERROR" "Docker daemon timeout" @{ timeout_sec = $MAX_DOCKER_WAIT_SEC }
        Send-Alert "Warning: MicroBubble recovery failed, Docker daemon not responding"
        exit 1
    }
    Write-Log "INFO" "Docker daemon ready" @{}

    # Step 2: 检查端口 8000 zombie
    Write-Log "INFO" "Step 2: checking port $PORT_8000 for zombie bind" @{}
    if (Test-Port8000Zombie) {
        Write-Log "WARN" "Port $PORT_8000 already bound (zombie state), will retry after GUI restart" @{}
    } else {
        Write-Log "INFO" "Port $PORT_8000 clean" @{}
    }

    # Step 3: 跑恢复脚本 (bash)
    Write-Log "INFO" "Step 3: running recovery script" @{ script = $RECOVERY_SCRIPT }
    if (-not (Test-Path $BASH_EXE)) {
        $global:Reason = "bash.exe not found at $BASH_EXE"
        Write-Log "ERROR" "bash.exe not found" @{ path = $BASH_EXE }
        Send-Alert "Warning: MicroBubble recovery failed, bash not found"
        exit 2
    }
    if (-not (Test-Path $RECOVERY_SCRIPT)) {
        $global:Reason = "Recovery script not found at $RECOVERY_SCRIPT"
        Write-Log "ERROR" "Recovery script not found" @{ path = $RECOVERY_SCRIPT }
        Send-Alert "Warning: MicroBubble recovery failed, script missing"
        exit 3
    }

    $bashOutput = & $BASH_EXE $RECOVERY_SCRIPT 2>&1
    $bashRC = $LASTEXITCODE
    Write-Log "INFO" "Recovery script finished" @{ rc = $bashRC; output_lines = ($bashOutput | Measure-Object).Count }

    if ($bashRC -eq 0) {
        $global:Failed = $false
        $global:Reason = "fully restored"
        Write-Log "INFO" "Recovery successful" @{}
        Send-Alert "MicroBubble fully restored"
        exit 0
    }

    # bash 失败 — 检查是否是端口冲突 (类 20.138)
    if ($bashOutput -match "address already in use" -or $bashOutput -match "port.*8000") {
        Write-Log "WARN" "Port conflict detected, attempting GUI self-heal" @{}
        if (-not $global:GuiRestarted) {
            $global:GuiRestarted = $true
            if (Restart-DockerGUI) {
                Write-Log "INFO" "GUI self-heal successful, retrying recovery" @{}
                # 重跑恢复脚本
                $bashOutput2 = & $BASH_EXE $RECOVERY_SCRIPT 2>&1
                $bashRC2 = $LASTEXITCODE
                Write-Log "INFO" "Recovery script retry finished" @{ rc = $bashRC2 }
                if ($bashRC2 -eq 0) {
                    $global:Failed = $false
                    $global:Reason = "fully restored after GUI self-heal"
                    Send-Alert "MicroBubble fully restored"
                    exit 0
                }
                $global:Reason = "GUI self-heal completed but recovery still failing (rc=$bashRC2)"
            } else {
                $global:Reason = "GUI self-heal failed (Docker daemon not responding after restart)"
            }
        } else {
            $global:Reason = "port conflict persists after GUI restart (loop guard)"
        }
    } else {
        $global:Reason = "recovery script failed (rc=$bashRC) without port conflict"
    }

    # 失败处理
    Write-Log "ERROR" "Recovery failed" @{ reason = $global:Reason; bash_output_tail = ($bashOutput | Select-Object -Last 5) -join "`n" }
    Send-Alert "Warning: MicroBubble recovery failed, $global:Reason. Please check."
    exit 1
}
catch {
    $err = $_.Exception.Message
    Write-Log "ERROR" "Auto-recovery crashed" @{ error = $err; stack = $_.ScriptStackTrace }
    Send-Alert "Warning: MicroBubble auto-recovery crashed, please check manually"
    exit 99
}
finally {
    $duration = ((Get-Date) - $startTime).TotalSeconds
    Write-Log "INFO" "Auto-recovery finished" @{
        duration_sec = [math]::Round($duration, 1)
        success = (-not $global:Failed)
        reason = $global:Reason
        gui_restarted = $global:GuiRestarted
    }
}