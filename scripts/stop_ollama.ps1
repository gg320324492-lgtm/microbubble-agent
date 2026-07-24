# MicroBubble Ollama One-Click Stop Script
# Usage: powershell scripts/stop_ollama.ps1 [-Force]
#
# Workflow:
#   1. Check if container exists
#   2. Graceful stop (docker stop, 10s timeout)
#   3. Verify container removed (--rm flag)
#   4. Optionally clean up dangling image (-Force)

param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Continue"
$ContainerName = "ollama"
$StopTimeoutSec = 10

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "[stop_ollama] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[stop_ollama] OK  $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[stop_ollama] WARN $Message" -ForegroundColor Yellow
}

try {
    Write-Step "Checking container '$ContainerName' ..."
    $exists = docker ps -a --filter "name=$ContainerName" --format "{{.Names}}" 2>$null
    if ($exists -ne $ContainerName) {
        Write-Warn "No container named '$ContainerName' found, nothing to stop"
        exit 0
    }

    $state = docker inspect --format '{{.State.Running}}' $ContainerName 2>$null
    if ($state -eq "true") {
        Write-Step "Graceful stop (timeout ${StopTimeoutSec}s) ..."
        docker stop --time $StopTimeoutSec $ContainerName 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Graceful stop failed (exit $LASTEXITCODE), forcing kill"
            docker kill $ContainerName 2>&1 | Out-Null
        }
    } else {
        Write-Ok "Container already stopped"
    }

    # --rm flag auto-removes on stop, but ensure cleanup if state is non-running
    $stillExists = docker ps -a --filter "name=$ContainerName" --format "{{.Names}}" 2>$null
    if ($stillExists -eq $ContainerName) {
        docker rm $ContainerName 2>&1 | Out-Null
    }

    $verifyState = docker ps --filter "name=$ContainerName" --format "{{.Names}}" 2>$null
    if ($verifyState -eq $ContainerName) {
        Write-Warn "Container '$ContainerName' still running after stop attempt"
        exit 1
    }
    Write-Ok "Container '$ContainerName' stopped and removed"

    if ($Force) {
        Write-Step "Force cleanup: removing dangling Ollama images ..."
        $dangling = docker images --filter "dangling=true" --filter "reference=ollama/*" --format "{{.ID}}" 2>$null
        if ($dangling) {
            $dangling | ForEach-Object { docker rmi $_ 2>$null | Out-Null }
            Write-Ok "Dangling images removed"
        } else {
            Write-Ok "No dangling images to remove"
        }
    }

    Write-Host ""
    Write-Host "[stop_ollama] Done." -ForegroundColor Green
    Write-Host "    Data preserved at: .ollama/ and models/ (mounts, not deleted)"
    Write-Host "    To restart: powershell scripts/start_ollama.ps1"
    Write-Host ""
}
catch {
    Write-Host "[stop_ollama] ERR  Unhandled error: $($_.Exception.Message)" -ForegroundColor Red
    exit 99
}