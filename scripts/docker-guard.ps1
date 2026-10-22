# MicroBubble Docker Desktop guard - graded self-heal.
#
# WHAT WAS WRONG (2026-10-22 incident, rewritten after the fact)
# -------------------------------------------------------------
# The old ladder was L1 (clean *.stale) -> L2 (restart Docker) -> L3
# ("wsl --unregister docker-desktop").  Every level of it was broken:
#
#   * L3 WAS INEFFECTIVE.  "wsl --unregister docker-desktop" drops the distro
#     REGISTRATION but leaves the 96 MB system disk
#     <dataRoot>\wsl\main\ext4.vhdx on disk.  Docker Desktop's wslmigrate
#     component then logs "WSL2 disk exists", SKIPS the provisioning branch
#     and tries to reuse a distro that is no longer registered -> the engine
#     never starts.  Measured in the backend log: the one good start said
#     "provisioning the WSL2 engine using a data disk" / "distro docker-desktop
#     not found, skipping terminate" / "copied distribution" / "setting up data
#     disk" / "connected to WSL distro docker-desktop" and all 13 containers
#     came up; every later start said "WSL2 disk exists" and died with
#     "initializing Ingest server: ... AF_UNIX listen ... bind: Only one usage
#     of each socket address".
#     => L3 now MOVES THE SYSTEM DISK ASIDE after the unregister, so the
#        "disk exists" reuse branch can no longer be taken.  This was the step
#        the old L3 was missing.
#
#   * L3 RAN TWICE INSIDE THREE MINUTES (05:15:38 and 05:18:00).  The 30
#     minute gate lived in state.json and Set-State is a read-modify-write
#     merge: a concurrent reader can observe the file mid-rewrite (Set-Content
#     truncates before it writes), Get-State then returns $null, the gate
#     reads "never ran" and opens.
#     => the gate now lives in its own file, is CLAIMED with an atomic
#        exclusive create and is written atomically.  state.json no longer
#        takes part in the decision (it only keeps a copy for observability).
#
#   * TWO GUARD INSTANCES RAN AT THE SAME TIME (the log holds pairs of
#     identical messages microseconds apart).  Reason: the scheduled task runs
#     wscript.exe, and scripts/run-hidden.vbs launches powershell.exe with
#     bWaitOnReturn = False, so the Task Scheduler considers the action
#     finished the moment wscript.exe exits and starts the next 5 minute
#     repetition while the previous PowerShell is still running.
#     MultipleInstances=IgnoreNew cannot see the detached child.
#     => the script now takes a GLOBAL MUTEX; a second instance exits at once.
#
#   * L2 RESTARTED DOCKER WHILE THE OLD BACKEND WAS STILL ALIVE, so two
#     backends could fight over the same AF_UNIX socket.
#     => L0/L2/L3 now poll until the old processes are really gone before
#        starting a new one.
#
#   * THE ACL OF THE SYSTEM DISK CAN BE LOST.  WSL grants the app-container
#     SIDs (S-1-5-83-1-*) DIRECTLY on each .vhdx, they are not inherited from
#     the parent directory, and a relocated data root loses them: measured 0
#     such ACEs on ext4.vhdx vs 27 on docker_data.vhdx.  The symptom is
#     Wsl/Service/CreateInstance/MountDisk/HCS/E_ACCESSDENIED -> the ingest
#     server cannot start -> the backend crashes.
#     => the new L0 repairs them with scripts/ci/fix-docker-wsl-vhdx-acl.ps1.
#
#   * "docker info returned 0" was treated as "recovered".
#     => recovery now requires docker info AND docker ps to both succeed.
#
#   * AN ORPHANED AF_UNIX SOCKET CANNOT BE DELETED.  On Windows it is an NTFS
#     reparse point; after an unclean exit the 0 byte file survives, deletion
#     fails with error 1920, it is invisible to Get-ChildItem, yet it still
#     owns the AF_UNIX address -> the next bind fails.  The upstream
#     workaround is to RENAME, never to delete (docker/desktop-feedback#460
#     and #531).  => L0 and L3 rename the runtime socket dirs aside.
#
#   * "wsl --unregister docker-desktop" DELETES THE WHOLE main\ DIRECTORY,
#     ext4.vhdx included (measured 2026-10-22).  That deletion is exactly
#     what makes Docker take the provisioning branch on the next start, so
#     L3 has to make sure it happened.  If the file is still there it is
#     moved aside.
#
# THE AF_UNIX PREMISE (this is the one that actually breaks the backend)
#   %LOCALAPPDATA%\Docker exists TWICE on this machine:
#     C:\Users\pc\AppData\Local\Docker                        (the real one)
#     C:\Users\pc\AppData\Local\Packages\Claude_*\LocalCache\Local\Docker
#                                                             (the MSIX view)
#   Both are junctions to the same physical data root, and BOTH HAVE TO KEEP
#   POINTING AT THE SAME PLACE.  Docker Desktop starts two backend processes
#   (the parent and the "services" child); when they resolve
#   %LOCALAPPDATA%\Docker to two different strings they bind the SAME
#   physical socket twice and the backend dies with
#     initializing Ingest server: listening on unix://.../run/sailor-ingest.sock:
#     AF_UNIX listen ... bind: Only one usage of each socket address
#   Note that renaming the run dir does NOT fix that, and that the run dir
#   can look completely empty (no leftover file is visible from Win32 or from
#   Linux) while the address is still taken.  The cure is the junction, not
#   the socket file.  => the script checks the premise on every run and
#   refuses the destructive L3 when it does not hold.
#
# THE LADDER
#   L0  non destructive: stop docker, wsl --shutdown, repair the vhdx ACL,
#       rename the runtime socket dirs aside, then start Docker and wait.
#       Many incidents stop here, so L0 is tried before anything destructive.
#   L1  remove the *.stale* leftovers inside the run dir.
#   L2  stop (and really wait for) Docker, then start it again.
#   L3  the measured recovery recipe: stop, wsl --shutdown, unregister the
#       distro, MOVE THE SYSTEM DISK ASIDE, verify the 62 GB data disk is
#       still there, make sure the run dir exists and is empty, start Docker.
#       Gated to one run per 30 minutes by an independent, atomic gate.
#
# PATHS ARE RESOLVED, NEVER HARD CODED
#   The Docker data root moves (2026-10-22: E:\DockerData\appdata ->
#   E:\microbubble-agent\data\docker\appdata, the old root was deleted).  The
#   root is read from the Lxss registry key of the docker-desktop distro
#   (BasePath = ...\wsl\main, up two levels), which is where WSL itself keeps
#   it and which does not traverse the reparse points.  %LOCALAPPDATA% is
#   read from the registry as well, because a packaged (MSIX) caller gets a
#   redirected LocalAppData.
#   The Docker junction itself is only ever entered, never deleted: a
#   junction has to be removed with "cmd /c rmdir" and that removes the link
#   only.
#
# TIMING BUDGET
#   The scheduled task has an 8 minute execution limit.  The worst case
#   ladder is about 6.2 minutes with the defaults below (L0 120s + L1 15s +
#   L2 90s + L3 60s + the process shutdown waits).  Do not raise the waits
#   without raising the limit in register-docker-guard-task.ps1.
#
# ASCII ONLY ON PURPOSE: PowerShell 5.1 decodes a BOM-less .ps1 as GBK, so
# non ASCII characters here would be mangled (repo rule "class 20.216 form
# 4").  This file is written without a BOM.

