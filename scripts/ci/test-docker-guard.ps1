# Unit tests for the helpers of scripts/docker-guard.ps1.
#
# The functions under test are EXTRACTED FROM THE REAL GUARD SCRIPT with the
# PowerShell AST, so this file can never drift away from the shipped code
# and there is no second copy to keep in sync.
#
# The guard script itself is NEVER executed here, and nothing in this file
# touches Docker, WSL, the scheduled tasks or any real state: the tests only
# use a temporary directory.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\ci\test-docker-guard.ps1
#
# ASCII only on purpose (PowerShell 5.1 decodes a BOM-less .ps1 as GBK).

param(
    [string]$GuardScript = (Join-Path (Split-Path -Parent $PSScriptRoot) 'docker-guard.ps1')
)

$ErrorActionPreference = 'Stop'
$script:Checks = 0
$script:Failures = 0

function Assert-Equal {
    param($Actual, $Expected, [string]$Name)
    $script:Checks++
    if ($Actual -eq $Expected) {
        Write-Host ("  PASS  {0}" -f $Name)
        return
    }
    $script:Failures++
    Write-Host ("  FAIL  {0}" -f $Name)
    Write-Host ("        expected: [{0}]" -f $Expected)
    Write-Host ("        actual  : [{0}]" -f $Actual)
}

function Assert-True {
    param($Value, [string]$Name)
    Assert-Equal -Actual ([bool]$Value) -Expected $true -Name $Name
}

function Assert-False {
    param($Value, [string]$Name)
    Assert-Equal -Actual ([bool]$Value) -Expected $false -Name $Name
}

# --------------------------------------------------------------- extraction
$wanted = @(
    'ConvertTo-NormalizedPath',
    'Resolve-DataRootFromBasePath',
    'Get-StaleName',
    'Test-GateOpen',
    'Initialize-AtomicRename',
    'Write-AtomicFile',
    'Get-WslSidCount',
    'Get-State',
    'Set-State',
    'Get-L3GateState',
    'Set-L3GateStamp',
    'Test-L3GateLockStale',
    'Try-ClaimL3Gate',
    'Release-L3Gate',
    'Get-RealLocalAppData',
    'Get-DockerDistroBasePath',
    'Resolve-DockerDataRoot',
    'Get-DockerPathVariants',
    'Get-DockerRuntimeDirs',
    'Get-DockerPathReport'
)

Write-Host '=== 0. extract the helpers from the guard script ==='
if (-not (Test-Path -LiteralPath $GuardScript)) {
    Write-Host ("guard script not found: {0}" -f $GuardScript)
    exit 1
}
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($GuardScript, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors -and $parseErrors.Count -gt 0) {
    Write-Host ("PARSE ERRORS in {0}" -f $GuardScript)
    foreach ($e in $parseErrors) {
        Write-Host ("  line {0}: {1}" -f $e.Extent.StartLineNumber, $e.Message)
    }
    exit 1
}
Write-Host ("  guard script parses cleanly ({0} tokens)" -f $tokens.Count)

$defs = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
$loaded = @()
foreach ($d in $defs) {
    if ($wanted -notcontains $d.Name) { continue }
    Invoke-Expression $d.Extent.Text
    $loaded += $d.Name
}
foreach ($w in $wanted) {
    if ($loaded -contains $w) {
        Write-Host ("  loaded {0}" -f $w)
    } else {
        Write-Host ("  MISSING {0}" -f $w)
        $script:Failures++
    }
}
if ($script:Failures -gt 0) { exit 1 }

