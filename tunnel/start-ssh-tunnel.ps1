# SSH 反向隧道启动脚本 - 替代 frpc
# 使用 Windows 内置 OpenSSH（微软签名，不受 WDAC 阻止）

param(
    [string]$Action = "start"
)

$SSH_USER = "root"
$SSH_HOST = "agent.mnb-lab.cn"
$SSH_KEY = "$env:USERPROFILE\.ssh\id_ed25519"
$LOG_FILE = Join-Path $PSScriptRoot "ssh-tunnel.log"
$PID_FILE = Join-Path $PSScriptRoot "ssh-tunnel.pid"
$SSH = "C:\Windows\System32\OpenSSH\ssh.exe"

$FORWARDS = @(
    @{RemotePort=8000; LocalAddr="127.0.0.1"; LocalPort=8000; Name="app"},
    @{RemotePort=9000; LocalAddr="127.0.0.1"; LocalPort=9000; Name="minio"},
    @{RemotePort=2222; LocalAddr="127.0.0.1"; LocalPort=22; Name="ssh"}
)

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp $Message" | Out-File -FilePath $LOG_FILE -Append -Encoding UTF8
    Write-Host "$timestamp $Message"
}

function Build-SshArgs {
    $sshArgs = @()
    $sshArgs += "-N"
    $sshArgs += "-i", $SSH_KEY
    $sshArgs += "-o", "StrictHostKeyChecking=accept-new"
    $sshArgs += "-o", "ServerAliveInterval=30"
    $sshArgs += "-o", "ServerAliveCountMax=3"
    $sshArgs += "-o", "ExitOnForwardFailure=yes"
    $sshArgs += "-o", "ConnectTimeout=10"
    foreach ($fw in $FORWARDS) {
        $sshArgs += "-R"
        $sshArgs += "0.0.0.0:$($fw.RemotePort):$($fw.LocalAddr):$($fw.LocalPort)"
    }
    $sshArgs += "${SSH_USER}@${SSH_HOST}"
    return $sshArgs
}

function Start-SshTunnel {
    if (-not (Test-Path $SSH_KEY)) {
        Write-Log "ERROR: SSH key not found at $SSH_KEY"
        return $false
    }

    $existingPid = $null
    if (Test-Path $PID_FILE) {
        $existingPid = Get-Content $PID_FILE -Raw | ForEach-Object { $_.Trim() }
    }
    if ($existingPid -and $existingPid -match '^\d+$') {
        $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existing -and $existing.Name -eq "ssh") {
            Write-Log "SSH tunnel already running (PID: $existingPid)"
            return $true
        }
    }

    $sshArgs = Build-SshArgs
    $fwNames = $FORWARDS | ForEach-Object { "$($_.Name): port $($_.RemotePort)" }
    Write-Log "Starting SSH tunnel to ${SSH_USER}@${SSH_HOST}"
    Write-Log "Forwards: $($fwNames -join ', ')"

    try {
        $proc = Start-Process -FilePath $SSH -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
        Start-Sleep -Seconds 4

        if ($proc.HasExited) {
            Write-Log "ERROR: SSH exited immediately (code: $($proc.ExitCode))"
            return $false
        }

        $proc.Id | Out-File -FilePath $PID_FILE -Encoding UTF8 -Force
        Write-Log "SSH tunnel started (PID: $($proc.Id))"

        Start-Sleep -Seconds 3
        $testCmd = "ss -tlnp | grep -c ':$($FORWARDS[0].RemotePort)' 2>/dev/null || echo 0"
        $result = & $SSH -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new -i $SSH_KEY root@$SSH_HOST $testCmd
        $result = $result.Trim()
        if ($result -match '^[1-9]') {
            Write-Log "Port $($FORWARDS[0].RemotePort) verified on server"
        } else {
            Write-Log "WARNING: port verification returned: $result"
        }

        return $true
    } catch {
        Write-Log "ERROR: Failed to start tunnel: $_"
        return $false
    }
}

function Stop-SshTunnel {
    Write-Log "Stopping SSH tunnel..."
    if (Test-Path $PID_FILE) {
        $tunnelPid = Get-Content $PID_FILE -Raw | ForEach-Object { $_.Trim() }
        if ($tunnelPid -match '^\d+$') {
            $proc = Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue
            if ($proc.Name -eq "ssh") {
                $proc.Kill()
                Write-Log "Killed PID $tunnelPid"
            }
        }
        Remove-Item $PID_FILE -Force -ErrorAction SilentlyContinue
    }
    Write-Log "SSH tunnel stopped"
}

function Get-TunnelStatus {
    $tunnelPid = Get-LiveTunnelPid
    if ($tunnelPid) {
        Write-Log "Status: RUNNING (PID: $tunnelPid)"
        Write-Log "Ports: $($FORWARDS.ForEach({ "$($_.Name): $($_.RemotePort)" }) -join ', ')"
        return
    }
    Write-Log "Status: STOPPED"
}

