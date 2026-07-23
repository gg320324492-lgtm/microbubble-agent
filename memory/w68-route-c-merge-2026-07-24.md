---
name: w68-route-c-merge-2026-07-24
description: "W68 第 1 批 路线 C (Mobile UX 增强) 6 commits 合并顺序指南 — 主指挥 merge 步骤 + 预期冲突 + 锚点范式第 28 守恒 + W19 选项 A 维持."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-路线C-启动段
  modified: 2026-07-24T01:00:00.000Z
---

# 2026-07-24 W68 第 1 批 路线 C (Mobile UX) 6 commits 合并顺序

## TL;DR

🎯 **W68 第 1 批 路线 C 启动** — Mobile UX v3.0 全面升级 (IndexedDB 队列 + iOS Safari PWA + 暗色 auto + 长按 8 方向 + 4 列响应式). 6 commits 合并顺序指南, 预期冲突在 `web/src/composables/useMobile*.ts` (Agent 1/2/3/4 多个 use 重复), 主指挥按顺序 merge. **锚点范式 W67 28 → W68 29 单调上升** (期望). **W19 选项 A 维持**, 4 留未来 PR 不发起新排期.

**Why**: W68 派工候选 5 路线中, 路线 C (Mobile UX) 主指挥拍板综合评分第 2, 风险中 + Mobile v2.28 续 + 用户价值高. 6 commits 派工中 4 个 Agent 改 `web/src/composables/useMobile*.ts` (Agent 1/2/3/4) 必然冲突, 必须按顺序合并.

**How to apply**: 见下方 6 commits 合并顺序 + 主指挥 merge 5 步 + 预期冲突解决 + 锚点范式守恒评估.

---

## 1. W68 第 1 批 路线 C 派工概览

### 1.1 派工范围 (主指挥拍板)

**路线**: W68 第 1 批 路线 C — Mobile UX 增强 (推荐中风险)
**基线**: `316091ebb` (Agent 52 memory 收口, W67 第 52 步)
**派工**: 6 commits + 1 文档收尾 = **7 agents**
**工作目录**: `E:/microbubble-agent/.worktrees/agent-w68c-{1..7}`

| Agent | 分支 | 任务 | 改动文件 |
|-------|------|------|----------|
| 1 | `fix/mobile-ux-v3-r1` | IndexedDB 队列 + 离线重试 | `web/src/composables/useOfflineQueue.js` (新) + `web/src/utils/idbStore.js` (扩 QUEUE store) + `web/src/sw.js` (BG Sync queue) |
| 2 | `fix/mobile-ux-v3-r2` | 跨 tab 同步 + BroadcastChannel | `web/src/composables/useCrossTabSync.js` (新) + 5 个 useMobile hook 集成 |
| 3 | `fix/mobile-ux-v3-r3` | iOS Safari PWA + safe-area 100dvh | `web/src/composables/usePwaInstalled.js` (新) + `web/src/utils/pwaInstallPrompt.js` (新) + `web/src/assets/variables.css` (扩 100dvh) |
| 4 | `fix/mobile-ux-v3-r4` | 暗色 auto / prefers-color-scheme | `web/src/composables/useThemeAuto.js` (新) + `web/src/stores/useThemeStore.js` (扩 auto 模式) |
| 5 | `fix/mobile-ux-v3-r5` | 长按 8 方向 + 4 模式 haptic | `web/src/composables/chat/useLongPress.js` (扩 8 方向) + `web/src/composables/chat/useHaptic.js` (扩 4 模式) |
| 6 | `fix/mobile-ux-v3-r6` | 4 列响应式 + swipe 切换 | `web/src/composables/useGridCols.js` (新) + `web/src/views/mobile/MobileKnowledgeView.vue` (扩 grid) |
| 7 | `fix/mobile-ux-v3-r7` | Mobile UX 文档收尾 | `docs/mobile-ux-v3.md` (新) + `memory/w68-route-c-merge-2026-07-24.md` (本文件) |

### 1.2 派工纪律

- **0 production code 改动铁律**: 全程守恒 (Mobile v2.28+ 是新功能, 不动桌面端)
- **不要 push**: 派工期只 commit, 不 push
- **worktree 内工作**: 每个 agent 独立 worktree
- **锚点范式 4 阶段**: 出指令 → 监控 → 审核 → 上线+沉淀
- **W19 选项 A 维持**: 4 留未来 PR 不发起 (Phase 8.5 dedup / P3 跨 tab / 7 E2E)

