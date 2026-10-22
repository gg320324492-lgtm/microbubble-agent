# Move Docker Desktop's data tree into the project folder.
#
# MUST be run from a NON-packaged context (a scheduled task), because the
# Claude Desktop MSIX package redirects C:\Users\pc\AppData\Local\<X> writes
# into
#   C:\Users\pc\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\<X>
# and this script has to touch the REAL C:\Users\pc\AppData\Local\Docker.
#
# Before:
#   E:\DockerData\appdata\      Docker data root (wsl\, log\, run\, tasks\)
#   E:\DockerData\wsl\           WSL swap file
#   E:\DockerData\vhdx-backup\
#   C:\Users\pc\AppData\Local\Docker   -> junction -> E:\DockerData\appdata
#   WSL registry BasePath: \\?\E:\DockerData\appdata\wsl\main
#   .wslconfig: swapFile=E:\\DockerData\\wsl\\swap.vhdx
#
# After:
#   E:\microbubble-agent\data\docker\appdata\   (real files)
#   E:\microbubble-agent\data\docker\wsl\
#   E:\microbubble-agent\data\docker\vhdx-backup\
#   C:\Users\pc\AppData\Local\Docker -> junction -> <new>\appdata
#   WSL registry BasePath: \\?\E:\microbubble-agent\data\docker\appdata\wsl\main
#   .wslconfig: swapFile=E:\\microbubble-agent\\data\\docker\\wsl\\swap.vhdx
#
# The registry BasePath has to be rewritten rather than left pointing at a
# junction: the \\?\ prefix does NOT traverse reparse points (measured:
# [System.IO.File]::Exists('\\?\E:\DockerData\_junctest\...') == False).
#
# E: to E: is one volume, so Move-Item is an instantaneous directory rename:
# no copy, and every ACL (including the S-1-5-83-1-* app-container SIDs WSL
# puts on the .vhdx files) is preserved byte for byte.
#
# ASCII-only on purpose (PowerShell 5.1 decodes a BOM-less .ps1 as GBK).
param(
    [string]$OldRoot = 'E:\DockerData',
    [string]$NewRoot = 'E:\microbubble-agent\data\docker',
    [string]$LogFile = 'E:\microbubble-agent\logs\docker-guard\move-docker-data.log'
)