# 2026-09-15 P0 修复（隧道抖动事故）:
# 本脚本的看门狗原来只认 PID_FILE 里的 pid。但 `scripts/tunnel/guard-ssh-tunnel.ps1`
# （计划任务每 5 分钟）也会按自己的判活逻辑拉起一条**独立**的 ssh 隧道，它不写本
# 脚本的 PID_FILE。于是出现两个监管者互不认账的局面：
#   看门狗认为"隧道已死" → 再拉一条 → 远端 8000/9000/2222 已被上一条占着 →
#   `-o ExitOnForwardFailure=yes` 让新连接立刻退出 255 → 看门狗 30s 后再来一次……
# 实测 2026-09-15 白天 `ssh-tunnel.log` 出现 115 次 `SSH exited immediately (code: 255)`，
# 持续约 70 分钟；隧道断时移动端就是 "Network Error"。
# 修法：判活时**兜底认领**进程表里任何一条连到本服务器的 ssh -R 隧道（并回写 PID_FILE
# 自愈），保证两个监管者最终收敛到同一条隧道，不再互相踩端口。
function Get-LiveTunnelPid {
    if (Test-Path $PID_FILE) {
        $tunnelPid = Get-Content $PID_FILE -Raw | ForEach-Object { $_.Trim() }
        if ($tunnelPid -match '^\d+$') {
            $proc = Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue
            if ($proc -and $proc.Name -eq "ssh") { return $tunnelPid }
        }
    }
    # 兜底：认领外部（guard 脚本）启动的隧道
    try {
        $ext = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$SSH_HOST*" -and $_.CommandLine -like '*-R *' } |
            Select-Object -First 1
        if ($ext) {
            $ext.Id | Out-File -FilePath $PID_FILE -Encoding ASCII -Force
            Write-Log "ADOPTED external tunnel (PID: $($ext.Id)) — PID_FILE 已自愈"
            return $ext.Id
        }
    } catch {
        Write-Log "WARN: adopt external tunnel failed: $_"
    }
    return $null
}

# Watchdog: 持续监控 ssh.exe 状态, 死了就重启
# v2026-07-02 新增 - 解决 ssh 进程因网络抖动/服务端 idle timeout 退出后不自动恢复的问题
# v2026-09-15 修复 - 认领外部隧道 + 连续失败指数退避（避免端口争抢活锁）
# 主入口调用后永不返回, 直到 PowerShell 进程被 SIGTERM (关机/手动 stop)
function Watch-SshTunnel {
    $BASE_INTERVAL_SEC = 30
    $MAX_INTERVAL_SEC = 300
    $interval = $BASE_INTERVAL_SEC
    $consecutiveFailures = 0
    Write-Log "Watchdog started (interval: ${BASE_INTERVAL_SEC}s, 失败退避上限 ${MAX_INTERVAL_SEC}s)"
    while ($true) {
        Start-Sleep -Seconds $interval
        $livePid = Get-LiveTunnelPid
        if ($livePid) {
            if ($consecutiveFailures -gt 0) {
                Write-Log "隧道恢复 (PID: $livePid)，退避重置"
            }
            $consecutiveFailures = 0
            $interval = $BASE_INTERVAL_SEC
            continue
        }
        Write-Log "WARN: tunnel not running, restarting... (连续失败 $consecutiveFailures 次)"
        $ok = Start-SshTunnel
        if ($ok) {
            $consecutiveFailures = 0
            $interval = $BASE_INTERVAL_SEC
        } else {
            $consecutiveFailures++
            # 指数退避：端口争抢时越急着重试，服务端越晚释放，会形成活锁
            $interval = [Math]::Min($BASE_INTERVAL_SEC * [Math]::Pow(2, [Math]::Min($consecutiveFailures, 4)), $MAX_INTERVAL_SEC)
            Write-Log "ERROR: restart failed (连续 $consecutiveFailures 次)，下次 ${interval}s 后重试"
        }
    }
    }
}

# Main
switch ($Action) {
    "stop" { Stop-SshTunnel }
    "status" { Get-TunnelStatus }
    default {
        if (Test-Path $PID_FILE) {
            $oldPid = Get-Content $PID_FILE -Raw | ForEach-Object { $_.Trim() }
            if ($oldPid -match '^\d+$') {
                $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
                if ($old.Name -eq "ssh") {
                    Write-Log "Stopping old tunnel (PID: $oldPid)..."
                    Stop-SshTunnel
                    Start-Sleep -Seconds 2
                }
            }
        }
        $ok = Start-SshTunnel
        if (-not $ok) { exit 1 }
        Write-Log "SSH tunnel started successfully, entering watchdog (Ctrl+C to stop)"
        Watch-SshTunnel
    }
}