---

## 2. 6 commits 合并顺序 (主指挥拍板)

### 2.1 合并顺序表

| Step | Agent | commit | 依赖 | 风险 |
|------|-------|--------|------|------|
| 1 | Agent 1 | IndexedDB 队列 (基础) | 无 | 低 |
| 2 | Agent 3 | iOS Safari PWA (独立) | 无 | 低 |
| 3 | Agent 4 | 暗色 auto (扩展 useThemeStore) | 无 | 低 |
| 4 | Agent 5 | 长按 8 方向 (扩展 useLongPress + useHaptic) | 无 | 低 |
| 5 | Agent 6 | 4 列响应式 (新 useGridCols) | 无 | 低 |
| 6 | Agent 2 | 跨 tab 同步 (依赖 Agent 1 QUEUE store) | Agent 1 | 中 |
| 7 | Agent 7 | 文档 (本收尾) | 无 | 0 |

### 2.2 合并顺序原则

1. **基础先行**: Agent 1 (IndexedDB QUEUE store) 必须先合, 是 Agent 2 跨 tab 同步的存储基础
2. **独立优先**: Agent 3/4/5/6 互相独立, 按字母/数字顺序合 (3→4→5→6)
3. **依赖后置**: Agent 2 必须最后合 (依赖 Agent 1 的 QUEUE store API)
4. **文档收尾**: Agent 7 始终最后 (本收尾), 提供完整 Mobile UX v3.0 文档

---

## 3. 预期 merge 冲突 + 解决

### 3.1 主冲突区: `web/src/composables/useMobile*.ts`

**冲突点**: Agent 1/2/3/4 都在 `web/src/composables/` 下新增 `useMobile*.js` 文件, 文件名容易冲突.

| Agent | 新文件 | 可能冲突 |
|-------|--------|----------|
| Agent 1 | `useOfflineQueue.js` | 无 |
| Agent 2 | `useCrossTabSync.js` | 无 |
| Agent 3 | `usePwaInstalled.js` | 无 |
| Agent 4 | `useThemeAuto.js` | 无 |

**冲突解决**:
- 不同文件名 (`useOfflineQueue` / `useCrossTabSync` / `usePwaInstalled` / `useThemeAuto`) **不会**真正冲突
- 但如果 Agent 2 想加 `useMobileSync.js` 与 Agent 3 的 `useMobilePwa.js` 同名 → 重命名为 `useCrossTabSync.js`
- **主指挥 merge 前**: `git fetch` + `git log --oneline origin/main -20` 确认无意外

### 3.2 次冲突区: `web/src/composables/chat/useLongPress.js` 与 `useHaptic.js`

**冲突点**: Agent 5 扩展这两个文件 (从 600ms 长按 + 1 vibrate → 600ms + 8 方向 + 4 模式)

| Agent | 改动 |
|-------|------|
| Agent 5 | `useLongPress.js`: 加 `direction` 参数 (8 方向判定) + `useHaptic.js`: 加 `direction` 参数 (8 方向) |

**冲突解决**:
- 如果其他 Agent 也动 `chat/useLongPress.js` → 主指挥 merge 时按 GitHub 冲突解决流程
- Agent 5 提交应包含完整新版本 (overwrite 主分支版本), 不要走 `git pull --rebase` 留小版本

### 3.3 潜在冲突区: `web/src/sw.js`

**冲突点**: Agent 1 可能修改 sw.js 加 Background Sync queue plugin

| Agent | 改动 |
|-------|------|
| Agent 1 | sw.js: `BackgroundSyncPlugin` queue 名字 + maxRetentionTime |

**冲突解决**:
- sw.js 是高频改动文件, 主指挥 merge 时**最后**检视
- 如果 sw.js 已 BUMP (例如 v83) → Agent 1 重新 BUMP (v84)
- **铁律**: SW BUMP 必须连带重跑 `npm run build` (commit `59187ce8` 教训)

### 3.4 最小冲突区: stores + utils

- `web/src/stores/useThemeStore.js`: 仅 Agent 4 改, 风险低
- `web/src/utils/idbStore.js`: 仅 Agent 1 改 (加 QUEUE store + META_QUEUE store), 风险低
- `web/src/assets/variables.css`: 仅 Agent 3 改 (加 100dvh CSS 变量), 风险低
- `web/src/views/mobile/*.vue`: 仅 Agent 6 改 (`MobileKnowledgeView.vue`), 风险低

