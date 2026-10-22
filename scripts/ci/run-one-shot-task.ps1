# Run a script once through Task Scheduler, in a clean (non-MSIX-packaged)
# process context, then wait for it and print the result.
#
# Why: the Claude Desktop app is an MSIX package. Every process it spawns
# sees C:\Users\<user>\AppData\Local\<X> redirected into
#   ...\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\<X>
# so anything that must touch the REAL %LOCALAPPDATA% has to run from a
# scheduler-launched process.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\ci\run-one-shot-task.ps1 `
#              -ScriptPath E:\...\something.ps1 [-TimeoutSeconds 900] [-TaskName Foo]
param(
    [Parameter(Mandatory = $true)][string]$ScriptPath,
    [string]$TaskName = 'MNB-OneShot',
    [int]$TimeoutSeconds = 900,
    [string]$ResultFile = ''
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $ScriptPath)) { throw "script not found: $ScriptPath" }

Write-Host "=== registering one-shot task ==="
Write-Host ("  script : {0}" -f $ScriptPath)

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $ScriptPath)
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1))
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 60)

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host ("  task registered: {0}" -f $TaskName)

Write-Host '=== running it ==='
Start-ScheduledTask -TaskName $TaskName

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$lastState = ''
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    $state = (Get-ScheduledTask -TaskName $TaskName).State
    if ("$state" -ne $lastState) {
        Write-Host ("  [{0}] state={1} lastResult={2}" -f (Get-Date -Format 'HH:mm:ss'), $state, $info.LastTaskResult)
        $lastState = "$state"
    }
    if ($state -ne 'Running' -and $info.LastRunTime -gt (Get-Date).AddMinutes(-30) -and $info.LastTaskResult -ne 267009) {
        Write-Host ("  finished: lastResult={0}" -f $info.LastTaskResult)
        break
    }
}

$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host ("  FINAL lastResult = {0} (0 = success, 1 = script error)" -f $info.LastTaskResult)

if ($ResultFile -and (Test-Path $ResultFile)) {
    Write-Host '=== result file ==='
    Get-Content $ResultFile | ForEach-Object { Write-Host ("  " + $_) }
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host '  task removed'
