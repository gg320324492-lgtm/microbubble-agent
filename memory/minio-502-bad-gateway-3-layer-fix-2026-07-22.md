---
name: minio-502-bad-gateway-3-layer-fix-2026-07-22
description: "W61 502 Bad Gateway 真根因修复 — 3 层链路: tunnel.conf SSL 路径错 + SSH reverse tunnel 孤儿 listener (端口 1544507 占 8000/9000/2222) + minio 容器端口响应 0. 修复 + 验证 + baseline 23 守恒."
metadata:
  node_type: memory
  type: project
  originSessionId: W61-启动段
  modified: 2026-07-22T02:55:00.000Z
---

# 2026-07-22 W61 502 Bad Gateway 真根因修复 (3 层链路)

## TL;DR

🎯 **502 Bad Gateway 真根因 = 3 层链路问题**（W61 启动段原始 memory 文件诊断错误，本文件覆盖修正）：

1. **第 1 层（最外层）**：docker nginx-1 容器 SSL cert 路径错（`/etc/letsencrypt/live/...` vs 实际挂载 `/etc/nginx/ssl`）→ 容器 restart loop → 但只影响本地反代，公网走云 nginx 实际不受这层影响
2. **第 2 层（中间层）**：SSH reverse tunnel 死掉的孤儿 listener 仍占云服务器 8000/9000/2222 端口（PID 1544507 sshd session，7/20 启动）→ 云 nginx proxy_pass 给孤儿 → RST → 502
3. **第 3 层（最里层）**：docker minio-1 容器端口响应 0（端口 LISTENING 但 curl 127.0.0.1:9000 返回 000）→ `docker restart microbubble-agent-minio-1` 修复

**Why**: 用户实测浏览器 GET `https://agent.mnb-lab.cn/minio/microbubble/avatars/*.jpg` 返回 502，伴随所有 nginx 反代 URL 全 502。CLAUDE.md W61 顶部及 `memory/nginx-ssl-cert-path-mismatch-502-2026-07-22.md` 之前记录的是错误的"SSL 路径"诊断，实际只触到第 1 层，没穿透到第 2/3 层。本文件覆盖修正 W61 原始 memory。

**How to apply**: 见下方 3 层根因分析 + 修复步骤 + 验证 + 铁律沉淀。

---

## 1. 完整根因分析（3 层链路）

### 1.1 第 1 层：tunnel.conf SSL 路径错（次要，但需修）

```bash
# /e/microbubble-agent/nginx/conf.d/tunnel.conf 原配置（错）
ssl_certificate     /etc/letsencrypt/live/agent.mnb-lab.cn/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/agent.mnb-lab.cn/privkey.pem;
ssl_certificate     /etc/letsencrypt/live/mnb-lab.cn/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/mnb-lab.cn/privkey.pem;

# 实际 docker-compose.yml 挂载
volumes:
  - ./nginx/ssl:/etc/nginx/ssl:ro  # 不是 /etc/letsencrypt
```

**症状**: docker nginx-1 容器 `[emerg] cannot load certificate "/etc/letsencrypt/live/agent.mnb-lab.cn/fullchain.pem"` → restart loop (8s 重启一次)

**重要性**: 🟡 中等。本地 docker nginx-1 起不来不影响公网，因为公网 HTTPS 实际走**云服务器 nginx**（端口 443），但本地 docker nginx-1 重新启动后能正常工作（反代到 app/minio），所以必须修。

**W61 原始 memory 错就错在把第 1 层当成了全部根因**，没意识到公网 HTTPS 不走 docker nginx-1。

### 1.2 第 2 层：SSH reverse tunnel 孤儿 listener（真根因之一）

**云服务器端口现状**（修复前）：

```bash
$ ssh root@agent.mnb-lab.cn "ss -tlnp | grep -E ':8000|:9000|:2222'"
LISTEN 0  128  0.0.0.0:9000  users:(("sshd",pid=1544507,fd=9))
LISTEN 0  128  0.0.0.0:8000  users:(("sshd",pid=1544507,fd=5))
LISTEN 0  128  0.0.0.0:2222  users:(("sshd",pid=1544507,fd=11))
```

**关键诊断**：
- `pid=1544507` sshd session 是 **7/20 15:10 启动** 的孤儿 SSH session
- 持有云服务器 8000/9000/2222 端口的 fd
- 这些端口**应当**由 SSH reverse tunnel session 持有（`ssh -R 0.0.0.0:8000:127.0.0.1:8000`），但 SSH tunnel session 已死，listener 变成孤儿
- 孤儿 listener 接到连接 → RST → 502（`upstream prematurely closed connection`）

