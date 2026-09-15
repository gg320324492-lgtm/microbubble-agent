# guard-ssh-tunnel.ps1 — SSH 反向隧道守护 (幂等, 计划任务每 5 分钟调一次)
#
# 隧道职责 (云端 nginx 依赖):
#   -R 0.0.0.0:8000 -> 本机 127.0.0.1:8000  (app-1, 主站 API)
#   -R 0.0.0.0:9000 -> 本机 127.0.0.1:9000  (minio-1, /minio 头像)
#   -R 0.0.0.0:2222 -> 本机 22              (紧急反向 SSH)
# 判活: 存在命令行含 agent.mnb-lab.cn 且带 -R 的 ssh.exe（任何一条即可）
#
# 2026-09-15 P0 修复（隧道抖动事故）:
#   原判活要求命令行出现 `-R 0.0.0.0:9000`。但 `tunnel/start-ssh-tunnel.ps1`
#   自带 30s 看门狗也会拉隧道，两个监管者判活口径不一致时会"互不认账"：
#   本脚本判定没有隧道 → 再拉一条 → 远端 8000/9000/2222 已被占用 →
#   因 `-o ExitOnForwardFailure=yes`，新连接立刻退出 255 → 5 分钟后再来一次。
#   实测 2026-09-15 白天 `ssh-tunnel.log` 出现 115 次
#   `SSH exited immediately (code: 255)`，断续约 70 分钟；隧道断 == 全站不可用，
#   移动端就是 "Network Error"。
#   修法：判活口径放宽为"任何连到本服务器的 ssh -R 隧道"，让两个监管者收敛到
#   同一条隧道；同时把 ssh 的 stderr 落盘（原来 Start-Process 不重定向，
#   失败原因完全看不到）。
$ErrorActionPreference = 'Stop'
$LogFile = 'E:\microbubble-agent\logs\tunnel-guard.log'
$SshErrLog = 'E:\microbubble-agent\logs\tunnel-guard-ssh.err.log'
$SshExe  = 'C:\Windows\System32\OpenSSH\ssh.exe'
$KeyFile = 'C:\Users\pc\.ssh\id_ed25519'
$HostName = 'agent.mnb-lab.cn'

function Log($msg) {
    New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Add-Content -Path $LogFile -Encoding utf8
}

function Get-LiveTunnel {
    Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$HostName*" -and $_.CommandLine -like '*-R *' }
}

try {
    $alive = Get-LiveTunnel
    if ($alive) {
        $pids = (($alive | Select-Object -First 3).ProcessId) -join ','
        Log "alive (pid=$pids) - no action"
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
        "root@$HostName"
    ) -join ' '
    Start-Process -FilePath $SshExe -ArgumentList $argline -WindowStyle Hidden `
        -RedirectStandardError $SshErrLog
    Start-Sleep -Seconds 5
    # 启动后复核：立刻退出（端口被占/认证失败）必须留痕，而不是只记"started"
    $now = Get-LiveTunnel
    if ($now) {
        Log "TUNNEL MISSING - started new ssh (hidden window, pid=$(($now | Select-Object -First 1).ProcessId))"
    } else {
        $tail = ''
        try { $tail = (Get-Content $SshErrLog -Tail 3 -ErrorAction SilentlyContinue) -join ' | ' } catch {}
        Log "TUNNEL MISSING - ssh exited immediately. stderr: $tail"
    }
    exit 0
} catch {
    Log "ERROR: $_"
    exit 1
}
