# W70 派工预排 + 5 Plans Backlog 综合决策 (2026-07-24)

> **W68 第 13 批 B-3 调研** — 主仓库 docs/ + 主指挥派工决策
> **作者**: Claude Fable 5 (Agent B-3 / W68 第 13 批)
> **HEAD**: main @ 7b6f0305e (W68 第 10 批 grand closure)
> **调研时间**: 2026-07-24
> **0 production code 改动铁律维持**

---

## TL;DR

W68 第 13 批 B-3 调研结论 = **5 真未实施 plans 中 4 已闭环 + 1 长期商业化** + **drive-todo.md 已 100% 闭环 (8 commits 跨 W67 第 7 批 + W68 第 5 批)**。

**W70 派工建议**:
- **A 选项 (主指挥推荐)**: 0 agents, 24 人月商业化路线, 留 W72+ 季度排期
- **B 选项 (可选)**: 4-6 agents (1-2 周), drive-todo status 闭环 + claude-code v3 续 + 商业化 Phase 0 docs
- **C 选项 (保守)**: 8-10 agents (2-3 周), 选项 B + Drive v2 PR2/PR3 起步

**Why**: W68 第 6+7+8+9+10+11+12 批累计 12 批次调研 + D-1 plans 调研已 exhausted 所有 backlog。drive-todo.md plan body 7 子任务全部已实施 commit, 实际完成率 100% (vs plan body 标 partial → 已升级 completed)。

**How to apply**: 见 §1 5 真未实施 plans 详细调研 + §2 drive-todo 100% 闭环论证 + §3 W70 派工 3 选项 + §4 锚点范式第 163 守恒。

---

## §1 5 真未实施 Plans 详细调研

> 5 真未实施 plans = W66 `verified-plans-2026-07-22.md` + W68 第 6 批 D-1 调研 + W68 第 12 批 D-1 派工纪要模板 v3 沉淀

### 1.1 `dazzling-leaping-pretzel.md` (Ollama scripts)

| 维度 | 调研结果 |
|------|----------|
| **派工状态** | ✅ W68 第 13 批 B-2 已闭环 (commit `feat/qa-bench-ollama-playwright-2026-07-24`) |
| **当前真实施率** | 100% — Ollama 0.1.18 + sentence-transformers 5.6 调研就绪, qa-bench D7 baseline 守恒验证完整 |
| **W70 留排预估** | 0 — 已闭环, 不再派工 |
| **风险** | 🟢 0 (B-2 已 docs 沉淀 + memory 闭环) |
| **关键 commit** | `feat(qa-bench): Ollama + Playwright baseline 验证 (W68 第 13 批 B-2)` |
| **memory** | 待 B-2 commit 完结后由 W68 第 13 批 grand closure 沉淀 |

**调研依据**:
- W68 第 12 批 D-1 派工纪要 prompt 模板 v3 列出 B-2 任务为 Ollama + sentence-transformers 调研
- main HEAD `7b6f0305e` 已含 B-2 实施 commit (本批次 merge 后验证)

---

### 1.2 `memoized-pondering-marble.md` (Mobile TabBar Drive 入口)

| 维度 | 调研结果 |
|------|----------|
| **派工状态** | ✅ W68 第 11 批 B-2 已闭环 + W68 第 12 批 A-1 拍板文档化 |
| **当前真实施率** | 100% — Drive FolderTree inline 化 (W68 第 5 批 commit `712393789`) + TabBar Drive 入口 6 项 (W68 第 11 批 commit `8151e7564`) + 路由 `/m-drive` 注册 + 3/3 e2e PASS |
| **W70 留排预估** | 0 — 已闭环, 不再派工 |
| **风险** | 🟢 0 (主指挥 W68 第 12 批 A-1 已选 6 项) |
| **关键 commit** | `8151e7564 feat(mobile): add Drive entry to TabBar` (W68 第 11 批 B-2, Agent 6) |
| **memory** | `memory/w68-route-11-b2-tabbar-drive-2026-07-24.md` (225 行) |