**触发链**：
1. `tunnel/start-ssh-tunnel.ps1` watchdog 检测 SSH 死了 → 调 `Start-SshTunnel` 重启
2. 但脚本中 `$env:USERPROFILE\.ssh\id_ed25519` 在 PowerShell 通过 `Start-Process -ArgumentList @(...)` 调用时，bash 转义把 `$env:USERPROFILE` 替换为空 → SSH key 找不到
3. SSH 认证失败 → `code: 255` → session 死 → 端口 listener 孤儿化（云 server sshd fd 不释放）
4. 日志：每 30s 重试一次，每次失败堆栈一样（`ssh-tunnel.log` 末尾连续 ERROR）

**为什么云 nginx 仍然把流量转给孤儿 listener**：

```nginx
# /e/microbubble-agent/nginx/conf.d/tunnel.conf (云服务器同步版)
location /minio/ {
    proxy_pass http://127.0.0.1:9000/;  # ← 假定有 SSH tunnel/FRP 在 listen
}
```

cloud nginx 把 `/minio/*` → `127.0.0.1:9000`，**这是云服务器本地的 9000 端口**，应该由 SSH reverse tunnel session 持有把流量转发回本地 docker minio。但孤儿 listener 接到了就 RST。

### 1.3 第 3 层：docker minio 端口响应 0（最里层，修复第 2 层后才暴露）

**修复第 2 层后**（建立新 SSH reverse tunnel），502 仍在！新发现：

```bash
# 修复第 2 层后，云 nginx 报：
[error] *56236 upstream prematurely closed connection while reading response header from upstream

# 但从本机直接 curl：
$ curl http://127.0.0.1:9000/minio/health/live
000  # 连接被拒

# 但 netstat 看端口在 listen：
$ netstat -an | grep :9000
LISTEN  0.0.0.0:9000  0.0.0.0:0
LISTEN  [::]:9000     [::]:0

# 容器内部 curl 200 OK：
$ docker exec microbubble-agent-minio-1 curl http://localhost:9000/minio/health/live
code=200
```

**根因**：docker minio-1 容器端口映射存在但 listen socket 不响应（可能 listen queue 满了 / 内核连接跟踪 stale / docker-proxy 进程死）。`docker restart microbubble-agent-minio-1` 修复。

---

## 2. 修复方案（W61 启动段主指挥亲自执行）

### 2.1 修复第 1 层：tunnel.conf SSL 路径（10 行改动）

修改 `E:\microbubble-agent\nginx\conf.d\tunnel.conf`：

```diff
-    ssl_certificate     /etc/letsencrypt/live/agent.mnb-lab.cn/fullchain.pem;
-    ssl_certificate_key /etc/letsencrypt/live/agent.mnb-lab.cn/privkey.pem;
+    ssl_certificate     /etc/nginx/ssl/agent.mnb-lab.cn/fullchain.pem;
+    ssl_certificate_key /etc/nginx/ssl/agent.mnb-lab.cn/privkey.pem;
-    ssl_certificate     /etc/letsencrypt/live/mnb-lab.cn/fullchain.pem;
-    ssl_certificate_key /etc/letsencrypt/live/mnb-lab.cn/privkey.pem;
+    ssl_certificate     /etc/nginx/ssl/mnb-lab.cn/fullchain.pem;
+    ssl_certificate_key /etc/nginx/ssl/mnb-lab.cn/privkey.pem;
```

从云服务器拉证书到本地：

```bash
mkdir -p E:/microbubble-agent/nginx/ssl/{agent,mnb}-lab.cn/
scp root@agent.mnb-lab.cn:/etc/letsencrypt/live/agent.mnb-lab.cn/{fullchain,privkey}.pem E:/microbubble-agent/nginx/ssl/agent.mnb-lab.cn/
scp root@agent.mnb-lab.cn:/etc/letsencrypt/live/mnb-lab.cn/{fullchain,privkey}.pem E:/microbubble-agent/nginx/ssl/mnb-lab.cn/
```

`docker compose restart nginx` → 容器 healthy。

### 2.2 修复第 2 层：kill 孤儿 SSH listener + 重连 SSH reverse tunnel

