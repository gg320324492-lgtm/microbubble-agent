# gitleaks 安装说明 (W86 第 1 批 A-1 沉淀)

> **状态 (2026-07-29)**: 本机当前 **未安装** gitleaks, 本任务只做文档化装机步骤, 不实际安装系统级二进制.
> W86 主指挥拍板后续安装时机 (避免破坏 docker compose / 依赖 git hooks 的现有链路).

---

## 为什么需要 gitleaks

项目已经做了两层凭据防护:

1. **`.gitignore`** — 排除 `**/id_ed25519`, `**/*.pem`, `**/*.key`, `.env`, `.ollama/` 等敏感路径
2. **`scripts/check-secrets-before-commit.sh`** — pre-commit 钩子硬门禁 (JWT 关键字 `eyJ...`)

但仍有盲点:
- **未跟踪文件绕过 .gitignore**: 一旦 `git add -f` 就会被绕过
- **PR 流程无扫描门禁**: 外部 contributor PR 不会被 pre-commit 拦截
- **历史 commit 无审计**: 一旦凭据入库, 没人主动扫历史
- **多凭据类型**: 现有钩子只挡 JWT, 不挡 Anthropic API key / OpenAI key / 私钥 / MinIO 默认密码

**gitleaks** 补齐这 4 个盲点:
- 扫 PR + push 触发 (CI 门禁)
- 扫历史 commit (默认 `base = "commits"` 模式)
- 内置 100+ 凭据规则, 覆盖常见 secret
- 输出 SARIF 报告接入 GitHub Code Scanning

---

## 安装步骤

### macOS (Homebrew)

```bash
brew install gitleaks
```

验证: `gitleaks version` 应输出 `8.x.x` 或更新.

### Linux (amd64 tarball)

```bash
# 最新 release
wget https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_Linux_x86_64.tar.gz

# 解压
tar -xzf gitleaks_Linux_x86_64.tar.gz

# 移动到 PATH
sudo mv gitleaks /usr/local/bin/

# 验证
gitleaks version
```

### Windows (Git Bash + winget)

```powershell
# 方法 1: winget (推荐)
winget install gitleaks

# 方法 2: 手动下载 release zip
# 1. 访问 https://github.com/gitleaks/gitleaks/releases/latest
# 2. 下载 gitleaks_Windows_x86_64.zip
# 3. 解压到 C:\Users\<user>\bin\
# 4. 把 C:\Users\<user>\bin\ 加到 PATH (用户变量)
# 5. 重启 Git Bash

# 验证
gitleaks version
```

### Docker (无需本地装)

```bash
docker pull zricethezav/gitleaks:latest

# 跑扫描
docker run --rm -v "$(pwd):/repo" zricethezav/gitleaks:latest detect \
    --source /repo \
    --report-path /repo/logs/gitleaks-report.json \
    --no-banner
```

> **本项目推荐**: Windows + Git Bash 环境下用 **winget 安装**, Linux/macOS 用对应包管理器.
> Docker 方案适合 CI (避免每台机器都装).

---

## 本机状态

执行 `which gitleaks` 输出:
```
which: no gitleaks in (...)
```

执行 `gitleaks version` 输出:
```
/usr/bin/bash: line 1: gitleaks: command not found
```

**结论**: 当前 worktree (Windows 11 + Git Bash) 无 gitleaks.

后续步骤:
- W86 主指挥 (a2529a8747406c75c) 决定装机时机 — 推荐等 W86-X-1 历史凭据清理 commit 落地后, 一次性装机并跑 baseline 扫描
- 避免在装机扫描时立刻失败 CI (现有 `check-secrets-before-commit.sh` 已经挡 JWT, 装机扫到历史 JWT 也算"已知泄漏")

---

## 与现有 pre-commit 钩子的关系

- **`scripts/check-secrets-before-commit.sh`** — 1 layer 硬门禁 (本地 commit 时挡 JWT 字面量)
- **gitleaks pre-commit hook** — 推荐再加 1 layer 全面规则扫描 (commit 时扫)
- **GitHub Actions** — CI 端 PR + push 扫描 (远程门禁)

三层叠加:
```
本地 commit → check-secrets-before-commit.sh (JWT 关键字)
            → gitleaks pre-commit (全规则)
            → git push → CI gitleaks-action (全规则 + 历史)
```

不会重复挡: gitleaks 配置 `.gitleaks.toml` 的 `allowlists` 段可以让 pre-commit + CI 共享已知泄漏清单.

---

## 关联文件

- `.gitleaks.toml` — 项目根配置 (本任务创建)
- `.github/workflows/secret-scan.yml` — CI 扫描 (本任务创建)
- `scripts/gitleaks/scan-history.sh` — 本地全仓库扫描 (本任务创建)
- `tests/gitleaks/test_scan_clean_repo.py` — e2e 验证 (本任务创建)
- `logs/gitleaks-report.json` — 扫描产物 (本任务首次扫描输出, .gitignore 兜底)
- `memory/w86-1st-batch-a1-gitleaks-scan-2026-07-29.md` — 扫描报告摘要 + 历史泄漏清单

---

## 沉淀 (W86 第 1 批 A-1 据实上报)

- gitleaks 未装机 (本机) — **0 production code 改动铁律守恒** (文档化, 不动代码)
- 装机由 W86 主指挥决定时机
- 首次扫描预期在本机有 gitleaks 之后跑, 当前 worktree 仅完成"装配 + 文档 + e2e 框架"