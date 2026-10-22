# Restore the original %LOCALAPPDATA%\Docker layout and expose which physical
# path Docker Desktop actually uses.
#
# What we learned (2026-10-22)
# ---------------------------
# This script's own PowerShell process runs INSIDE the Claude Desktop MSIX
# package, so every write under C:\Users\pc\AppData\Local\<X> is REDIRECTED
# into
#   C:\Users\pc\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\<X>
# That is why the 2026-06-17 junction
#   C:\Users\pc\AppData\Local\Docker  ->  E:\microbubble-agent\data\docker\appdata
# is NOT visible at the real path (WSL sees no such directory) but IS visible
# under the package's LocalCache. Docker Desktop itself is an ordinary Win32
# app and does NOT get that redirection, which is why its two processes can
# disagree about where %LOCALAPPDATA%\Docker\run\sailor-ingest.sock lives.
#
# This script:
#   1. removes the experimental 'Docker' directory this investigation created
#      inside the package LocalCache (junctions are removed link-only, so the
#      E: targets are never touched),
#   2. renames Docker_junction_backup back to Docker,
#   3. reports, from a NON-packaged viewpoint (WSL), what exists at the real
#      C:\Users\pc\AppData\Local\Docker path.
param()

$ErrorActionPreference = 'Continue'

$pkgLocal = 'C:\Users\pc\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local'
$expDir   = Join-Path $pkgLocal 'Docker'
$backup   = Join-Path $pkgLocal 'Docker_junction_backup'
$realPath = 'C:\Users\pc\AppData\Local\Docker'

Write-Host '=== 1. stop Docker ==='
Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build' -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host ("  stopping {0} (pid {1})" -f $_.ProcessName, $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 5

Write-Host '=== 2. remove the experimental Docker dir (junctions link-only) ==='
if (Test-Path $expDir) {
    Get-ChildItem $expDir -Force | ForEach-Object {
        $isReparse = ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        if ($isReparse) {
            cmd /c rmdir "$($_.FullName)" | Out-Null
            Write-Host ("  removed junction: {0}" -f $_.Name)
        } elseif ($_.PSIsContainer) {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host ("  removed dir: {0}" -f $_.Name)
        } else {
            Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
            Write-Host ("  removed file: {0}" -f $_.Name)
        }
    }
    Remove-Item $expDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ("  experimental dir gone: {0}" -f (-not (Test-Path $expDir)))
} else {
    Write-Host '  nothing to remove'
}

Write-Host '=== 3. restore the original junction ==='
if (Test-Path $backup) {
    if (Test-Path (Join-Path $pkgLocal 'Docker')) { Remove-Item (Join-Path $pkgLocal 'Docker') -Recurse -Force -ErrorAction SilentlyContinue }
    Rename-Item -Path $backup -NewName 'Docker'
    Write-Host '  restored package LocalCache\Local\Docker -> E:\microbubble-agent\data\docker\appdata'
} else {
    Write-Host '  backup junction not found'
}

Write-Host '=== 4. what exists where (from inside the package view) ==='
foreach ($p in @($realPath, (Join-Path $pkgLocal 'Docker'))) {
    if (Test-Path $p) {
        $i = Get-Item $p -Force
        Write-Host ("  {0}" -f $p)
        Write-Host ("     container={0} attrs={1} linkType={2} target={3}" -f $i.PSIsContainer, $i.Attributes, $i.LinkType, ($i.Target -join ' | '))
    } else {
        Write-Host ("  {0}  (absent in package view)" -f $p)
    }
}

Write-Host '=== 5. the truth, from a NON-packaged viewpoint (WSL) ==='
& wsl.exe -d Ubuntu-24.04 -- ls -la /mnt/c/Users/pc/AppData/Local/Docker/ 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
Write-Host '  --- package LocalCache view ---'
& wsl.exe -d Ubuntu-24.04 -- ls -la "/mnt/c/Users/pc/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Local/Docker/" 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