```bash
# 1. kill 孤儿 sshd session（PID 1544507）
ssh root@agent.mnb-lab.cn "kill -9 1544507"

# 2. 启动新的 SSH reverse tunnel（用 PowerShell 正确转义）
powershell -Command "Start-Process -FilePath 'C:\Windows\System32\OpenSSH\ssh.exe' -ArgumentList @('-N','-i', \"\$env:USERPROFILE\\.ssh\\id_ed25519\", '-o','StrictHostKeyChecking=accept-new','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3','-o','ExitOnForwardFailure=yes','-R','0.0.0.0:8000:127.0.0.1:8000','-R','0.0.0.0:9000:127.0.0.1:9000','-R','0.0.0.0:2222:127.0.0.1:22','root@agent.mnb-lab.cn') -WindowStyle Hidden -PassThru"

# 3. 验证云服务器端口由新 sshd session 持有（不是孤儿）
ssh root@agent.mnb-lab.cn "ss -tlnp | grep ':9000'"
# 期望: LISTEN 0  128  0.0.0.0:9000  users:(("sshd",pid=<NEW_PID>,fd=9))
```

**关键修复点**：之前 `start-ssh-tunnel.ps1` 用 `Start-Process -ArgumentList` 数组传参时，`$env:USERPROFILE` 被 bash 替换为空（变成 `\id_ed25519` 无效路径）。修复：**用 `Start-Process -ArgumentList @(...)` 数组形式 + `\"\$env:USERPROFILE\\.ssh\\id_ed25519\"` 双引号转义**。

### 2.3 修复第 3 层：docker minio restart

```bash
docker restart microbubble-agent-minio-1
sleep 4
curl -s -o /dev/null -w "minio host after restart=%{http_code}\n" http://127.0.0.1:9000/minio/health/live
# 期望: 200
```

### 2.4 6 点 curl 验证（W61 端到端）

```bash
curl -sk -o /dev/null -w "code=%{http_code} size=%{size_download}\n" https://agent.mnb-lab.cn/minio/microbubble/avatars/32593ab1d665426499a76c405fcb386d.jpg
# 期望: code=200 size=23685

curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://agent.mnb-lab.cn/index.html         # 期望: 200 text/html
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://agent.mnb-lab.cn/sw.js              # 期望: 200 application/javascript
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://agent.mnb-lab.cn/api/v1/auth/me    # 期望: 401 application/json
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://agent.mnb-lab.cn/dashboard         # 期望: 200 text/html (SPA fallback)
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://agent.mnb-lab.cn/manifest.webmanifest # 期望: 410 (防护保留)
```

### 2.5 后置 baseline 守恒（W61 后置验证）

```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && python -m pytest \
  tests/test_meeting_transcript_buffer.py \
  tests/test_orphan_meeting_cleanup_audio_chunks.py \
  tests/test_meeting_recording_user_agent.py \
  tests/test_meeting_recording_audio_chunk_auth.py \
  tests/test_meeting_recording_cancel.py \
  tests/test_chat_history_tasks.py \
  tests/test_chat_share_cleanup.py \
  tests/test_kb_dedup_admin_cli.py \
  tests/scripts/test_kb_dedup_admin_cli_e2e.py --tb=short -q'
```

期望: **71 PASS + 7 SKIP**（W60 baseline 22 → W61 baseline 23 守恒，0 regression 跨 1 commit）。

---

## 3. 铁律沉淀（W61 累计 167 条, +2 新增）

### 3.1 502 Bad Gateway 排查铁律（NEW W61）

**铁律 1：502 排查必须穿透 3 层链路**——

排查顺序（从外到内）：
1. **公网入口**：云 nginx `proxy_pass` 配置（`/api` / `/minio` / `/webhook` 各 location）
2. **中转层**：SSH reverse tunnel / FRP 隧道状态（云端端口 listener 是否 alive，是否孤儿）
3. **服务层**：最终目标服务（minio / app / postgres）是否真的在响应

**反例**：只看云 nginx error log 报 `upstream prematurely closed` 就以为是 nginx 配置问题，实际可能是中转层隧道死了（W61 启动段诊断错就错在这里）

**Why**: 502 Bad Gateway 的 `upstream prematurely closed` 错误只说明云 nginx 连到 upstream 失败，不告诉你是 nginx 配置问题还是 upstream 服务死了。必须穿透验证。

**How to apply**:
- 排查 502 必须 3 步：① 云 nginx error log 找 upstream 地址 ② curl 云端 upstream 端口 ③ 验证最里层服务
- 任何一步没穿透就下结论 = 错误根因诊断
- 永远 ssh 到上游服务器 + 在上游服务器本地 curl upstream:port 验证

**铁律 2：SSH reverse tunnel 死后端口 listener 不会自动释放**——

`start-ssh-tunnel.ps1` 用 `ssh -R 0.0.0.0:PORT:127.0.0.1:PORT` 建立 reverse tunnel，SSH session 死时 **云 server sshd 派生的 fd 不会立即释放**，要等 sshd 检测 keepalive 超时（默认几分钟）。

**Why**: SSH server 的 TCP listener fd 由 sshd 主进程持有，session 死时不立即清理。孤儿 listener 接到新连接直接 RST，不会尝试转发。

