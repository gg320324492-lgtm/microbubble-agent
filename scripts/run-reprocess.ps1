<#
MicroBubble reprocess meeting wrapper
Usage:
  powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\path\to\audio.m4a"
  powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify
  powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps regen
#>

param(
    [int]$Meeting = 0,
    [string]$AudioPath = "",
    [string]$Steps = "load,extract,cluster,vote,assign,apply,regen,verify",
    [string]$Container = "microbubble-agent-app-1",
    [switch]$Help
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ScriptLocalPath = Join-Path $ProjectRoot "scripts\reprocess_meeting.py"

function Step  { param($t) Write-Host "[$t]" -ForegroundColor Cyan }
function OK    { param($t) Write-Host "  OK  $t" -ForegroundColor Green }
function Warn  { param($t) Write-Host "  WARN $t" -ForegroundColor Yellow }
function Err   { param($t) Write-Host "  ERR $t" -ForegroundColor Red; exit 1 }

if ($Help -or $Meeting -eq 0) {
    Write-Host "Usage:"
    Write-Host "  powershell scripts/run-reprocess.ps1 -Meeting <id> -AudioPath <path>"
    Write-Host "  powershell scripts/run-reprocess.ps1 -Meeting <id> -Steps <steps>"
    Write-Host ""
    Write-Host "Steps: load,extract,cluster,vote,assign,apply,regen,verify"
    Write-Host "  verify  - 8 fields check (no audio needed)"
    Write-Host "  regen   - regenerate summary/key_points/decisions (reuses result.json)"
    Write-Host "  apply   - full reprocess (extract + apply + regen)"
    Write-Host "  (default) = all steps"
    exit 0
}

# 1. container
Step "1/5 container check"
$dockerPs = docker ps --format "{{.Names}}" 2>&1
if ($LASTEXITCODE -ne 0) { Err "docker command not available" }
if ($dockerPs -notcontains $Container) {
    Err "container $Container not running. Active: $($dockerPs -join ', ')"
}
OK "container: $Container"

# 2. copy script
Step "2/5 sync script to container"
docker cp $ScriptLocalPath "${Container}:/tmp/reprocess_meeting.py" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Err "docker cp reprocess_meeting.py failed" }
OK "/tmp/reprocess_meeting.py synced"

# 3. copy audio
$dockerAudioPath = ""
if ($AudioPath) {
    Step "3/5 copy audio to container"
    if (-not (Test-Path $AudioPath)) { Err "audio file not found: $AudioPath" }
    $audioName = Split-Path $AudioPath -Leaf
    $dockerAudioPath = "/tmp/$audioName"
    docker cp $AudioPath "${Container}:${dockerAudioPath}" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Err "docker cp audio failed" }
    $sizeMB = [math]::Round((Get-Item $AudioPath).Length / 1MB, 1)
    OK "audio: $dockerAudioPath ($sizeMB MB)"
} else {
    Step "3/5 skip audio copy"
    if ($Steps -match "extract") { Warn "Steps has extract but no -AudioPath" }
}

# 4. execute
Step "4/5 run reprocess"
Write-Host "    Meeting: $Meeting"
Write-Host "    Steps:   $Steps"
Write-Host "    Audio:   $dockerAudioPath"
Write-Host ""

# Build python args
$pyArgs = "--meeting $Meeting --steps $Steps"
if ($dockerAudioPath) { $pyArgs += " --audio $dockerAudioPath" }

Write-Host "------ docker exec output ------" -ForegroundColor DarkGray
# Pass args as array (avoids PowerShell splitting single arg string)
if ($dockerAudioPath) {
    docker exec -i $Container python /tmp/reprocess_meeting.py --meeting $Meeting --steps $Steps --audio $dockerAudioPath
} else {
    docker exec -i $Container python /tmp/reprocess_meeting.py --meeting $Meeting --steps $Steps
}
$execExit = $LASTEXITCODE
Write-Host "------ end (exit $execExit) ------" -ForegroundColor DarkGray

if ($execExit -ne 0) {
    Err "reprocess_meeting.py failed (exit $execExit)"
}

# 5. output info
Step "5/5 output files in container"
Write-Host "    /tmp/reprocess_${Meeting}_result.json          (intermediate)"
Write-Host "    /tmp/reprocess_${Meeting}_new_transcript.json (new transcript)"
Write-Host "    /tmp/meeting_${Meeting}_backup_*.json         (apply backup)"
Write-Host "    /tmp/meeting_${Meeting}_summary_backup_*.json (regen backup)"
Write-Host ""
OK "done"
Write-Host ""
Write-Host "Verify in browser: hard refresh (Ctrl+Shift+R) to see new speakers" -ForegroundColor Yellow
