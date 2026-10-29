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
#
# 2026-10-29 新增: 数据通路探活 + 定点自愈（原守卫只判「进程在」⇒ 隧道 alive 但数据不通）
#   事故: 14:23 起 Docker 的宿主端口转发器 (com.docker.backend) 卡死 ——
#         容器内 MinIO 正常（容器网络直连 /minio/health/live = 200）、app 走容器
#         网络也正常，但宿主 127.0.0.1:9000 连接被接受后直接关闭 ⇒ 云端 nginx 报
#         "upstream prematurely closed connection while reading response header"
#         ⇒ 全站头像 502。隧道守卫全程日志 "alive - no action"（它只看 ssh 进程
#         在不在）⇒ 断了 6.5 小时才被发现。
#         类 20.220: 状态字段(进程在) ≠ 副作用(数据真能过去)。
#   修法: 两级探针 + 定点自愈
#     L1 本机   http://127.0.0.1:9000/minio/health/live
#         不通 ⇒ Docker 端口转发器卡死 ⇒ 重启 minio 容器重建转发（实测有效；
#         数据在 volume 里，重启不丢）。
#     L2 端到端 https://agent.mnb-lab.cn/minio/minio/health/live
#         （云端 nginx → SSH 反向隧道 → 本机 9000 → 容器）
#         L1 通而 L2 不通 ⇒ 隧道/云端侧 ⇒ 只记日志，**不自动重启隧道**
#         （2026-09-15 教训：两个监管者判活口径不一致会互相不认账）。
#   ⚠ 探针必须带 --noproxy '*': 本机 HTTP_PROXY=127.0.0.1:7897 (Clash) 会劫持
#     对外请求；NO_PROXY 只含 localhost,127.0.0.1 ⇒ 端到端那条探针会被代理。
$ErrorActionPreference = 'Stop'
$LogFile = 'E:\microbubble-agent\logs\tunnel-guard.log'
$SshErrLog = 'E:\microbubble-agent\logs\tunnel-guard-ssh.err.log'
$SshExe  = 'C:\Windows\System32\OpenSSH\ssh.exe'
$KeyFile = 'C:\Users\pc\.ssh\id_ed25519'
$HostName = 'agent.mnb-lab.cn'

# 数据通路探针 (2026-10-29)
$CurlExe          = 'C:\Windows\System32\curl.exe'
$MinioContainer   = 'microbubble-agent-minio-1'
$AppContainer     = 'microbubble-agent-app-1'
# 每条通路两探针:
#   Local = 宿主 -> 容器发布端口 (Docker 端口转发器这一段)
#   E2E   = 云端 nginx -> SSH 反向隧道 -> 宿主 -> 容器 (整条真实链路)
# app 的影响面比 minio 大 (全站 API), 同样纳入守护。
$DataPathTargets = @(
    @{ Name = 'minio'; Container = $MinioContainer;
       Local = 'http://127.0.0.1:9000/minio/health/live';
       E2E   = 'https://agent.mnb-lab.cn/minio/minio/health/live' },
    @{ Name = 'app';   Container = $AppContainer;
       Local = 'http://127.0.0.1:8000/health';
       E2E   = 'https://agent.mnb-lab.cn/health' }
)
# 容器启动不足这个秒数时不重启 (它可能只是还在启动中) —— 防重启风暴
$MinAgeBeforeRestartSec = 120

function Log($msg) {
    New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Add-Content -Path $LogFile -Encoding utf8
}

function Get-LiveTunnel {
    Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$HostName*" -and $_.CommandLine -like '*-R *' }
}

# HTTP 200 探针。--noproxy '*' 是必须的: 本机设了 HTTP_PROXY (Clash),
# 否则对 agent.mnb-lab.cn 的探针会被代理接管, 判据就变成"代理通不通"而不是
# "隧道通不通"。返回 $true/$false, 不抛异常。
function Test-Http200($url, $timeoutSec) {
    try {
        if (-not (Test-Path -LiteralPath $CurlExe)) { return $false }
        $out = & $CurlExe -sS -o NUL -w '%{http_code}' --max-time $timeoutSec --noproxy '*' $url 2>$null
        $rc  = $LASTEXITCODE
        $code = ($out | Select-Object -Last 1)
        return ($rc -eq 0 -and $code -eq '200')
    } catch {
        return $false
    }
}

# 容器已启动多少秒。取不到时返回 -1 (调用方按"不阻止重启"处理)。
function Get-ContainerUptimeSec($container) {
    try {
        $raw = docker inspect -f '{{.State.StartedAt}}' $container 2>$null | Select-Object -Last 1
        if (-not $raw) { return -1 }
        # StartedAt 形如 2026-10-29T21:12:34.123456789Z —— .NET 解析不了 9 位小数,
        # 截到毫秒再解析 (否则 Parse 直接抛, 每次探针都走异常分支)。
        $s = ($raw.Trim() -replace '\.(\d{3})\d*', '.$1')
        $started = [datetime]::Parse($s, [cultureinfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AdjustToUniversal -bor [System.Globalization.DateTimeStyles]::AssumeUniversal)
        return [int]((Get-Date).ToUniversalTime() - $started).TotalSeconds
    } catch {
        return -1
    }
}

# 单条数据通路的探活 + 定点自愈。返回 $true 表示这条通路本地侧健康。
function Test-DataPath($target) {
    $name = $target.Name
    if (Test-Http200 $target.Local 8) {
        # 本地侧正常; 再验端到端 (云端 nginx -> 隧道 -> 宿主 -> 容器)
        if (-not (Test-Http200 $target.E2E 15)) {
            Log "WARNING - [$name] local OK but end-to-end probe failed ($($target.E2E)) => 隧道/云端侧问题; 不自动重启隧道 (2026-09-15 教训), 需人工判断"
        }
        return $true
    }
    # 本地侧不通 => Docker 宿主端口转发器卡死
    $up = Get-ContainerUptimeSec $target.Container
    if ($up -ge 0 -and $up -lt $MinAgeBeforeRestartSec) {
        Log "DATA PATH BROKEN - [$name] local probe failed but container started ${up}s ago (< ${MinAgeBeforeRestartSec}s) => 可能仍在启动中, 本轮不重启"
        return $false
    }
    Log "DATA PATH BROKEN - [$name] local probe failed ($($target.Local)) => docker host port forward is wedged; restarting $($target.Container) to rebuild it"
    try {
        docker restart $target.Container 2>&1 | Out-Null
        Start-Sleep -Seconds 8
    } catch {
        Log "ERROR: [$name] container restart threw: $_"
    }
    if (Test-Http200 $target.Local 10) {
        Log "RECOVERED - [$name] $($target.Container) restarted, local probe OK"
        return $true
    }
    Log "STILL BROKEN - [$name] local probe still failing after container restart (需人工介入: 查 Docker backend / com.docker.backend)"
    return $false
}

try {
    $alive = Get-LiveTunnel
    if ($alive) {
        $pids = (($alive | Select-Object -First 3).ProcessId) -join ','
        Log "alive (pid=$pids)"

        # --- 数据通路探活: 隧道"在"不等于数据"能过去" ---
        foreach ($t in $DataPathTargets) {
            Test-DataPath $t | Out-Null
        }
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
