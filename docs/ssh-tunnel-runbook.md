# SSH 反向隧道 Runbook — 生产链路 (agent.mnb-lab.cn)

> 2026-08-30 建立。本文档是生产可用性的关键依赖清单——**机器重启 / 隧道断开时按此处置**。

## 1. 链路总览

```
浏览器 → 云服务器 nginx:443 (agent.mnb-lab.cn)
            ├─ /            → 云端静态文件 (web/dist)
            ├─ /api/*       → 云 127.0.0.1:8000 ─┐
            ├─ /minio/*     → 云 127.0.0.1:9000 ─┤ SSH 反向隧道 (-R)
            └─ (紧急) 2222  → 云 127.0.0.1:2222 ─┘
                                        ↓
本机 Windows (60.205.93.8 的对端):
    ssh.exe -N -R 0.0.0.0:8000:127.0.0.1:8000
            -R 0.0.0.0:9000:127.0.0.1:9000
            -R 0.0.0.0:2222:127.0.0.1:22
            root@agent.mnb-lab.cn
                                        ↓
    127.0.0.1:8000 = app-1 容器        (主站 API)
    127.0.0.1:9000 = minio-1 容器      (头像/文件)
    22             = 本机 sshd         (紧急反向登录)
```

**三条 -R 缺一不可**: 断 8000 = 主站 API 全挂; 断 9000 = /minio 头像全 502; 断 2222 = 失去紧急通道。

## 2. 现役命令行 (精确)

```
C:\Windows\System32\OpenSSH\ssh.exe -N
  -i C:\Users\pc\.ssh\id_ed25519
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3   # 30s×3 探活, 死链 90s 自杀退出
  -o ExitOnForwardFailure=yes                          # 端口占用即失败(不半活)
  -o ConnectTimeout=10
  -R 0.0.0.0:8000:127.0.0.1:8000
  -R 0.0.0.0:9000:127.0.0.1:9000
  -R 0.0.0.0:2222:127.0.0.1:22
  root@agent.mnb-lab.cn
```

## 3. 守护机制 (2026-08-30 建)

- **计划任务** `MicroBubble-SSH-Tunnel-Guard`: 每 5 分钟跑
  `scripts/tunnel/guard-ssh-tunnel.bat` → `guard-ssh-tunnel.ps1`
- 判活: 存在命令行含 `agent.mnb-lab.cn` 且带 `-R 0.0.0.0:9000` 的 ssh.exe → no-op;
  否则按第 2 节原样拉起 (隐藏窗口)
- `-StartWhenAvailable`: 开机错过的触发点补跑 → 重启登录后 ≤5 分钟隧道自动恢复
- 日志: `E:\microbubble-agent\logs\tunnel-guard.log` (alive/started/ERROR)
- 卸载: `scripts\tunnel\uninstall-tunnel-guard.bat`

**边界**: 任务以当前用户 Interactive 令牌运行 → 机器开机但**未登录**时不跑; 登录后 ≤5 分钟内补上。需免登录自启则改用服务化 (nssm) — 当前未做。

## 4. 手动运维

```powershell
# 看隧道状态 (含 pid)
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" |
  Where-Object { $_.CommandLine -like '*agent.mnb-lab.cn*' } |
  Select-Object ProcessId, CommandLine

# 立即手动恢复 (不等待计划任务)
E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.bat

# 看守护日志
Get-Content E:\microbubble-agent\logs\tunnel-guard.log -Tail 20

# 真实恢复演练 (生产中断几秒, 慎用)
taskkill /F /PID <ssh_pid>; E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.bat
curl -o NUL -s -w "%{http_code}" https://agent.mnb-lab.cn/api/v1/health   # 期望 200
```

## 5. 事故记录

### 2026-08-30 /minio 头像全 502 (两层根因)
1. **类 20.140 翻版**: `docker compose up -d` 重建后 minio-1 **漏挂 docker 网络** →
   本机 nginx 解析 upstream `minio` 失败 → 崩溃重启循环。
   修复: `docker network connect --alias minio microbubble-agent_default microbubble-agent-minio-1`
2. **-R 9000 断线 (2 天未发现)**: 隧道指向本机 9000, 但 8/28 事故救急时 minio 只以
   19000 端口被救回, 9000 无人监听。修复: compose minio 补 `127.0.0.1:9000:9000`
   (commit c40457057)。
3. **教训**: 8/28 会话把生产救急接线 (app-revived + 19000 minio) 留在了一套"看起来
   像残留"的 compose 项目里, 8/30 清理时被当残留误删 — 清理前必须查容器用途
   (`docker inspect` mounts + 生产端口依赖), 不能只看名字和年龄。

### 2026-08-18 SSH 反向隧道链断 (历史, CLAUDE.md 20.139)
服务器 nginx 502 → 排查入口永远在本机; frp 方案已废弃, 现役隧道即本文档的 ssh.exe。

## 6. 快速健康检查 (一键)

```bash
# 云端三件套全 200 = 隧道 + app + minio 全活
for u in "https://agent.mnb-lab.cn/" "https://agent.mnb-lab.cn/api/v1/health" \
         "https://agent.mnb-lab.cn/minio/microbubble/avatars/4334d29c3b36432badce1ecff17b9705.jpg"; do
  curl -s -o /dev/null -w "%{http_code} $u\n" -m 15 "$u"
done
```
