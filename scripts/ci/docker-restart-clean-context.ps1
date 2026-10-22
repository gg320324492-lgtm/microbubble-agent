# Repair the package-redirected view of %LOCALAPPDATA%\Docker and start Docker
# Desktop from a CLEAN (non-MSIX-packaged) process context.
#
# Why this is needed
# ------------------
# The Claude Desktop app is an MSIX package. Processes it spawns see
#   %LOCALAPPDATA%\Docker
# redirected to
#   %LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\Docker
# Docker Desktop.exe inherits that identity when it is launched from such a
# process, and then it looks for its data root in the package view. After the
# data was moved to the project folder, the package-side junction still
# pointed at the old (now gone) E:\DockerData\appdata, so Docker Desktop died
# at startup with:
#   creating <HOME>\AppData\Local\Docker: mkdir <HOME>\AppData\Local\Docker:
#   Cannot create a file when that file already exists.
#
# This script (run via Task Scheduler):
#   1. re-points the package-side junction at the new location,
#   2. removes the stale docker-secrets-engine.stale leftover,
#   3. starts Docker Desktop and waits for the daemon,
#   4. verifies containers / images / volumes.
param(
    [string]$AppData = 'E:\microbubble-agent\data\docker\appdata',
    [string]$PkgLocal = 'C:\Users\pc\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local',
    [int]$WaitSeconds = 240
)

$ErrorActionPreference = 'Continue'
$out = 'E:\microbubble-agent\logs\docker-guard\docker-restart-clean.log'
$dir = Split-Path -Parent $out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
function Say { param([string]$m) $line = '{0}  {1}' -f (Get-Date -Format 'HH:mm:ss'), $m; Write-Host $line; Add-Content -Path $out -Value $line -Encoding UTF8 }

Say '=== docker restart from a clean context ==='
Say ("  appdata target : {0}" -f $AppData)

Write-Host '=== 1. package-side junction ==='
$pkgDocker = Join-Path $PkgLocal 'Docker'
if (Test-Path $pkgDocker) {
    $i = Get-Item $pkgDocker -Force
    Say ("  current: link={0} target={1}" -f $i.LinkType, ($i.Target -join ' | '))
    if ($i.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c rmdir "$pkgDocker" | Out-Null
        Say '  removed the stale junction (link only, target untouched)'
    }
}
if (-not (Test-Path $pkgDocker)) {
    New-Item -ItemType Junction -Path $pkgDocker -Target $AppData | Out-Null
    Say ("  junction {0} -> {1}" -f $pkgDocker, $AppData)
} else {
    Say ("  still present: {0}" -f $pkgDocker)
}

Write-Host '=== 2. stale leftovers ==='
foreach ($stale in @((Join-Path $PkgLocal 'docker-secrets-engine.stale'), 'C:\Users\pc\AppData\Local\docker-secrets-engine.stale')) {
    if (Test-Path $stale) {
        Remove-Item $stale -Recurse -Force -ErrorAction SilentlyContinue
        Say ("  removed {0}" -f $stale)
    }
}

Write-Host '=== 3. start Docker Desktop ==='
Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue |
    ForEach-Object { Say ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 6
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe' | Out-Null
Say ("  launched at {0}" -f (Get-Date -Format 'HH:mm:ss'))

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$up = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 10
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $up = $true; Say ("  *** DAEMON UP at {0} ***" -f (Get-Date -Format 'HH:mm:ss')); break }
    Say ("  [{0}] waiting (backend procs={1})" -f (Get-Date -Format 'HH:mm:ss'), @(Get-Process -Name 'com.docker.backend' -ErrorAction SilentlyContinue).Count)
}
if (-not $up) { Say '  *** DAEMON STILL DOWN ***' }

Say '=== 4. verify ==='
docker ps -a --format '  {{.Names}} | {{.Status}}' 2>&1 | ForEach-Object { Say $_ }
Say ("  images  : {0}" -f (@(docker images -q 2>$null).Count))
Say ("  volumes : {0}" -f (@(docker volume ls -q 2>$null).Count))
Say '=== end ==='
