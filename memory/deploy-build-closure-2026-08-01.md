---
name: deploy-build-closure-2026-08-01
description: DEPLOY-BUILD W99 +10 web/dist build 收口 — PWA 禁用致 manifest 检查 N/A + webhook 仅认 main 两项派工前提错配据实上报
metadata:
  type: project
---

# DEPLOY-BUILD 2026-08-01 收口 (锚点 W99 +10)

commit `0608da83e` | branch `chore/deploy-build` | base `6c134158a` | 385 files (+145 / -487)
runbook: `docs/deploy-build-2026-08-01.md`

## 两项派工前提错配 (类 20, 据实上报未凑 PASS)

**错配 A — PWA 已禁用, hashed manifest / sw.js 检查判 N/A**
派工 brief 段 2.2/2.3 要求验证 `manifest.{hash}.webmanifest` 存在 + `sw.js` unhashed grep 为空。
实测 `web/vite.config.js:241` = `VitePWA({ disable: true })` (W68 第 14 批 H-3 起), 不产出 sw.js / manifest;
HEAD dist 481 文件亦 0 manifest/sw; postbuild 走 "PWA 已禁用" 分支正常 exit 0。
→ 判 **N/A 而非 PASS**, 未伪造哈希, 未为凑 PASS 重启 PWA (那属 production code 改动, 超边界)。

**错配 B — push 本分支不触发部署**
brief 段 2.4 称 push 触发 webhook 自动部署。实测 `scripts/webhook.py:118` 仅 `ref == "refs/heads/main"` 才部署,
非 main 走 `logger.info("忽略非 main 分支")`。→ 已按指令 push 分支, **生产部署待主指挥合并入 main**;
未擅自 merge (超边界)。

## 关键处置

- **node_modules 缺失**: worktree 无 `web/node_modules`; package.json + package-lock.json 与主仓库 md5 全同
  → 建 Windows 目录联接 (`mklink /J`) 复用主仓库 694 项依赖, 避免重装引版本漂移。
- **358 项删除**: fresh build 255 文件 vs HEAD 481 → vite 清空 outDir 删陈旧哈希资产 (333 js + 25 css,
  全在 assets/ 内)。有先例 (95fb59dd8 删 234 / fec6e9cb6 删 108)。
  `--no-renames` 口径 132 A / 358 D / 1 M (git 默认带 rename 检测显示 26 A / 252 D / 1 M / 106 R)。
- **防 404 闭环**: 全 dist **226 个 hashed 引用 100% 命中磁盘, 0 dangling**; index.html 4 引用 +
  index-2bc54e5e.js 72 lazy chunk 引用全部已 staged。这是 CLAUDE.md 2026-06-26 f6a2bc3d 白屏教训的核心校验。

## 5 件套

alembic 1 head `093_add_search_log_answer_rating` 守恒 / pytest 不跑 (纯 build) /
`npm run build` PASS 8.20s / 0 production code (diff origin/main app+web/src+alembic = 0 行) / 锚点 0 → 1。

## 铁律实战

`npm run build` 唯一合法 (未用 `vite build` / `build:raw`) — CLAUDE.md §2026-07-11 PWA 410 回归。
`git add -f web/dist/` 必须 (`.gitignore:78` 含 `web/dist/`)。
pre-commit hook (secrets → dist) 未 bypass, 无 `--no-verify`。

相关: [[w85-1st-grand-closure-full-2026-07-29]]