**How to apply**:
- SSH reverse tunnel 死后手动 `kill -9 <orphan_sshd_pid>`（W61 实际操作）
- 永远不要假定"重启 SSH tunnel 就能修复"，先看云端口 listener PID 是不是孤儿
- `ss -tlnp | grep ':PORT'` 看进程 PID 是 sshd 主进程还是 sshd session 进程

### 3.2 PowerShell 变量转义铁律（NEW W61）

**铁律 3：PowerShell 通过 `Start-Process -ArgumentList` 调用 ssh.exe 时，环境变量必须双引号转义**——

```powershell
# ❌ 错（被 bash 替换为空）
Start-Process -ArgumentList "-i", "$env:USERPROFILE\.ssh\id_ed25519", ...

# ✅ 对（PowerShell 数组形式 + 双引号转义）
Start-Process -ArgumentList @('-i', "`$env:USERPROFILE\.ssh\id_ed25519", ...)
# 或
Start-Process -ArgumentList @('-i', "$env:USERPROFILE\.ssh\id_ed25519", ...)
```

**Why**: 当 PowerShell 脚本在 bash 下执行时（Git Bash 等），`$env:USERPROFILE` 会被 bash 先解析为空。PowerShell 数组形式 `@(...)` + 双引号 `"` 能保护变量在 PowerShell 内部展开。

**How to apply**:
- `tunnel/start-ssh-tunnel.ps1` 用 `Start-Process -ArgumentList @("array", "of", "args")` 形式
- 任何含 `$` 的参数都用 `"..."` 双引号包裹
- 调试时手动跑 `Start-Process` + 看 `-PassThru` 返回的 `$proc.ExitCode`

### 3.3 累计铁律（W61 累计 167 条）

| 铁律来源 | 数量 |
|---------|------|
| 5 主协调铁律 (W7) | 5 |
| 6 技术铁律 (W10) | 6 |
| 11 协调铁律 (W10) | 11 |
| 139 技术/方法论铁律 (8 大类) | 139 |
| 4 锚点范式铁律 | 4 |
| **2 W61 新铁律 (502 排查 + PowerShell 转义)** | **2** |
| **累计** | **167** |

---

## 4. 相关 memory + docs

- `memory/multi-agent-task-orchestration-baseline.md` — 项目级协调范式锚点
- `memory/w11-13-baseline-closure-2026-07-22.md` — W11 13 baseline 守恒
- `memory/anchor-paradigm-21-day-validation-2026-07-22.md` — 锚点范式 21 天实战
- `memory/2026-07-22-50-commit-w51-w100-roadmap.md` — W51-W100 跨主题时间线
- `memory/w60-coordination-grand-closure-2026-07-22.md` — W60 跨主题收口 final
- `memory/w60-future-pr-evaluation-post-dedup.md` — W60 future PR post-dedup 评估
- `docs/frps-systemd-postmortem-2026-07-02.md` — 历史 frps systemd 修复（共享 SSH fd 孤儿经验）
- `memory/frps-systemd-postmortem-2026-07-02.md` — 历史 frps systemd 修复 memory
- `tunnel/start-ssh-tunnel.ps1` — SSH reverse tunnel 启动脚本（受 W61 启动段影响，需修 PowerShell 转义）
- `nginx/conf.d/tunnel.conf` — 云 nginx tunnel 配置（W61 已修）

---

## 5. 总结

W61 502 Bad Gateway 真根因修复 = **3 层链路穿透**：
1. **第 1 层（最外）**：docker nginx-1 SSL 路径错 → 容器 restart loop（修了 tunnel.conf + 拉证书）
2. **第 2 层（中间）**：SSH reverse tunnel 死后的孤儿 listener 占云 8000/9000/2222 → 云 nginx 反代给孤儿 → RST → 502（kill 孤儿 + 重启 SSH tunnel 用正确转义）
3. **第 3 层（最里）**：docker minio-1 端口 LISTENING 但不响应 → `docker restart` 修复

**关键教训**：
- 502 错误必须穿透 3 层排查，不能只看云 nginx error log
- SSH reverse tunnel 死后 listener 孤儿化是常见陷阱
- PowerShell `Start-Process -ArgumentList @(...)` 数组形式 + 双引号是安全转义
- W61 原始 memory 文件诊断错误，本文件覆盖修正

锚点范式 W61 实战 = **W19 选项 B (实质开发模式)**，累计 baseline 23 + 累计铁律 167 + 累计 commit 89（W60 88 + W61 1）。

---

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-22
**Version**: W61 502 真根因修复 v1.0 (覆盖修正原始 memory)