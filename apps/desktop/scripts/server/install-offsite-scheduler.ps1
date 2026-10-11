# Offsite OSS sync scheduler installer (R-9 C)
#
# Registers a Windows scheduled task that mirrors the server backup share to Aliyun OSS
# once a day. ASCII-only on purpose: this file may be copied to servers with a non-UTF8
# code page, where non-ASCII characters get mangled (lesson from the parent project).
#
# Usage (run as Administrator on the backup server):
#   powershell -ExecutionPolicy Bypass -File install-offsite-scheduler.ps1 `
#       -Root "D:\share\backups" -Time 02:30
#
# Credentials are NOT stored by this script. Set them once for the service account, e.g.:
#   setx OSS_ACCESS_KEY_ID "..." /M
#   setx OSS_ACCESS_KEY_SECRET "..." /M
# (or pass -CredsFile and keep the JSON readable only by that account)

param(
    [Parameter(Mandatory = $true)][string]$Root,
    [string]$Time = "03:30",
    [string]$TaskName = "MNB-OffsiteOssSync",
    [string]$CredsFile = "",
    [string]$PythonExe = "python",
    [string]$PassphraseFile = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SyncScript = Join-Path $ScriptDir "offsite-oss-sync.py"
$LogDir = Join-Path $ScriptDir "logs"

if (-not (Test-Path $SyncScript)) {
    Write-Host "[ERROR] sync script not found: $SyncScript" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Root)) {
    Write-Host "[ERROR] backup root not found: $Root" -ForegroundColor Red
    exit 1
}