param(
    [switch]$Quiet = $false,
    # NOTE: in a PowerShell param() block the comma has to come BEFORE a
    # trailing comment, otherwise the comment eats the comma and the parser
    # reports MissingEndParenthesisInFunctionParameterList.
    [int]$BootGraceMinutes = 3,
    [int]$JustFailedGraceMinutes = 2,
    [string]$DataRoot = '',
    [int]$L0WaitSeconds = 120,
    [int]$L2WaitSeconds = 90,
    [int]$L3WaitSeconds = 60,
    [int]$ProcessExitWaitSeconds = 20,
    [int]$L3GateMinutes = 30
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs\docker-guard"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ("docker-guard-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$StateFile = Join-Path $LogDir "state.json"
$L3GateFile = Join-Path $LogDir "l3-gate.json"
$L3GateLockFile = Join-Path $LogDir "l3-gate.lock"

$DOCKER_EXE = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$DOCKER_PROC_NAMES = @("Docker Desktop", "com.docker.backend", "com.docker.build", "vpnkit")
$DOCKER_PROC_PRIORITY = @("Docker Desktop", "com.docker.backend", "com.docker.build", "vpnkit")

# ==========================================================================
# PURE FUNCTIONS
# These have no side effects and no dependency on script scoped state, so
# scripts/ci/test-docker-guard.ps1 can extract them from this file (via the
# PowerShell AST) and assert on them without ever running the guard.
# ==========================================================================

function ConvertTo-NormalizedPath {
    # Strips the \\?\ extended length prefix that WSL puts in front of the
    # BasePath of a distro.  \\?\UNC\server\share becomes \\server\share.
    param([string]$Path)
    if (-not $Path) { return $Path }
    $p = $Path
    if ($p.StartsWith('\\?\UNC\')) { return ('\\' + $p.Substring(8)) }
    while ($p.StartsWith('\\?\')) { $p = $p.Substring(4) }
    return $p
}

function Resolve-DataRootFromBasePath {
    # <root>\wsl\main -> <root>.  Returns $null when the shape is unexpected.
    param([string]$BasePath)
    if (-not $BasePath) { return $null }
    $clean = ConvertTo-NormalizedPath $BasePath
    $wsl = Split-Path -Parent $clean
    if (-not $wsl) { return $null }
    if ((Split-Path -Leaf $wsl) -ne 'wsl') { return $null }
    return (Split-Path -Parent $wsl)
}

function Get-StaleName {
    # The name a runtime dir gets when it is moved aside.  Rename, never
    # delete: an orphaned AF_UNIX socket is a reparse point that cannot be
    # removed (error 1920) but can be renamed.
    param([string]$Leaf, [string]$Stamp)
    return ("{0}.stale-{1}" -f $Leaf, $Stamp)
}

function Test-GateOpen {
    # Pure 30 minute gate decision.  An unreadable or missing timestamp means
    # "never ran" and therefore an open gate.
    param([string]$LastRunAt, [datetime]$Now = (Get-Date), [int]$Minutes = 30)
    if (-not $LastRunAt) { return $true }
    $last = [datetime]::MinValue
    if (-not [datetime]::TryParse($LastRunAt, [ref]$last)) { return $true }
    $age = ($Now - $last).TotalMinutes
    if ($age -lt 0) { return $true }
    return ($age -ge $Minutes)
}

function Initialize-AtomicRename {
    # MoveFileEx with MOVEFILE_REPLACE_EXISTING swaps the DIRECTORY ENTRY, so
    # a concurrent reader sees either the old file or the new one and never a
    # half written one.  Add-Type needs a compiler, so fall back to
    # File.Replace (also atomic) when it is not available.
    if ($null -ne $script:MoveFileExAvailable) { return $script:MoveFileExAvailable }
    $script:MoveFileExAvailable = $false
    try {
        if (-not ("MicroBubbleDockerGuard.NativeMethods" -as [type])) {
            Add-Type -Namespace 'MicroBubbleDockerGuard' -Name 'NativeMethods' -MemberDefinition '[DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern bool MoveFileExW(string lpExistingFileName, string lpNewFileName, int dwFlags);'
        }
        $script:MoveFileExAvailable = $true
    } catch {
        $script:MoveFileExAvailable = $false
    }
    return $script:MoveFileExAvailable
}

function Write-AtomicFile {
    # Write via a temp file in the same directory and then swap it in with a
    # single rename, so a concurrent reader never observes a half written
    # file.  Set-Content truncates first and was the reason the old
    # state.json gate could be bypassed.
    #
    # Measured on this machine with a reader hammering the file while the
    # writer ran (300 writes, ~2 s, one reader thread):
    #   MoveFileEx(MOVEFILE_REPLACE_EXISTING)   0 broken reads
    #   File.Replace                             0 broken reads
    #   Move-Item -Force                       143 broken reads  <- NOT atomic
    #   Set-Content                             truncates, and fails
    #                                           outright while a reader
    #                                           holds the file
    # Move-Item -Force is the obvious PowerShell idiom and it is wrong.
    param([string]$Path, [string]$Content)
    $tmp = "{0}.tmp.{1}" -f $Path, $PID
    try {
        $enc = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tmp, $Content, $enc)
        $haveNative = Initialize-AtomicRename
        $done = $false
        for ($attempt = 1; $attempt -le 5 -and -not $done; $attempt++) {
            try {
                if (-not [System.IO.File]::Exists($Path)) {
                    [System.IO.File]::Move($tmp, $Path)
                    $done = $true
                } elseif ($haveNative) {
                    $done = [MicroBubbleDockerGuard.NativeMethods]::MoveFileExW($tmp, $Path, 1)
                    if (-not $done) { Start-Sleep -Milliseconds 40 }
                } else {
                    [System.IO.File]::Replace($tmp, $Path, $null)
                    $done = $true
                }
            } catch {
                Start-Sleep -Milliseconds 40
            }
        }
        if (-not $done) {
            # NEVER fall back to a truncating write on the target.
            # Set-Content truncates first, so a concurrent reader would observe
            # a half written file - which is exactly the failure this function
            # exists to prevent, and exactly how the old Set-State let the L3
            # gate open by accident (a reader got $null and read it as
            # "never ran").
            # Measured: with the Set-Content fallback in place the concurrent
            # reader of the 44 check suite saw 272 broken reads out of 10932
            # (2.5%); without it, 0 out of ~12000.
            # A STALE state file is harmless. A CORRUPT one is not.
            # Keeping the old file also keeps the L3 gate CLOSED, because the
            # old stamp is still there and still inside the 30 minute window.
            try { if ([System.IO.File]::Exists($tmp)) { [System.IO.File]::Delete($tmp) } } catch { }
            return $false
        }
        return $true
    } catch {
        try { if ([System.IO.File]::Exists($tmp)) { [System.IO.File]::Delete($tmp) } } catch { }
        return $false
    }
}

function Get-WslSidCount {
    # How many S-1-5-83-1-* (WSL app container) ACEs a file carries.
    # Returns -1 when the file does not exist or cannot be inspected.
    param([string]$Path)
    if (-not $Path) { return -1 }
    if (-not (Test-Path -LiteralPath $Path)) { return -1 }
    try {
        $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
        $ids = @($acl.Access |
            Where-Object { $_.IdentityReference.Value -like 'S-1-5-83-1-*' } |
            ForEach-Object { $_.IdentityReference.Value } |
            Sort-Object -Unique)
        return $ids.Count
    } catch {
        return -1
    }
}

# ==========================================================================
# CONTEXT RESOLUTION
# ==========================================================================

function Get-RealLocalAppData {
    # %LOCALAPPDATA% is redirected for packaged (MSIX) callers, so read the
    # real path from the registry and fall back to the environment variable.
    try {
        $k = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders' -ErrorAction Stop
        $v = $k.'Local AppData'
        if ($v) { return ([Environment]::ExpandEnvironmentVariables($v)) }
    } catch { }
    return $env:LOCALAPPDATA
}

function Get-DockerDistroBasePath {
    # Where WSL keeps the docker-desktop distro.
    try {
        $keys = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' -ErrorAction Stop
        foreach ($k in $keys) {
            $p = Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue
            if ($p -and $p.DistributionName -eq 'docker-desktop') { return $p.BasePath }
        }
    } catch { }
    return $null
}

function Resolve-DockerDataRoot {
    # Explicit parameter wins, then the Lxss registry, then the Docker
    # junction under the real LocalAppData.
    param([string]$Explicit)
    if ($Explicit) { return $Explicit }
    $base = Get-DockerDistroBasePath
    if ($base) {
        $root = Resolve-DataRootFromBasePath $base
        if ($root -and (Test-Path (Join-Path $root 'wsl'))) { return $root }
    }
    return (Join-Path (Get-RealLocalAppData) 'Docker')
}

function Get-DockerPathVariants {
    # %LOCALAPPDATA%\Docker exists TWICE on this machine:
    #   the real one, C:\Users\pc\AppData\Local\Docker, and
    #   the MSIX package redirected one that the Claude Desktop app sees,
    #   ...\Packages\Claude_*\LocalCache\Local\Docker.
    # Both are junctions to the same physical data root.  That has to stay
    # true: Docker Desktop starts two backend processes (the parent and the
    # "services" child) and when they resolve %LOCALAPPDATA%\Docker to two
    # different strings they bind the SAME physical socket twice, which kills
    # the backend with
    #   AF_UNIX listen ... bind: Only one usage of each socket address
    # The package directory is discovered, not hard coded.
    $realLocal = Get-RealLocalAppData
    $variants = @()
    $variants += (Join-Path $realLocal 'Docker')
    $pkgRoot = Join-Path $realLocal 'Packages'
    foreach ($pkg in @(Get-ChildItem -LiteralPath $pkgRoot -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue)) {
        $localCache = Join-Path $pkg.FullName 'LocalCache\Local\Docker'
        if (Test-Path -LiteralPath $localCache) { $variants += $localCache }
    }
    return @($variants | Sort-Object -Unique)
}

function Get-DockerRuntimeDirs {
    # Every directory Docker puts a unix socket into.  The run dir exists
    # under every path variant (they normally resolve to one and the same
    # physical directory) and the secrets engine has its own place.
    $dirs = @()
    foreach ($base in (Get-DockerPathVariants)) {
        $dirs += (Join-Path $base 'run')
    }
    $realLocal = Get-RealLocalAppData
    $dirs += (Join-Path $realLocal 'docker-secrets-engine')
    $pkgRoot = Join-Path $realLocal 'Packages'
    foreach ($pkg in @(Get-ChildItem -LiteralPath $pkgRoot -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue)) {
        $localCache = Join-Path $pkg.FullName 'LocalCache\Local'
        if (Test-Path -LiteralPath $localCache) {
            $dirs += (Join-Path $localCache 'docker-secrets-engine')
        }
    }
    return @($dirs | Sort-Object -Unique)
}

function Get-DockerPathReport {
    # The guard for the AF_UNIX premise described in Get-DockerPathVariants:
    # every Docker path variant has to resolve to the same physical data
    # root, and that root has to be the one WSL has registered.
    $realLocal = Get-RealLocalAppData
    $rows = @()
    foreach ($v in (Get-DockerPathVariants)) {
        $target = $v
        $isLink = $false
        $exists = $false
        try {
            $i = Get-Item -LiteralPath $v -Force -ErrorAction Stop
            $exists = $true
            $isLink = (($i.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
            if ($i.Target) { $target = @($i.Target)[0] }
        } catch { }
        $rows += @{ path = $v; target = $target; is_link = $isLink; exists = $exists }
    }
    $distinct = @($rows | Where-Object { $_.exists } | ForEach-Object { $_.target } | Sort-Object -Unique)
    $agree = ($distinct.Count -le 1)
    $registryRoot = $null
    try { $registryRoot = Resolve-DataRootFromBasePath (Get-DockerDistroBasePath) } catch { }
    if ($registryRoot -and $distinct.Count -gt 0 -and ($distinct -notcontains $registryRoot)) {
        $agree = $false
    }
    return @{ variants = $rows; distinct_targets = $distinct; registry_root = $registryRoot; agree = $agree }
}

# ==========================================================================
# LOGGING AND STATE
# ==========================================================================

function Write-Log {
    param([string]$Level, [string]$Message, [hashtable]$Extra = @{})
    if ($Extra.Count -eq 0) { $Extra = @{} }
    $entry = [ordered]@{
        timestamp = Get-Date -Format "o"
        level     = $Level
        script    = "docker-guard"
        message   = $Message
    }
    foreach ($k in $Extra.Keys) { $entry[$k] = $Extra[$k] }
    try {
        Add-Content -Path $LogFile -Value ($entry | ConvertTo-Json -Compress) -Encoding UTF8
    } catch { }
    if (-not $Quiet) {
        try { Write-Host ("[{0}] {1}" -f $Level, $Message) } catch { }
    }
}

function Get-State {
    # Never throws.  A transient read failure must NOT be read as "there is
    # no state": that is exactly what used to open the L3 gate by accident.
    # Retry a few times before giving up.
    param([string]$Path = $StateFile)
    if (-not $Path) { return $null }
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            if (-not (Test-Path -LiteralPath $Path)) { return $null }
            $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
            if ($raw) {
                $obj = ConvertFrom-Json -InputObject $raw -ErrorAction Stop
                if ($null -ne $obj) { return $obj }
            }
        } catch {
            # sharing violation or a half written file: try again
        }
        Start-Sleep -Milliseconds 40
    }
    return $null
}

function Set-State {
    param([hashtable]$Data, [string]$Path = $StateFile)
    if (-not $Path) { return $false }
    # Merge rather than overwrite: last_ok_at is a cross run baseline.
    # The write itself is atomic so a concurrent reader cannot see a
    # truncated file (that bug used to open the L3 gate by accident).
    $old = Get-State -Path $Path
    $merged = @{}
    if ($old) {
        foreach ($p in $old.PSObject.Properties) { $merged[$p.Name] = $p.Value }
    }
    foreach ($k in $Data.Keys) { $merged[$k] = $Data[$k] }
    if ($merged.level -eq "OK" -and -not $Data.ContainsKey("last_ok_at")) {
        $merged.last_ok_at = Get-Date -Format "o"
    }
    # A failed atomic write keeps the PREVIOUS content on purpose (see
    # Write-AtomicFile). Report it, but do not fall back to a truncating
    # write: a stale state file is harmless, a corrupt one is what made the
    # L3 gate open by accident.
    if (-not (Write-AtomicFile -Path $Path -Content ($merged | ConvertTo-Json -Compress))) {
        # Write-Log may not exist when this function is extracted on its own
        # (scripts/ci/test-docker-guard.ps1 pulls a subset of the functions
        # out of this file), so the report must not be a hard dependency.
        if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
            Write-Log "WARN" "state file could not be replaced atomically, keeping the previous one" @{ path = $Path }
        }
    }
}

# ==========================================================================
# DOCKER PROBES
# ==========================================================================

function Get-DockerStatus {
    # Side effect check, not just an exit code: the daemon has to answer
    # "docker info" AND "docker ps" before we call Docker healthy.
    $res = @{ daemon = $false; listed = $false; total = -1; running = -1; error = '' }
    $cli = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $cli) { $res.error = 'docker cli not found'; return $res }
    try { docker info 2>&1 | Out-Null } catch { $res.error = $_.Exception.Message; return $res }
    if ($LASTEXITCODE -ne 0) { $res.error = ("docker info exit {0}" -f $LASTEXITCODE); return $res }
    $res.daemon = $true
    try {
        $states = @(docker ps -a --format "{{.State}}" 2>&1)
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            $res.error = ("docker ps exit {0}: {1}" -f $code, (($states | Select-Object -Last 1) -join ' '))
            return $res
        }
        $known = @('running', 'exited', 'created', 'paused', 'restarting', 'removing', 'dead')
        $clean = @($states | Where-Object { $known -contains ([string]$_).Trim() })
        $res.listed = $true
        $res.total = $clean.Count
        $res.running = @($clean | Where-Object { ([string]$_).Trim() -eq 'running' }).Count
    } catch {
        $res.error = $_.Exception.Message
    }
    return $res
}

function Test-DockerRecovered {
    param([hashtable]$Status)
    if (-not $Status) { return (Test-DockerRecovered -Status (Get-DockerStatus)) }
    return ($Status.daemon -and $Status.listed)
}

function Wait-DockerRecovered {
    # Poll until the daemon answers both probes, or the budget runs out.
    # Docker cold start measured 59 s, the engine can take longer.
    param([int]$Seconds)
    $deadline = (Get-Date).AddSeconds($Seconds)
    $last = Get-DockerStatus
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 10
        $last = Get-DockerStatus
        if (Test-DockerRecovered -Status $last) { return $last }
    }
    return $last
}

