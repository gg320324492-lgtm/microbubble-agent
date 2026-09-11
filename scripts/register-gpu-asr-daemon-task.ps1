# Register boot/logon auto-start for GPU ASR daemons (8005 + 8006).
# Idempotent: -Force re-registers. Class 20.216 discipline: after register,
# read back Actions[0].Execute and verify length + no control chars.
$ErrorActionPreference = 'Stop'
$bat = 'E:\microbubble-agent\scripts\start_gpu_asr_daemon.bat'

$action = New-ScheduledTaskAction -Execute $bat -WorkingDirectory 'E:\microbubble-agent'
$trigger1 = New-ScheduledTaskTrigger -AtStartup
$trigger2 = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName 'MicroBubble-GPU-ASR-Daemon' -Action $action `
    -Trigger @($trigger1, $trigger2) -Settings $settings -Force `
    -Description 'VibeVoice GPU ASR daemons (8005 meeting 7B + 8006 streaming), launched at boot/logon; app-side health probe + SenseVoice auto-fallback if down' | Out-Null

$t = Get-ScheduledTask -TaskName 'MicroBubble-GPU-ASR-Daemon'
$exe = $t.Actions[0].Execute
$hasControl = $exe -match "[\x00-\x1F]"
Write-Output ("registered task: " + $t.TaskName)
Write-Output ("action path    : [" + $exe + "] len=" + $exe.Length)
Write-Output ("expected path  : [" + $bat + "] len=" + $bat.Length)
Write-Output ("exact match    : " + ($exe -eq $bat))
Write-Output ("hasControlChar : " + $hasControl)
