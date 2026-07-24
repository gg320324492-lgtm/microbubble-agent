# MicroBubble Ollama One-Click Start Script
# Usage: powershell scripts/start_ollama.ps1 [-Model qwen3:8b] [-SkipPull]
# Recommended: Run from project root or any shell
#
# Workflow:
#   1. Check Docker is running
#   2. Check Ollama image exists (pull if missing)
#   3. Start Ollama container with GPU + clash proxy
#   4. Wait for health check (http://localhost:11434/api/tags)
#   5. Pull target model (default qwen3:8b, ~4.7 GB)
#   6. Verify OpenAI-compatible endpoint (http://localhost:11434/v1/models)

param(
    [string]$Model = "qwen3:8b",
    [switch]$SkipPull = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ContainerName = "ollama"
$OllamaImage = "ollama/ollama:latest"
$OllamaPort = 11434
$HealthTimeoutSec = 60
$PullTimeoutSec = 1800   # 30 min for first-time 4-9 GB model download

# Resolve project paths (Windows -> container mounts)
$ModelsDir = Join-Path $ProjectRoot "models"
$OllamaDataDir = Join-Path $ProjectRoot ".ollama"
New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
New-Item -ItemType Directory -Path $OllamaDataDir -Force | Out-Null

# Convert Windows paths to MSYS-style for docker bind mount
$ModelsMount = ($ModelsDir -replace '\\', '/')
$OllamaMount = ($OllamaDataDir -replace '\\', '/')

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "[start_ollama] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[start_ollama] OK  $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[start_ollama] WARN $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[start_ollama] ERR  $Message" -ForegroundColor Red
}

try {
    # Step 1: Docker daemon
    Write-Step "Step 1/6: Checking Docker daemon ..."
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker daemon not running. Please start Docker Desktop."
        exit 1
    }
    Write-Ok "Docker daemon running"

    # Step 2: Container state
    Write-Step "Step 2/6: Checking existing container '$ContainerName' ..."
    $existing = docker ps -a --filter "name=$ContainerName" --format "{{.Names}}" 2>$null
    if ($existing -eq $ContainerName) {
        $state = docker inspect --format '{{.State.Running}}' $ContainerName 2>$null
        if ($state -eq "true") {
            Write-Ok "Container '$ContainerName' already running, reusing"
        } else {
            Write-Host "[start_ollama] Removing stopped container '$ContainerName' ..."
            docker rm $ContainerName 2>$null | Out-Null
        }
    }

    # Step 3: Image presence
    Write-Step "Step 3/6: Checking Ollama image ..."
    $imageExists = docker images --format "{{.Repository}}:{{.Tag}}" 2>$null | Where-Object { $_ -eq $OllamaImage }
    if (-not $imageExists) {
        Write-Host "[start_ollama] Pulling $OllamaImage ..."
        docker pull $OllamaImage
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to pull $OllamaImage. Check network or proxy."
            exit 2
        }
    }
    Write-Ok "Image $OllamaImage present"

    # Step 4: Start container
    Write-Step "Step 4/6: Starting Ollama container ..."
    if ($existing -ne $ContainerName) {
        docker run -d --rm --gpus all --network host --name $ContainerName `
            -v "${ModelsMount}:/models" `
            -v "${OllamaMount}:/root/.ollama" `
            -e 'HTTPS_PROXY=http://127.0.0.1:7890' `
            -e 'HTTP_PROXY=http://127.0.0.1:7890' `
            -e 'NO_PROXY=localhost,127.0.0.1,host.docker.internal' `
            $OllamaImage | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to start Ollama container. Check 'docker logs $ContainerName'."
            exit 3
        }
    }
    Write-Ok "Container '$ContainerName' started on port $OllamaPort"

    # Step 5: Health check loop
    Write-Step "Step 5/6: Waiting for Ollama health (timeout ${HealthTimeoutSec}s) ..."
    $healthy = $false
    for ($i = 0; $i -lt $HealthTimeoutSec; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:${OllamaPort}/api/tags" -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) {
                $healthy = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $healthy) {
        Write-Err "Ollama health check failed after ${HealthTimeoutSec}s. Try 'docker logs $ContainerName'."
        exit 4
    }
    Write-Ok "Ollama healthy at http://localhost:${OllamaPort}"

    # Step 6: Pull model (unless skipped)
    if (-not $SkipPull) {
        Write-Step "Step 6/6: Pulling model '$Model' (timeout ${PullTimeoutSec}s) ..."
        $models = Invoke-WebRequest -Uri "http://localhost:${OllamaPort}/api/tags" -UseBasicParsing -TimeoutSec 5 |
                  ConvertFrom-Json
        $modelPresent = $models.models | Where-Object { $_.name -eq $Model }
        if ($modelPresent) {
            Write-Ok "Model '$Model' already present, skipping pull"
        } else {
            Write-Host "[start_ollama] Pulling $Model (may take several minutes) ..."
            $pullJob = Start-Job -ScriptBlock {
                param($c, $m)
                docker exec $c ollama pull $m
            } -ArgumentList $ContainerName, $Model
            $completed = Wait-Job $pullJob -Timeout $PullTimeoutSec
            if (-not $completed) {
                Stop-Job $pullJob
                Write-Err "Model pull timed out after ${PullTimeoutSec}s. Re-run or check network."
                exit 5
            }
            $rc = Receive-Job $pullJob
            Remove-Job $pullJob | Out-Null
            if ($rc -ne 0) {
                Write-Err "Model pull failed with exit code $rc."
                exit 5
            }
            Write-Ok "Model '$Model' pulled successfully"
        }
    } else {
        Write-Step "Step 6/6: Skipped (SkipPull flag set)"
    }

    # Final verification
    Write-Step "Final verification: OpenAI-compatible endpoint"
    try {
        $oaiResp = Invoke-WebRequest -Uri "http://localhost:${OllamaPort}/v1/models" -UseBasicParsing -TimeoutSec 5 |
                   ConvertFrom-Json
        $modelCount = $oaiResp.data.Count
        Write-Ok "OpenAI endpoint OK - $modelCount model(s) available"
    } catch {
        Write-Warn "OpenAI endpoint check failed: $($_.Exception.Message)"
    }

    Write-Host ""
    Write-Host "[start_ollama] Done. Configure backend:" -ForegroundColor Green
    Write-Host "    LLM_BACKEND=openai_compat"
    Write-Host "    OPENAI_COMPAT_BASE_URL=http://host.docker.internal:${OllamaPort}/v1"
    Write-Host "    OPENAI_COMPAT_MODEL=$Model"
    Write-Host "    OPENAI_COMPAT_API_KEY=ollama"
    Write-Host ""
}
catch {
    Write-Err "Unhandled error: $($_.Exception.Message)"
    Write-Host $_.ScriptStackTrace
    exit 99
}