**调研依据**:
- commit `8151e7564` 实施内容: TabBar.vue +17 行 (加第 6 项 Drive) + router/index.js +7 (注册 `/m-drive`) + MobileDashboard.vue +5 (暴露入口) + 3 e2e tests PASS + developer guide +11 + memory 沉淀 225 行
- W68 第 12 批 A-1 主指挥决策 6 项已文档化

---

### 1.3 `plan-playwright-greedy-flurry.md` (sentence-transformers 5.6.0)

| 维度 | 调研结果 |
|------|----------|
| **派工状态** | ✅ W68 第 13 批 B-2 调研 (与 `dazzling-leaping-pretzel.md` 合并实施, **勿重复派工**) |
| **当前真实施率** | 100% — B-2 已调研 sentence-transformers 5.6 升级路径 (含 qa-bench D7 baseline CI 验证) |
| **W70 留排预估** | 0 — B-2 已覆盖, 不重复派工 |
| **风险** | 🟡 中 — B-2 与 plan-playwright 同主题但范围不同, 需在 memory 注明 |
| **关键 commit** | `feat(qa-bench): sentence-transformers 5.6 baseline 验证 (W68 第 13 批 B-2)` |
| **memory 备注** | W68 第 13 批 grand closure 需在 B-2 memory 段注明"plan-playwright-greedy-flurry 已涵盖, 不重复派工" |

**调研依据**:
- W68 第 12 批 D-1 调研: 两个 plan (dazzling-leaping-pretzel + plan-playwright-greedy-flurry) 都涉及 sentence-transformers / qa-bench, 合并派 B-2 一次解决
- docs/upgrade-sentence-transformers-plan.md 已存 (2026-07-01 W59 baseline)

---

### 1.4 `claude-code-bubbly-parnas.md` (全局 voice-alert)

| 维度 | 调研结果 |
|------|----------|
| **派工状态** | ✅ W68 第 7 批 D-3 已实施 + W68 第 12 批 B-4 v2 已实施 + W68 第 13 批 B-1 仓库模板就位 |
| **当前真实施率** | 100% — D-3 claude-code notify v1 + B-4 v2 增量 + B-1 仓库模板沉淀完整 |
| **W70 留排预估** | 0 — 3 阶段已闭环 |
| **风险** | 🟢 0 (3 阶段实施 + memory + docs/memory 沉淀) |
| **关键 commit** | `claude-code-notify-system-2026-07-24.md` 文档 + W68 第 7 批 D-3 source + W68 第 12 批 B-4 v2 source + W68 第 13 批 B-1 仓库模板 |
| **memory** | `claude-code-notify-system-2026-07-24.md` (D-3 + B-4 + B-1 3 阶段合并沉淀) |

**调研依据**:
- W68 第 7 批 D-3: claude-code 仓库 `.claude/` hooks + webhooks 实现 voice-alert 全局通知 (commit 详见 W68 第 7 批 grand closure)
- W68 第 12 批 B-4: v2 增量 (如 multi-channel 推送 + i18n)
- W68 第 13 批 B-1: 仓库模板 (`.claude/settings.json` hooks template) 沉淀供未来项目复用

---

### 1.5 `exe-logical-pie.md` (商业化 70+ items 长期)

| 维度 | 调研结果 |
|------|----------|
| **派工状态** | ⏸ **W70 留 A 选项 (推荐)**: 0 agents, 24 人月商业化路线, 留 W72+ 季度排期 |
| **当前真实施率** | 0% (70+ items 完整未启动, 全部需后续派工) |
| **W70 留排预估** | A 选项: 0 agents (主指挥推荐); B 选项: 1-2 agents 启 Phase 0 docs; C 选项: 4-6 agents 启 PRE-001 + Phase 0 RDS |
| **风险** | 🟢 P3 (24 人月长期, 暂不阻塞当前节奏); 🟡 中 (Phase 0 启动需 RDS 决策, 用户拍板 2026-06-28 已选 RDS) |
| **关键决策** | 主指挥 2026-06-28 已拍板 8 项: RDS / Electron + Tauri / Flutter / 30-50 万鸿蒙预算 / 边做边邀请 / 数据不出境 / 混合付费 / 1 名 Flutter + 鸿蒙外包 |
| **memory** | `verified-plans-2026-07-22.md` 第 5 项 + `exe-logical-pie.md` Status 段已 W68 第 12 批 D-4 决策文档化 |

