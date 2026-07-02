---
name: ollama-ssh-key-gitignore-fix
description: 2026-07-02 .ollama/ SSH 私钥 + Ollama 模型缓存 .gitignore 兜底修复 — 防 commit 时凭据泄漏 + 5GB GGUF 模型污染 repo
metadata:
  type: project
---

# 2026-07-02 .ollama/ SSH 私钥 + Ollama 缓存 .gitignore 兜底修复

> **commit**: 附 PR6-P15 commit `5bab3f15` (永久教训沉淀)
> **完整 CHANGELOG.md**: PR6-P15 章节末尾"附带 .gitignore 修复"

## 触发场景

用户跑 Ollama 本地 LLM 实验时 (LLM 3-Way Benchmark 阶段), 把 `id_ed25519` SSH 私钥 (387 字节, OpenSSH PRIVATE KEY) 放到 `.ollama/` 目录作为 Ollama 容器 connect 的 SSH key.

`git status` 显示 `.ollama/` 整个目录 untracked (因旧 `.gitignore` 没匹配). 如果 `git add .` 或 `git add .ollama/` 直接 commit, SSH 私钥会入库, 凭据泄漏.

**幸运发现**: 在准备 PR6-P15 commit 时 git status 提醒 `.ollama/` untracked, 主动 `cat .ollama/id_ed25519` 验证发现是真实私钥, 立即修复 `.gitignore` 兜底.

## 修复

### 1. `.gitignore` 加 `.ollama/` 整个目录

```gitignore
# Ollama 本地 LLM 部署残留（2026-07-02 v3 benchmark + Ollama container bind mount）
# 含 id_ed25519 SSH 私钥 + cache/ (qwen3:8b ~5GB GGUF 模型 manifest + blob) + models/
# 教训: 2026-07-02 .ollama/id_ed25519 是 OpenSSH PRIVATE KEY (387 字节), 不入库等于凭据泄漏
.ollama/
```

### 2. 兜底规则防任何位置 SSH/TLS 私钥

```gitignore
# 兜底: 全项目所有 SSH 私钥文件 (id_*, id.*, *_id_ed25519, *_id_rsa 等)
# 任何 SSH 私钥都不应入库, 必须 ignore 兜底 (CLAUDE.md 2026-07-02 教训)
**/id_ed25519
**/id_rsa
**/id_dsa
**/id_ecdsa
**/id_ed25519.pub.bak
**/*.pem
**/*.key
```

## 4 新铁律

1. **任何 SSH/TLS 私钥必须 ignore** — 不依赖具体路径, 全项目 glob 兜底 (`**/id_ed25519` / `**/*.pem` / `**/*.key`)
2. **`.ollama/` 整个目录 ignore** — 含 SSH 私钥 + cache/ (qwen3:8b ~5GB GGUF 模型 manifest + blob) + models/ (manifest.json + config.json + template), 总计 5GB+ 不可能入库
3. **commit 前必 `git status --short` + `git diff --cached` 验证 staged diff 干净** — 永远不要 `git add .` 偷懒, 任何全项目 add 前必须 review untracked
4. **发现 untracked 敏感文件立刻处理** — 不要等下次 commit 才查, `git status` 显示就立刻 `cat` 验证 + 加 ignore 规则

## 端到端验证

```bash
# 1. 验证 .ollama 不再 untracked
git status
# 期望: nothing to commit, working tree clean

# 2. 验证 SSH 私钥兜底规则生效
touch /tmp/test_id_ed25519
cd /tmp && git init && git add test_id_ed25519
# 期望: The following paths are ignored by one of your .gitignore files: test_id_ed25519
rm /tmp/test_id_ed25519 && rm -rf /tmp/.git

# 3. 验证 .pem 文件兜底
touch /tmp/test.pem
cd /tmp && git init && git add test.pem
# 期望: ignored

# 4. 强制 add 确认私钥不会被 commit
git add -f .ollama/id_ed25519
# 期望: warning + add 失败 (除非 -f 强制, 但 -f 后必须手动检查)
```

## 跟项目历史教训的关系

- **CLAUDE.md 2026-06-17 docker-desktop-fix**: 数据 E 盘化 + .dockerignore 17× 提速, 防止 build context 污染
- **CLAUDE.md 2026-07-01 `_login.json` admin JWT 凭据泄露修复**: `tests/qa-bench/_login.json` + `_token.txt` 含 admin JWT exp 2026-07-21, 必须删 + .gitignore 兜底 (`**/_login.json` / `**_token.txt` / `**/_*.json`)
- **本次 .ollama/ SSH 私钥**: 同类风险, 不同位置, 同样兜底修复

## 永久教训沉淀

任何"含敏感凭据或大体积缓存"的本地工具 (Ollama / Docker bind mounts / test fixtures / CI artifacts), 都必须在 `.gitignore` 加显式规则, 不依赖开发者每次手动 exclude.

## 不在本次范围 (留给未来)

- **历史 commit 检查** — 验证没有历史 commit 已包含 SSH 私钥 (用 `git log --all --full-history -- "**/id_ed25519"` 检索)
- **gitleaks pre-commit hook** — 自动化扫描 commit 内容, 任何高熵字符串报警 (类似项目已有的 `scripts/check-secrets-before-commit.sh`)
- **gpg 签名 commit 强制** — 所有 commit 必须 GPG 签名, 防冒名 commit
- **`gh secret scan` GitHub Action** — PR 触发 secret scanning, 防 OAuth tokens / SSH keys 入库
