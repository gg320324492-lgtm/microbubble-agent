# Workaround for docker/desktop-feedback#531 / #460:
#   "Backend aborts startup when it cannot remove its own AF_UNIX socket"
#
# On Windows an AF_UNIX socket is an NTFS reparse point. After an unclean exit
# the 0-byte socket file survives with an orphaned marker, and Win32 deletion
# fails with error 1920 (ERROR_CANT_ACCESS_FILE). The orphan is invisible to
# Get-ChildItem / ls -la, so the run directory LOOKS empty while the address is
# still in use -> the backend dies with
#   starting services: initializing Ingest server: listening on
#   unix://<HOME>/AppData/Local/Docker/run/sailor-ingest.sock: AF_UNIX listen
#   ... bind: Only one usage of each socket address
#
# The upstream workaround is to RENAME (never delete) the run directory and the
# docker-secrets-engine directory while no Docker process is running, so Docker
# Desktop recreates them fresh.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts\ci\docker-rename-run-dir.ps1
#
# ASCII-only on purpose (PowerShell 5.1 decodes a BOM-less .ps1 as GBK).
param(
    [string]$DataRoot = 'E:\microbubble-agent\data\docker\appdata'
)

$ErrorActionPreference = 'Continue'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

Write-Host '=== 1. make sure no Docker process is alive ==='
$procs = Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build', 'vpnkit' -ErrorAction SilentlyContinue
if ($procs) {
    $procs | ForEach-Object { Write-Host ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 6
} else {
    Write-Host '  none running'
}
$left = @(Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build', 'vpnkit' -ErrorAction SilentlyContinue)
Write-Host ("  remaining docker processes: {0}" -f $left.Count)
if ($left.Count -gt 0) { Write-Host '  WARNING: still running, the rename may not release the socket' }

Write-Host '=== 2. shutdown WSL ==='
wsl --shutdown 2>$null | Out-Null
Start-Sleep -Seconds 5

Write-Host '=== 3. rename the runtime socket directories (never delete) ==='
$targets = @(
    (Join-Path $DataRoot 'run'),
    (Join-Path $env:LOCALAPPDATA 'docker-secrets-engine')
)
foreach ($t in $targets) {
    if (-not (Test-Path $t)) { Write-Host ("  absent, skipped: {0}" -f $t); continue }
    $parent = Split-Path -Parent $t
    $leaf   = Split-Path -Leaf $t
    $dest   = Join-Path $parent ("{0}.stale-{1}" -f $leaf, $stamp)
    try {
        Rename-Item -Path $t -NewName (Split-Path -Leaf $dest) -ErrorAction Stop
        Write-Host ("  renamed: {0}" -f $t)
        Write-Host ("        -> {0}" -f $dest)
    } catch {
        Write-Host ("  RENAME FAILED: {0}" -f $t)
        Write-Host ("     {0}" -f $_.Exception.Message)
    }
}

Write-Host '=== 4. state after rename ==='
foreach ($t in $targets) {
    if (Test-Path $t) {
        Write-Host ("  {0} exists again (Docker recreated it? no - we have not started Docker yet)" -f $t)
    } else {
        Write-Host ("  {0} is gone (good)" -f $t)
    }
}
Write-Host '  Done. Start Docker Desktop now.'