function Get-DockerProcessCount {
    $p = @(Get-Process -Name $DOCKER_PROC_NAMES -ErrorAction SilentlyContinue)
    return $p.Count
}

function Stop-DockerProcesses {
    # Kill in priority order (the UI first, it would otherwise respawn the
    # backend) and then WAIT until the processes are really gone.  Starting a
    # new backend while the old one still holds the AF_UNIX socket is what
    # produced "Only one usage of each socket address".
    param([int]$WaitSeconds = 20)
    foreach ($name in $DOCKER_PROC_PRIORITY) {
        foreach ($p in @(Get-Process -Name $name -ErrorAction SilentlyContinue)) {
            try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
        }
    }
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        if ((Get-DockerProcessCount) -eq 0) { return 0 }
        Start-Sleep -Seconds 2
    }
    return (Get-DockerProcessCount)
}

function Start-DockerDesktop {
    if (-not (Test-Path -LiteralPath $DOCKER_EXE)) { return $false }
    try {
        Start-Process -FilePath $DOCKER_EXE -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Invoke-Wsl {
    # wsl can hang, and the scheduled task has an 8 minute execution limit,
    # so every wsl call is bounded and killed on timeout.
    param([string]$Arguments = '', [int]$TimeoutSeconds = 60)
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = 'wsl.exe'
        $psi.Arguments = $Arguments
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        if (-not $p.WaitForExit($TimeoutSeconds * 1000)) {
            try { $p.Kill() } catch { }
            return @{ ok = $false; exit_code = -1; output = 'timeout' }
        }
        $out = $p.StandardOutput.ReadToEnd()
        $err = $p.StandardError.ReadToEnd()
        return @{ ok = ($p.ExitCode -eq 0); exit_code = $p.ExitCode; output = (($out + $err) -replace '\s+', ' ').Trim() }
    } catch {
        return @{ ok = $false; exit_code = -1; output = $_.Exception.Message }
    }
}

# ==========================================================================
# L3 GATE (independent file, atomic write, atomic claim)
# ==========================================================================

function Get-L3GateState {
    param([string]$Path = $L3GateFile)
    $fromGateFile = $null
    if ($Path) {
        for ($attempt = 1; $attempt -le 5; $attempt++) {
            try {
                if (-not (Test-Path -LiteralPath $Path)) { break }
                $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
                if ($raw) {
                    $obj = ConvertFrom-Json -InputObject $raw -ErrorAction Stop
                    if ($null -ne $obj) { $fromGateFile = $obj; break }
                }
            } catch {
                # transient read failure, try again
            }
            Start-Sleep -Milliseconds 40
        }
    }
    # Fallback: the state file carries last_l3 as well. If the dedicated gate
    # file could not be replaced atomically (the swap is refused while a
    # reader holds it), the gate MUST still read as CLOSED - otherwise a
    # failed write would re-open the very gate it is supposed to hold. Take
    # the newer of the two timestamps.
    $fromState = $null
    $st = Get-State
    if ($st -and $st.last_l3) { $fromState = @{ last_l3_at = [string]$st.last_l3; source = 'state.json' } }
    if ($fromGateFile -and $fromState) {
        $t1 = [datetime]::MinValue
        $t2 = [datetime]::MinValue
        [void][datetime]::TryParse([string]$fromGateFile.last_l3_at, [ref]$t1)
        [void][datetime]::TryParse([string]$fromState.last_l3_at, [ref]$t2)
        return $(if ($t2 -gt $t1) { $fromState } else { $fromGateFile })
    }
    if ($fromGateFile) { return $fromGateFile }
    if ($fromState) { return $fromState }
    return $null
}

function Set-L3GateStamp {
    param([string]$Path = $L3GateFile)
    if (-not $Path) { return $false }
    $payload = @{ last_l3_at = (Get-Date -Format "o"); pid = $PID } | ConvertTo-Json -Compress
    return (Write-AtomicFile -Path $Path -Content $payload)
}

function Test-L3GateLockStale {
    # A lock file whose owner died stays behind and would block every later
    # L3 forever.  The lock carries its creation time, so an old one is
    # treated as stale.
    param([string]$LockPath = $L3GateLockFile, [int]$StaleMinutes = 20)
    $raw = $null
    try {
        $raw = Get-Content -LiteralPath $LockPath -Raw -ErrorAction Stop
    } catch {
        # A live holder keeps the file open with FileShare.None, so a read
        # failure means "someone is working on it", NOT "it is stale".
        # Getting this backwards would delete the lock of a running instance.
        return $false
    }
    if (-not $raw) { return $true }
    $t = [datetime]::MinValue
    if (-not [datetime]::TryParse($raw.Trim(), [ref]$t)) { return $true }
    return (((Get-Date) - $t).TotalMinutes -gt $StaleMinutes)
}

function Try-ClaimL3Gate {
    # Atomic mutual exclusion: exactly one instance can create the lock file.
    # Returns the open FileStream (keep it alive, it is the lock) or $null.
    param([string]$LockPath = $L3GateLockFile)
    if (-not $LockPath) { return $null }
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        try {
            $fs = [System.IO.File]::Open($LockPath,
                                        [System.IO.FileMode]::CreateNew,
                                        [System.IO.FileAccess]::Write,
                                        [System.IO.FileShare]::None)
            try {
                $bytes = [System.Text.Encoding]::UTF8.GetBytes((Get-Date -Format "o"))
                $fs.Write($bytes, 0, $bytes.Length)
                $fs.Flush()
            } catch { }
            return $fs
        } catch [System.IO.IOException] {
            if ($attempt -eq 1 -and (Test-L3GateLockStale -LockPath $LockPath)) {
                try { Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue } catch { }
                continue
            }
            return $null
        } catch {
            return $null
        }
    }
    return $null
}

