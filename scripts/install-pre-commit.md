# Pre-commit 框架装机指南 (W86-D-1, 2026-07-29)

> **状态**: W86 第 1 批 D-1 交付. 锚点范式 320 → 321 预期.

## 为什么需要 pre-commit 框架

项目已有 `scripts/setup-hooks.sh` 装纯 bash 的 git hooks (`check-secrets-before-commit.sh` + `check-dist-before-commit.sh`). 这能拦住 2 条 CLAUDE.md 纪律 (凭据 + 漏 dist), 但还有 5 条纪律需要机械化:

| # | 纪律出处 | Hook id | 拦截内容 |
|---|---------|---------|---------|
| 1 | CLAUDE.md 永久纪律 (凭据) | `gitleaks-scan` | 检测 .env / JWT / SSH key 等敏感凭据 (gitleaks 二级扫描) |
| 2 | CLAUDE.md 永久纪律 (Trivy) | `dockerfile-pinning` | Dockerfile / docker-compose base image 必须含具体次版本号 |
| 3 | CLAUDE.md §2.3 (alembic 串单链, commit 1852468a6) | `alembic-chain` | alembic migration 链不能多 head |
| 4 | CLAUDE.md 641 行 (check_typing_imports.sh) | `typing-imports` | Python typing import 必须齐全 (Dict/List/Optional 等) |
| 5 | CLAUDE.md 永久纪律 (manifest 410 教训) | `dist-manifest-hash` | web/dist 不能有 unhashed `manifest.webmanifest` 引用 |

