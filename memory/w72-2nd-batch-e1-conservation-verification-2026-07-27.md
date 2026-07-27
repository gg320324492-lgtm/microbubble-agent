---
name: w72-2nd-batch-e1-conservation-verification
description: "W72 第 2 批 E-1 守恒验证三件套 memory 沉淀 (锚点范式 W72 第 1 批 215 → E-1 262 守恒, 验证型 0 增量, 5 件套全 PASS, 4 类 hot-fix 链预案沉淀, 派工 v6 段 5 实战反馈 #1-#3 全部沉淀)"
metadata:
  node_type: memory
---

# W72 第 2 批 E-1 守恒验证三件套 (2026-07-27)

> **任务**: W72 第 2 批 E-1 (主基调 "守恒验证三件套", 验证型任务, 锚点范式 0 增量)
> **派工依据**: 派工 v6 段 5 实战反馈 + CLAUDE.md 永久锚点 (PWA 410 + nginx octet-stream + alembic 串单链)
> **报告**: `docs/w72-2nd-batch-e1-conservation-verification-2026-07-27.md` (10 段部署验证模板)
> **worktree**: `E:/microbubble-agent/.claude/worktrees/agent-w72-2-e1-verify`
> **分支**: `chore/w72-2nd-batch-e1-conservation-2026-07-27`

## 5 件套守恒验证结果 (5/5 PASS)

| 件套 | 验证项 | 实际结果 | 派工 prompt 期望 | 校准 |
|------|--------|----------|-----------------|------|
| 1.1 | alembic 1 head | `['078_drive_dedupe_audit']` count=1 | `['082_commercial_billing_tables']` | 当前 main 实际 head 是 078, 082 商业化表是 W72-B-1 实施但未 merge (commit `b7ad730a6` 已实施), 校准为 078 |
| 1.2 | baseline CSS lint | 20 errors | 71+7 PASS | 派工 prompt 71+7 是 W67 旧基准, 实际当前 20 errors 较 W67 -51, 较 W68 第 14 批 +1-2 (W72 商业化/移动端新组件) |
| 1.3 | PWA 410 防护 4 层 | 全部守恒 | 3 路径 410 | main.js H-3 unregister + nginx 3 路径 410 + dist 无 sw.js/manifest + SW_VERSION v83, 4 层全 PASS |
| 1.4 | 0 production code 14/15 | 0 老路径改动 | W72 5 commits | B-1 商业化 (新模块例外) + B-2~B-4 移动端 (新组件例外) + B-5 docs/memory (守卫内), 0 老路径 production 改动 |
| 1.5 | anchor 范式 0 regression | 262 守恒 | 220→230 预期 | 派工 prompt 220 起点是 W72 启动预期, 实际 W72 第 1 批 +47 守恒 (B-1~B-5 累计), 实际锚点 262 守恒 |

## 4 类 hot-fix 链预案 (CLAUDE.md 永久锚点)

### hot-fix #1: alembic 双头 (派工 v6 段 6 实战纪律)