function Release-L3Gate {
    param($Lock, [string]$LockPath = $L3GateLockFile)
    if ($Lock) {
        try { $Lock.Close(); $Lock.Dispose() } catch { }
    }
    if ($LockPath) {
        try { Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue } catch { }
    }
}

# ==========================================================================
# FILESYSTEM HELPERS
# ==========================================================================

function Rename-ToStale {
    # Rename, never delete.  An orphaned AF_UNIX socket is an NTFS reparse
    # point: deletion fails with error 1920 and the file stays invisible to
    # Get-ChildItem while still owning the socket address.
    param([string]$Path, [string]$Stamp)
    if (-not $Path) { return $null }
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $parent = Split-Path -Parent $Path
    $leaf = Split-Path -Leaf $Path
    $newName = Get-StaleName -Leaf $leaf -Stamp $Stamp
    try {
        Rename-Item -LiteralPath $Path -NewName $newName -ErrorAction Stop
        return (Join-Path $parent $newName)
    } catch {
        Write-Log "WARN" "rename to stale failed" @{ path = $Path; error = $_.Exception.Message }
        return $null
    }
}

function Reset-RuntimeSocketDirs {
    # Move the runtime socket dirs aside and make sure an empty run dir
    # exists.  Docker Desktop recreates both on the next start.
    # Every path variant is handled; the ones that do not exist (or that
    # resolve to the same physical directory) are simply skipped.
    param([string]$Stamp)
    $moved = @()
    foreach ($t in $script:RuntimeSocketDirs) {
        if (-not $t) { continue }
        if (-not (Test-Path -LiteralPath $t)) { continue }
        $dest = Rename-ToStale -Path $t -Stamp $Stamp
        if ($dest) { $moved += $dest }
    }
    if ($script:RunDir -and -not (Test-Path -LiteralPath $script:RunDir)) {
        try {
            New-Item -ItemType Directory -Path $script:RunDir -Force -ErrorAction Stop | Out-Null
        } catch {
            Write-Log "WARN" "could not create run dir" @{ path = $script:RunDir; error = $_.Exception.Message }
        }
    }
    return $moved
}