# The passphrase is a HARD requirement, not an option: the sync script encrypts
# unconditionally (no plaintext fallback). Better to fail here than to have the task
# fail silently every night (class 20.220: verify side effects, don't trust state fields).
#
# NOTE: keep this file ASCII-only (see header). Adding non-ASCII characters requires a
# UTF-8 BOM, because PowerShell 5.1 decodes BOM-less files with the ANSI code page and
# 3-byte UTF-8 Chinese then misaligns by one byte, swallowing structural characters.
if ($PassphraseFile -eq "") {
    # <repo> = $ScriptDir(server) -> scripts -> desktop -> apps -> <repo>
    $RepoRoot = $ScriptDir
    for ($i = 0; $i -lt 4; $i++) { $RepoRoot = Split-Path -Parent $RepoRoot }
    $PassphraseFile = Join-Path $RepoRoot ".secrets\offsite_backup.passphrase"
}
if (-not (Test-Path $PassphraseFile)) {
    Write-Host "[ERROR] passphrase file not found: $PassphraseFile" -ForegroundColor Red
    Write-Host "        The sync script encrypts unconditionally (no plaintext fallback)." -ForegroundColor Yellow
    Write-Host "        Create it yourself first (the script will not generate or print it):" -ForegroundColor Yellow
    Write-Host "          python -c `"import secrets,pathlib;p=pathlib.Path(r'$PassphraseFile');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(secrets.token_urlsafe(48),encoding='utf-8')`"" -ForegroundColor Yellow
    Write-Host "        Or pass -PassphraseFile <path>." -ForegroundColor Yellow
    exit 1
}
if ((Get-Item $PassphraseFile).Length -lt 32) {
    Write-Host "[WARN] passphrase file is shorter than 32 bytes; consider regenerating it." -ForegroundColor Yellow
}

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# ---- Credential pre-check (unless -CredsFile was given) ----
# A scheduled task runs with the environment of its principal, NOT of the shell that
# installs it. The OSS credentials here live in **User-level** env vars, so this only
# proves anything for a task registered under this same user -- which is why the
# principal below is the current user, not SYSTEM. Checking now turns "fails at 03:30
# every night" into "told at install time".
if ($CredsFile -eq "") {
    $missing = @()
    foreach ($k in @("OSS_BUCKET", "OSS_ENDPOINT", "OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET")) {
        $v = [Environment]::GetEnvironmentVariable($k, "User")
        if (-not $v) { $missing += $k }
    }
    if ($missing.Count -gt 0) {
        Write-Host "[WARN] not set for user '$env:USERDOMAIN\$env:USERNAME': $($missing -join ', ')" -ForegroundColor Yellow
        Write-Host "       The sync script will fail-loud at $Time until these are set (setx, then log off/on)." -ForegroundColor Yellow
        Write-Host "       Or pass -CredsFile <json> to supply them from a file instead." -ForegroundColor Yellow
    } else {
        Write-Host "[OK] OSS credentials present in user environment"
    }
} else {
    if (-not (Test-Path $CredsFile)) { Write-Host "[ERROR] -CredsFile not found: $CredsFile" -ForegroundColor Red; exit 1 }
    Write-Host "[OK] using credentials file: $CredsFile"
}

# ---- Interpreter self-check (class 20.220: verify the side effect really happens) ----
# The sync script cannot upload anything without `cryptography` (encryption has no
# switch). On this machine `python` on PATH resolves to **Python 3.10, which does NOT
# have it**, while Python 3.12 does. A task installed against the wrong interpreter
# would therefore fail silently every night with a log full of "[FATAL] needs
# cryptography". Catch that here, at install time, instead of at 03:30 every day.
#
# NOTE: probe with a snippet that prints a marker and swallows the ImportError, so
# nothing goes to stderr. `$ErrorActionPreference = "Stop"` turns ANY stderr from a
# native command into a terminating error, which would surface a raw Python
# traceback instead of the actionable message below.
# Resolve the interpreter path FIRST. `Test-Path` alone is wrong here: it returns
# false for a bare command name like "python" even when it resolves fine on PATH
# (that mistake made this check reject the very interpreter we wanted to accept).
# Get-Command handles both an absolute path and a PATH name / py launcher.
$pyCmd = $null
try { $pyCmd = Get-Command $PythonExe -ErrorAction Stop } catch { $pyCmd = $null }
$pyVer = ""
if ($pyCmd) {
    $pyVer = (& $PythonExe -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null)
}
if (-not $pyVer) {
    Write-Host "[ERROR] -PythonExe '$PythonExe' is not a runnable Python interpreter." -ForegroundColor Red
    Write-Host "        Check the path, or use the py launcher:  -PythonExe 'py -3.12'" -ForegroundColor Yellow
    exit 1
}
$pyCrypto = (& $PythonExe -c "import importlib.util as u,sys;sys.stdout.write(u.find_spec('cryptography') and 'yes' or 'no')" 2>$null)
if ($pyCrypto -ne "yes") {
    Write-Host "[ERROR] interpreter '$PythonExe' (Python $pyVer) has no 'cryptography'." -ForegroundColor Red
    Write-Host "        Encryption is unconditional, so every upload would fail at $Time nightly." -ForegroundColor Yellow
    Write-Host "        Either install it:  $PythonExe -m pip install cryptography" -ForegroundColor Yellow
    Write-Host "        Or point at an interpreter that has it:" -ForegroundColor Yellow
    Write-Host "          -PythonExe 'C:\Users\pc\AppData\Local\Programs\Python\Python312\python.exe'" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] interpreter: $PythonExe (Python $pyVer, cryptography present)"

# Log filename uses an **ISO date**, not %DATE%.
# zh-CN %DATE% is "2026/10/12 <weekday>" -- it contains Chinese and spaces, so the
# \=- substitution still leaves Chinese in the name, cmd's redirect then fails on the
# very first line, and the task completes every night having written **zero logs**.
# That was the previous version's failure mode (class 20.216).
$Stamp = (Get-Date -Format "yyyy-MM-dd")
$LogFile = Join-Path $LogDir "offsite-sync-$Stamp.log"
$CredsArg = ""
if ($CredsFile -ne "") { $CredsArg = " --creds `"$CredsFile`"" }

# Set PYTHONIOENCODING=utf-8 for the child: the script's messages are Chinese and
# Python encodes them with the **ANSI code page** (GBK on this machine), while
# `chcp 65001` below makes the console/redirect expect UTF-8. The mismatch is what
# produced mojibake in the very first real run. Also use ASCII timestamps instead of
# %DATE%, which injects a Chinese weekday into every log line.
$Inner = "set `"PYTHONIOENCODING=utf-8`" & `"$PythonExe`" `"$SyncScript`" --apply --confirm --root `"$Root`" --passphrase-file `"$PassphraseFile`"$CredsArg >> `"$LogFile`" 2>&1"
$Wrapper = Join-Path $LogDir "run-offsite-sync.cmd"

# cmd wrapper keeps schtasks /TR simple and avoids quoting hell in the task definition.
$WrapperBody = @(
    "@echo off",
    "chcp 65001 > nul",
    "echo [%DATE% %TIME%] offsite sync start >> `"$LogFile`"",
    $Inner,
    "echo [%DATE% %TIME%] offsite sync exit=%ERRORLEVEL% >> `"$LogFile`""
)
Set-Content -Path $Wrapper -Value $WrapperBody -Encoding ASCII

# Idempotent: remove an existing task first, otherwise /Create fails with "already exists".
#
# Use the Get-ScheduledTask cmdlet rather than `schtasks /Query`: schtasks writes
# "ERROR: The system cannot find the file specified." to **stderr** when the task does
# not exist -- which is the normal first-install case -- and with
# $ErrorActionPreference="Stop" that stderr becomes a terminating error. The install
# therefore aborted on every clean machine (reproduced here). A cmdlet returns $null
# instead and never writes to stderr.
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[INFO] removing existing task $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Register via the cmdlets rather than `schtasks /Create` for the same stderr reason
# as above. Register-ScheduledTask also lets us be explicit about the things that
# silently produce a task that never runs:
#   - Action points at the .cmd wrapper (an executable), never at a script file;
#   - StartWhenAvailable, so a machine that was off at 03:30 still runs it.
#
# CAUTION: Principal = the **current user**, deliberately NOT SYSTEM. The OSS credentials
# live in **User-level** environment variables, and SYSTEM does not read those --
# a SYSTEM task would fail-loud with "missing OSS_BUCKET" every single night.
# RunLevel stays Limited: registering as SYSTEM is also what silently breaks the
# `Credentials must not be empty` check above, since a different principal has a
# different environment.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute $Wrapper
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null
} catch {
    Write-Host "[ERROR] Register-ScheduledTask failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] scheduled task registered" -ForegroundColor Green
Write-Host "     task     : $TaskName"
Write-Host "     schedule : daily at $Time"
Write-Host "     root     : $Root"
Write-Host "     wrapper  : $Wrapper"
Write-Host "     log      : $LogFile"
Write-Host "     passphrase: $PassphraseFile"
Write-Host ""
Write-Host "Verify with:  schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Dry run now:  $PythonExe `"$SyncScript`" --scan --root `"$Root`" --passphrase-file `"$PassphraseFile`""
Write-Host ""

# ---- Read-back verification (class 20.216 / 20.220) ----
# schtasks can report a successful registration while mangling backslash paths in /TR
# into control characters; the task then exits 1 forever and writes **no log at all**
# (the process never starts). LastTaskResult will lie about it. So read the real Action
# back after registering and check for control characters plus wrapper presence.
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "[ERROR] post-check: task not found after Create" -ForegroundColor Red
    exit 1
}
$action = $task.Actions[0]
$exe = $action.Execute
$ctrl = [regex]::Matches($exe, "[\x00-\x1F]").Count
if ($ctrl -gt 0) {
    Write-Host "[ERROR] post-check: task action contains $ctrl control char(s) -> path corruption" -ForegroundColor Red
    Write-Host "        Execute = $([regex]::Escape($exe))" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Wrapper)) {
    Write-Host "[ERROR] post-check: wrapper missing: $Wrapper" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] post-check passed: action clean, wrapper present" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT - run it once and confirm the side effect actually happened:" -ForegroundColor Cyan
Write-Host "  1. schtasks /Run /TN $TaskName"
Write-Host "  2. Start-Sleep -Seconds 20"
Write-Host "  3. Get-Content '$LogFile' -Tail 30     # <- the log MUST exist and be non-empty"
Write-Host "  (a missing log file means the process never started - do not trust LastTaskResult)"
Write-Host ""
Write-Host "Reminder: set OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET for the task account,"
Write-Host "          or pass -CredsFile. This script stores no credentials."
