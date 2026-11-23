<#
.SYNOPSIS
FRP 客户端判活守护: 确保 frpc.exe 常驻, 异常退出自动重启。
被 scripts/run-hidden.vbs 或计划任务调用, 每 5 分钟一轮。

依赖 (本机提供, 不入库): tunnel/frp/frpc.exe + tunnel/frp/frpc.toml
(配置含鉴权 token, 禁止提交到 git; 换机需自行放置这两个文件)。
计划任务: MicroBubble-FRP-Guard, 每 5 分钟触发本脚本。
#>
$ErrorActionPreference = 'Stop'
$repo = 'E:\microbubble-agent'
$exe  = Join-Path $repo 'tunnel\frp\frpc.exe'
$cfg  = Join-Path $repo 'tunnel\frp\frpc.toml'
$log  = Join-Path $repo 'logs\frp-guard.log'

function Write-Log($msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $log -Value $line -Encoding UTF8
}

$running = @(Get-CimInstance Win32_Process -Filter "Name = 'frpc.exe'" |
    Where-Object { $_.CommandLine -match [regex]::Escape($exe) })

if ($running.Count -gt 0) {
    Write-Log ("alive (pid={0}) - no action" -f ($running[0].ProcessId))
    exit 0
}

try {
    $p = Start-Process -FilePath $exe -ArgumentList @('-c', $cfg) `
        -WorkingDirectory $repo -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
    $p.Refresh()
    if ($p.HasExited) { throw ("frpc exited immediately, code={0}" -f $p.ExitCode) }
    Write-Log ("restarted frpc (pid={0})" -f $p.Id)
} catch {
    Write-Log ("ERROR: {0}" -f $_.Exception.Message)
    exit 1
}