function Remove-StaleRunFiles {
    # The leftover *.stale* files inside the run dir.  This is a best effort
    # delete of ordinary files; a reparse point that refuses to go is left
    # alone (it is only a leftover, not the live socket).
    # NOTE: the run dir is only ever entered, never the Docker junction
    # itself - the junction has to be removed with "cmd /c rmdir" and only
    # removes the link, so it is never touched from here.
    $removed = 0
    $failed = 0
    foreach ($dir in $script:RunDirVariants) {
        foreach ($f in @(Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue |
                        Where-Object { $_.Name -like "*.stale*" })) {
            try {
                Remove-Item -LiteralPath $f.FullName -Force -ErrorAction Stop
                $removed++
            } catch {
                $failed++
            }
        }
    }
    return @{ removed = $removed; failed = $failed }
}

function Invoke-AclRepair {
    # Repair the S-1-5-83-1-* ACEs on the WSL system disk.  The helper is
    # the one the 2026-10-22 recovery used; it is idempotent and returns
    # immediately when the ACL is already complete.
    if (-not (Test-Path -LiteralPath $script:AclFixScript)) {
        return @{ ok = $false; detail = "acl helper missing: $($script:AclFixScript)" }
    }
    if (-not (Test-Path -LiteralPath $script:SystemDisk)) {
        return @{ ok = $false; detail = 'system disk absent, nothing to repair' }
    }
    if (-not (Test-Path -LiteralPath $script:DataDisk)) {
        return @{ ok = $false; detail = 'data disk absent, refusing to guess the template' }
    }
    try {
        $psExe = Join-Path $PSHOME 'powershell.exe'
        if (-not (Test-Path -LiteralPath $psExe)) { $psExe = 'powershell.exe' }
        $out = & $psExe -NoProfile -ExecutionPolicy Bypass -File $script:AclFixScript -DataRoot $script:DataRoot 2>&1
        $code = $LASTEXITCODE
        $detail = (($out | Select-Object -Last 3) -join ' | ')
        return @{ ok = ($code -eq 0); detail = $detail }
    } catch {
        return @{ ok = $false; detail = $_.Exception.Message }
    }
}