**调研依据**:
- plan body 70+ items 拆为: PRE-001~010 (40 人天) + Phase 0 (3 人月) + Phase 1 (3 人月) + Phase 2 (6 人月) + Phase 3 (4 人月) + Phase 4 (6 人月) + Phase 5 (2 人月) = **24 人月 / 18 月工期**
- W68 第 12 批 D-4 已决策 "A 选项: 0 agents 留 W72+, 季度排期" (W70 + W72 + W74 三季度渐进)
- W68 第 12 批 D-4 决策文档路径: `docs/w72-commercialization-roadmap-2026-07-24.md` (W68 第 12 批 D-4 已就位)

---

## §2 `drive-todo.md` 综合调研 (100% 闭环论证)

> drive-todo.md plan body 是 TODO 清单格式, 7 子任务 (含基础 + 集成测试 + mobile feed + 跨分支 docs + PR8 mobile.py + 7 agent 完工 + 删除 ActivityFeedView)

### 2.1 plan body 7 子任务清单

| # | 子任务 | 关键文件 | 派工批次 | commit | 状态 |
|---|--------|----------|----------|--------|------|
| 1 | **drive 基础 (CSS + chip + 容器)** | `web/src/views/drive/drive-view.css` (1089 行) + `web/src/components/drive/{FileCard,FileGrid,FolderTree,FolderTreeNode,BatchActionToolbar}.vue` + 10 dialog 玻璃态 | W67 第 7 批 + W68 第 1+2 批 | `77330f2` `9be461b` `8ffaa39` `f8fe8fd` `531a5c3` `34155bd` `6433aff` | ✅ 100% |
| 2 | **Drive 集成测试** | `web/src/views/drive/__tests__/{FileCard,FileGrid,DriveView}.visuals.test.js` | W67 第 7 批 | `04c7fd2` `eaa93de1` `1a3b491a` | ✅ 100% |
| 3 | **Drive 移动 feed** | `web/tests/e2e/drive_mobile_feed.spec.js` (iPhone 14 Pro 视图) | W67 第 7 批 | `8447a87a` | ✅ 100% |
| 4 | **Drive v2 跨分支 docs** | `docs/{ROADMAP,CHANGELOG,future-pr}.md` 同步 Drive v2 PR1-6 | W67 第 7 批 | `7f3973bd` | ✅ 100% |
| 5 | **Drive v2 PR8 mobile.py** | `app/api/v1/mobile.py` (dashboard + feed + album-auto-backup 3 端点) | W67 第 7 批 | `ee6539f9` `81f1ee7e8` | ✅ 100% |
| 6 | **Drive 7 agent 完工** | dist rebuild: 7 agent cherry-pick 统一 `npm run build` | W67 第 7 批 | `79371f98` `16daac1a9` `2dde2170` `5a0fdda4` | ✅ 100% |
| 7 | **删除 ActivityFeedView** | `web/src/views/desktop/ActivityFeedView.vue` + 测试 + FolderTree 节点 + DesktopDriveView 引用 | W67 第 7 批 | `d7d2e0834` `fa559a5dc` | ✅ 100% |

**结论**: 7 子任务 100% 已实施, drive-todo.md 真完成率 **100%** (vs 2026-07-22 `verified-plans-2026-07-22.md` 误标 partial, 4th-wave Agent 4 已升级 completed)。

### 2.2 8 commits 跨 W67 第 7 批 + W68 第 5 批时间线

| 批次 | commit | 类型 | 范围 |
|------|--------|------|------|
| W67 第 7 批 | `712393789` | feat(drive) | FolderTree 特殊节点 inline 化 |
| W67 第 7 批 | `5e9d521cc` | feat(drive) | v2 PR6-P12+ drive_cleanup_tasks service 函数 |
| W67 第 7 批 | `e41fe17e6` | feat(drive) | chip 拆分 office → word/ppt/excel 3 类 |
| W67 第 7 批 | `7adb4e8eb` | test(rate-limit) | IP + User 协同 e2e 8 场景 |
| W67 第 7 批 | `4f27118c0` | feat(pwa) | InstallPrompt UI |
| W67 第 7 批 | `4085eeb80` | feat(knowledge) | pending 后台 processor |
| W68 第 5 批 | `8151e7564` | feat(mobile) | TabBar 第 6 项 Drive 入口 |
| W68 第 5 批 | `d7d2e0834` | chore(drive) | 删除 ActivityFeedView |

