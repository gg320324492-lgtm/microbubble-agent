# Make %LOCALAPPDATA%\Temp a junction to E:\microbubble-agent\data\tmp.
#
# Why
# ---
# The user-level TEMP/TMP was redirected to E: so that NEW processes stop
# writing to C:. But processes that were already running (the Claude Desktop
# app and the sessions it spawned, including the LabCairn test harness) still
# carry the OLD %TEMP% in their environment - a child inherits the parent's
# environment, and the app was started before the change. Measured: a freshly
# spawned child of this very session still sees the old value, so restarting a
# session cannot fix it.
#
# A directory junction fixes it for EVERY process, old or new: both
# C:\Users\pc\AppData\Local\Temp and E:\microbubble-agent\data\tmp then
# resolve to the same physical directory, so there is no split and no
# duplication.
#
# Procedure
#   1. delete everything under Temp (with the \\?\ long-path prefix, because
#      the leftovers contain node_modules\.pnpm paths far beyond MAX_PATH and
#      Remove-Item -Recurse silently fails on them),
#   2. move the live "claude" subtree OUT of Temp (a same-volume rename, which
#      does not touch the files inside and works even while the app holds
#      handles to them). The app recreates %TEMP%\claude on demand, and after
#      step 3 that lands on E:,
#   3. replace Temp with a junction to the new root,
#   4. merge the moved-aside claude content into the new location.
#
# Reversible: the junction can be removed and the original Temp directory
# restored from E:\microbubble-agent\data\tmp (everything was moved there,
# nothing was deleted).
param(
    [string]$NewRoot = 'E:\microbubble-agent\data\tmp',
    [string]$TempDir = 'C:\Users\pc\AppData\Local\Temp',
    [string]$AsideDir = 'C:\Users\pc\AppData\Local\TempClaude'
)

$ErrorActionPreference = 'Continue'

function Say { param([string]$m) Write-Host ("  {0}" -f $m) }

Say '=== 1. delete the leftovers with the \\?\ long-path prefix ==='
$left = 0
foreach ($e in @(Get-ChildItem $TempDir -Force -ErrorAction SilentlyContinue)) {
    if ($e.Name -eq 'claude') { continue }
    $p = '\\?\' + $e.FullName
    if ($e.PSIsContainer) {
        cmd /c "rd /s /q `"$p`"" 2>$null | Out-Null
    } else {
        cmd /c "del /f /q `"$p`"" 2>$null | Out-Null
    }
    if (Test-Path -LiteralPath $e.FullName) { $left++ }
}
Say ("  still present: {0}" -f $left)
$remaining = @(Get-ChildItem $TempDir -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'claude' })
foreach ($r in $remaining) { Say ("    leftover: {0}" -f $r.Name) }

Say '=== 2. move the live claude subtree out of Temp (rename, same volume) ==='
$claude = Join-Path $TempDir 'claude'
if (Test-Path $claude) {
    if (Test-Path $AsideDir) {
        Say ("  {0} already exists, merging into it first" -f $AsideDir)
        robocopy $claude $AsideDir /E /MOVE /SL /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NP /NJH /NJS | Out-Null
        Say ("  robocopy rc = {0}" -f $LASTEXITCODE)
    }
    if (Test-Path $claude) {
        try {
            Rename-Item -Path $claude -NewName (Split-Path -Leaf $AsideDir) -ErrorAction Stop
            Say ("  renamed to {0}" -f $AsideDir)
        } catch {
            Say ("  RENAME FAILED: {0}" -f $_.Exception.Message)
        }
    }
} else {
    Say '  no claude subtree present'
}

Say '=== 3. replace Temp with a junction ==='
$stillThere = @(Get-ChildItem $TempDir -Force -ErrorAction SilentlyContinue)
if ($stillThere.Count -gt 0) {
    Say ("  Temp is not empty ({0} entries) - aborting, nothing changed" -f $stillThere.Count)
    foreach ($s in $stillThere) { Say ("    {0}" -f $s.Name) }
    exit 1
}
try {
    Remove-Item -LiteralPath $TempDir -Force -Recurse -ErrorAction Stop
    Say '  removed the empty Temp directory'
} catch {
    Say ("  could not remove Temp: {0}" -f $_.Exception.Message)
    exit 1
}
New-Item -ItemType Junction -Path $TempDir -Target $NewRoot | Out-Null
Say ("  junction {0} -> {1}" -f $TempDir, $NewRoot)

Say '=== 4. merge the moved-aside claude content into the new location ==='
if (Test-Path $AsideDir) {
    $dst = Join-Path $NewRoot 'claude'
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    robocopy $AsideDir $dst /E /SL /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NP /NJH /NJS | Out-Null
    Say ("  robocopy rc = {0}" -f $LASTEXITCODE)
    Remove-Item $AsideDir -Recurse -Force -ErrorAction SilentlyContinue
    Say ("  removed the moved-aside copy: {0}" -f (-not (Test-Path $AsideDir)))
}

Say '=== 5. verify ==='
$i = Get-Item $TempDir -Force
Say ("  linkType = {0}  target = {1}" -f $i.LinkType, ($i.Target -join ' | '))
Say ("  C free GB = {0}" -f [math]::Round((Get-Volume C).SizeRemaining / 1GB, 1))
Say ("  E free GB = {0}" -f [math]::Round((Get-Volume E).SizeRemaining / 1GB, 1))