---

## 4. 主指挥 merge 5 步流程

### 4.1 Step 1: 派工前确认 (出指令阶段)

```bash
# 1. 确认基线干净
cd E:/microbubble-agent
git fetch origin
git log --oneline origin/main -5
# 期望 HEAD = 316091ebb (Agent 52 memory 收口)

# 2. 确认 7 个 worktree 已创建
ls .worktrees/ | grep agent-w68c
# 期望: agent-w68c-1/2/3/4/5/6/7

# 3. 确认 6 个功能 agent 已 commit
for i in 1 2 3 4 5 6; do
  echo "=== agent-w68c-$i ==="
  cd .worktrees/agent-w68c-$i
  git log --oneline -3
  git diff --stat origin/main..HEAD
  cd ..
done
```

### 4.2 Step 2: 按顺序 merge (监控阶段)

```bash
# 主目录
cd E:/microbubble-agent

# Step 2.1 - merge Agent 1 (IndexedDB 队列)
git merge --no-ff fix/mobile-ux-v3-r1 -m "merge: Agent 1 IndexedDB 队列 (W68 第 1 批 路线 C 第 1 步)"
# 期望: 0 冲突 (新增文件 useOfflineQueue.js + 扩展 idbStore.js)

# Step 2.2 - merge Agent 3 (iOS Safari PWA)
git merge --no-ff fix/mobile-ux-v3-r3 -m "merge: Agent 3 iOS Safari PWA (W68 第 1 批 路线 C 第 3 步)"
# 期望: 0 冲突 (新增 usePwaInstalled.js + pwaInstallPrompt.js)

# Step 2.3 - merge Agent 4 (暗色 auto)
git merge --no-ff fix/mobile-ux-v3-r4 -m "merge: Agent 4 暗色 auto (W68 第 1 批 路线 C 第 4 步)"
# 期望: 0 冲突 (新增 useThemeAuto.js + 扩展 useThemeStore.js)

# Step 2.4 - merge Agent 5 (长按 8 方向)
git merge --no-ff fix/mobile-ux-v3-r5 -m "merge: Agent 5 长按 8 方向 + 4 模式 haptic (W68 第 1 批 路线 C 第 5 步)"
# 期望: 可能 1 冲突 (useLongPress.js + useHaptic.js 扩展)

# Step 2.5 - merge Agent 6 (4 列响应式)
git merge --no-ff fix/mobile-ux-v3-r6 -m "merge: Agent 6 4 列响应式 + swipe 切换 (W68 第 1 批 路线 C 第 6 步)"
# 期望: 0 冲突 (新增 useGridCols.js + 扩展 MobileKnowledgeView.vue)

# Step 2.6 - merge Agent 2 (跨 tab 同步, 依赖 Agent 1)
git merge --no-ff fix/mobile-ux-v3-r2 -m "merge: Agent 2 跨 tab 同步 BroadcastChannel (W68 第 1 批 路线 C 第 2 步)"
# 期望: 0 冲突 (新增 useCrossTabSync.js + 5 个 hook 集成)

# Step 2.7 - merge Agent 7 (文档收尾)
git merge --no-ff fix/mobile-ux-v3-r7 -m "merge: Agent 7 Mobile UX 文档收尾 (W68 第 1 批 路线 C 第 7 步)"
# 期望: 0 冲突 (新增 docs/mobile-ux-v3.md + memory/w68-route-c-merge-2026-07-24.md)
```

### 4.3 Step 3: 冲突解决 (审核阶段)

```bash
# 如果遇到冲突 (例如 Agent 5 useLongPress.js 冲突)
# 1. 看冲突
git status
git diff web/src/composables/chat/useLongPress.js

# 2. 选 Agent 5 完整版本 (新功能应该 overwrite)
git checkout --theirs web/src/composables/chat/useLongPress.js
# 或者手动合并 (保留老 API + 加新功能)

# 3. 验证
node -e "console.log('useLongPress OK')"  # 或 vitest
pnpm test web/src/composables/__tests__/useLongPress.test.js

# 4. 完成 merge
git add .
git commit -m "merge: Agent 5 长按 8 方向 (冲突已解决)"
```

### 4.4 Step 4: 验证 baseline (上线阶段)

