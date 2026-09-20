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
    [string]$Time = "02:30",
    [string]$TaskName = "MNB-OffsiteOssSync",
    [string]$CredsFile = "",
    [string]$PythonExe = "python"
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
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# Build the command line. Redirect stdout/stderr to a dated log so failures are visible.
$Stamp = "%DATE:/=-%"
$LogFile = Join-Path $LogDir "offsite-sync-$Stamp.log"
$CredsArg = ""
if ($CredsFile -ne "") { $CredsArg = " --creds `"$CredsFile`"" }

$Inner = "`"$PythonExe`" `"$SyncScript`" --apply --confirm --root `"$Root`"$CredsArg >> `"$LogFile`" 2>&1"
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
Write-Host ""
Write-Host "Verify with:  schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Dry run now:  $PythonExe `"$SyncScript`" --scan --root `"$Root`""
Write-Host ""
Write-Host "Reminder: set OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET for the task account,"
Write-Host "          or pass -CredsFile. This script stores no credentials."
