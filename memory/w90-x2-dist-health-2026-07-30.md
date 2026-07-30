# W90-X-2 dist_health orphan chunk 修复 — 据实上报 BLOCKED

## 任务定义

W89-X-17 据实: `dist/index.html` 缺 `index-be8f90c0.js` (W87 B-1 cherry-pick 改 deps 未重跑 build)。
本任务: `npm run build` 重跑 + dist 完整性验证 + e2e 守卫。

## 工作目录

- 新 worktree: `E:\agent-w90-x2-dist-health`
- 新分支: `claude/w90-x2-dist-health`
- base ref: `034343f8a` (main tip 实测, 锚点 463)

## 步骤 1 — 当前状态校核

**确认根因 (= W89-X-17 据实)**:

```
$ grep -oE 'index-[a-f0-9]+\.js' web/dist/index.html | sort -u
index-d64e7046.js

$ ls web/dist/assets/index-*.js
web/dist/assets/index-be8f90c0.js   (130 KB)
web/dist/assets/index-d64e7046.js
```

- `index-d64e7046.js` 是 index.html 实际引用的 entry
- `index-be8f90c0.js` 是 orphan (在 dist 但 index.html 未引用)
- e2e 测试 `tests/dist_health/test_no_orphan_index_chunks` 直接断言 FAIL:
  ```
  AssertionError: orphan index chunks (在 dist 但 index.html 未引用): {'be8f90c0'}
  ```

**orphan 来源回溯** (`git log -- web/dist/assets/index-be8f90c0.js`):
- 引入 commit: `ddb7ab93c [merge-01 W89] merge: PR6 SearchLog 前端接通`
- 这是 W91+W89 PR6 SearchLog merge 时带入, **不是 W87 B-1 cherry-pick**
- 派工 brief 假设的"W87 B-1 cherry-pick 改 deps 未重跑 build" 只是一例 history 案例,
  **当前 main 的实际 orphan 来自 W91 PR6 merge**

## 步骤 2 — 真跑 `npm run build` (CLAUDE.md 永久纪律)

```
$ cd web && npm install && npm run build
```

**预期**: postbuild-fix-manifest.js 自动跑 3 件事 + 健全性自检, build 成功。

**实际 — BUILD FAIL**:
```
src/views/admin/RAGEvalPanel.vue (24:18): "Play" is not exported
  by "node_modules/@element-plus/icons-vue/dist/index.js"

  24: import { Refresh, Play, DataAnalysis } from '@element-plus/icons-vue'
                       ^^^^
```

**根因 (派工前主指挥未察觉)**:
- PR5 W91 commit `cb5c98498 feat(pwa): RAGEvalPanel.vue + useRAGEval.js + router (PR6 模式对齐)`
  引入 `web/src/views/admin/RAGEvalPanel.vue` 含 `import { ..., Play, ... } from '@element-plus/icons-vue'`
- `@element-plus/icons-vue` v2.x **不导出 `Play`** (Element Plus 改名为 `VideoPlay`)
- `grep -E 'Play' node_modules/@element-plus/icons-vue/dist/index.js` → `name: "VideoPlay"`, 没有 `Play` 导出
- 这是 **W91 PR5 引入的 build regression**, 既不属于 W87 B-1 案, 也不属于本 X-2 scope
- 派工 brief 假设 build 可一键成功, **实际 build 因 PR5 已 break**

## 步骤 3 — 边界复检 (严格遵守)

派工 brief 规定:
- **允许改**: `web/dist/**` (force-add), `web/package.json` / `web/package-lock.json` (若 build 改了), `memory/w90-x2-dist-health-2026-07-30.md` (新)
- **禁止改**: 业务代码 (`web/src/`、`alembic/`、`nginx/`、`docker/`、`commercial/`)

RAGEvalPanel.vue Play → VideoPlay 修复在 `web/src/views/admin/RAGEvalPanel.vue` (line 24) —
**`web/src/` 业务代码, 严格禁止改**。

即使 X-2 派工前主指挥已批 RAGEvalPanel 修复, 本任务 brief 仍明确划入"禁止改"区段。
主指挥应单独派 WR-1 (web/src/admin RAGEvalPanel.vue icon 修复) → 解 build 不再 block → 本 X-2 即可走 `npm run build` 跑通 dist refresh。

## 步骤 4 — e2e 验证

```bash
$ SKIP_DB_SETUP=1 pytest tests/dist_health/ -v
FAILED tests/dist_health/test_no_orphan_chunks.py::test_no_orphan_index_chunks
  AssertionError: orphan index chunks (在 dist 但 index.html 未引用): {'be8f90c0'}
1 failed, 2 passed, 1 warning
```

