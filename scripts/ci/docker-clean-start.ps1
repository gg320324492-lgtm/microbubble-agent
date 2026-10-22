# Clean single-instance start of Docker Desktop, with the evidence that matters.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts\ci\docker-clean-start.ps1 [-WaitSeconds 180]
#
# Prints:
#   - the exact pre-start state (distro registration, system disk presence)
#   - the decisive backend log lines (provisioning / bootstrap / distro attach)
#   - the daemon + container state afterwards
#
# ASCII-only on purpose (PowerShell 5.1 decodes a BOM-less .ps1 as GBK).
param(
    [string]$DataRoot = 'E:\microbubble-agent\data\docker\appdata',
    [int]$WaitSeconds = 180
)

$ErrorActionPreference = 'Continue'
$backendLog = Join-Path $DataRoot 'log\host\com.docker.backend.exe.log'
$dockerExe  = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'

Write-Host '=== 1. stop everything ==='
Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 6
wsl --shutdown 2>$null | Out-Null
Start-Sleep -Seconds 5

Write-Host '=== 2. pre-start state ==='
$reg = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' -ErrorAction SilentlyContinue |
    Where-Object { (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DistributionName -eq 'docker-desktop' }
if ($reg) {
    Write-Host ("  distro registered, BasePath = {0}" -f (Get-ItemProperty $reg.PSPath).BasePath)
} else {
    Write-Host '  distro NOT registered'
}
$mainDir = Join-Path $DataRoot 'wsl\main'
if (Test-Path $mainDir) {
    Get-ChildItem $mainDir -Force | Select-Object Name, Length | Format-Table -AutoSize
}
$runDir = Join-Path $DataRoot 'run'
if (Test-Path $runDir) {
    Write-Host '  run dir contents:'
    Get-ChildItem $runDir -Force | Select-Object Name, Length | Format-Table -AutoSize
}

Write-Host '=== 3. start Docker Desktop (single instance) ==='
Start-Process -FilePath $dockerExe | Out-Null
Write-Host ("  launched at {0}" -f (Get-Date -Format 'HH:mm:ss'))

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$up = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 10
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $up = $true; break }
    $n = @(Get-Process -Name 'com.docker.backend' -ErrorAction SilentlyContinue).Count
    Write-Host ("  [{0}] not up yet (backend procs={1})" -f (Get-Date -Format 'HH:mm:ss'), $n)
}
if ($up) { Write-Host '  *** DAEMON UP ***' } else { Write-Host '  *** DAEMON STILL DOWN ***' }

Write-Host '=== 4. decisive backend log lines ==='
if (Test-Path $backendLog) {
    Get-Content $backendLog -Tail 400 | Select-String -Pattern 'provisioning|WSL2 disk exists|distro:|copied distribution|setting up data disk|connected to WSL distro|bootstrap|AF_UNIX|E_ACCESSDENIED|cross-distro|wslintegration' |
        Select-Object -Last 25 | ForEach-Object { Write-Host ("  " + $_.Line.Substring(0, [Math]::Min(220, $_.Line.Length))) }
}

Write-Host '=== 5. final state ==='
wsl -l -v 2>$null | ForEach-Object { Write-Host ("  " + $_) }
Write-Host '  --- containers ---'
docker ps -a --format '  {{.Names}}`t{{.Status}}' 2>&1 | ForEach-Object { Write-Host $_ }