**pre-commit 框架** ([pre-commit.com](https://pre-commit.com/)) 是 Python 写的 git hook 管理器, 用 YAML 配置, 自动管理 hook 安装/升级/缓存. 我们用它把这 5 条纪律机械化.

## 与现有 setup-hooks.sh 的关系

| 项 | `setup-hooks.sh` | `pre-commit` 框架 |
|---|---|---|
| 配置 | 纯 bash in-script | `.pre-commit-config.yaml` |
| 安装命令 | `bash scripts/setup-hooks.sh` | `pip install pre-commit && pre-commit install` |
| 依赖 | 无 (纯 bash + 已 tracked 脚本) | 需 `pip install pre-commit` (Python 包) |
| 失败时 | 硬阻断 (脚本 exit 1) | 同上, 但可 skip (`--no-verify` 或 `SKIP=...`) |
| Hook 数量 | 2 (secrets + dist) | 5 (gitleaks-scan + dockerfile-pinning + alembic-chain + typing-imports + dist-manifest-hash) |

**结论**: 两者可并存. 开发者可选 (a) 只用 setup-hooks.sh (轻量, 无外部依赖) 或 (b) 同时启用 pre-commit 框架 (全纪律机械化). 当前设计: 两者并存, 互不冲突.

## 装机步骤 (开发者本机)

```bash
# Step 1: 安装 Python 包 (仅首次)
pip install pre-commit
# 验证: pre-commit --version → 应输出 "pre-commit 3.x.x"

# Step 2: 在仓库根装钩子
cd <repo-root>
pre-commit install
# 这一步写 .git/hooks/pre-commit (Python wrapper, 调 .pre-commit-config.yaml)

# Step 3: 首次跑全量检查 (缓存 + 下载 hook repos, 仅第一次)
pre-commit run --all-files
# 输出: 5 个 hook PASS / FAIL. 如 FAIL, 按提示修复后 `git add` 再 commit.

# Step 4: 验证 framework 接入
pytest tests/precommit/ -v
# 期望: tests/precommit/test_config_valid.py + test_hooks_executable.py 全 PASS
```

## 装好后日常体验

```bash
# 正常 git commit
git commit -m "feat: ..."
# pre-commit 自动跑 5 个 hook:
#   - gitleaks-scan (gitleaks 扫描文本文件)
#   - dockerfile-pinning (扫 Dockerfile*)
#   - alembic-chain (扫 alembic/versions/*.py)
#   - typing-imports (扫 app/*.py)
#   - dist-manifest-hash (扫 web/dist/)
# 任一失败 → commit 阻止.

# 临时跳过单个 hook (e.g. 紧急 hot-fix 急着 commit)
SKIP=alembic-chain git commit -m "hotfix: ..."   # 跳 alembic 检查
SKIP=gitleaks-scan,dist-manifest-hash git commit ... # 跳多个

# 跳所有 (不推荐, 与 --no-verifies 等价)
git commit --no-verify -m "..."
```

## Hook 失败时如何修复

| Hook id | 失败修复 |
|---------|----------|
| `gitleaks-scan` | 找到违规文件的:行号, 把凭据移到 .gitignore 路径或替换成占位符 |
| `dockerfile-pinning` | 把 `:latest` 改成具体次版本 (e.g. `python:3.11-slim-bookworm`) |
| `alembic-chain` | 见 [scripts/alembic/check_single_head.sh](../alembic/check_single_head.sh) 输出, 改 down_revision + clear `__pycache__` |
| `typing-imports` | 在文件顶部加 `from typing import Dict, List, Optional, ...` |
| `dist-manifest-hash` | 删 `web/dist/manifest.webmanifest`, 跑 `cd web && npm run build` 重新生成 hashed manifest |

## 验证 (W86-D-1 硬门禁)

```bash
pytest tests/precommit/ -v
```

期望输出:
```
tests/precommit/test_config_valid.py::test_yaml_syntax_valid PASSED
tests/precommit/test_config_valid.py::test_all_hooks_present PASSED
tests/precommit/test_config_valid.py::test_hook_ids_unique PASSED
tests/precommit/test_hooks_executable.py::test_pinned_images_executable PASSED
tests/precommit/test_hooks_executable.py::test_alembic_chain_executable PASSED
tests/precommit/test_hooks_executable.py::test_dist_manifest_executable PASSED
tests/precommit/test_hooks_executable.py::test_typing_imports_executable PASSED
tests/precommit/test_hooks_executable.py::test_pinned_images_exit_zero PASSED
```

## 已知问题

1. **pip 安装需 Python ≥ 3.8** — 项目用 Python 3.11, 满足.
2. **pre-commit 不在 git tracked** — `.git/hooks/pre-commit` 是 wrapper, **不**入库. 新成员需手动 `pre-commit install`.
3. **hook 跑顺序** — 框架默认 fail-fast=false, 所有 hook 都跑完. 如要改 fail-fast, 编辑 `.pre-commit-config.yaml` 顶部 `fail_fast: true`.
4. **gitleaks 二级扫描** — 当前 `gitleaks-scan` hook 在 W86-A-1 完成后会用真 gitleaks 配置. 在此之前, fallback 到既有 `check-secrets-before-commit.sh`. 不破坏现有 hook.

## 与 CLAUDE.md 纪律映射

本框架**严格按** CLAUDE.md 5 条纪律实现, 不发明新纪律:

```yaml
# 纪律 #1 (gitleaks / secrets):
#   CLAUDE.md W67 第 41 步: "凭据不能入库"
#   hook: gitleaks-scan (entry fallback 到 check-secrets-before-commit.sh)

# 纪律 #2 (Trivy / Dockerfile pinning):
#   CLAUDE.md 永久纪律: image 必须有具体版本号
#   hook: dockerfile-pinning

# 纪律 #3 (alembic 串单链):
#   CLAUDE.md §2.3 (W68 第 3 批 commit 1852468a6 教训)
#   hook: alembic-chain

# 纪律 #4 (typing imports):
#   CLAUDE.md 641 行 (check_typing_imports.sh 106 文件 0 错误)
#   hook: typing-imports

# 纪律 #5 (dist manifest hash):
#   CLAUDE.md 永久纪律 (commit 59187ce8 + 5d2bcdfd 教训)
#   hook: dist-manifest-hash
```

## 主指挥合并时注意

合 W86-D-1 commit 时, `.gitignore` 加一行 (避免 pre-commit cache 文件入库):

```
# Pre-commit framework cache (Python wrapper creates .pre-commit-cache/)
.pre-commit-cache/
```

这一步**不在本任务范围内** (用户没授权改 `.gitignore`). 主指挥合并时建议手动加, 详 [memory/w86-1st-batch-d1-pre-commit-2026-07-29.md](../../memory/w86-1st-batch-d1-pre-commit-2026-07-29.md) 沉淀文件.

## 参考

- Pre-commit 官方文档: https://pre-commit.com/
- 项目内参考:
  - `.pre-commit-config.yaml` (本任务交付)
  - `scripts/trivy/check_pinned_images.py` (本任务交付)
  - `scripts/alembic/check_single_head.sh` (本任务交付)
  - `scripts/web/check_dist_manifest.sh` (本任务交付)
  - `tests/precommit/test_config_valid.py` (本任务交付)
  - `tests/precommit/test_hooks_executable.py` (本任务交付)
  - `scripts/setup-hooks.sh` (本任务顶部注释 + 末尾可选安装段更新)
  - `memory/w86-1st-batch-d1-pre-commit-2026-07-29.md` (本任务沉淀)
