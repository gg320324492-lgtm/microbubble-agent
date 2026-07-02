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
    if (Test-Path $PID_FILE) {
        $tunnelPid = Get-Content $PID_FILE -Raw | ForEach-Object { $_.Trim() }
        if ($tunnelPid -match '^\d+$') {
            $proc = Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue
            if ($proc.Name -eq "ssh") {
                Write-Log "Status: RUNNING (PID: $tunnelPid)"
                Write-Log "Ports: $($FORWARDS.ForEach({ "$($_.Name): $($_.RemotePort)" }) -join ', ')"
                return
            }
        }
    }
    Write-Log "Status: STOPPED"
}

# Watchdog: 持续监控 ssh.exe 状态, 死了就重启
# v2026-07-02 新增 - 解决 ssh 进程因网络抖动/服务端 idle timeout 退出后不自动恢复的问题
# 主入口调用后永不返回, 直到 PowerShell 进程被 SIGTERM (关机/手动 stop)
function Watch-SshTunnel {
    $WATCH_INTERVAL_SEC = 30
    Write-Log "Watchdog started (interval: ${WATCH_INTERVAL_SEC}s, Ctrl+C / Stop-SshTunnel to exit)"
    while ($true) {
        Start-Sleep -Seconds $WATCH_INTERVAL_SEC
        $alive = $false
        if (Test-Path $PID_FILE) {
            $curPid = Get-Content $PID_FILE -Raw | ForEach-Object { $_.Trim() }
            if ($curPid -match '^\d+$') {
                $cur = Get-Process -Id $curPid -ErrorAction SilentlyContinue
                if ($cur -and $cur.Name -eq "ssh") { $alive = $true }
            }
        }
        if (-not $alive) {
            Write-Log "WARN: tunnel not running, restarting..."
            $ok = Start-SshTunnel
            if (-not $ok) {
                Write-Log "ERROR: restart failed, will retry next cycle"
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
