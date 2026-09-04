@echo off
rem 注册隧道守护计划任务 (每 5 分钟; StartWhenAvailable=开机错过补跑; 当前用户免管理员)
rem 2026-09-04 修复: 原文件里 'scripts\tunnel' 曾被 heredoc 写坏成 TAB (类 20.216), 重装即复发
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a = New-ScheduledTaskAction -Execute 'E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.bat'; $t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650); $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 4); Register-ScheduledTask -TaskName 'MicroBubble-SSH-Tunnel-Guard' -Action $a -Trigger $t -Settings $s -Description 'SSH reverse tunnel guardian (cloud 8000/9000/2222 -> local app/minio/sshd)' -Force"
if %errorlevel%==0 (echo [tunnel-guard] scheduled task registered) else (echo [tunnel-guard] register FAILED)
