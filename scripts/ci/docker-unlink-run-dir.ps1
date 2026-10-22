# Controlled experiment: remove the junction from the AF_UNIX socket path.
#
# Hypothesis under test
# ---------------------
# The Docker Desktop backend binds its ingest socket at
#   %LOCALAPPDATA%\Docker\run\sailor-ingest.sock
# On this machine %LOCALAPPDATA%\Docker is a JUNCTION to E:\microbubble-agent\data\docker\appdata,
# so the socket path traverses a reparse point. Windows AF_UNIX bind keys the
# address on the resolved path; if the parent backend and the "services" child
# resolve it to two different strings that map to the same file, the second
# bind fails with WSAEADDRINUSE ("Only one usage of each socket address ...").
#
# This script rebuilds the layout so that %LOCALAPPDATA%\Docker is a REAL
# directory on C: and only the big trees (wsl/, wsl-backup/, log/, tasks/) are
# junctions into E:. The socket path then contains no reparse point at all.
#
# The data (E:\microbubble-agent\data\docker\appdata\wsl\disk\docker_data.vhdx) is never touched.
# The original junction is kept as Docker_junction_backup so this is reversible.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts\ci\docker-unlink-run-dir.ps1
param(
    [string]$AppData = 'E:\microbubble-agent\data\docker\appdata',
    [string]$LocalRoot = 'C:\Users\pc\AppData\Local'
)

$ErrorActionPreference = 'Stop'

Write-Host '=== 1. stop Docker ==='
Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 6
wsl --shutdown 2>$null | Out-Null
Start-Sleep -Seconds 4

$dockerDir = Join-Path $LocalRoot 'Docker'
$backup   = Join-Path $LocalRoot 'Docker_junction_backup'

Write-Host '=== 2. move the existing junction aside ==='
if (Test-Path $backup) { Remove-Item $backup -Force -Recurse -ErrorAction SilentlyContinue }
if (Test-Path $dockerDir) {
    $item = Get-Item $dockerDir -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Rename-Item -Path $dockerDir -NewName 'Docker_junction_backup'
        Write-Host "  junction renamed -> $backup"
    } else {
        Write-Host '  not a junction, leaving as is'
    }
} else {
    Write-Host '  Docker dir absent'
}

Write-Host '=== 3. create a REAL Docker dir on C: ==='
if (-not (Test-Path $dockerDir)) {
    New-Item -ItemType Directory -Path $dockerDir -Force | Out-Null
    Write-Host "  created $dockerDir"
}

Write-Host '=== 4. junction the big trees back into E: ==='
foreach ($name in @('wsl', 'wsl-backup', 'log', 'tasks')) {
    $link = Join-Path $dockerDir $name
    $target = Join-Path $AppData $name
    if (Test-Path $link) { Write-Host ("  already present: {0}" -f $link); continue }
    if (-not (Test-Path $target)) { Write-Host ("  target absent, skipped: {0}" -f $target); continue }
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host ("  junction {0} -> {1}" -f $link, $target)
}

Write-Host '=== 5. verify: the socket parent must be a plain C: directory ==='
$runDir = Join-Path $dockerDir 'run'
if (-not (Test-Path $runDir)) { New-Item -ItemType Directory -Path $runDir -Force | Out-Null }
$runItem = Get-Item $runDir -Force
Write-Host ("  {0}  container={1} attrs={2} linkType={3}" -f $runItem.FullName, $runItem.PSIsContainer, $runItem.Attributes, $runItem.LinkType)
Write-Host '  --- layout ---'
Get-ChildItem $dockerDir -Force | ForEach-Object {
    $t = ''
    if ($_.Target) { $t = ' -> ' + ($_.Target -join ' | ') }
    Write-Host ("    {0,-22} {1,-10} {2}{3}" -f $_.Name, $_.Mode, $_.Attributes, $t)
}
Write-Host '  Done. Start Docker Desktop now.'