function Get-BackendDiagnostics {
    # The decisive lines of the Docker backend log.  They are the difference
    # between "the engine came up" and "the engine took the reuse path and
    # died on a stale socket".
    param([int]$Tail = 500)
    if (-not (Test-Path -LiteralPath $script:BackendLog)) { return @() }
    try {
        $pattern = 'provisioning the WSL2 engine|WSL2 disk exists|copied distribution|setting up data disk|connected to WSL distro|running bootstrap|AF_UNIX|E_ACCESSDENIED|backend crashed|error resuming Docker Desktop|distro: '
        $hits = @(Get-Content -LiteralPath $script:BackendLog -Tail $Tail -ErrorAction SilentlyContinue |
            Select-String -Pattern $pattern -ErrorAction SilentlyContinue |
            Select-Object -Last 8)
        $out = @()
        foreach ($h in $hits) {
            $line = [string]$h.Line
            if ($line.Length -gt 200) { $line = $line.Substring(0, 200) }
            $out += $line.Trim()
        }
        return $out
    } catch {
        return @()
    }
}

# ==========================================================================
# RECOVERY LEVELS
# ==========================================================================

function Invoke-L0Recovery {
    # Non destructive repair: ACL of the system disk + stale AF_UNIX sockets.
    param([string]$Stamp)
    $res = @{ started = $false; remaining = 0; acl_ok = $false; acl_detail = ''; moved = @() }

    $res.remaining = Stop-DockerProcesses -WaitSeconds $ProcessExitWaitSeconds
    if ($res.remaining -gt 0) {
        Write-Log "WARN" "L0 docker processes still alive, giving up on L0" @{ remaining = $res.remaining }
        return $res
    }

    Invoke-Wsl -Arguments '--shutdown' -TimeoutSeconds 30 | Out-Null
    Start-Sleep -Seconds 3

    $acl = Invoke-AclRepair
    $res.acl_ok = $acl.ok
    $res.acl_detail = $acl.detail
    if ($acl.ok) {
        Write-Log "INFO" "L0 system disk ACL repaired" @{
            system_disk = $script:SystemDisk
            data_disk   = $script:DataDisk
            detail      = $acl.detail
        }
    } else {
        Write-Log "WARN" "L0 system disk ACL repair failed" @{ detail = $acl.detail }
    }

    $res.moved = Reset-RuntimeSocketDirs -Stamp $Stamp
    if ($res.moved.Count -gt 0) {
        Write-Log "INFO" "L0 runtime socket dirs moved aside" @{ moved = $res.moved }
    }

    $res.started = Start-DockerDesktop
    if (-not $res.started) {
        Write-Log "WARN" "L0 could not start Docker Desktop" @{ exe = $DOCKER_EXE }
    }
    return $res
}

