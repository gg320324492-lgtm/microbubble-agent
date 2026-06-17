---
name: docker-desktop-fix-2026-06-17
description: Docker Desktop 引擎崩溃循环根因 + 数据全 E 盘化方案 + 清华/aliyun 镜像源切换
metadata:
  type: project
---

# Docker Desktop 修复与数据迁移 (2026-06-17)

1. **引擎崩溃根因**: WSL2 `docker-desktop-data` 发行版丢失（注册表 `HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Lxss` 下没有），导致 `com.docker.service` 每 7-9 分钟反复启动又停止（事件日志可见）。`wsl -l -v` 只看到 `docker-desktop` 没有 `docker-desktop-data` 就是这个症状
2. **数据全 E 盘方案**: 删 C 盘 `AppData\Local\Docker` 24GB（先备份到 E 盘）→ Docker Desktop 启动时自动重建 `docker-desktop-data` 发行版在 E 盘 → 用 `mklink /J` 创建 junction 透明重定向：删 C 盘原目录 + 创建 `C:\Users\pc\AppData\Local\Docker` → `E:\DockerData\appdata` 的 junction。C 盘 0 字节占用，Docker 透明读写 E 盘
3. **huaweicloud 镜像源 404**: Debian bookworm 的 `bookworm-security` 仓库已从 `debian/` 迁到 `debian-security/`，huaweicloud 旧路径 404。换 `mirrors.aliyun.com/debian-security bookworm-security main contrib`（路径正确支持）
4. **PyPI 限速真相**: aliyun PyPI 镜像对单连接限速 600KB/s，下 torch 532MB 装 13 分钟且 502 瞬时错误。清华 TUNA 前 12 秒 14MB/s 后降到 320KB/s 仍会断。**最稳方案是 pip `--retries 10 --timeout 60` 重试机制**（最终成功 7 分钟装完 200+ 包）
5. **PyTorch 官方基础镜像 GPG 缺失**: `pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime` 精简了 Debian keyring，apt 装包 GPG 失败（`NO_PUBKEY 6ED0E7B82643E131`）。`[trusted=yes]` 和 `Acquire::AllowInsecureRepositories=true` 在新版 apt 不生效。**最佳方案：保持 `python:3.11-slim-bookworm` 基础镜像**（自带完整 keyring）
6. **frp 开机自启**: 用 `Register-ScheduledTask` 创建用户级登录任务（`AtLogOn`），调 wrapper 脚本 `start-frpc.ps1`（检测 frpc 已运行则退出，避免重复进程）。避免用 `sc create`（命令行引号转义问题）+ UAC 提权问题
7. **dockerproxy.net 500 错误**: Docker Desktop 内部用 `dockerproxy.net` 代理 docker.io 镜像。500 是 daemon 没完全起来。**解决：完全 kill 所有 Docker 进程 → 等 10 秒 → 重启 Docker Desktop → 等 90-120 秒 daemon 完全起来**（不能光退出 Docker Desktop UI，要 kill `com.docker.backend` 进程）
8. **~/.docker/config.json 不要随便加 proxies 字段**: 加了 `proxies.default.httpsProxy: http://host.docker.internal:7890` 后 Docker Desktop daemon 内部通信出错（500 错误），需要恢复原状。Docker Desktop 走代理应通过 Settings GUI 配置，不通过 config.json
9. **.dockerignore 是必须的**: `models/` 目录含 huggingface/torch/modelscope 缓存（10+ GB），build context 传到 Docker daemon 慢且占空间。建 .dockerignore 排除 models/data/logs/.git/.agents/docs，build context 从 12GB 降到 700MB
10. **docker-compose.override.yml 默认加载**: 文件名 `override.yml` 会被 compose 自动加载合并到主 compose 上，不需要 `-f` 指定

**How to apply:**

- **C 盘软件迁移到 E 盘**（任何软件，不只是 Docker）：删 C 盘原目录 → 用 `mklink /J "C:\path" "E:\real\path"` 创建 junction → 软件硬编码路径继续工作，物理数据在 E 盘
- **WSL Docker 引擎恢复**：`wsl -l -v` 看发行版 → 缺 `docker-desktop-data` → 重置 Docker Desktop（设置 → Troubleshoot → Reset to factory defaults）→ 自动重建发行版
- **国内装大 Python 包**：清华源 + pip `--retries 10 --timeout 60` 重试。PyTorch 直接走 `download.pytorch.org/whl/cu121` 官方 wheel 源（清华源对 torch 2.12+ 同步滞后）
- **Docker Desktop 走代理**：Settings → Resources → Proxies → 配 HTTP/HTTPS 代理 → Apply & Restart。**不要改 config.json**
- **服务自启（frp 类）**：`Register-ScheduledTask` + PowerShell wrapper（隐藏窗口、检测重复进程）
