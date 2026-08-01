# DEPLOY-BUILD 2026-08-01 — web/dist build runbook + dist 健全性报告

> 锚点范式 **W99 +10** | commit `0608da83e` | branch `chore/deploy-build` | base `6c134158a` (= origin/main)

## 1. 任务范围

`npm run build` 生成 web/dist → 健全性自检 → `git add -f` → commit → push origin。
**不动** production code (`app/` / `web/src/` / `alembic/`)、测试、alembic。

## 2. 派工前提据实上报 (类 20 错配 2 项)

### 2.1 错配 A — PWA 已禁用, hashed manifest / sw.js 检查 N/A (非 PASS)

派工 brief 段 2.2 / 2.3 要求:
- 验证 `web/dist/assets/manifest.{hash}.webmanifest` 存在
- 验证 `git diff --cached -- web/dist/sw.js | grep '"url":"manifest.webmanifest"'` 为空
- `find web/dist/assets -name 'manifest-*.webmanifest' | wc -l` ≥ 1

**实测与 brief 不符**:

| 检查 | brief 期望 | 实测 | 判定 |
|---|---|---|---|
| `web/vite.config.js:241` | — | `VitePWA({ disable: true })` (W68 第 14 批 H-3) | PWA 禁用 |
| `web/dist/sw.js` | 存在 | 不存在 | N/A |
| `find web/dist -name '*.webmanifest'` | ≥ 1 | **0** | N/A |
| `git ls-tree -r HEAD -- web/dist/ \| grep -iE 'manifest\|sw\.js'` | — | **0 条** (HEAD 481 文件亦无) | 历史一致 |
| postbuild 脚本分支 | rename manifest | `[postbuild] PWA 已禁用 ... 跳过所有 PWA 后处理` → `exit 0` | 正常 |

**结论**: 该 2 项判定 **N/A**, 不是 PASS。禁用状态自 W68 第 14 批 H-3 起已持续, 本任务不改变它。
**未伪造 manifest 哈希**, 未为凑 PASS 而重新启用 PWA (那属 production code 改动, 超出派工边界)。

### 2.2 错配 B — push 本分支不触发 webhook 部署

派工 brief 段 2.4 称 "push origin **触发 webhook 自动部署**"。

`scripts/webhook.py:118` 实际逻辑:
```python
if ref == "refs/heads/main":
    threading.Thread(target=self._run_deploy, daemon=True).start()
else:
    logger.info(f"忽略非 main 分支: {ref}")
```

`chore/deploy-build` → 走 else 分支, **只记日志, 不部署**。
本任务已按 brief 指令 push 该分支; **生产部署需主指挥将其合并入 main** 后才会触发。
未擅自 merge 到 main (超出派工边界)。

## 3. Build 前置 (阶段 1)

| 项 | 结果 |
|---|---|
| worktree | `E:/agent-deploy-build` @ `chore/deploy-build`, base `6c134158a`, 起始 clean |
| `git fetch origin` | origin/main = `6c134158a` (与 base 同) |
| alembic heads | **1 head** `093_add_search_log_answer_rating` ✓ |
| `web/package.json` build | `vite build && node scripts/postbuild-fix-manifest.js` ✓ |
| `web/scripts/postbuild-fix-manifest.js` | 存在 (7037 B) ✓ |
| `scripts/check-dist-before-commit.sh` | 存在 (5233 B), 已装为 `.git/hooks/pre-commit` (串 secrets → dist) ✓ |
| `.dockerignore` | 含 `agent-w*/` ✓ |
| **`web/node_modules`** | **缺失** — worktree 未 install |

### 3.1 node_modules 处置

worktree 无 `web/node_modules`。`package.json` + `package-lock.json` 与主仓库 **md5 完全一致**
(`fb109bf6…` / `97600190…`), 遂建 Windows 目录联接复用主仓库依赖, 避免重装引入版本漂移:

```bash
cd /e/agent-deploy-build/web
cmd //c "mklink /J node_modules E:\microbubble-agent\web\node_modules"
# → 694 项, node_modules/.bin/vite 可用
```

联接为构建期产物, 不入库 (`.gitignore` 已含 `node_modules`)。

## 4. npm run build (阶段 2)

```
✓ built in 8.20s
[postbuild] PWA 已禁用 (vite-plugin-pwa disable: true), sw.js 不存在 — 跳过所有 PWA 后处理
[postbuild] H-3 修复: 强制注销浏览器老 SW + 清空 Cache Storage 已在 main.js 顶部实现
[postbuild] 完成 ✓
```

- 命令: `npm run build` (**唯一合法**, CLAUDE.md §2026-07-11 PWA 410 铁律; 未用 `vite build` / `build:raw`)
- 产出: `web/dist` 255 文件
- chunk 告警: `element-plus-desktop` 1,035 kB / `echarts` 1,035 kB > 500 kB — 既有基线, 非本次引入

## 5. dist 健全性自检 (阶段 3)

