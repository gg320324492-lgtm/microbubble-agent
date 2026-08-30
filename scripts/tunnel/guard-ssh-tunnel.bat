@echo off
rem SSH 反向隧道守护入口 — 计划任务 MicroBubble-SSH-Tunnel-Guard 每 5 分钟调用
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.ps1"
