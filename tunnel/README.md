# MicroBubble Agent SSH Tunnel — Onboarding Guide

> **2026-07-08 P1-10 fix**: 项目从 frp 切到 SSH tunnel (2026-07-02). 此 README 让新成员 clone 仓库后知道怎么启用隧道.
> 之前部署脚本 `scripts/deploy-local.sh` 引用了 frpc.exe / frpc.toml, 已清理 (dead code).

---

## ⚠️ 目录边界（结构重构批次 6，2026-10-10 补）

本目录是**隧道本体**：负责**建立 / 启动 / 停止** ssh 反向隧道进程本身。

| | 本目录 `tunnel/` | [`../scripts/tunnel/`](../scripts/tunnel/) |
|---|---|---|
| 角色 | **隧道本体**（建隧道） | **隧道守护器**（守隧道） |
| 内容 | `setup-ssh-key.ps1` / `start-ssh-tunnel.ps1` / `start-ssh-tunnel.vbs` | `guard-ssh-tunnel.ps1` / `.bat` / `install-*.bat` / `uninstall-*.bat` |
| 调用方 | 人工 / 开机任务 `MicroBubble-SSH-Tunnel` | 计划任务 **`MicroBubble-SSH-Tunnel-Guard`**（每 5 分钟） |

**职责互补，不是重复 —— 勿合并。** 一个负责把隧道拉起来（`start-ssh-tunnel.ps1`
自带 30s 看门狗），一个负责判活并在断了之后重新拉起（`guard-ssh-tunnel.ps1`，
计划任务每 5 分钟调一次）。合并会同时打断这两条链路。

跨目录耦合是**已知且刻意**的：`scripts/tunnel/guard-ssh-tunnel.ps1` 会回调本目录的
`tunnel/start-ssh-tunnel.ps1` 重新拉隧道 —— 守护器引用本体是设计，不是层级错乱。

### `ssh-tunnel.log` / `ssh-tunnel.pid` 为什么在目录里

两个都是**运行时产物**，由 `start-ssh-tunnel.ps1` 生成，已在 `.gitignore` 里，
仓库中看到的通常是本地跑过的残留。**不是**待清理的死文件，也不要 `git add -f` 提交。

### ⚠️ 类 20.214：本隧道是生产依赖的裸进程单点

`ssh.exe` 是一个**没有 supervisor、没有容器托管**的裸进程。隧道一断，
云端 nginx 的 `proxy_pass http://127.0.0.1:8000` 立刻 502，
移动端表现就是 "Network Error" —— **全站不可用**。

因此存在两层保障，且都必须保留：

1. `tunnel/start-ssh-tunnel.ps1` 内置 30s 看门狗
2. `scripts/tunnel/guard-ssh-tunnel.ps1` 由计划任务 **`MicroBubble-SSH-Tunnel-Guard`**
   每 5 分钟判活并重拉

改任何一侧前先读 `CLAUDE.md` 的**类 20.214**（隧道 `-R` 端口与容器发布端口的对应
关系：8000↔app、9000↔minio）。

### 判活口径必须与本体一致（2026-09-15 P0 事故教训）

`guard-ssh-tunnel.ps1` 早期要求命令行必须出现 `-R 0.0.0.0:9000` 才算"隧道活着"，
而本目录 `start-ssh-tunnel.ps1` 拉起的隧道不带这个字面量 —— 两个监管者口径不一致时
会"互不认账"：守护器认为隧道没了 → 再拉一条 → 远端端口已被占用 → 因
`ExitOnForwardFailure=yes` 立即退出 255 → 5 分钟后再来一次。
实测 2026-09-15 白天 `ssh-tunnel.log` 出现 **115 次** `SSH exited immediately (code: 255)`，
断续约 70 分钟。修法是判活口径放宽为"任何连到本服务器的 `ssh -R` 隧道"。

**改判活逻辑时必须两个目录一起看**，否则会复发。

---

## 架构

```
[cloud server agent.mnb-lab.cn]
       ↓ ssh -R (反向隧道)
[local Windows] ssh.exe 进程 (后台, 由 Task Scheduler 拉起)
       ↓ -R 8000:127.0.0.1:8000 (app)
       ↓ -R 9000:127.0.0.1:9000 (minio)
       ↓ -R 2222:127.0.0.1:22  (ssh)
```

**反向隧道**让 cloud 的 `127.0.0.1:8000` 直接转发到 local 的 `127.0.0.1:8000`. Nginx 在 cloud 用 `proxy_pass http://127.0.0.1:8000` 即可访问 local 服务, 无需公网 IP / 端口映射.

## 新成员首次启用 (3 步)

### 步骤 1: 生成 SSH key (本地 Windows)

```powershell
# 如果你已经有 id_ed25519 可跳过
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519 -N ""
type $env:USERPROFILE\.ssh\id_ed25519.pub
# 把输出的公钥发给 admin 帮你加到 cloud 的 ~/.ssh/authorized_keys
```

或者用辅助脚本 `setup-ssh-key.ps1` (见下面).

### 步骤 2: 测试 SSH 隧道能通