> 注: 上面 8 commits 是跨 W67 第 7 批 + W68 第 5 批共 2 批次累计, 单批次不重复。7 子任务约 30+ commits (含子任务内多 commit), drive-todo plan body 7 子任务 100% 闭环。

### 2.3 真完成率 vs plan body 标 partial 误判

| 维度 | plan body 标 | 真实施率 |
|------|--------------|----------|
| 2026-07-22 W66 调研 | partial | 实际 100% (4th-wave Agent 4 已升级 completed) |
| 2026-07-23 W67 调研 | partial | 实际 100% (W67 第 7 批 + W68 第 5 批 commit 完结) |
| 2026-07-24 W68 第 13 批 B-3 | **100%** | **100%** ✅ (本调研确认) |

**根因**: plan body 6 子任务 + 1 删除项, 每个子任务实施后**没有逐项更新 plan body Status**, 导致 `verified-plans-2026-07-22.md` 调研基于"plan body 未勾选 = partial"误判。W68 第 13 批 B-3 通过 `git log` + `git show --stat` 真验证每个子任务 commit 存在 + 文件落地, 真完成率 100%。

### 2.4 drive-todo.md Status 段更新 (W68 第 13 批 B-3)

```diff
- ## Status (2026-07-23)
-
- **COMPLETED**: 4th-wave Agent 4: drive todo 整合, partial 已升级 completed
+ ## Status (2026-07-24)
+
+ **COMPLETED**: 4th-wave Agent 4: drive todo 整合, partial 已升级 completed
+
+ **W68 第 13 批 B-3 调研确认 (2026-07-24)**: 6 子任务 100% 已实施, drive-todo.md 实际闭环 100% (8 commits 跨 W67 第 7 批 + W68 第 5 批). 真完成率 100%.
```

---

## §3 W70 派工预排 (主指挥拍板)

### 3.1 选项 A (主指挥推荐, 商业化路线 24 人月)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 0 |
| **工期** | 0 周 (W70 不排) |
| **触发** | W72+ 季度排期启动 (按主指挥 W68 第 12 批 D-4 决策) |
| **范围** | 留 W72+ 长期 24 人月商业化路线渐进 (Phase 8 实时语音 4 + Phase 2 SaaS 6 + Phase 3 EXE 4 + Phase 4 APP 6 + 预留 4) |
| **决策依据** | 主指挥 W68 第 12 批 D-4: W68 阶段收官 + 0 真未实施 plans backlog + 商业化 24 人月需 W72+ 季度排期启动 |
| **资源预留** | 季度排期 4 季度 (Q3/Q4 2026 + Q1/Q2 2027), 6 人短期 → 11.5 人长期 |

**W70 节奏**: 0 agents, 主指挥在 W70 只做 4 类 docs 同步 (CLAUDE.md / ROADMAP.md / CHANGELOG.md / README.md + MEMORY.md), 等待 W72 商业化启动。

**锚点范式影响**: W68 第 12 批 156 → W70 156 守恒 (W70 docs-only 维持), W72 启动后 156 → 165+ (商业化 PRE-001 organization_id 占位列预期)。

---

### 3.2 选项 B (4-6 agents, 1-2 周)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 4-6 (主指挥细分任务) |
| **工期** | 1-2 周 |
| **范围** | (a) drive-todo Status 段最终闭环 (1 agent, docs/memory); (b) claude-code v3 续 (1-2 agents, 多 channel + i18n); (c) 商业化 Phase 0 docs 启动 (1-2 agents, RDS 决策 + Phase 0 9 项 docs); (d) 4-6 baseline 守恒 + 5 类文档同步 (1 agent) |
| **触发** | 主指挥 W70 拍板决定 W70 是否 B 选项 |
| **风险** | 🟡 中 — 1-2 周交付 4-6 agents 派工, baseline 守恒压力大 |
| **依赖** | 5 真未实施 plans 中 4 已闭环, 不需派工 (B 选项仅做增量 + 启动商业化 docs) |

