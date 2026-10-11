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

# Log filename uses an **ISO date**, not %DATE%.
# zh-CN %DATE% is "2026/10/12 <weekday>" -- it contains Chinese and spaces, so the
# \=- substitution still leaves Chinese in the name, cmd's redirect then fails on the
# very first line, and the task completes every night having written **zero logs**.
# That was the previous version's failure mode (class 20.216).
$Stamp = (Get-Date -Format "yyyy-MM-dd")
$LogFile = Join-Path $LogDir "offsite-sync-$Stamp.log"
$CredsArg = ""
if ($CredsFile -ne "") { $CredsArg = " --creds `"$CredsFile`"" }

$Inner = "`"$PythonExe`" `"$SyncScript`" --apply --confirm --root `"$Root`" --passphrase-file `"$PassphraseFile`"$CredsArg >> `"$LogFile`" 2>&1"
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
$existing = schtasks /Query /TN $TaskName 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[INFO] removing existing task $TaskName"
    schtasks /Delete /TN $TaskName /F | Out-Null
}

$output = schtasks /Create /TN $TaskName `
    /TR "`"$Wrapper`"" `
    /SC DAILY /ST $Time `
    /RL HIGHEST /F 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] schtasks /Create failed: $output" -ForegroundColor Red
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
