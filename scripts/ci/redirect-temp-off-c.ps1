# Redirect the user TEMP/TMP to E: and relocate the stale %TEMP% payload off C:.
#
# Why
# ---
# Measured 2026-10-22: %TEMP% on C: holds ~57 GB, and the largest part is
# ~506 directories named lcp* / lcr* (about 35 GB) which a DIFFERENT project's
# test harness (LabCairn, whose repo lives at E:\LabCairn) creates by cloning
# itself into %TEMP%. The newest of those directories was written two minutes
# before the measurement, i.e. the harness is ACTIVELY filling C: right now.
#
# Fixing this project's own code paths alone would not stop that flood, so the
# user-level TEMP/TMP are moved to E: as well. Existing directories are moved
# (not deleted) so nothing is destroyed, and a manifest is written.
#
# Safety rules
# ------------
#   * anything modified within -StaleHours hours is left alone (a live run may
#     be using it),
#   * the 'claude' subtree is never touched (it holds the running agent
#     transcripts of this very session),
#   * files are MOVED, never deleted.
#
# ASCII-only on purpose (PowerShell 5.1 decodes a BOM-less .ps1 as GBK).
param(
    [string]$NewTemp = 'E:\microbubble-agent\data\tmp',
    [string]$DisplacedRoot = 'E:\_displaced_temp_20261022',
    [int]$StaleHours = 6
)

$ErrorActionPreference = 'Continue'
$log = 'E:\microbubble-agent\logs\docker-guard\redirect-temp.log'
$logDir = Split-Path -Parent $log
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
function Say { param([string]$m) $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m; Write-Host $line; Add-Content -Path $log -Value $line -Encoding UTF8 }

$oldTemp = $env:TEMP
Say '=== redirect TEMP/TMP off C: ==='
Say ("  old TEMP : {0}" -f $oldTemp)
Say ("  new TEMP : {0}" -f $NewTemp)

Write-Host '=== 1. create the new temp root ==='
New-Item -ItemType Directory -Path $NewTemp -Force | Out-Null
Say ("  exists : {0}" -f (Test-Path $NewTemp))

Write-Host '=== 2. set the user-level environment variables ==='
foreach ($name in @('TEMP', 'TMP')) {
    [Environment]::SetEnvironmentVariable($name, $NewTemp, 'User')
    Say ("  user {0} = {1}" -f $name, ([Environment]::GetEnvironmentVariable($name, 'User')))
    Set-Item -Path ("Env:{0}" -f $name) -Value $NewTemp
    Say ("  session {0} = {1}" -f $name, (Get-Item ("Env:{0}" -f $name)).Value)
}

Write-Host '=== 3. relocate the stale %TEMP% payload ==='
$cutoff = (Get-Date).AddHours(-$StaleHours)
Say ("  cutoff (older than) : {0}" -f $cutoff)
New-Item -ItemType Directory -Path $DisplacedRoot -Force | Out-Null

$moved = 0
$movedBytes = 0
$skipped = 0
$manifest = Join-Path $DisplacedRoot 'MANIFEST.txt'
$manifestLines = New-Object System.Collections.Generic.List[string]

$entries = Get-ChildItem $oldTemp -Force -ErrorAction SilentlyContinue
foreach ($e in $entries) {
    if ($e.Name -like 'claude*') { Say ("  SKIP (in use by this session): {0}" -f $e.Name); $skipped++; continue }
    if ($e.LastWriteTime -gt $cutoff) { Say ("  SKIP (modified recently): {0}  {1}" -f $e.Name, $e.LastWriteTime); $skipped++; continue }
    if (-not $e.PSIsContainer) { continue }

    $src = $e.FullName
    $dst = Join-Path $DisplacedRoot $e.Name
    if (Test-Path $dst) { Say ("  SKIP (destination exists): {0}" -f $e.Name); $skipped++; continue }

    $sz = (Get-ChildItem $src -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if (-not $sz) { $sz = 0 }
    # robocopy /MOVE is reliable for cross-volume relocation of a whole tree.
    & robocopy $src $dst /E /MOVE /COPY:DAT /DCOPY:DAT /R:1 /W:1 /MT:8 /NFL /NDL /NP /NJH /NJS | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -lt 8) {
        $moved++
        $movedBytes += $sz
        $manifestLines.Add(('{0}`t{1:N0}`t{2}' -f $e.Name, $sz, $e.LastWriteTime))
        Say ("  moved {0}  ({1:N0} bytes, robocopy rc={2})" -f $e.Name, $sz, $rc)
    } else {
        Say ("  FAILED {0}  (robocopy rc={1})" -f $e.Name, $rc)
    }
}

$manifestLines | Set-Content -Path $manifest -Encoding UTF8
Say ("  moved {0} entries, {1:N0} bytes; skipped {1}" -f $moved, $movedBytes, $skipped)
Say ("  manifest : {0}" -f $manifest)

Write-Host '=== 4. report ==='
$c = Get-Volume -DriveLetter C
$e = Get-Volume -DriveLetter E
Say ("  C: free = {0:N1} GB" -f ($c.SizeRemaining / 1GB))
Say ("  E: free = {0:N1} GB" -f ($e.SizeRemaining / 1GB))
Say '=== done ==='