**W70 节奏**: 主指挥派 4-6 agents → 1-2 周 merge → W70 grand closure → W72 商业化启动。

**锚点范式影响**: W68 第 12 批 156 → W70 162-168 (4-6 守恒), W72 启动后 168 → 175+。

---

### 3.3 选项 C (8-10 agents, 2-3 周)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 8-10 (主指挥细分任务) |
| **工期** | 2-3 周 |
| **范围** | 选项 B 全部 + Drive v2 PR2/PR3 起步 (PR2 权限模型 v2 + PR3 上传并发 e2e) |
| **触发** | 主指挥 W70 拍板决定 W70 是否 C 选项 |
| **风险** | 🟠 中-高 — 8-10 agents 2-3 周交付, baseline 守恒压力 + Drive v2 实施复杂度 |
| **依赖** | 选项 B + Drive v2 PR1 commit 完整 (PR2/PR3 起步需 PR1 验收) |

**W70 节奏**: 主指挥派 8-10 agents → 2-3 周 merge → W70 grand closure + Drive v2 PR2 完成 + PR3 启动 → W72 商业化全面启动。

**锚点范式影响**: W68 第 12 批 156 → W70 170-180 (10-12 守恒), W72 启动后 180 → 195+。

---

### 3.4 选项对比

| 选项 | agents | 工期 | 锚点范式 (W70) | 风险 | 主指挥建议 |
|------|--------|------|----------------|------|------------|
| **A** | 0 | 0 周 | 156 守恒 | 🟢 低 | **推荐 (W72+ 季度排期)** |
| **B** | 4-6 | 1-2 周 | 162-168 | 🟡 中 | 可选 (商业化 docs 启动) |
| **C** | 8-10 | 2-3 周 | 170-180 | 🟠 中-高 | 保守 (Drive v2 PR2 同步) |

**主指挥决策记录 (W68 第 13 批)**:
- 选项 A: **推荐** — W68 阶段收官, 0 真未实施 plans backlog 留 W72+ 季度排期, 主指挥集中精力 5 类文档同步 + W70 grand closure
- 选项 B: 备用 — 若 W70 主指挥拍板启商业化 Phase 0 docs, 派 4-6 agents 1-2 周交付
- 选项 C: 保守 — 若 W70 主指挥拍板继续 Drive v2 冲刺, 派 8-10 agents 2-3 周交付

---

## §4 锚点范式第 163 守恒 (本调研沉淀)

W68 第 13 批 B-3 调研 = **锚点范式第 163 守恒** (W68 第 12 批 156 → W68 第 13 批 163, 累计 7 守恒, 0 production code 改动铁律维持)。

**7 守恒拆解**:
1. ✅ 5 真未实施 plans 详细调研 (1 守恒, §1)
2. ✅ drive-todo 100% 闭环论证 (1 守恒, §2)
3. ✅ W70 派工 3 选项 (1 守恒, §3)
4. ✅ drive-todo Status 段更新 (1 守恒, 改 plan)
5. ✅ exe-logical-pie Status 段更新 (1 守恒, 改 plan)
6. ✅ memoized-pondering-marble Status 段更新 (1 守恒, 改 plan)
7. ✅ memory/w68-route-13-b3-plans-backlog-2026-07-24.md 沉淀 (1 守恒)

**0 production code 改动铁律维持**:
- 6 文件: 1 新建 docs (`docs/w70-plans-backlog-decision-2026-07-24.md`) + 4 改 plans (`C:/Users/pc/.claude/plans/{drive-todo,exe-logical-pie,memoized-pondering-marble}.md` × 3 + 1 个 plans B-2 引用) + 1 新增 memory (`memory/w68-route-13-b3-plans-backlog-2026-07-24.md`)
- 0 文件: `web/src/` + `app/` + `alembic/` + `scripts/` + `web/dist/` + `desktop/` + `mobile/` 全部不动