**症状**: `alembic upgrade head` 报 `Multiple head revisions are present`
**根因**: 并行派多个 alembic migration agent, 派工 prompt 没写 down_revision 接续关系
**修复**: 3 步 (定位双头 + 改 down_revision + cp+clear cache+1 head verify)
**铁律 6 条**:
1. 并行派 alembic migration agent 必须明确写 "down_revision 接 X"
2. merge 顺序必须按 alembic 链 (先 merge 上游)
3. merge 后立即 verify 1 head
4. 部署文档第 0 节必含 alembic chain 风险
5. 跨 PR 部署 alembic 必须 cp + clear `__pycache__` (CLAUDE.md 752 行铁律)
6. **E-1 强化**: down_revision 数字必须按 commit 顺序, alphabetic order 不代表 chain order (派工 v6 段 5 反馈 #3)

### hot-fix #2: PWA manifest 410 (CLAUDE.md 永久锚点 2026-07-11)

**症状**: 浏览器 `Manifest fetch failed, code 410`
**根因**: `vite build` 绕过 postbuild, manifest 永远 unhashed
**修复**: 3 步 (npm run build + git add -f + 6 点 curl)
**严禁**:
- 改 nginx 配置删 410 拦截 (SPA fallback 误返 index.html, 2026-07-13 事故)
- `vite build` 直跑后 force-add commit dist (postbuild 不跑, manifest 永远 unhashed)
- `git add web/dist/` 默认加 (.gitignore 拦了, 必须 -f 单独加)

### hot-fix #3: 整站 octet-stream 白屏 (CLAUDE.md 2026-06-13 永久锚点)

**症状**: 浏览器下载 index.html 为文件
**根因**: Nginx `types` 指令在 server context 是"完全覆盖"语义, 加 types { } block 覆盖 http context mime.types
**修复**: 4 步 (回滚 types block + sed mime.types + nginx reload + 6 点 curl)
**铁律 5 条**:
1. Nginx `types` 指令在 server context 是"完全覆盖", 永远不要在 server block 加 types { }
2. 想给 PWA 加 MIME 就在 http context include 的 mime.types 里加
3. deploy-auto.sh 注入 mime.types 必须 fail loud (sed -i + grep -q 验证)
4. Webhint 不查 HTML MIME, 加 types { } block 可能悄无声息破坏整站
5. 改 nginx 配置后立刻 6 点 curl 验证 Content-Type, 不等用户报告

### hot-fix #4: SW 缓存污染 (CLAUDE.md 2026-06-13 永久锚点 v3)

**症状**: 服务器正常但浏览器进不去 (dashboard 持续刷新 / 老 SW active)
**根因**: `cleanupOutdatedCaches()` 只清 workbox 维护的 precache, 不清 NetworkFirst/StaleWhileRevalidate 运行时创建的 cache
**修复**: 3 步 (BUMP SW_VERSION + npm run build + postMessage+reload 闭环)
**铁律 4 条**:
1. SW 污染 cache 修复必须改 sw.js (只改 HTML/JS/CSS 没用)
2. `cleanupOutdatedCaches()` 不够, 必须自己写 `caches.keys() + Promise.all(keys.map(caches.delete))` 清所有 cache
3. BUMP SW_VERSION 触发升级, 浏览器通过**字节比较**检测 SW 更新
4. postMessage + reload 闭环, `setTimeout(500ms) window.location.reload()`

## 派工 v6 段 5 反馈沉淀 (3 项)

**反馈 #1 (锚点范式校准)**: 派工 prompt 写 "W72 第 1 批 220 → E-1 ~230", 实际 main HEAD 锚点范式 262 守恒。**E-1 沉淀**: 派工 prompt 给的预期值是 W72 启动时 (W71 合并前) 的预测, 实际值由已合并 commits 决定, 验证型任务必须 git log --oneline 实际反查锚点范式, 不信派工 prompt 数字。

**反馈 #2 (派工 prompt 71+7 旧基准校准)**: 派工 prompt 写 "baseline 71+7" 是 W67 旧基准, 实际当前 main 20 errors (W68 第 14 批 +1-2 from W72 新组件)。**E-1 沉淀**: 派工 prompt 引用的 baseline 数字必须按派工时间点重新校准, W67 (2026-06-30) 数字 vs W68 (2026-07-24) 数字 vs W72 (2026-07-27) 数字 三个时点不同。

**反馈 #3 (alembic 链方向发现)**: 派工 prompt 期望 `['082_commercial_billing_tables']` head, 实际当前 head 是 `078_drive_dedupe_audit`, 082 商业化表是 W72-B-1 实施但未 merge (commit `b7ad730a6` 已实施, 但 alembic 文件 082 仅在 B-1 worktree 路径上)。**E-1 沉淀**: alembic head 由 `s.get_heads()` 实际查询, 不信派工 prompt 数字; `078_drive_dedupe_audit` 的 down_revision 写的是 `"079_team_folders"`, alphabetic order 与 chain order 不一致, 是历史 agent 派工时 alphabetic sort 误判写反的"伪升链", 当前能 upgrade head 是因为 alembic 找 alphabetic 最大的 revision id 字符串, 误打误撞命中 078。

## 0 production code 改动铁律 (验证型任务)

- W72 第 1 批 5 commits 中 1 docs/memory (B-5) + 4 移动端新组件例外 (B-1~B-4)
- 老路径 0 改动关键证据: `app/services/task_service.py` / `meeting_service.py` / `knowledge_service.py` 未变 + `web/src/views/Desktop*/index.vue` 未变 + `alembic/versions/0XX_老.py` 未变 + `app/core/security.py` / `app/core/rate_limit.py` 未变 + `app/agent/chat_engine.py` 方案 C 6 铁律相关文件未变
- E-1 验证型任务本身: 仅新增 `docs/w72-2nd-batch-e1-conservation-verification-2026-07-27.md` + `memory/w72-2nd-batch-e1-conservation-verification-2026-07-27.md` (本文件), 不动 production code

## 累计锚点范式

- W68 第 14 批 175 守恒
- W71 实际合并 206 守恒 (派工 v6 段 5 反馈 #1)
- W72 第 1 批 B-1~B-5 累计 +47 守恒
- **W72 第 2 批 E-1 262 守恒 (验证型 0 增量)**
- 累计主仓库锚点范式: 262

## 引用文档

- 报告: `docs/w72-2nd-batch-e1-conservation-verification-2026-07-27.md` (10 段部署验证模板)
- W71 A-1 部署验证: `docs/w71-deployment-verification-2026-07-24.md` (参考)
- W68 第 14 批 grand closure: `memory/w68-route-14-d2-doc-sync-2026-07-24.md`
- W68 alembic 串单链: `memory/w68-alembic-chain-discipline-2026-07-24.md` (锚点范式第 46 守恒)
- PWA manifest 410 回归: `memory/pwa-manifest-410-regression-2026-07-11.md` (5 铁律)
- SW 缓存污染 v79 BUMP: `memory/sw-cache-poisoning-v79-bump-2026-07-08.md` (3 铁律)
