# guard-ssh-tunnel.ps1 — SSH 反向隧道守护 (幂等, 计划任务每 5 分钟调一次)
#
# 隧道职责 (云端 nginx 依赖):
#   -R 0.0.0.0:8000 -> 本机 127.0.0.1:8000  (app-1, 主站 API)
#   -R 0.0.0.0:9000 -> 本机 127.0.0.1:9000  (minio-1, /minio 头像)
#   -R 0.0.0.0:2222 -> 本机 22              (紧急反向 SSH)
# 判活: 存在命令行含 agent.mnb-lab.cn 且带 -R 0.0.0.0:9000 的 ssh.exe
$ErrorActionPreference = 'Stop'
$LogFile = 'E:\microbubble-agent\logs\tunnel-guard.log'
$SshExe  = 'C:\Windows\System32\OpenSSH\ssh.exe'
$KeyFile = 'C:\Users\pc\.ssh\id_ed25519'

function Log($msg) {
    New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Add-Content -Path $LogFile -Encoding utf8
}

try {
    $alive = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" |
        Where-Object { $_.CommandLine -like '*agent.mnb-lab.cn*' -and
                       $_.CommandLine -like '*-R 0.0.0.0:9000*' }
    if ($alive) {
        Log "alive (pid=$($alive.ProcessId)) - no action"
        exit 0
    }
    $argline = (
        '-N',
        "-i $KeyFile",
        '-o StrictHostKeyChecking=accept-new',
        '-o ServerAliveInterval=30',
        '-o ServerAliveCountMax=3',
        '-o ExitOnForwardFailure=yes',
        '-o ConnectTimeout=10',
        '-R 0.0.0.0:8000:127.0.0.1:8000',
        '-R 0.0.0.0:9000:127.0.0.1:9000',
        '-R 0.0.0.0:2222:127.0.0.1:22',
        'root@agent.mnb-lab.cn'
    ) -join ' '
    Start-Process -FilePath $SshExe -ArgumentList $argline -WindowStyle Hidden
    Log "TUNNEL MISSING - started new ssh (hidden window)"
    exit 0
} catch {
    Log "ERROR: $_"
    exit 1
}