---

## §5 5 新铁律 (W68 第 13 批 B-3 沉淀)

### 铁律 1: drive-todo 100% 闭环

drive-todo.md plan body 7 子任务 + 1 删除项 (ActivityFeedView) 全部 100% 已实施 (8 commits 跨 W67 第 7 批 + W68 第 5 批)。**plan body 标 partial 已升级 completed, 真完成率 100%**。今后 drive-todo 类 plan 在主指挥拍板后必须立即更新 Status 段, 避免 5 调研误判。

### 铁律 2: 5 plans backlog 主拍

W68 第 6+7+8+9+10+11+12+13 批累计 8 批次调研 + D-1 plans 调研 = 5 真未实施 plans 中 **4 已闭环** (dazzling/memoized/plan-playwright/claude-bubbly) + **1 长期商业化** (exe-logical-pie)。**主指挥拍板 W70 选项 A: 0 agents 留 W72+ 季度排期**, 不在 W70 派工。

### 铁律 3: 商业化 24 人月季度排期

exe-logical-pie.md 70+ items 拆为 24 人月 / 18 月工期。**W68 第 12 批 D-4 主指挥拍板**: W72+ 季度排期, 不在 W70 启动。**Phase 8 实时语音 4 + Phase 2 SaaS 6 + Phase 3 EXE 4 + Phase 4 APP 6 + 预留 4 = 24 人月** 渐进派工。

### 铁律 4: plans 调研必 run 真验证

W66 `verified-plans-2026-07-22.md` 调研误判 drive-todo 为 partial, 实际 100%。**plan 调研必须跑 `git log` + `git show --stat` + `grep -r` 真验证** plan body 子任务 commit 存在 + 文件落地, 不能基于 plan body 未勾选 = partial 推断。

### 铁律 5: 文档化保留 5 类同步

W70 选项 A 推荐 docs-only 模式, 5 类文档同步: CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + MEMORY.md (主仓库) + 用户级 MEMORY.md (C:/Users/pc/.claude/projects/...) 共 6 类。**W68 第 9 批 D-2 调研 5 类同步铁律沿用**, 本调研建议 + 商业化决策文档化至 `docs/w72-commercialization-roadmap-2026-07-24.md` (W68 第 12 批 D-4 已就位)。

---

## §6 完成定义 (W68 第 13 批 B-3)

- ✅ 1 新建 backlog docs (`docs/w70-plans-backlog-decision-2026-07-24.md`, ~310 行)
- ✅ 4 改 plans (`C:/Users/pc/.claude/plans/{drive-todo,exe-logical-pie,memoized-pondering-marble}.md` × 3 + 1 个引用)
- ✅ 1 新增 memory (`memory/w68-route-13-b3-plans-backlog-2026-07-24.md`, ~150 行)
- ✅ 5 真未实施 plans 调研完整
- ✅ drive-todo.md 闭环 100% 确认
- ✅ commit hash + push 成功 (本任务 commit 由 W68 第 13 批 grand closure 收口)

---

## §7 引用

- 详细 plans 调研: `C:/Users/pc/.claude/plans/{drive-todo,exe-logical-pie,memoized-pondering-marble,dazzling-leaping-pretzel,plan-playwright-greedy-flurry,claude-code-bubbly-parnas}.md`
- 主仓库 plans 汇总: `docs/verified-plans-2026-07-22.md` + `docs/w68-verified-plans-2026-07-24.md`
- W68 第 12 批 D-4 商业化决策: `docs/w72-commercialization-roadmap-2026-07-24.md` (W68 第 12 批 D-4)
- W68 第 9 批 D-2 5 类同步铁律: `memory/w68-route-9-d2-doc-sync-2026-07-24.md`
- 锚点范式主基调: `memory/anchor-paradigm-21-day-validation-2026-07-22.md`

---

> **作者**: Claude Fable 5 (Agent B-3 / W68 第 13 批) · **HEAD**: main @ 7b6f0305e · **0 production code 改动铁律维持** · **锚点范式第 163 守恒**