`test_manifest_hash_pinned` PASS (PWA manifest 410 防护生效)。
`test_sw_version_consistent` PASS (sw.js 不存在, PWA 已禁用)。

## 步骤 5 — 不擅自扩 ≈ 派工 v6 §5 反馈 #13 实战

派工 v6 §5 反馈 #13 锚点: "派工前提错配不擅自扩 — 实际上没基础做的不假装做了"。
本任务 = **BLOCKED** (派工前提 = build 可一键成功, 实际 = PR5 regression 阻塞)。

**未做的事**:
- 未删除 `web/dist/assets/index-be8f90c0.js` (因为它通过 `__vite__mapDeps` 被 100+ 其他 chunks 引用,
  单独删除会让其余 chunks 运行时 `FetchError: 404` — 比 orphan 更糟)
- 未提交 dist refresh commit (build 失败, 无 fresh dist 可 commit)
- 未手改 `web/src/views/admin/RAGEvalPanel.vue` (非本任务 scope)

## 步骤 6 — 类 20.85 沉淀 (派工 v6 §5 反馈)

**类 20.85 新增**: "dist_health 修复必经 npm run build 真跑 (不仅 git 历史) —

(a) dist refresh 派工 brief 必先 `npm run build` 真跑确认 source 可编译
(b) 不基于"git log 显示曾经 build 过"假设, 因为后续 source commit 可能 break
(c) 发现 orphan + build fail = 派工前提错配, 不擅自扩改 source, 应新派 scope 修 source
(d) 留口: 派工 brief 加 `"build_status": "PASS"` 段, 派工前主指挥必实测"

**完整类 20 累计 38 实例** (W90 +1): 20.1-20.36 + 20.46 + **20.85 (W90-X-2)**。

## 步骤 7 — 报告

**X-2 BLOCKED — 等 PR5 W91 RAGEvalPanel.vue Play icon 修复**:

| 项 | 状态 |
|---|---|
| orphan be8f90c0.js 确认 | YES |
| npm run build 真跑 | FAIL (PR5 regression) |
| dist refresh commit | NO (block) |
| e2e 守卫 test | 已存在 (W87-X-2 commit 223ae469b), 重命名建议 |
| 锚点增量 | 0 (本任务为调研 + 据实上报) |
| 派工 brief 假设 | 类 20.13 错配 (W89-X-17 据实 = W91 PR6 merge, 不仅是 W87 B-1) |

**主指挥 next step**:

1. 派 **WR-1** = `web/src/views/admin/RAGEvalPanel.vue` 改 `Play` → `VideoPlay` (import + 用法 2 处)
2. WR-1 commit 合并后, 主指挥重派 X-2 (或直接接力) → `npm run build` 跑通 → dist refresh commit
3. dist refresh commit 跑 `pytest tests/dist_health/` PASS → X-2 close

## 步骤 8 — 不 commit 业务代码

本任务:**只写 memory/, 不 commit 任何代码 / dist 改动**。

派工 v6 §5 反馈 #13 实战: 派工前提错配 → 不擅自扩 → 报告主指挥 → 重派 / 接力。

## 教训

1. **`npm run build` 真跑是 dist_health 派的硬门禁** — 不能基于 git log 推断 build 状态。
   后续 dist refresh 派工 brief 必加 `build_status: PASS` 字段, 主指挥派工前实测。
2. **orphan 与 __vite__mapDeps 联动** — 不能孤立删除 orphan (会引发 100+ chunks 运行时 404),
   必须 rebuild 整个 dist 才能彻底解。
3. **dist 引入源头 = merge commit, 不一定是 cherry-pick** — W91 PR6 merge 与 W87 B-1 cherry-pick
   两种路径都可能引入 orphan, 派工 brief 简化为 "W87 B-1" 是 shorthand误指。
4. **W91 PR5 build regression 是 X-2 真正阻塞** — 与 W87 B-1 案同源 (都因 deps 变 / 源码 没重跑 build),
   但触发点是 Vue 文件 import 错误 (Play icon), 比 dep 变更更隐蔽。

## 锚点范式

- base: `034343f8a` (main tip, 锚点 463)
- tip: `034343f8a` (本任务不 commit 业务代码, 锚点守恒)
- **0 增量** (X-2 BLOCKED, 调研 + 报告为主)
- 0 production code 改动铁律 1/1 守恒 (本任务唯一改动 = memory 文件, 强制例外已实测)
