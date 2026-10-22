# Rollback: remove nested junctions created by the interrupted migration and
# restore the original, known-good Docker data layout under E:\DockerData\appdata.
#
# Context (2026-10-22): an interrupted migration had renamed
#   E:\DockerData\appdata\wsl          -> wsl__moved
#   E:\DockerData\appdata\wsl-backup   -> wsl-backup__moved
# and replaced them with directory junctions pointing at
#   E:\microbubble-agent\data\docker\...
#
# The WSL registry BasePath for the docker-desktop distro is
#   \\?\E:\DockerData\appdata\wsl\main
# (a \\?\ path, which does not traverse reparse points the same way a normal
# path does), so the nested junction is not a safe steady state.
#
# This script is ASCII-only on purpose: PowerShell 5.1 decodes a .ps1 without
# a BOM as GBK and mangles non-ASCII text.
$ErrorActionPreference = 'Stop'

$appdata = 'E:\DockerData\appdata'

Write-Host '=== step 1: stop any Docker processes ==='
$procs = Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue
if ($procs) {
    $procs | ForEach-Object { Write-Host ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 6
} else {
    Write-Host '  no Docker processes running'
}

Write-Host '=== step 2: remove the nested junctions (link only, target untouched) ==='
foreach ($j in @("$appdata\wsl", "$appdata\wsl-backup")) {
    if (-not (Test-Path $j)) { Write-Host ("  not present: {0}" -f $j); continue }
    $item = Get-Item $j -Force
    $isReparse = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
    if ($isReparse) {
        # cmd rmdir removes the reparse point itself; it does NOT recurse into the target.
        cmd /c rmdir "$j" | Out-Null
        Write-Host ("  removed junction: {0}" -f $j)
    } else {
        Write-Host ("  NOT a reparse point, refusing to touch: {0}" -f $j)
    }
}

Write-Host '=== step 3: restore original directory names ==='
if (Test-Path "$appdata\wsl__moved") {
    Rename-Item -Path "$appdata\wsl__moved" -NewName 'wsl'
    Write-Host '  wsl__moved -> wsl'
} else { Write-Host '  wsl__moved not present' }

if (Test-Path "$appdata\wsl-backup__moved") {
    Rename-Item -Path "$appdata\wsl-backup__moved" -NewName 'wsl-backup'
    Write-Host '  wsl-backup__moved -> wsl-backup'
} else { Write-Host '  wsl-backup__moved not present' }

Write-Host '=== step 4: verify layout ==='
Get-ChildItem $appdata -Force | Select-Object Name, LinkType, Length | Format-Table -AutoSize
Write-Host '--- wsl/ ---'
Get-ChildItem "$appdata\wsl" -Force | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host '--- wsl/disk/ ---'
Get-ChildItem "$appdata\wsl\disk" -Force | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host '--- registry BasePath still resolves? ---'
$reg = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' |
    Where-Object { (Get-ItemProperty $_.PSPath).DistributionName -eq 'docker-desktop' }
$base = (Get-ItemProperty $reg.PSPath).BasePath
Write-Host ("  BasePath = {0}" -f $base)
$probe = Join-Path $base 'ext4.vhdx'
Write-Host ("  ext4.vhdx present = {0}" -f (Test-Path $probe))