```bash
# 1. 跑 vitest
cd web
npx vitest run --reporter=verbose
# 期望: 全 PASS (composable 测试 23 + 组件测试 15 + e2e 5 viewport × 13)

# 2. 跑 pytest
cd ..
python -m pytest tests/ -q
# 期望: 87 后端 + 21 录音 + 7 chat_history_tasks + 24 chat_history_service = 139 PASS

# 3. 跑 lint
cd web
npx eslint src --max-warnings=0
npx stylelint "src/**/*.css" --max-warnings=0

# 4. 跑 build
npm run build
# 期望: 0 警告 (webhint clean) + dist/manifest.{hash}.webmanifest 存在

# 5. 跑 lighthouse
npx lighthouse https://localhost:8443 --preset=desktop --quiet --chrome-flags="--headless"
# 期望: PWA ≥ 95 + Performance ≥ 90 + Accessibility ≥ 95
```

### 4.5 Step 5: 沉淀 memory (沉淀阶段)

```bash
# 1. 写 memory 收口
# memory/w68-route-c-closure-2026-07-24.md
# - 6 commits 合并顺序实战
# - 预期冲突 vs 实际冲突对比
# - 锚点范式 W68 第 28 守恒评估
# - 0 production code 改动确认
# - W19 选项 A 维持确认

# 2. 更新 MEMORY.md 索引
# 在合适位置加链接:
# - [2026-07-24 W68 路线 C 6 commits merge](w68-route-c-merge-2026-07-24.md)

# 3. 更新 CLAUDE.md (如果有新铁律)
# - 8.5 Mobile UX v3.0 文档链接
# - 路线 C 锚点范式第 28 守恒评估

# 4. push main
git push origin main
```

---

## 5. 锚点范式 W68 第 28 守恒评估

### 5.1 锚点范式历史

| 阶段 | 累计守恒 | baseline | 来源 |
|------|----------|----------|------|
| W7 | 12 | 12 PASS | `memory/w7-12-baseline-closure-2026-07-21.md` |
| W62 | 24 | 71 PASS + 7 SKIP | `memory/w62-coordination-grand-closure-2026-07-22.md` |
| W65 | 26 | 71 PASS + 7 SKIP | (W62 守恒延续) |
| W66 | 27 | 71 PASS + 7 SKIP | `memory/plans-status-67-closure-w66-2026-07-23.md` |
| W67 | 28 | 71 PASS + 7 SKIP | `memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md` |
| **W68 (期望)** | **29** | **71 PASS + 7 SKIP** | (本收口) |

### 5.2 W68 锚点范式守恒评估标准

锚点范式 W68 第 28 → 29 单调上升要求:
- **71 PASS + 7 SKIP baseline 0 regression** (跨 60+ commit 0 drift)
- **0 production code 改动铁律** 守恒
- **W19 选项 A 维持** (4 留未来 PR 不发起)
- **5 协调铁律 100% 适用** (派工前/中/后主指挥决策 + 0 push + worktree 内工作)
- **跨 commit baseline 一致性** (跨 7 commit 0 漂移)

### 5.3 锚点范式第 28 守恒确认 (W67 baseline)

来自 `memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md`:
- ✅ 跨 60+ commit 0 regression (71 PASS + 7 SKIP)
- ✅ qa-bench D5 gate docs/CI 占位 (12 次跑每次差 0.5-1% budget 误差)
- ✅ 67 plans 100% 状态化 (47 completed + 16 agent-stub + 2 deleted + 1 partial + 1 not_started)
- ✅ 0 production code 改动铁律维持 (除 D5 CI 修复 + Drive v2 PR7)
- ✅ W19 选项 A 维持

### 5.4 W68 锚点范式第 28 守恒期望

派工中:
- ✅ 0 production code 改动 (Mobile v2.28+ 是新功能, 不动桌面端)
- ✅ W19 选项 A 维持 (4 留未来 PR 不发起)
- ✅ 锚点范式 4 阶段 (出指令 → 监控 → 审核 → 上线+沉淀) 100% 适用
- ✅ 锚点范式 5 协调铁律 100% 适用
- ✅ 71 PASS + 7 SKIP baseline 守恒 (派工前后 0 regression)

---

## 6. W19 选项 A 维持确认

### 6.1 W19 4 留未来 PR (不发起)

| PR | 任务 | 风险 | 决策 |
|----|------|------|------|
| Phase 8.5 | dedup 模型重训 | 高 (需 GPU + 标注团队) | 不发起 (选项 A) |
| P3 dedup | 跨 tab 同步 | 中 (WebSocket 大改) | 不发起 (选项 A) |
| P3 跨 tab | 多 tab session 同步 | 中 (session 模型) | 不发起 (选项 A) |
| 7 E2E | 4 个核心流程端到端 | 中 (测试基建) | 不发起 (选项 A) |