function Invoke-L3Recovery {
    # The measured recovery recipe.  The only destructive part is the
    # unregister; the 62 GB data disk is never touched, and the system disk
    # is moved aside (not deleted) so Docker takes the provisioning branch.
    param([string]$Stamp)
    $res = @{ ok = $false; reason = ''; moved = @(); system_disk_gone = $false }

    $remaining = Stop-DockerProcesses -WaitSeconds $ProcessExitWaitSeconds
    if ($remaining -gt 0) {
        $res.reason = "docker processes still alive: $remaining"
        return $res
    }
    Write-Log "INFO" "L3 docker processes stopped" @{}

    Invoke-Wsl -Arguments '--shutdown' -TimeoutSeconds 30 | Out-Null
    Start-Sleep -Seconds 5

    # The data disk must be there BEFORE anything destructive happens.
    if (-not (Test-Path -LiteralPath $script:DataDisk)) {
        $res.reason = ("data disk missing, aborting L3 so Docker cannot provision an empty one: {0}" -f $script:DataDisk)
        Write-Log "ERROR" "L3 aborted, data disk missing" @{ data_disk = $script:DataDisk }
        return $res
    }
    $dataLenBefore = (Get-Item -LiteralPath $script:DataDisk).Length

    # Unregister the distro.  This removes the registration only.
    $unreg = Invoke-Wsl -Arguments '--unregister docker-desktop' -TimeoutSeconds 90
    Write-Log "INFO" "L3 distro unregistered" @{ exit_code = $unreg.exit_code; output = $unreg.output }

    # THE STEP THE OLD L3 WAS MISSING: the system disk has to be gone, or
    # wslmigrate logs "WSL2 disk exists", skips provisioning and reuses a
    # distro that is not registered any more -> the engine never starts.
    if (Test-Path -LiteralPath $script:SystemDisk) {
        $dest = Rename-ToStale -Path $script:SystemDisk -Stamp $Stamp
        if (-not $dest) {
            $res.reason = "system disk could not be moved aside"
            return $res
        }
        Write-Log "WARN" "L3 system disk moved aside so Docker re-provisions it" @{
            from = $script:SystemDisk
            to   = $dest
        }
        # The unregister is supposed to take the whole main\ directory with
        # it.  If only the file was left behind, take the now empty
        # directory too, so "WSL2 disk exists" cannot be answered from the
        # directory either.  A reparse point is never removed here.
        try {
            if (Test-Path -LiteralPath $script:MainDir) {
                $mi = Get-Item -LiteralPath $script:MainDir -Force -ErrorAction Stop
                $isLink = (($mi.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
                $left = @(Get-ChildItem -LiteralPath $script:MainDir -Force -ErrorAction SilentlyContinue)
                if ((-not $isLink) -and $left.Count -eq 0) {
                    Remove-Item -LiteralPath $script:MainDir -Force -ErrorAction Stop
                    Write-Log "INFO" "L3 empty main dir removed" @{ path = $script:MainDir }
                }
            }
        } catch {
            Write-Log "WARN" "L3 could not remove the empty main dir" @{
                path = $script:MainDir
                error = $_.Exception.Message
            }
        }
    } else {
        Write-Log "INFO" "L3 system disk already gone" @{ path = $script:SystemDisk }
    }
    $res.system_disk_gone = -not (Test-Path -LiteralPath $script:SystemDisk)

    # The data disk must still be there and unchanged.
    if (-not (Test-Path -LiteralPath $script:DataDisk)) {
        $res.reason = "data disk disappeared during L3"
        Write-Log "ERROR" "L3 data disk disappeared" @{ data_disk = $script:DataDisk }
        return $res
    }
    $dataLenAfter = (Get-Item -LiteralPath $script:DataDisk).Length
    if ($dataLenAfter -ne $dataLenBefore) {
        Write-Log "WARN" "L3 data disk size changed" @{
            before = $dataLenBefore
            after  = $dataLenAfter
            path   = $script:DataDisk
        }
    }

    $res.moved = Reset-RuntimeSocketDirs -Stamp $Stamp
    if (-not (Test-Path -LiteralPath $script:RunDir)) {
        Write-Log "WARN" "L3 run dir missing after reset" @{ path = $script:RunDir }
    }

    if (-not (Start-DockerDesktop)) {
        $res.reason = "could not start Docker Desktop"
        return $res
    }
    $res.ok = $true
    return $res
}

# ==========================================================================
# MAIN
# ==========================================================================

# A named global mutex keeps two guard instances from running at the same
# time.  The scheduled task cannot do this for us: its action is wscript.exe
# and run-hidden.vbs launches powershell.exe with bWaitOnReturn = False, so
# the Task Scheduler believes the action is over as soon as wscript.exe exits
# and starts the next repetition while the previous PowerShell is still
# alive.  MultipleInstances=IgnoreNew only sees the wscript.exe process.
$script:GuardMutex = $null
$mutexHeld = $false
try {
    $script:GuardMutex = New-Object System.Threading.Mutex($false, "Global\MicroBubbleDockerGuard")
    $mutexHeld = $script:GuardMutex.WaitOne(0)
} catch {
    $script:GuardMutex = $null
}
if ($script:GuardMutex -and -not $mutexHeld) {
    Write-Log "INFO" "another guard instance is running, skipping this run" @{}
    exit 0
}

function Exit-Guard {
    param([int]$Code = 0)
    if ($script:GuardMutex) {
        try { $script:GuardMutex.ReleaseMutex() } catch { }
        try { $script:GuardMutex.Dispose() } catch { }
    }
    exit $Code
}

try {
    # ---------------------------------------------------------------- paths
    $script:DataRoot = Resolve-DockerDataRoot -Explicit $DataRoot
    $script:MainDir = Join-Path $script:DataRoot 'wsl\main'
    $script:SystemDisk = Join-Path $script:MainDir 'ext4.vhdx'
    $script:DiskDir = Join-Path $script:DataRoot 'wsl\disk'
    $script:DataDisk = Join-Path $script:DiskDir 'docker_data.vhdx'
    $script:RunDir = Join-Path $script:DataRoot 'run'
    $script:BackendLog = Join-Path $script:DataRoot 'log\host\com.docker.backend.exe.log'
    $script:AclFixScript = Join-Path $ProjectRoot 'scripts\ci\fix-docker-wsl-vhdx-acl.ps1'
    $script:RuntimeSocketDirs = Get-DockerRuntimeDirs
    $script:RunDirVariants = @()
    foreach ($base in (Get-DockerPathVariants)) {
        $script:RunDirVariants += (Join-Path $base 'run')
    }
    $script:RunDirVariants = @($script:RunDirVariants | Sort-Object -Unique)

    # The AF_UNIX premise: every Docker path variant has to resolve to the
    # same physical data root, and that root has to be the one WSL has
    # registered.  When they disagree, the two backend processes bind the
    # same physical socket twice and the backend dies with
    #   AF_UNIX listen ... bind: Only one usage of each socket address
    # Renaming the run dir cannot fix that; only the junction can.
    $pathReport = Get-DockerPathReport
    $script:PathVariantsAgree = [bool]$pathReport.agree
    $variantRows = @()
    foreach ($row in $pathReport.variants) {
        $variantRows += ("{0} -> {1}" -f $row.path, $row.target)
    }
    if ($script:PathVariantsAgree) {
        Write-Log "INFO" "docker path variants agree" @{
            data_root = $script:DataRoot
            variants = $variantRows
        }
    } else {
        Write-Log "ERROR" "docker path variants DISAGREE, the backend will die with AF_UNIX EADDRINUSE" @{
            data_root = $script:DataRoot
            registry_root = $pathReport.registry_root
            variants = $variantRows
            distinct_targets = $pathReport.distinct_targets
            hint = "re-point every %LOCALAPPDATA%\Docker junction at the same data root (see scripts/ci/docker-restart-clean-context.ps1)"
        }
    }

    # ------------------------------------------------------------ healthy?
    $status = Get-DockerStatus
    if (Test-DockerRecovered -Status $status) {
        $st = Get-State
        if ($st -and $st.level -and $st.level -ne "OK") {
            Write-Log "INFO" "Docker recovered" @{ from = $st.level; uptime_s = $st.uptime_s }
        }
        Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                    last_ok_at = (Get-Date -Format "o") }
        Exit-Guard 0
    }

    # A daemon that answers "docker info" but not "docker ps" is a zombie.
    # Give it one more chance before escalating to a restart.
    if ($status.daemon -and -not $status.listed) {
        Write-Log "WARN" "docker daemon answers but docker ps fails, retrying once" @{ error = $status.error }
        Start-Sleep -Seconds 15
        $status = Get-DockerStatus
        if (Test-DockerRecovered -Status $status) {
            Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                        last_ok_at = (Get-Date -Format "o") }
            Exit-Guard 0
        }
    }

    # ------------------------------------------------------------- grace
    # The criterion is never a single one: this task runs every 5 minutes, so
    # the first run after a boot can land exactly on the grace border and
    # skip a real outage.  Use "time since Docker was last seen healthy".
    $st = Get-State
    $boot = $null
    try { $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime } catch { }
    $sinceLastOk = $null
    if ($st -and $st.last_ok_at) {
        try { $sinceLastOk = ((Get-Date) - [datetime]$st.last_ok_at).TotalMinutes } catch { $sinceLastOk = $null }
    }
    $sinceBoot = if ($boot) { ((Get-Date) - $boot).TotalMinutes } else { $null }

    $withinGrace = $false
    $graceReason = ""
    if ($null -ne $sinceLastOk -and $sinceLastOk -lt $JustFailedGraceMinutes) {
        $withinGrace = $true
        $graceReason = "just-failed"
    } elseif ($null -ne $sinceBoot -and $sinceBoot -lt $BootGraceMinutes) {
        $withinGrace = $true
        $graceReason = "boot"
    }
    if ($withinGrace) {
        Write-Log "INFO" "Docker not up yet, within grace period" @{
            reason = $graceReason
            minutes_since_last_ok = if ($null -ne $sinceLastOk) { [math]::Round($sinceLastOk, 1) } else { $null }
            minutes_since_boot = if ($null -ne $sinceBoot) { [math]::Round($sinceBoot, 1) } else { $null }
            detail = $status.error
        }
        Exit-Guard 0
    }

    $level = if ($st -and $st.level) { $st.level } else { "L0" }
    Write-Log "WARN" "Docker daemon unavailable, escalating" @{
        from_level = $level
        boot_minutes = if ($boot) { [math]::Round(((Get-Date) - $boot).TotalMinutes, 1) } else { $null }
        data_root = $script:DataRoot
        detail = $status.error
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'

    # ---------------------------------------------------------------- L0
    # Non destructive: repair the vhdx ACL and clear the stale sockets, then
    # simply start Docker.  Most incidents stop here.
    $l0 = Invoke-L0Recovery -Stamp $stamp
    if ($l0.started) {
        $status = Wait-DockerRecovered -Seconds $L0WaitSeconds
        if (Test-DockerRecovered -Status $status) {
            Write-Log "INFO" "Docker came up after L0 (ACL repair + socket reset)" @{
                containers_total = $status.total
                containers_running = $status.running
            }
            Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                        last_ok_at = (Get-Date -Format "o") }
            Exit-Guard 0
        }
        Write-Log "WARN" "Docker still down after L0" @{
            waited_s = $L0WaitSeconds
            containers_total = $status.total
            backend_log = (Get-BackendDiagnostics)
        }
    }
    Set-State @{ level = "L1"; checked_at = (Get-Date -Format "o"); uptime_s = 0 }

    # ---------------------------------------------------------------- L1
    $stale = Remove-StaleRunFiles
    if ($stale.removed -gt 0 -or $stale.failed -gt 0) {
        Write-Log "INFO" "L1 cleaned stale socket files" @{
            removed = $stale.removed
            failed = $stale.failed
        }
    }
    Start-Sleep -Seconds 15
    $status = Get-DockerStatus
    if (Test-DockerRecovered -Status $status) {
        Write-Log "INFO" "Docker came up after L1 cleanup" @{
            containers_total = $status.total
            containers_running = $status.running
        }
        Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                    last_ok_at = (Get-Date -Format "o") }
        Exit-Guard 0
    }
    Set-State @{ level = "L2"; checked_at = (Get-Date -Format "o"); uptime_s = 0 }

    # ---------------------------------------------------------------- L2
    # Restart Docker Desktop, but only after the old backend is really gone:
    # two backends fighting over the same AF_UNIX socket is what produced
    # "Only one usage of each socket address".
    $remaining = Stop-DockerProcesses -WaitSeconds $ProcessExitWaitSeconds
    if ($remaining -gt 0) {
        Write-Log "WARN" "L2 old docker processes did not exit" @{ remaining = $remaining }
    } else {
        Write-Log "INFO" "L2 old docker processes exited" @{}
    }
    if (Start-DockerDesktop) {
        $status = Wait-DockerRecovered -Seconds $L2WaitSeconds
        if (Test-DockerRecovered -Status $status) {
            Write-Log "INFO" "Docker came up after L2 restart" @{
                containers_total = $status.total
                containers_running = $status.running
            }
            Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                        last_ok_at = (Get-Date -Format "o") }
            Exit-Guard 0
        }
        Write-Log "WARN" "Docker still down after L2 restart" @{
            waited_s = $L2WaitSeconds
            backend_log = (Get-BackendDiagnostics)
        }
    } else {
        Write-Log "WARN" "L2 could not start Docker Desktop" @{ exe = $DOCKER_EXE }
    }
    Set-State @{ level = "L3"; checked_at = (Get-Date -Format "o"); uptime_s = 0 }

    # ---------------------------------------------------------------- L3
    # The gate lives in its own file and is claimed atomically, so two
    # instances can never open it at the same time.
    #
    # L3 is the only destructive level, so it is skipped when the Docker path
    # variants disagree: in that state the backend dies on the AF_UNIX
    # address no matter how often the distro is rebuilt, and rebuilding it
    # would only throw away the registration for nothing.
    if (-not $script:PathVariantsAgree) {
        Write-Log "ERROR" "L3 skipped, the docker path variants disagree" @{
            data_root = $script:DataRoot
            variants = $variantRows
            hint = "re-point every %LOCALAPPDATA%\Docker junction at the same data root first"
        }
        Exit-Guard 1
    }

    $gateLock = Try-ClaimL3Gate
    if (-not $gateLock) {
        Write-Log "INFO" "L3 skipped, another instance holds the gate" @{}
        Exit-Guard 1
    }
    $l3Exit = 1
    try {
        $gate = Get-L3GateState
        $lastL3 = if ($gate -and $gate.last_l3_at) { [string]$gate.last_l3_at } else { '' }
        if (-not (Test-GateOpen -LastRunAt $lastL3 -Minutes $L3GateMinutes)) {
            Write-Log "INFO" "L3 skipped, ran recently" @{ last_l3 = $lastL3 }
            $l3Exit = 1
        } else {
            Write-Log "WARN" "L3 rebuilding docker-desktop distro (user data disk untouched)" @{
                data_root = $script:DataRoot
                system_disk = $script:SystemDisk
                data_disk = $script:DataDisk
                data_disk_bytes = if (Test-Path -LiteralPath $script:DataDisk) { (Get-Item -LiteralPath $script:DataDisk).Length } else { $null }
            }
            $l3 = Invoke-L3Recovery -Stamp $stamp
            if (-not (Set-L3GateStamp)) {
                # The dedicated gate file could not be replaced atomically.
                # The state file carries last_l3 too, and Get-L3GateState
                # takes the newer of the two, so the gate still reads CLOSED.
                Write-Log "WARN" "L3 gate stamp could not be written, falling back to the state file copy" @{}
            }
            if ($l3.ok) {
                $status = Wait-DockerRecovered -Seconds $L3WaitSeconds
                if (Test-DockerRecovered -Status $status) {
                    # Read back the ACL of the freshly provisioned system disk.
                    # It is only reported, never changed here: the disk is
                    # mounted at this point.  A missing S-1-5-83-1-* ACE is
                    # the 2026-10-19 failure mode and is repaired by
                    # scripts/ci/fix-docker-wsl-vhdx-acl.ps1 on the next L0.
                    $sysSids = Get-WslSidCount -Path $script:SystemDisk
                    $dataSids = Get-WslSidCount -Path $script:DataDisk
                    Write-Log "INFO" "Docker came up after L3 recovery" @{
                        containers_total = $status.total
                        containers_running = $status.running
                        system_disk_sids = $sysSids
                        data_disk_sids = $dataSids
                    }
                    if ($sysSids -ge 0 -and $dataSids -gt $sysSids) {
                        Write-Log "WARN" "the system disk is missing WSL app container ACEs" @{
                            system_disk = $script:SystemDisk
                            system_disk_sids = $sysSids
                            data_disk_sids = $dataSids
                            hint = "run scripts/ci/fix-docker-wsl-vhdx-acl.ps1"
                        }
                    }
                    Set-State @{ level = "OK"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                                last_ok_at = (Get-Date -Format "o")
                                last_l3 = (Get-Date -Format "o") }
                    $l3Exit = 0
                } else {
                    Write-Log "WARN" "Docker still down after L3 recovery" @{
                        waited_s = $L3WaitSeconds
                        reason = $l3.reason
                        system_disk_gone = $l3.system_disk_gone
                        system_disk_sids = (Get-WslSidCount -Path $script:SystemDisk)
                        data_disk_sids = (Get-WslSidCount -Path $script:DataDisk)
                        backend_log = (Get-BackendDiagnostics)
                    }
                    Set-State @{ level = "L3"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                                last_l3 = (Get-Date -Format "o") }
                    $l3Exit = 1
                }
            } else {
                Write-Log "ERROR" "L3 failed" @{
                    reason = $l3.reason
                    backend_log = (Get-BackendDiagnostics)
                }
                Set-State @{ level = "L3"; checked_at = (Get-Date -Format "o"); uptime_s = 0
                            last_l3 = (Get-Date -Format "o") }
                $l3Exit = 1
            }
        }
    } finally {
        Release-L3Gate -Lock $gateLock
    }
    Exit-Guard $l3Exit
} catch {
    Write-Log "ERROR" "guard aborted with an unexpected error" @{
        error = $_.Exception.Message
        at = $_.InvocationInfo.Line.Trim()
    }
    Exit-Guard 1
}
