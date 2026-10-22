# Recover Docker Desktop's WSL distro by forcing the "fresh provisioning" path.
#
# Why this script exists (2026-10-22 incident)
# ---------------------------------------------
# Timeline measured from the backend log (UTC) and the guard log (local):
#   21:06:51  backend pause/resume failed:
#             "Got an error resuming Docker Desktop: seeking
#              /sys/fs/cgroup/procd-paused/cgroup.procs"
#             -> the idle-paused WSL VM could not be woken -> backend crash.
#   21:15:38  MicroBubble-Docker-Guard L3: wsl --unregister docker-desktop
#   21:18:00  guard L3 again (the 30-minute gate was bypassed by a
#             concurrent writer of state.json)
#   21:27:56  Docker Desktop took the FRESH-PROVISIONING path
#             ("provisioning the WSL2 engine using a data disk",
#              "distro docker-desktop not found, skipping terminate/unregister",
#              "copied distribution", "setting up data disk", bootstrap OK,
#              "connected to WSL distro docker-desktop") and EVERYTHING CAME UP:
#             all 13 containers healthy.
#   21:28:44+ every later start took the "WSL2 disk exists" reuse path and
#             died with "initializing Ingest server: ... AF_UNIX listen ...
#             bind: Only one usage of each socket address".
#
# The reuse path is the broken one. This script puts the machine back on the
# path that is proven to work: drop the distro registration AND the 96 MB
# system disk, let Docker Desktop re-provision it, keep the 62 GB data disk
# (images / containers / volumes) exactly where it is.
#
# What this script does NOT touch:
#   - <dataRoot>\appdata\wsl\disk\docker_data.vhdx  (all user data)
#   - <dataRoot>\appdata\wsl-backup\                 (the 23 GB install-time copy)
#   - the broken system disk: it is renamed, not deleted.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\ci\recover-docker-wsl-distro.ps1
#
# ASCII-only on purpose (PowerShell 5.1 decodes a BOM-less .ps1 as GBK).
param(
    [string]$DataRoot = 'E:\DockerData\appdata',
    [switch]$DisableAutoPause
)

$ErrorActionPreference = 'Stop'

$mainDir  = Join-Path $DataRoot 'wsl\main'
$sysDisk  = Join-Path $mainDir 'ext4.vhdx'
$settings = Join-Path $env:APPDATA 'Docker\settings-store.json'

Write-Host '=== step 1: stop Docker Desktop ==='
Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 5

Write-Host '=== step 2: shutdown WSL ==='
wsl --shutdown 2>$null | Out-Null
Start-Sleep -Seconds 5

Write-Host '=== step 3: unregister the docker-desktop distro ==='
$reg = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' -ErrorAction SilentlyContinue |
    Where-Object { (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DistributionName -eq 'docker-desktop' }
if ($reg) {
    Write-Host '  docker-desktop is registered -> unregistering'
    wsl --unregister docker-desktop 2>&1 | Out-Null
} else {
    Write-Host '  docker-desktop is not registered (already gone)'
}
Start-Sleep -Seconds 3

Write-Host '=== step 4: move the system disk aside (not delete) ==='
if (Test-Path $sysDisk) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dest = Join-Path $mainDir ("ext4.vhdx.broken-$stamp")
    Rename-Item -Path $sysDisk -NewName (Split-Path -Leaf $dest)
    Write-Host ("  {0}" -f $dest)
} else {
    Write-Host '  system disk already absent'
}

Write-Host '=== step 5: report ==='
Get-ChildItem $mainDir -Force -ErrorAction SilentlyContinue |
    Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
$dataDisk = Join-Path $DataRoot 'wsl\disk\docker_data.vhdx'
if (Test-Path $dataDisk) {
    $len = (Get-Item $dataDisk).Length
    Write-Host ("  data disk intact: {0} ({1:N0} bytes)" -f $dataDisk, $len)
} else {
    Write-Host '  WARNING: data disk missing!'
}

if ($DisableAutoPause) {
    Write-Host '=== step 6: disable Docker Desktop idle auto-pause ==='
    if (Test-Path $settings) {
        $raw = Get-Content $settings -Raw
        $obj = $raw | ConvertFrom-Json
        if ($obj.PSObject.Properties.Name -contains 'AutoPauseTimeoutSeconds') {
            Write-Host ("  AutoPauseTimeoutSeconds was {0}" -f $obj.AutoPauseTimeoutSeconds)
        } else {
            Write-Host '  AutoPauseTimeoutSeconds not present yet (default applies)'
        }
        $obj | Add-Member -NotePropertyName 'AutoPauseTimeoutSeconds' -NotePropertyValue 0 -Force
        $obj | ConvertTo-Json -Depth 20 | Set-Content -Path $settings -Encoding UTF8
        Write-Host '  AutoPauseTimeoutSeconds = 0 (never pause)'
    } else {
        Write-Host ("  settings file not found: {0}" -f $settings)
    }
}

Write-Host '  Done. Now start Docker Desktop and watch for "provisioning the WSL2 engine using a data disk".'