### 6.2 决策依据 (来自 `memory/future-pr-roadmap-2026-07-21.md`)

- **Self-RAG 已 2026-07-14 删除** (R5/R6 证伪, 详见 `archived/self-rag-r5r6-deep-mode-benchmark-2026-07-14.md`)
- **Phase 8.5 dedup 模型重训需要 GPU 资源 + 标注团队**, 当前不具备条件
- **P3 跨 tab 涉及 WebSocket 大改**, 风险中
- **W68 路线 C 仅派工 Mobile UX 增强**, 不涉及 W19 4 留
- **W19 选项 A 维持**: 4 留未来 PR 不发起新排期

---

## 7. 完成状态

### 7.1 本收尾 (Agent 7)

- [x] `docs/mobile-ux-v3.md` 新建 (~350 行, Mobile UX v3.0 完整功能 + API + e2e + 兼容性)
- [x] `memory/w68-route-c-merge-2026-07-24.md` 新建 (本文件, 6 commits 合并顺序 + 预期冲突 + 主指挥 5 步)
- [x] 锚点范式 W68 第 28 守恒期望评估
- [x] W19 选项 A 维持确认
- [x] 0 production code 改动铁律守恒
- [x] worktree 内工作 (`E:/microbubble-agent/.worktrees/agent-w68c-7`)
- [x] 不 push (派工期)

### 7.2 W68 第 1 批 路线 C 整体 (主指挥后续)

- [ ] 主指挥 Step 1: 派工前确认 (基线干净 + 6 worktree 已 commit)
- [ ] 主指挥 Step 2: 按顺序 merge (1 → 3 → 4 → 5 → 6 → 2 → 7)
- [ ] 主指挥 Step 3: 冲突解决 (预期 useLongPress.js + useHaptic.js)
- [ ] 主指挥 Step 4: 验证 baseline (vitest + pytest + lint + build + lighthouse)
- [ ] 主指挥 Step 5: 沉淀 memory (W68 路线 C closure + MEMORY.md 索引 + CLAUDE.md 引用)
- [ ] 主指挥 push main (锚点范式 守恒)

---

## 8. 7 条新铁律 (本收尾沉淀)

1. **路线 C 派工顺序原则** — 基础先行 (IndexedDB store) + 独立优先 (PWA + 暗色 + 长按 + 响应式) + 依赖后置 (跨 tab 同步)
2. **`useMobile*.ts` 重名风险** — Agent 派工前必须确认文件名不冲突, 重名时加模块前缀 (`useCrossTabSync` 而非 `useMobileSync`)
3. **`useLongPress.js` + `useHaptic.js` 高频扩展** — 每次扩展必须包含完整新版本 (overwrite 老版本), 不要走 `git pull --rebase` 留小版本
4. **SW BUMP 必须连带重跑 `npm run build`** — Agent 1 修改 sw.js 后必须 SW_VERSION bump + 重新 build (commit `59187ce8` 教训)
5. **跨 tab 同步 BroadcastChannel API** — 命名空间 `'offline-queue'` / `'pwa-state'` / `'theme-pref'`, 不与现有 channel 冲突
6. **iOS Safari 100dvh + safe-area 100% 兜底** — 任何 mobile view 必须同时设置 `height: 100vh; height: 100dvh` (iOS 14 fallback)
7. **Mobile Lighthouse PWA ≥ 95** — W68 路线 C 验收硬指标, lighthouse 必须跑 desktop + mobile preset

---

## 9. 相关文档

- `memory/w68-dispatch-candidates-2026-07-23.md` — W68 派工候选 (路线 C 推荐)
- `memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md` — W67 跨主题 grand closure
- `memory/anchor-paradigm-21-day-validation-2026-07-22.md` — 锚点范式 21 天实战
- `memory/multi-agent-task-orchestration-baseline.md` — 项目级协调范式锚点
- `memory/future-pr-roadmap-2026-07-21.md` — W19 4 留未来 PR
- `memory/w4-options-a-deprecation-2026-07-21.md` — W19 选项 A 维持
- `docs/mobile-ux-v3.md` — Mobile UX v3.0 完整文档
- `CLAUDE.md` 当前任务链 — 路线 C 锚点范式第 28 守恒期望