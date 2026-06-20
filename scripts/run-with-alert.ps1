# MicroBubble run-with-alert (PowerShell 核心) — 包装任意长命令，跑完自动 voice-alert
#
# 用法:
#   powershell scripts/run-with-alert.ps1 <command> [args...]
#
# 一般通过 .bat 包装调: scripts\run-with-alert <command> [args...]
# 也可独立调（适合 PowerShell 用户）:
#   powershell -File scripts/run-with-alert.ps1 "npm test"

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VoiceAlertPs1 = Join-Path $ScriptDir "voice-alert.ps1"

if (-not (Test-Path $VoiceAlertPs1)) {
    Write-Error "voice-alert.ps1 not found at $VoiceAlertPs1"
    exit 1
}

if ($Command.Count -eq 0) {
    Write-Host "Usage: run-with-alert.ps1 <command> [args...]"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  run-with-alert.ps1 pytest tests/"
    Write-Host "  run-with-alert.ps1 'npm run build'"
    Write-Host ""
    Write-Host "Wraps <command> and triggers voice-alert on completion:"
    Write-Host "  exit 0  -> voice-alert -TaskDone"
    Write-Host "  exit N  -> voice-alert -OnError 'exit code N'"
    exit 1
}

# 把数组拼成单条命令字符串，透传给 cmd.exe 处理（支持 shell built-in / pipe / && 等）
$cmdLine = $Command -join ' '
Write-Host "[run-with-alert] Running: $cmdLine"

$startTime = Get-Date
cmd /c $cmdLine
$exitCode = $LASTEXITCODE
$duration = (Get-Date) - $startTime
$mins = [int]$duration.TotalMinutes
$secs = [int]$duration.TotalSeconds % 60

# 按 exit code 决定提醒
if ($exitCode -eq 0) {
    Write-Host "[run-with-alert] OK in ${mins}m${secs}s"
    & $VoiceAlertPs1 -TaskDone
} else {
    Write-Host "[run-with-alert] FAILED exit=$exitCode in ${mins}m${secs}s"
    & $VoiceAlertPs1 -OnError "exit code $exitCode"
}

# 透传原命令的 exit code
exit $exitCode