$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("dockerguard-test-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

try {
    # ------------------------------------------------------- path resolution
    Write-Host '=== 1. path resolution ==='
    Assert-Equal (ConvertTo-NormalizedPath '\\?\E:\DockerData\appdata\wsl\main') `
                 'E:\DockerData\appdata\wsl\main' 'normalized: strips the \\?\ prefix'
    Assert-Equal (ConvertTo-NormalizedPath '\\?\UNC\server\share') `
                 '\\server\share' 'normalized: rewrites the UNC form'
    Assert-Equal (ConvertTo-NormalizedPath 'E:\plain\path') `
                 'E:\plain\path' 'normalized: a plain path is unchanged'
    Assert-Equal (ConvertTo-NormalizedPath '') '' 'normalized: empty stays empty'

    Assert-Equal (Resolve-DataRootFromBasePath '\\?\E:\microbubble-agent\data\docker\appdata\wsl\main') `
                 'E:\microbubble-agent\data\docker\appdata' 'data root: derived from the Lxss BasePath'
    Assert-Equal (Resolve-DataRootFromBasePath 'E:\x\wsl\main') `
                 'E:\x' 'data root: derived without the prefix'
    Assert-Equal (Resolve-DataRootFromBasePath 'E:\x\notwsl\main') `
                 $null 'data root: an unexpected shape is rejected'
    Assert-Equal (Resolve-DataRootFromBasePath 'E:\x\wsl') `
                 $null 'data root: a truncated path is rejected'
    Assert-Equal (Resolve-DataRootFromBasePath '') `
                 $null 'data root: an empty path is rejected'

    # ---------------------------------------------------------- stale naming
    Write-Host '=== 2. stale naming (rename, never delete) ==='
    Assert-Equal (Get-StaleName -Leaf 'run' -Stamp '20261022-060000-000') `
                 'run.stale-20261022-060000-000' 'stale name of the run dir'
    Assert-Equal (Get-StaleName -Leaf 'docker-secrets-engine' -Stamp 'S1') `
                 'docker-secrets-engine.stale-S1' 'stale name of the secrets engine dir'
    Assert-Equal (Get-StaleName -Leaf 'ext4.vhdx' -Stamp 'S2') `
                 'ext4.vhdx.stale-S2' 'stale name of the WSL system disk'

    # ------------------------------------------------------------- the gate
    Write-Host '=== 3. the L3 gate (30 minute rule) ==='
    $now = Get-Date
    Assert-False (Test-GateOpen -LastRunAt $now.AddMinutes(-10).ToString('o') -Now $now -Minutes 30) `
                 'gate: a run 10 minutes ago closes the gate'
    Assert-False (Test-GateOpen -LastRunAt $now.AddMinutes(-29).ToString('o') -Now $now -Minutes 30) `
                 'gate: a run 29 minutes ago closes the gate'
    Assert-True (Test-GateOpen -LastRunAt $now.AddMinutes(-31).ToString('o') -Now $now -Minutes 30) `
                'gate: a run 31 minutes ago opens the gate'
    Assert-True (Test-GateOpen -LastRunAt '' -Now $now -Minutes 30) `
                'gate: never ran, the gate is open'
    Assert-True (Test-GateOpen -LastRunAt 'not-a-timestamp' -Now $now -Minutes 30) `
                'gate: an unreadable timestamp, the gate is open'
    Assert-True (Test-GateOpen -LastRunAt $now.AddMinutes(10).ToString('o') -Now $now -Minutes 30) `
                'gate: the clock moved backwards, the gate is open'

    # ------------------------------------------------------ atomic file write
    Write-Host '=== 4. atomic file write ==='
    $statePath = Join-Path $tmpDir 'state.json'
    Assert-True (Write-AtomicFile -Path $statePath -Content '{"a":1}') 'atomic write: the first write succeeds'
    Assert-True (Test-Path -LiteralPath $statePath) 'atomic write: the file exists'
    Assert-Equal (Get-Content -LiteralPath $statePath -Raw).Trim() '{"a":1}' 'atomic write: the content is what was asked for'
    Assert-True (Write-AtomicFile -Path $statePath -Content '{"a":2}') 'atomic write: the overwrite succeeds'
    Assert-Equal (Get-Content -LiteralPath $statePath -Raw).Trim() '{"a":2}' 'atomic write: the content was replaced'
    $leftovers = @(Get-ChildItem -LiteralPath $tmpDir -Filter '*.tmp.*' -Force -ErrorAction SilentlyContinue)
    Assert-Equal $leftovers.Count 0 'atomic write: no temp file is left behind'

    # ------------------------------------------------------- state merge
    Write-Host '=== 5. state merge keeps the cross run fields ==='
    Set-State -Path $statePath -Data @{ level = 'L3'; last_l3 = '2026-10-22T05:15:38+08:00' }
    Set-State -Path $statePath -Data @{ level = 'L2' }
    $merged = Get-State -Path $statePath
    Assert-Equal $merged.level 'L2' 'state merge: the new level is applied'
    Assert-Equal $merged.last_l3 '2026-10-22T05:15:38+08:00' 'state merge: last_l3 survives an unrelated write'
    Set-State -Path $statePath -Data @{ level = 'OK' }
    $merged = Get-State -Path $statePath
    Assert-True ([bool]$merged.last_ok_at) 'state merge: last_ok_at is stamped on OK'

    # ------------------------------------------------- concurrent read safety
    # This is the regression test for the 2026-10-22 incident: the old
    # Set-State truncated the file and wrote it, so a concurrent reader could
    # observe a half written file, Get-State returned $null and the L3 gate
    # read "never ran".
    Write-Host '=== 6. a concurrent reader never sees a half written state ==='
    $readerScript = {
        param($path, $millis)
        $end = (Get-Date).AddMilliseconds($millis)
        $bad = 0
        $reads = 0
        # FileShare.Delete lets the reader coexist with the atomic replace, so
        # a broken read can only mean a half written file, never a lock
        # conflict.
        $share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        while ((Get-Date) -lt $end) {
            try {
                $fs = [System.IO.File]::Open($path,
                        [System.IO.FileMode]::Open,
                        [System.IO.FileAccess]::Read,
                        $share)
                $sr = New-Object System.IO.StreamReader($fs)
                $raw = $sr.ReadToEnd()
                $sr.Dispose()
                $fs.Dispose()
                if ($raw) {
                    $null = ConvertFrom-Json -InputObject $raw -ErrorAction Stop
                    $reads++
                }
            } catch {
                $bad++
            }
        }
        return @{ reads = $reads; bad = $bad }
    }
    $rs = [runspacefactory]::CreateRunspace()
    $rs.Open()
    $ps = [powershell]::Create()
    $ps.Runspace = $rs
    $null = $ps.AddScript($readerScript.ToString()).AddArgument($statePath).AddArgument(2500)
    $handle = $ps.BeginInvoke()
    for ($i = 0; $i -lt 300; $i++) {
        Set-State -Path $statePath -Data @{ level = 'L2'; counter = $i }
    }
    $readerResult = $ps.EndInvoke($handle)
    $rs.Close()
    $rs.Dispose()
    $atomicBad = 0
    $atomicReads = 0
    if ($readerResult -and $readerResult.Count -gt 0) {
        $atomicBad = [int]$readerResult[0].bad
        $atomicReads = [int]$readerResult[0].reads
    }
    Write-Host ("  reader did {0} reads, {1} of them saw a broken file" -f $atomicReads, $atomicBad)
    Assert-Equal $atomicBad 0 'atomic write: the concurrent reader never saw a broken file'
    Assert-True ($atomicReads -gt 0) 'atomic write: the concurrent reader really did read the file'

    # ------------------------------------------- gate mutual exclusion
    Write-Host '=== 7. the gate lock keeps two instances apart ==='
    $gateDir = Join-Path $tmpDir 'gate'
    New-Item -ItemType Directory -Path $gateDir -Force | Out-Null
    $lockPath = Join-Path $gateDir 'l3-gate.lock'
    $gatePath = Join-Path $gateDir 'l3-gate.json'

    $first = Try-ClaimL3Gate -LockPath $lockPath
    Assert-True ($null -ne $first) 'gate lock: the first instance claims it'
    $second = Try-ClaimL3Gate -LockPath $lockPath
    Assert-True ($null -eq $second) 'gate lock: a second instance is refused while the first holds it'

    Set-L3GateStamp -Path $gatePath | Out-Null
    $gate = Get-L3GateState -Path $gatePath
    Assert-True ($null -ne $gate) 'gate stamp: the stamp file is readable'
    Assert-False (Test-GateOpen -LastRunAt ([string]$gate.last_l3_at) -Minutes 30) `
                 'gate stamp: a fresh stamp closes the gate'

    Release-L3Gate -Lock $first -LockPath $lockPath
    Assert-False (Test-Path -LiteralPath $lockPath) 'gate lock: the lock file is removed on release'
    $third = Try-ClaimL3Gate -LockPath $lockPath
    Assert-True ($null -ne $third) 'gate lock: it can be claimed again after the release'
    Release-L3Gate -Lock $third -LockPath $lockPath

    # A lock left behind by a dead process must not block L3 forever.
    [System.IO.File]::WriteAllText($lockPath, (Get-Date).AddMinutes(-45).ToString('o'))
    $reclaimed = Try-ClaimL3Gate -LockPath $lockPath
    Assert-True ($null -ne $reclaimed) 'gate lock: a stale lock from a dead process is reclaimed'
    Release-L3Gate -Lock $reclaimed -LockPath $lockPath

    # ---------------------------------------------------------- sid counting
    Write-Host '=== 8. WSL app container SID counting ==='
    Assert-Equal (Get-WslSidCount -Path (Join-Path $tmpDir 'missing.vhdx')) -1 `
                 'sid count: a missing file reports -1'
    $plain = Join-Path $tmpDir 'plain.bin'
    [System.IO.File]::WriteAllText($plain, 'x')
    Assert-True ((Get-WslSidCount -Path $plain) -ge 0) 'sid count: an existing file reports a number'

    # -------------------------------------------------- the live machine
    # Read only.  These assertions are the canary for the AF_UNIX premise:
    # every %LOCALAPPDATA%\Docker path variant has to resolve to the same
    # physical data root, otherwise the two Docker backend processes bind
    # the same socket twice and the backend dies.
    Write-Host '=== 9. the live machine (read only) ==='
    $resolvedRoot = Resolve-DockerDataRoot -Explicit ''
    Write-Host ("  resolved data root : {0}" -f $resolvedRoot)
    Assert-True ([bool]$resolvedRoot) 'live: the data root is resolved from the Lxss registry'
    if ($resolvedRoot) {
        Assert-True (Test-Path -LiteralPath (Join-Path $resolvedRoot 'wsl\disk\docker_data.vhdx')) `
                    'live: the 62 GB data disk is reachable under the resolved root'
        Assert-True (Test-Path -LiteralPath (Join-Path $resolvedRoot 'run')) `
                    'live: the run dir is reachable under the resolved root'
    }
    $variants = @(Get-DockerPathVariants)
    Write-Host ("  path variants      : {0}" -f ($variants -join ' | '))
    Assert-True ($variants.Count -ge 1) 'live: at least one Docker path variant is found'
    $runtimeDirs = @(Get-DockerRuntimeDirs)
    Write-Host ("  runtime socket dirs : {0}" -f ($runtimeDirs -join ' | '))
    Assert-True ($runtimeDirs.Count -ge 1) 'live: the runtime socket dirs are found'
    $report = Get-DockerPathReport
    foreach ($row in $report.variants) {
        Write-Host ("  variant {0} -> {1} (link={2}, exists={3})" -f $row.path, $row.target, $row.is_link, $row.exists)
    }
    Write-Host ("  registry root       : {0}" -f $report.registry_root)
    Assert-True ([bool]$report.agree) `
                'live: every %LOCALAPPDATA%\Docker variant points at the same data root (AF_UNIX premise)'
}
finally {
    try {
        if (Test-Path -LiteralPath $tmpDir) {
            Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    } catch { }
}

Write-Host ''
Write-Host ("{0} checks, {1} failures" -f $script:Checks, $script:Failures)
if ($script:Failures -gt 0) { exit 1 }
exit 0