```powershell
# 临时测试 (前台, Ctrl+C 退出)
powershell -ExecutionPolicy Bypass -File tunnel\start-ssh-tunnel.ps1

# 另一个 terminal 测试隧道
curl http://127.0.0.1:8000/api/v1/auth/me
# 应该返 401 (后端 alive)
```

### 步骤 3: 配 Windows Task Scheduler (开机自动启动)

```powershell
# 管理员 PowerShell
schtasks /Create /TN "MicroBubble-SSH-Tunnel" `
  /TR "powershell -ExecutionPolicy Bypass -File E:\microbubble-agent\tunnel\start-ssh-tunnel.ps1" `
  /SC ONLOGON /RL HIGHEST /F

# 验证
schtasks /Query /TN "MicroBubble-SSH-Tunnel" /V /FO LIST
```

重启电脑后, Task Scheduler 自动拉起 SSH tunnel (登录时).

## 辅助脚本

### `setup-ssh-key.ps1` — 一键生成 + 显示公钥

```powershell
powershell -ExecutionPolicy Bypass -File tunnel\setup-ssh-key.ps1

# 输出:
# 1. 检测是否已有 key (有就跳过, 不覆盖)
# 2. 生成新的 ed25519 key
# 3. 把公钥打到屏幕上
# 4. 提示用户复制公钥发给 admin 加到 cloud authorized_keys
```

### `start-ssh-tunnel.ps1` — 启动/管理隧道

```powershell
# 默认 action=start
powershell -ExecutionPolicy Bypass -File tunnel\start-ssh-tunnel.ps1

# 状态查询 (前台)
powershell -ExecutionPolicy Bypass -File tunnel\start-ssh-tunnel.ps1 -Action status

# 停止
powershell -ExecutionPolicy Bypass -File tunnel\start-ssh-tunnel.ps1 -Action stop
```

**自动行为**:
- 检测 PID 文件 `tunnel/ssh-tunnel.pid`, 已有进程就不重复拉起
- 日志 `tunnel/ssh-tunnel.log` 7 天轮转 (start.sh 自动清理)
- `StrictHostKeyChecking=accept-new` 首次连接自动信任 host key
- `ServerAliveInterval=30` + `ServerAliveCountMax=3` 30s 心跳保活

## 故障排查

| 症状 | 检查 | 修复 |
|---|---|---|
| 隧道启动失败, 日志 "Connection refused" | cloud 的 sshd 端口 (默认 22) 是否开 | 联系 admin 确认 cloud firewall |
| 隧道启动失败, 日志 "Permission denied (publickey)" | 本地 `~/.ssh/id_ed25519` 是否在 cloud authorized_keys | 重新生成 key + 加到 cloud |
| 隧道启动成功, 但 cloud 访问 `https://agent.mnb-lab.cn` 502 | nginx → 127.0.0.1:8000 不通 | SSH 隧道死了, 重启 (`start-ssh-tunnel.ps1`) |
| Task Scheduler 启动后无日志 | 任务运行身份 `SYSTEM` 无法读用户 SSH key | 改用当前用户身份 (ONLOGON + RL HIGHEST) |

## 配置文件

- `tunnel/start-ssh-tunnel.ps1` — 启动/管理脚本 (~120 行, 全部内联)
- `tunnel/ssh-tunnel.pid` — 当前运行进程 PID (运行时生成, gitignore)
- `tunnel/ssh-tunnel.log` — 运行日志 (运行时生成, gitignore)
- `tunnel/setup-ssh-key.ps1` — 一键生成 SSH key 辅助脚本

**关键 SSH 参数** (硬编码在 start-ssh-tunnel.ps1):
- 端口转发: 8000 (app) / 9000 (minio) / 2222 (ssh)
- 心跳: ServerAliveInterval=30s + ServerAliveCountMax=3
- 失败退出: ExitOnForwardFailure=yes (任一端口转发失败立即退出, 避免假活)

## 历史: 为什么切到 SSH tunnel (2026-07-02)

之前用 frpc (frp client) 走 frp/frps 内网穿透. 三个问题:
1. **frpc.exe 版本管理** — GitHub release 经常更新, 需要持续同步
2. **clash 代理冲突** — frpc 默认走系统代理, clash 误劫持 (CLAUDE.md 2026-06-13 frpc.exe 僵尸进程陷阱)
3. **WDAC 阻止** — frpc.exe 未签名, Windows Defender Application Control 阻止 (公司策略)

SSH tunnel 优势:
- ✅ Windows 内置 OpenSSH (微软签名, WDAC 允许)
- ✅ 用现成 ed25519 key (已有 GitHub Deploy Key 同款)
- ✅ 无需新依赖 (不用下载 frp release)

**完整事故链**: CLAUDE.md `### 2026-06-13 frpc.exe 僵尸进程陷阱` + `## 2026-07-02 WebSocket 502 事故根因沉淀 + frps systemd 守护部署`

## 相关

- `scripts/install-frps-systemd.sh` — **cloud 端** systemd 守护 (admin 部署)
- `CLAUDE.md` 顶部"开发注意事项" — 隧道状态常见问题