$ErrorActionPreference = 'Stop'
$logDir = Split-Path -Parent $LogFile
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
function Say {
    param([string]$m)
    $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

Say '=== move-docker-data ==='
Say ("  old root : {0}" -f $OldRoot)
Say ("  new root : {0}" -f $NewRoot)
Say ("  exe      : {0}" -f [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName)

Write-Host '=== 1. stop Docker and WSL ==='
Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue |
    ForEach-Object { Say ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 8
wsl --shutdown 2>$null | Out-Null
Start-Sleep -Seconds 6
Say ("  remaining docker processes: {0}" -f @(Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue).Count)

Write-Host '=== 2. inventory of the old root ==='
if (-not (Test-Path $OldRoot)) { throw "old root not found: $OldRoot" }
Get-ChildItem $OldRoot -Force | ForEach-Object {
    Say ("  {0,-16} {1}" -f $_.Name, $(if ($_.PSIsContainer) { '<dir>' } else { "$($_.Length) bytes" }))
}

Write-Host '=== 3. move the trees (same volume => instant rename) ==='
New-Item -ItemType Directory -Path $NewRoot -Force | Out-Null
foreach ($name in @('appdata', 'wsl', 'vhdx-backup')) {
    $src = Join-Path $OldRoot $name
    $dst = Join-Path $NewRoot $name
    if (-not (Test-Path $src)) { Say ("  skip (absent): {0}" -f $src); continue }
    if (Test-Path $dst) { Say ("  skip (destination exists): {0}" -f $dst); continue }
    Move-Item -Path $src -Destination $dst
    Say ("  moved {0} -> {1}" -f $src, $dst)
}

Write-Host '=== 4. drop the stale 2026-06-17 install-time backup copy of the data disk ==='
$stale = Join-Path $NewRoot 'appdata\wsl-backup'
if (Test-Path $stale) {
    $len = (Get-ChildItem $stale -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    Say ("  wsl-backup = {0:N0} bytes (a snapshot of docker_data.vhdx taken when Docker Desktop was installed; the live data disk is separate and untouched)" -f $len)
    Remove-Item $stale -Recurse -Force -ErrorAction SilentlyContinue
    Say ("  deleted: {0}" -f (-not (Test-Path $stale)))
}

Write-Host '=== 5. re-point the %LOCALAPPDATA%\Docker junction ==='
$localDocker = Join-Path $env:LOCALAPPDATA 'Docker'
$newAppdata = Join-Path $NewRoot 'appdata'
if (Test-Path $localDocker) {
    $item = Get-Item $localDocker -Force
    Say ("  existing: linkType={0} target={1}" -f $item.LinkType, ($item.Target -join ' | '))
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c rmdir "$localDocker" | Out-Null
        Say '  removed the old junction (link only, target untouched)'
    }
} else {
    Say '  no existing entry'
}
if (-not (Test-Path $localDocker)) {
    New-Item -ItemType Junction -Path $localDocker -Target $newAppdata | Out-Null
    Say ("  junction {0} -> {1}" -f $localDocker, $newAppdata)
}

Write-Host '=== 6. rewrite the WSL registry BasePath for docker-desktop ==='
$reg = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' -ErrorAction SilentlyContinue |
    Where-Object { (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DistributionName -eq 'docker-desktop' }
if ($reg) {
    $oldBase = (Get-ItemProperty $reg.PSPath).BasePath
    $newBase = '\\?\' + (Join-Path $newAppdata 'wsl\main')
    Say ("  old BasePath : {0}" -f $oldBase)
    Say ("  new BasePath : {0}" -f $newBase)
    if ($oldBase -ne $newBase) {
        Set-ItemProperty -Path $reg.PSPath -Name 'BasePath' -Value $newBase
        Say ("  updated, now = {0}" -f (Get-ItemProperty $reg.PSPath).BasePath)
    }
} else {
    Say '  docker-desktop is not registered (Docker Desktop will provision it at start)'
}

Write-Host '=== 7. rewrite the .wslconfig swap file location ==='
$wslConfig = Join-Path $env:USERPROFILE '.wslconfig'
if (Test-Path $wslConfig) {
    $raw = Get-Content $wslConfig -Raw
    $newSwap = 'E:\\microbubble-agent\\data\\docker\\wsl\\swap.vhdx'
    if ($raw -match 'swapFile\s*=\s*(.+)') {
        $oldSwap = $Matches[1].Trim()
        Say ("  old swapFile : {0}" -f $oldSwap)
        if ($oldSwap -ne $newSwap) {
            $updated = [regex]::Replace($raw, '(?m)^swapFile\s*=.*$', "swapFile=$newSwap")
            [System.IO.File]::WriteAllText($wslConfig, $updated, (New-Object System.Text.UTF8Encoding($false)))
            Say ("  new swapFile : {0}" -f $newSwap)
        }
    } else {
        Say '  no swapFile key found'
    }
} else {
    Say '  .wslconfig not found'
}

Write-Host '=== 8. verify every path that used to point at the old location ==='
foreach ($c in @(
    (Join-Path $NewRoot 'appdata\wsl\main\ext4.vhdx'),
    (Join-Path $NewRoot 'appdata\wsl\disk\docker_data.vhdx'),
    (Join-Path $NewRoot 'wsl\swap.vhdx'),
    $localDocker,
    (Join-Path $env:LOCALAPPDATA 'docker-secrets-engine')
)) {
    if (Test-Path $c) {
        $i = Get-Item $c -Force
        Say ("  OK   {0}  attrs={1} link={2}" -f $c, $i.Attributes, $i.LinkType)
    } else {
        Say ("  MISS {0}" -f $c)
    }
}

Say '=== done ==='