| # | 检查 | 结果 |
|---|---|---|
| 1 | `web/dist/index.html` 存在 | ✓ 1747 B |
| 2 | `find web/dist/assets -name 'index-*.js'` | **1** ✓ |
| 3 | `find web/dist -name '*.webmanifest'` | 0 — **N/A** (见 §2.1) |
| 4 | `web/dist/sw.js` unhashed manifest grep | **N/A** (sw.js 不存在) |
| 5 | staged 中含 `manifest.webmanifest` | **空** ✓ (无 unhashed 误提交) |
| 6 | index.html 4 个 `/assets/*` 引用均已 staged | **4/4 OK** ✓ |
| 7 | `index-2bc54e5e.js` 72 个 lazy chunk 引用 | **72/72 命中, 0 missing** ✓ |
| 8 | **全 dist 226 个 hashed 引用 vs 磁盘** | **226/226 命中, 0 dangling** ✓ |
| 9 | staged 中 `web/dist/` 之外文件 | **0** ✓ |

第 8 项是防 404 白屏的关键闭环 (CLAUDE.md 2026-06-26 f6a2bc3d 教训): 任一引用缺文件 →
SPA `try_files` fallback 返 `text/html` → 白屏。实测 0 dangling。

### 5.1 index.html 变更

```diff
-  <script type="module" crossorigin src="/assets/index-c94fdca5.js"></script>
+  <script type="module" crossorigin src="/assets/index-2bc54e5e.js"></script>
-  <link rel="stylesheet" crossorigin href="/assets/index-fbc08681.css">
+  <link rel="stylesheet" crossorigin href="/assets/index-06f87bc7.css">
```
`element-plus-desktop-1d867305.js` / `-e89501c3.css` 哈希不变 (依赖未动)。

### 5.2 358 项删除说明 (重要)

fresh build 255 文件 vs HEAD tracked 481 → vite 清空 outDir, 陈旧 hashed 资产被删。

`--no-renames` 口径: **132 A / 358 D / 1 M**
(git 默认检测重命名后显示为 26 A / 252 D / 1 M / 106 R — 同一变更两种口径)

- 358 D 全部落在 `web/dist/assets/` 内 (**333 js + 25 css**), **0 个** assets 之外文件被删
- 均为历次 build 累积的旧哈希产物, 无当前引用 (§5 第 8 项已证 0 dangling)
- **有先例**: `95fb59dd8` 删 234、`fec6e9cb6` 删 108、`5290cab5b` 删 2、`cfa8c1bf4` 删 1

风险提示: 持旧 `index.html` 缓存的浏览器请求旧哈希资产会 404, 需硬刷 —
此为项目既有 dist 提交模式的固有行为, 非本次新增。

### 5.3 pre-commit hook 行为

`.git/hooks/pre-commit` = secrets (hard block) → dist (soft auto-fix)。
本次 commit 前已手动 `git add -f web/dist/` (`.gitignore:78` 含 `web/dist/`, 不加 `-f` 静默跳过),
dist hook 的 auto-add 分支因无 "未 staged 的新 dist 产物" 而空过; **未 bypass 任何 hook** (无 `--no-verify`)。
token-orphan 检查前置条件为 "staged 含 `web/src/` 改动", 本次 0 改动故未触发。

## 6. commit + push (阶段 4)

| 项 | 值 |
|---|---|
| commit | `0608da83e81485096f6a6f8930297d3fa221b57b` |
| message | `[DEPLOY-BUILD W99 +10] chore(web): build dist for webhook auto-deploy` |
| stat | **385 files changed, 145 insertions(+), 487 deletions(-)** |
| push | `origin/chore/deploy-build` = `0608da83e` ✓ (new branch) |
| ahead of origin/main | **1** |
| worktree 终态 | clean |

## 7. 5 件套守恒

| # | 件 | 结果 |
|---|---|---|
| 1 | `python -m alembic heads` | **1 head** `093_add_search_log_answer_rating` ✓ (未动 alembic) |
| 2 | pytest | **不跑** — 纯 build 范畴 (据实, 非 PASS) |
| 3 | `npm run build` | **PASS** — 8.20s + postbuild 自检 ✓ |
| 4 | 0 production code | `git diff origin/main -- app/ web/src/ alembic/ \| wc -l` = **0** ✓ |
| 5 | 锚点范式 | `git log --grep "DEPLOY-BUILD" \| wc -l` = **1** (0 → 1) ✓ |

## 8. 待办 (交主指挥)

1. **合并 `chore/deploy-build` → main 才会真正部署** (webhook 仅认 `refs/heads/main`)
2. 合并后建议 6 点 curl 验证 Content-Type (CLAUDE.md §Nginx octet-stream 白屏事故):
   `/index.html` `/` `/dashboard` `/assets/index-2bc54e5e.js` `/assets/index-06f87bc7.css` `/favicon.ico`
   — 任一返 `application/octet-stream` 即 nginx MIME 配置错
   (原清单中 `/sw.js` `/manifest.{hash}.webmanifest` 因 PWA 禁用不适用)
3. 部署后确认 `/var/log/webhook-deploy.log` 出现 "部署成功 ✓"
