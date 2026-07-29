# Trivy 安装说明 (W86-C-1)

> 本机 (2026-07-29 验证) **未安装** trivy — `trivy --version` → `command not found`。
> 本文档只说明安装方式, **不代表已在系统安装**。CI 侧由
> `.github/workflows/image-scan.yml` 的 `aquasecurity/trivy-action` 自带 trivy, 无需本机安装。

## macOS

```bash
brew install trivy
```

## Linux (Debian / Ubuntu, apt 仓库)

```bash
sudo apt-get install wget gnupg lsb-release
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor | sudo tee /usr/share/keyrings/trivy.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb generic main" | sudo tee /etc/apt/sources.list.d/trivy.list
sudo apt-get update
sudo apt-get install trivy
```

## Windows

```powershell
winget install trivy
```

或从 release 页下载 zip 解压后把 `trivy.exe` 放进 `PATH`:
<https://github.com/aquasecurity/trivy/releases>

## 安装后验证

```bash
trivy --version
```

## 本地扫描入口

| 脚本 | 用途 |
|------|------|
| `scripts/trivy/scan-images.sh` | 扫 8 个 Dockerfile + 本地已存在镜像, 输出 `logs/trivy-report.txt`, HIGH/CRITICAL 命中即 exit 1 |
| `scripts/trivy/scan-all.sh` | 全量扫 (Dockerfile + 本地镜像 + sarif 输出到 `logs/trivy-sarif/`) |

## 注意 (本机网络环境)

本机 shell 出网被拦 (`registry-1.docker.io` / `hub.docker.com` curl 均超时),
`docker pull` 走 daocloud / ustc / aliyun 镜像加速器。首次跑 trivy 需要下载
漏洞库 (`trivy-db`), 若直连 GitHub 失败, 用:

```bash
trivy --cache-dir ./.trivycache image --download-db-only
```

或设置 `TRIVY_DB_REPOSITORY` 指向内网/镜像仓库。
