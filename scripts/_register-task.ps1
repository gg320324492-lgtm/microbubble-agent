# MicroBubble Auto Recovery - Direct Scheduled Task Registration
# Avoids bash/cmd escaping hell by using PowerShell array args
# Self-elevates to admin if not already running as admin

$ErrorActionPreference = "Stop"

$taskName = 'MicroBubble-Auto-Recovery'
$scriptPath = 'E:\microbubble-agent\scripts\auto-recovery-eventlog.ps1'
# XPath for ONEVENT trigger - Winlogon EventID=7002 (User logon session created)
# CRITICAL: schtasks /MO argument parser treats "and" as a switch keyword.
# Solution: nested predicates [System[Provider[...]]][EventID=...] (no "and" needed)
$xpath = "*[System[Provider[@Name='Microsoft-Windows-Winlogon']][EventID=7002]]"

Write-Host "============================================================"
Write-Host " MicroBubble Auto Recovery - Task Registration"
Write-Host "============================================================"
Write-Host ""

# Check admin - if not, relaunch self with elevation
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Not running as admin. Relaunching elevated..."
    $scriptFull = $MyInvocation.MyCommand.Path
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-ExecutionPolicy', 'Bypass', '-File', "`"$scriptFull`"") -Verb RunAs -Wait -PassThru
    exit $process.ExitCode
}

Write-Host "  Task name: $taskName"
Write-Host "  Script:    $scriptPath"
Write-Host "  Trigger:   ONEVENT Winlogon EventID=7002 + DELAY 2 min"
Write-Host ""

$argList = @(
    '/Create'
    '/TN', $taskName
    '/TR', "`"$scriptPath`""
    '/SC', 'ONEVENT'
    '/EC', 'Application'
    '/MO', $xpath
    '/DELAY', '0002:00'
    '/RL', 'HIGHEST'
    '/F'
)

Write-Host "Running schtasks..."
$process = Start-Process -FilePath 'schtasks.exe' -ArgumentList $argList -Wait -PassThru -NoNewWindow
Write-Host "schtasks exit code: $($process.ExitCode)"
exit $process.ExitCode