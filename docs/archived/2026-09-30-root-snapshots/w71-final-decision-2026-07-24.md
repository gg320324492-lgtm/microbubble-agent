# W71 + W72 拍板决策 — 主指挥最终路线图 (2026-07-24)

> **W68 第 14 批 D-4** — 主指挥派工纪要拍板 + W71+W72 季度排期最终决策
> **作者**: Claude Fable 5 (Agent D-4 / W68 第 14 批)
> **日期**: 2026-07-24
> **基线 HEAD**: `9b7c0e8a9` (W68 第 13 批 grand closure merge 后, W68 第 14 批起点)
> **前序调研**:
> - [`docs/chatgpt-structured-floyd-w69-plan.md`](./chatgpt-structured-floyd-w69-plan.md) — W69 子 plan ②/③ 完整调研 (锚点范式第 90 守恒)
> - [`docs/w70-plans-backlog-decision-2026-07-24.md`](./w70-plans-backlog-decision-2026-07-24.md) — W68 第 13 批 B-3 5 plans 综合调研 (drive-todo 100% 闭环 + 5 真未实施 4 已闭环 + 1 长期商业化)
> - [`docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md`](./w70-w71-plans-backlog-survey-v2-2026-07-24.md) — W68 第 14 批 A-3 调研 (待 A-3 完成)
> - [`docs/qa-bench-d8-comprehensive-survey-2026-07-24.md`](./qa-bench-d8-comprehensive-survey-2026-07-24.md) — W68 第 14 批 C-1 调研 (qa-bench D5-D8 后续路线综合)
> **铁律**: 0 production code 改动 (本任务纯 docs/memory) + W19 选项 A 维持 + 锚点范式持续单调上升 + 71 PASS + 7 SKIP baseline 守恒

---

## 🎯 TL;DR

W71 + W72 2 周 + 2 周季度排期, 主拍 **选项 A (W71) + 选项 A (W72)** = 累计 8 agents / 4 周 / 0 真未实施 plans backlog 闭环 / 子 plan ② 完整落地 + 子 plan ③ UI redesign 起步。

| 维度 | W71 (推荐选项 A) | W72 (推荐选项 A) |
|------|------------------|------------------|
| **派工 agents 数** | 5 | 3 |
| **工期** | 2 周 (2026-08-03 → 2026-08-16) | 2 周 (2026-08-17 → 2026-08-30) |
| **范围** | 子 plan ② qa-bench 7 维 + 5 道防线 + KB 闭环 + Dashboard | 子 plan ③ UI redesign NavRail + ThinkingModeSwitch + ChatBreadcrumb |
| **风险** | 🟡 中 (qa-bench 7 维首次落地, AUTO_KB_INTAKE 默认 False) | 🟠 中-高 (UI redesign 跨多组件, Playwright baseline 必然冲突) |
| **锚点范式预期** | W68 第 13 批 168 → W71 ~178 (+10) | W71 178 → W72 ~188 (+10) |
| **0 prod code 例外** | 5 例外预算: `app/services/` <50 行 + `web/src/views/admin/` <350 行 + `.github/workflows/` <5 行 | 3 例外预算: `web/src/components/` <400 行 + `web/src/views/chat/` <200 行 + `tests/visual/desktop/` <100 行 |
| **失败回滚** | 单 agent 回滚, 全部失败 → docs/CI 占位 (W67 第 47 步铁律) | 单组件回滚, Playwright baseline rebuild |

**主推选项**: W71 选项 A (5 agents 子 plan ②) + W72 选项 A (3 agents 子 plan ③) = 累计 8 agents, 锚点范式 168 → 188 (20 守恒, 4 周), 与 W68 第 4+5+6+7+8 批节奏 (平均每批 5-15 agents) 一致。

**Why**: W68 第 13 批 8 plans Status 闭环 + B-3 plans backlog 调研 + W68 第 14 批 A-3 + C-1 调研 = 子 plan ② (qa-bench 7 维 + 5 道防线 + KB 闭环 + Dashboard) 是 W71 唯一可立即派工的方案 (子 plan ② 子任务清晰, 风险可控, 灰度发布开关 `AUTO_KB_INTAKE_ENABLED=False` 默认关)。子 plan ③ UI redesign 是 W72 续 (依赖 W71 7 维评分数据 + 36 题 + 入库闭环验证), 3 组件清晰, 复用现有 utilities。

**How to apply**:
1. 主指挥 review §2 W71 4 选项矩阵 + §3 W72 4 选项矩阵
2. 主指挥在 W71 启动前 1 周拍板选项 A/B/C/D
3. W71 第 1 批派工 prompt 必须含"派工依据文档 = `docs/w71-final-decision-2026-07-24.md`", Agent 按 §4 派工清单展开
4. W71 完成后启动 W72, W72 派工 prompt 同步引用本文件 + W71 grand closure memory
5. 失败时按 §5 失败回滚 + §6 10 步 deployment checklist 走

---

## 1️⃣ 现状锚定 (W68 第 13 批 grand closure 后)

### 1.1 W68 累计 grand closure + commits

| 批 | commit 数 | 锚点范式 | 关键里程碑 |
|----|----------|----------|-----------|
| W68 第 1 批 | 14+1 agents → 30 commits | W67 28 → W68 30 | Drive v2 PR8 + Mobile UX v3.0 |
| W68 第 2 批 | 3 agents | W68 30 → 32 | qa-bench D6 调研 + 文档同步 + baseline 守恒 |
| W68 第 3 批 | 11 agents | W68 32 → 42 | Drive v2 PR9 + qa-bench D6 + docs |
| W68 第 4 批 | 15 agents | W68 42 → 57 | PR9 后续 + Plan 闭环 2/2 |
| W68 第 5 批 | 15 agents | W68 57 → 72 | Drive v2 PR10 + Mobile v3.2 PWA Push |
| W68 第 6 批 | 16 agents | W68 72 → 88 | 70+ plans 审计 + Drive v2 PR11-12 |
| W68 第 7 批 | 1 agent | W68 88 → 89 | plans Status 闭环 |
| W68 第 8 批 | 14 agents | W68 89 → 102 | Drive v2 部署 + 永久纪律沉淀 + 文档收口 |
| W68 第 9 批 | 15 agents | W68 102 → 116 | Drive v2 PR11 + plans 闭环 + 任务模式基调 v2 |
| W68 第 10 批 | 14 agents | W68 116 → 134 | 部署收口 + W69 派工 + P0 VAPID |
| W68 第 11 批 | 15 agents | W68 134 → 144 | plans 状态闭环 13 + W69 派工实施 + alembic rebase |
| W68 第 12 批 | 14 agents | W68 144 → 156 | 路线 C 续 + plans 闭环续 + D7 baseline CI |
| W68 第 13 批 | 12 agents | W68 156 → 168 | 8 plans 闭环 + W70 派工实施 + 派工纪要 v4 |
| **W68 第 14 批 (本批)** | **15 agents (D-4 在内)** | **W68 168 → ~183 (锚点范式第 183 守恒预测)** | **W71+W72 拍板 + 调研收尾 + 部署收口** |

### 1.2 0 真未实施 plans backlog (B-3 调研)

W68 第 13 批 B-3 调研 ([`docs/w70-plans-backlog-decision-2026-07-24.md`](./w70-plans-backlog-decision-2026-07-24.md)) 结论:
- 5 真未实施 plans: dazzling/memoized/plan-playwright/claude-bubbly/exe-logical-pie
- 4 已闭环 (dazzling/memoized/plan-playwright/claude-bubbly) — 不再派工
- 1 长期商业化 (exe-logical-pie, 24 人月) — 留 W72+ 季度排期启动
- drive-todo.md 100% 闭环 — 升级 completed

### 1.3 W69/W70 已有排期 (主指挥参考)

[`docs/w69-w70-roadmap-decision-2026-07-24.md`](./w69-w70-roadmap-decision-2026-07-24.md) (W68 第 9 批 D-5):
- W69 推荐: 选项 A (5-7 agents 子 plan ② + 6 plans 小修)
- W70 推荐: 8-12 agents 子 plan ③ UI redesign + Drive v2 PR 续
- 累计锚点范式预期: W68 90 → W69 95-100 → W70 100-115

**W71 + W72 拍板与 W69/W70 排期关系**:
- W69 实际派工: 8 agents (子 plan ② 5 + 小修 3) — 与本文件 §2 选项 A 一致
- W70 实际派工: 12 agents (子 plan ③ 5-7 + Drive v2 续 5) — 与本文件 §3 选项 A 类似
- **W71 + W72 是 W69 + W70 后续排期**, 延续子 plan ② 落地 + 子 plan ③ 收口模式

---

## 2️⃣ W71 4 选项矩阵 (主指挥拍板)

### 2.1 W71 选项 A (推荐, 5 agents 子 plan ②)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 5 |
| **工期** | 2 周 (2026-08-03 → 2026-08-16, 估算 14-22 人时) |
| **范围** | 子 plan ② qa-bench 7 维评分 + 5 道防线 + KB 闭环 + Dashboard MVP + CI smoke 200 题 |
| **触发** | 主指挥 W71 启动前 1 周拍板, 立即派工 |
| **风险** | 🟡 中 (qa-bench 7 维首次落地, 灰度发布开关 `AUTO_KB_INTAKE_ENABLED=False` 默认关, 7 天手动审核期) |
| **预期锚点** | W68 第 13 批 168 → W71 ~178 (+10 守恒) |
| **0 prod code 例外** | 5 agents 全部允许 `tests/qa-bench/` + `web/src/views/admin/` + `app/services/` <50 行 + `.github/workflows/` <5 行 |

**5 agents 详细任务**:
- Agent #1: 7 维评分算法 (`tests/qa-bench/scoring/seven_dim.py` ~200 行 + `weights.json` ~30 行) — 16h 估时
- Agent #2: save_to_kb.py 5 道防线 (`tests/qa-bench/kb_queue/dedup.py` + 4 防线) — 12h 估时
- Agent #3: Celery auto_intake_rollback_task (`app/services/qa_bench_tasks.py` ~100 行) — 8h 估时
- Agent #4: KB 闭环端到端 (评测 → 入库 → 抽检 → 回滚) — 12h 估时
- Agent #5: Dashboard MVP + CI smoke 200 题 — 10h 估时

**失败回滚**:
- 单 agent 失败 → 单 agent 回滚 (删除对应文件 + revert commit)
- 5 agents 全部失败 → 接受 docs/CI 占位 (W67 第 47 步铁律), 不做第 3 次尝试
- 3 道防线任一 fail → 关闭 `AUTO_KB_INTAKE_ENABLED` flag, 走 manual review

**主推理由**:
- W69 子 plan ② 已规划 5 agents ([`docs/chatgpt-structured-floyd-w69-plan.md`](./chatgpt-structured-floyd-w69-plan.md) §2.9)
- B-3 调研 0 真未实施 plans backlog, W71 不需要小修
- 灰度发布开关 `AUTO_KB_INTAKE_ENABLED=False` 默认关, 7 天手动审核期, 风险可控
- 锚点范式预期 168 → 178, 与 W68 第 4+5+6 批节奏一致

### 2.2 W71 选项 B (8 agents 子 plan ② + 子 plan ③ 部分起步)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 8 |
| **工期** | 3 周 (2026-08-03 → 2026-08-23) |
| **范围** | 选项 A 全部 + 子 plan ③ NavRail 组件 3 agents 起步 (不含 ThinkingModeSwitch + ChatBreadcrumb) |
| **触发** | 主指挥拍板 W71 同时推进子 plan ② + 子 plan ③ NavRail |
| **风险** | 🟠 中-高 (子 plan ② + ③ 跨主题并行, 0 prod code 铁律部分例外) |
| **预期锚点** | W68 第 13 批 168 → W71 ~188 (+20 守恒, 3 周) |

**额外 3 agents 任务 (子 plan ③ NavRail)**:
- Agent #6: NavRail.vue 新组件 (~250 行)
- Agent #7: SessionSidebar 重构 (overlap bug 修复 + actions 改 right-click)
- Agent #8: NavRail 移动端断点 + dark mode 验证

**主推不选理由**:
- 子 plan ③ 起步依赖子 plan ② 7 维评分数据落地 (W72 上半周才能看到 7 维评分跑通)
- W71 同时派 8 agents 风险高, W68 第 5 批 15 agents 节奏验证过 3 周才稳
- 0 prod code 铁律例外预算: `web/src/components/` <400 行 + `web/src/views/` 续改 + `tests/visual/` 重建 baseline

### 2.3 W71 选项 C (4 agents 子 plan ② 跳过 KB 闭环)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 4 |
| **工期** | 2 周 (2026-08-03 → 2026-08-16) |
| **范围** | 子 plan ② Agent #1 (7 维评分) + Agent #2 (5 道防线) + Agent #5 (Dashboard MVP + CI smoke) — **跳过 Agent #3 (Celery auto_intake_rollback) + Agent #4 (KB 闭环端到端)** |
| **风险** | 🟡 中 (无 KB 闭环, 入库需手动审核, 风险可控但 backlog 压力大) |
| **预期锚点** | W68 第 13 批 168 → W71 ~184 (+16 守恒) |

**主推不选理由**:
- KB 闭环是子 plan ② 核心交付物, 跳过 → 子 plan ② 不闭环
- Agent #3 (Celery auto_intake_rollback) + Agent #4 (端到端) 是 5 道防线自动化的关键
- 跳过 → save_to_kb.py 5 道防线仅 dry-run, apply 模式不能上线

### 2.4 W71 选项 D (0 agents 商业化优先)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 0 |
| **工期** | 0 周 (W71 不排) |
| **范围** | 24 人月商业化路线 (Phase 0/1/2/8) 季度排期启动 |
| **风险** | 🟢 极低 (0 派工 0 风险, 但锚点范式停滞) |
| **预期锚点** | W68 第 13 批 168 → W71 168 (0 守恒, 不升不降) |

**主推不选理由**:
- W68 第 6+7+8+9+10+11+12+13 批累计 8 批次调研 + W72 商业化 24 人月季度排期已就位 ([`docs/w72-commercialization-roadmap-2026-07-24.md`](./w72-commercialization-roadmap-2026-07-24.md) W68 第 12 批 D-4 已写)
- W71 不派工 → W72 子 plan ③ UI redesign 启动晚 2 周, 子 plan ③ 闭环延后到 W73+
- 商业化启动前必做 Phase 8 (实时语音 4 人月) + Phase 2 (多组织 SaaS 6 人月), 主指挥 2026-09 + 2026-10 拍板 (W74 + W78), 不在 W71 启动

### 2.5 W71 选项对比

| 选项 | agents | 工期 | 锚点范式 | 风险 | 主指挥建议 |
|------|--------|------|----------|------|------------|
| **A** | 5 | 2 周 | 178 (+10) | 🟡 中 | **推荐** |
| B | 8 | 3 周 | 188 (+20) | 🟠 中-高 | 可选 (跨主题并行) |
| C | 4 | 2 周 | 184 (+16) | 🟡 中 | 保守 (跳过 KB 闭环) |
| D | 0 | 0 周 | 168 (0) | 🟢 极低 | 商业化优先 |

---

## 3️⃣ W72 4 选项矩阵 (主指挥拍板)

### 3.1 W72 选项 A (推荐, 3 agents 子 plan ③ UI redesign)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 3 |
| **工期** | 2 周 (2026-08-17 → 2026-08-30, 估算 10-15 人时) |
| **范围** | 子 plan ③ NavRail + ThinkingModeSwitch + ChatBreadcrumb 3 组件 |
| **触发** | W71 完成后立即启动 (依赖 W71 7 维评分 + KB 闭环验证数据) |
| **风险** | 🟠 中-高 (UI redesign 跨多组件, Playwright baseline 必然冲突, dark mode 跨组件 6 主题验证) |
| **预期锚点** | W71 178 → W72 ~188 (+10 守恒) |
| **0 prod code 例外** | 3 agents 允许 `web/src/components/` <400 行 + `web/src/views/chat/` <200 行 + `tests/visual/desktop/` <100 行 |

**3 agents 详细任务**:
- Agent #1: NavRail.vue 新组件 (~250 行) + SessionSidebar 重构 (overlap bug 修复)
- Agent #2: ThinkingModeSwitch.vue (~80 行) + ChatBreadcrumb.vue (~60 行) + useUiStore.js v-model
- Agent #3: ChatViewSSE 顶栏 3-zone 重构 + 移动端同步 + Playwright visual regression baseline 重建

**失败回滚**:
- 单 agent 失败 → 单 agent 回滚 (删除 NavRail/ThinkingModeSwitch/ChatBreadcrumb.vue + revert commit)
- 3 agents 全部失败 → 接受 SessionSidebar overlap bug + 🧠🧠 toggle 冲突继续存在 (用户可观察痛点)
- Playwright baseline 冲突 → `--update-snapshots` 重建 baseline + 自动 commit (CLAUDE.md v76 流程)

**主推理由**:
- 子 plan ③ UI redesign 4 个现存痛点 (overlap / 🧠🧠 / aria-label / 顶栏拥挤) 全部 user-observable
- 复用现有 utilities: `web/src/components/chat/SearchPalette.vue` + `web/src/stores/useUiStore.js` `useDeepThinking` (44, 66) + `web/src/stores/useThemeStore.js` `toggle()` (90-92)
- 3 组件清晰, 风险可控 (复用现有模式, 不引入新依赖)
- 0 prod code 例外预算 <700 行 (跨多组件但新增为主, 不改现有 el-* 组件)

### 3.2 W72 选项 B (5 agents 选项 A 续 + W72 docs 同步 + 调研)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 5 |
| **工期** | 3 周 (2026-08-17 → 2026-09-06) |
| **范围** | 选项 A 全部 + W72 docs 同步 + W73 派工调研 |
| **风险** | 🟡 中 (跨主题收口 + 调研, 节奏稳) |
| **预期锚点** | W71 178 → W72 ~198 (+20 守恒, 3 周) |

**额外 2 agents 任务**:
- Agent #4: 6 类文档同步 (CLAUDE.md/ROADMAP.md/CHANGELOG.md/README.md/MEMORY.md + 用户级 MEMORY.md)
- Agent #5: W73 派工前 plans backlog 调研 + W72 grand closure memory

**主推不选理由**:
- 6 类文档同步已在 W68 第 13 批 D-2 完成, W72 不需要重复 (W68 第 13 批 168 守恒已含)
- W73 派工调研可由主指挥在 W72 末启动前 1 周做, 不需要单独 agent

### 3.3 W72 选项 C (0 agents 转商业化阶段)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 0 |
| **工期** | 0 周 |
| **范围** | 启动 Phase 8 (实时语音 4 人月) + Phase 2 (多组织 SaaS 6 人月) 商业化季度排期 |
| **风险** | 🟢 极低 |
| **预期锚点** | W71 178 → W72 178 (0 守恒) |

**主推不选理由**:
- 商业化季度排期已 W68 第 12 批 D-4 拍板 ([`docs/w72-commercialization-roadmap-2026-07-24.md`](./w72-commercialization-roadmap-2026-07-24.md)), W72 不重复决策
- Phase 8 + Phase 2 启动需主指挥 W74 + W78 拍板 (2026-09 + 2026-10), 不在 W72 启动
- W72 不派工 → UI redesign 3 个用户痛点延后到 W73+ 闭环

### 3.4 W72 选项 D (6 agents 长期演化 Drive v2 PR19-PR22)

| 维度 | 内容 |
|------|------|
| **派工 agents 数** | 6 |
| **工期** | 3-4 周 |
| **范围** | Drive v2 PR19 (审计日志查询 UI) + PR20 (回收站 v2 软删) + PR21 (文件请求 token 化) + PR22 (分享链接审计) |
| **风险** | 🟠 中-高 (Drive v2 跨多 service, 0 prod code 铁律部分例外) |
| **预期锚点** | W71 178 → W72 ~198 (+20 守恒) |

**主推不选理由**:
- W68 第 13 批 B-3 调研已决策 Drive v2 续留 W72+ 季度排期 (与子 plan ③ 同步), 但 W72 季度排期尚未到
- Drive v2 PR19-PR22 是长期演化路线, 单批 6 agents 风险高
- W72 优先子 plan ③ UI redesign, Drive v2 PR 续留 W73+ 启动

### 3.5 W72 选项对比

| 选项 | agents | 工期 | 锚点范式 | 风险 | 主指挥建议 |
|------|--------|------|----------|------|------------|
| **A** | 3 | 2 周 | 188 (+10) | 🟠 中-高 | **推荐** |
| B | 5 | 3 周 | 198 (+20) | 🟡 中 | 可选 (跨主题收口) |
| C | 0 | 0 周 | 178 (0) | 🟢 极低 | 商业化转阶段 |
| D | 6 | 3-4 周 | 198 (+20) | 🟠 中-高 | 长期演化 |

---

## 4️⃣ 累计 W71 + W72 预期 (主推 A + A)

### 4.1 累计派工

| 周 | 选项 | agents | 工期 | 锚点 (起点) | 锚点 (终点) | 累计 |
|----|------|--------|------|-------------|-------------|------|
| W71 | A | 5 | 2 周 | 168 | 178 | +10 |
| W72 | A | 3 | 2 周 | 178 | 188 | +10 |
| **累计** | **A+A** | **8** | **4 周** | **168** | **188** | **+20** |

### 4.2 累计交付物

**W71 交付物** (子 plan ② 完整闭环):
- 7 维评分算法 + verdict consensus (`tests/qa-bench/scoring/seven_dim.py` ~200 行)
- save_to_kb.py 5 道防线 (`tests/qa-bench/kb_queue/dedup.py` + 4 防线)
- Celery auto_intake_rollback_task (`app/services/qa_bench_tasks.py` ~100 行)
- KB 闭环端到端 (评测 → 入库 → 抽检 → 回滚)
- Dashboard MVP 4 指标卡 (`web/src/views/admin/QaBenchDashboard.vue` ~400 行)
- CI smoke 200 题 < 5min (`.github/workflows/qa-bench-smoke.yml` ~30 行)
- `AUTO_KB_INTAKE_ENABLED=False` 默认关 + 7 天手动审核期

**W72 交付物** (子 plan ③ UI redesign 收官):
- NavRail.vue 新组件 (~250 行) — 桌面端左侧导航栏
- ThinkingModeSwitch.vue (~80 行) — 3 档模式 segmented control
- ChatBreadcrumb.vue (~60 行) — 中央标题 + breadcrumb path
- SessionSidebar 重构 (overlap bug 修复 + actions 改 right-click)
- ChatViewSSE 顶栏 3-zone 重构 + 移动端同步
- Playwright visual regression baseline 重建

**累计 user-visible 改进**:
- qa-bench 595 → 780 题 (+31%) + 7 维评分 + 自动入库闭环
- UI 4 个现存痛点 (overlap / 🧠🧠 / aria-label / 顶栏拥挤) 全部解决
- KB 月增 50+ 候选 (全自动入库, 5 道防线监控)
- 评测自动化率 0% → 95%
- 高分率 84% → 92%+

### 4.3 累计 0 prod code 例外清单

| 周 | 例外文件 | 例外行数 | 例外类型 |
|----|----------|----------|----------|
| W71 | `tests/qa-bench/scoring/*` + `tests/qa-bench/kb_queue/*` | ~500 行 (NEW) | 测试目录新增 |
| W71 | `tests/qa-bench/ci/smoke_200.py` | ~150 行 (NEW) | 测试目录新增 |
| W71 | `tests/qa-bench/dashboard/index.html` | ~150 行 (NEW) | 测试目录新增 |
| W71 | `app/services/qa_bench_tasks.py` | ~100 行 (NEW) | service 新增 |
| W71 | `app/config.py` (加 1 setting) | ~3 行 (MOD) | config 增量 |
| W71 | `tests/qa-bench/save_to_kb.py` (重写) | ~280 行 (MOD) | 测试目录重写 |
| W71 | `web/src/views/admin/QaBenchDashboard.vue` | ~400 行 (NEW) | admin view 新增 |
| W71 | `web/src/api/qaBenchDashboard.js` | ~60 行 (NEW) | api 新增 |
| W71 | `.github/workflows/qa-bench-smoke.yml` | ~30 行 (NEW) | workflow 新增 |
| **W71 累计** | **9 文件 (8 NEW + 1 MOD)** | **~1673 行** | **scope 限定** |
| W72 | `web/src/components/chat/NavRail.vue` | ~250 行 (NEW) | component 新增 |
| W72 | `web/src/components/chat/ThinkingModeSwitch.vue` | ~80 行 (NEW) | component 新增 |
| W72 | `web/src/components/chat/ChatBreadcrumb.vue` | ~60 行 (NEW) | component 新增 |
| W72 | `web/src/components/chat/SessionSidebar.vue` | +60/-90 行 (MOD) | component 重构 |
| W72 | `web/src/views/chat/ChatViewSSE.vue` | +120/-80 行 (MOD) | view 重构 |
| W72 | `web/src/stores/chatSessions.ts` | +3 行 (MOD) | store 增量 |
| W72 | `web/src/views/mobile/chat/MobileChatView.vue` | +30/-10 行 (MOD) | mobile view 同步 |
| W72 | `web/src/components/mobile/MobileHeader.vue` | +20/-30 行 (MOD) | mobile component 简化 |
| W72 | `web/src/components/mobile/MobileInputBar.vue` | +25 行 (MOD) | mobile component 增量 |
| W72 | `web/src/components/mobile/MobileThinkingModeSwitch.vue` | ~60 行 (NEW) | mobile component 新增 |
| W72 | `web/src/assets/variables.css` | +20 行 (MOD) | design token 增量 |
| W72 | `tests/visual/desktop/v78-ui-redesign.spec.mjs` | ~60 行 (NEW) | visual regression 新增 |
| **W72 累计** | **12 文件 (4 NEW + 8 MOD)** | **~696 行 (净增)** | **scope 限定** |

**纪律**: 所有例外必须按 W68 第 8 批 §3 "0 production code 改动铁律例外清单" 走 — Drive v2 / Mobile UX / qa-bench / alembic / Plan 闭环 / scripts/ 6 类允许, 其他类别严禁。W71 + W72 累计 21 文件, 全部属于上述 6 类例外清单, 0 违规。

---

## 5️⃣ 失败回滚方案 (5 类)

### 5.1 alembic 双头 → 主指挥 rebase 改编号

**触发**: W71 Agent #3 (Celery auto_intake_rollback_task) 或其他 alembic migration agent 写了新 migration 但 down_revision 错了, alembic 链分叉成双头。

**检测**:
```bash
docker exec microbubble-agent-app-1 alembic heads
# 期望输出: 单 head (例如 081_qa_bench_tasks)
# 异常输出: 2+ heads → 双头
```

**回滚步骤**:
1. **立即停推**: 主指挥 W71 grand closure 不 merge 有问题的分支
2. **rebase 改编号**: 主指挥在 W71 grand closure 时改 081 `down_revision` 接 080 (而非另一个上游)
3. **cp + clear cache**:
   ```bash
   docker cp alembic/versions/081_qa_bench_tasks.py microbubble-agent-app-1:/app/alembic/versions/
   docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
   docker exec microbubble-agent-app-1 alembic upgrade head
   ```
4. **verify 单头**: `docker exec microbubble-agent-app-1 alembic heads` 期望只 1 个 head

**铁律来源**: W68 第 8 批 §2.3 alembic 串单链纪律 + 2026-07-24 commit `1852468a6` (CLAUDE.md 永久锚点)

### 5.2 baseline 退化 → git revert

**触发**: W71 + W72 累计 8 agents 任一失败导致 vitest/pytest PASS 数从 71 减少或 SKIP 数从 7 增加。

**检测**:
```bash
# W71 启动前 baseline
cd /e/microbubble-agent/web && npx vitest run 2>&1 | tail -10
# 期望: Test Files 38 passed, Tests 71 passed, 7 skipped

cd /e/microbubble-agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/ -v 2>&1 | tail -20
# 期望: pytest PASS 数与 W68 第 13 批一致
```

**回滚步骤**:
1. **立即 git revert**: 主指挥在 main 分支 `git revert <commit-hash>` 有问题的 agent commit
2. **重启服务**: `docker compose restart app celery-worker`
3. **重跑 baseline**: vitest + pytest 全过
4. **记录**: 主指挥在 W71 grand closure memory 注明"Agent #X 失败回滚, 派 hot-fix agent 后续 W71 第 2 批补"

**铁律来源**: CLAUDE.md 永久锚点 "71 PASS + 7 SKIP baseline 守恒" + W68 第 8 批 §1.2 (验证步骤)

### 5.3 6 点 curl 502 → 修 nginx / SSH tunnel

**触发**: W71 + W72 部署后 `curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/...` 任一返回 502 (Bad Gateway) 或 504 (Gateway Timeout)。

**检测 6 点**:
```bash
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/index.html
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/dashboard
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/sw.js
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/pwa-192.png
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/manifest.{hash}.webmanifest
# 任一非 200/304 即配置错误
```

**回滚步骤**:
1. **检查 nginx tunnel.conf**: `ssh root@xxx "cat /etc/nginx/conf.d/tunnel.conf | grep -E 'proxy_pass|server '"`
2. **检查 FRP 隧道**: `ssh root@xxx "systemctl status frpc"`
3. **检查 docker app**: `docker logs microbubble-agent-app-1 --tail 50`
4. **修法**:
   - nginx 502 → 修 `proxy_pass http://127.0.0.1:8000` (SSH reverse tunnel listener)
   - SSH tunnel 孤儿 listener → `ps aux | grep sshd | grep 1544507` 找到孤儿 PID + kill
   - docker app 端口 0 → `docker compose restart app` + `docker logs microbubble-agent-app-1 | grep "Application startup"`

**铁律来源**: 2026-07-22 W61 502 真根因 3 层修复 (CLAUDE.md 永久锚点) + nginx types 指令 5 铁律

### 5.4 PWA manifest 404 → 跑 `npm run build` 重 build

**触发**: W71 + W72 部署后浏览器 DevTools Console 报 "Manifest fetch failed, code 404" 或 PWA install 失败。

**检测**:
```bash
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/manifest.webmanifest
# 期望: 410 (有意防护)
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/manifest.{hash}.webmanifest
# 期望: 200 (hashed manifest)
```

**回滚步骤**:
1. **检查 dist 是否含 hashed manifest**:
   ```bash
   ls web/dist/manifest.*.webmanifest 2>/dev/null
   # 期望: 1 个 manifest.{hash}.webmanifest
   # 异常: 0 个 → 漏 force-add 或未跑 npm run build
   ```
2. **跑 npm run build**:
   ```bash
   cd web && npm run build
   # postbuild 自动 3 件事 + 健全性自检
   ```
3. **force-add hashed manifest**:
   ```bash
   git add -f web/dist/manifest.{hash}.webmanifest
   ```
4. **commit + push**:
   ```bash
   git commit -m "fix(pwa): npm run build 重建 hashed manifest (W71/W72 hotfix)"
   git push origin docs/w68-14th-batch-d4-w71-decision-2026-07-24
   ```

**铁律来源**: 2026-07-11 PWA manifest.webmanifest 410 回归 (CLAUDE.md 永久锚点) + 2026-07-10 PWA SW install 410 (commit `59187ce8` cascade + `5d2bcdfd` 修复)

### 5.5 端到端 fail → git revert + 派 hot-fix agent

**触发**: W71 + W72 部署后 qa-bench smoke 200 题失败, 或 Drive v2 PR5/17/18 端到端 e2e fail。

**检测**:
```bash
# qa-bench smoke
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/qa-bench/ci/smoke_200.py -v --timeout=300
# 期望: 200 PASSED, 时长 < 5min
# 异常: < 200 PASSED → fail

# Drive v2 端到端
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/integration/test_drive_v2_e2e.py -v
# 期望: 所有 PASS
```

**回滚步骤**:
1. **立即 git revert**: 主指挥在 main 分支 `git revert <commit-hash>` 有问题的 agent commit
2. **重启服务**: `docker compose restart app celery-worker`
3. **派 hot-fix agent**: W71 第 2 批 / W72 第 2 批派 1 hot-fix agent 修根因
4. **hot-fix commit message 模板**: `fix(<scope>): W71-N-th-batch-hotfix-<short-desc> (<short-bug-id>)` + body 含 root cause 1 段 + 修复 1 段 + 验证 1 段

**铁律来源**: W68 第 8 批 §2.4 跨 session hot-fix 必须 commit message 含 "hotfix" 标识 + 主指挥 git log 跟踪

---

## 6️⃣ 10 步 deployment checklist (W68 第 14 批部署必做)

### 步骤 1: 主指挥合并 W68 第 14 批 15 分支到 main

**顺序**: A-1~A-4 → B-1~B-4 → C-1~C-3 → D-1~D-4

**操作**:
```bash
# 主指挥在 main 分支, 依次 merge
git checkout main
git pull origin main

# A 路线 (4 分支: A-1~A-4)
git merge --no-ff origin/docs/w68-14th-batch-a1-plans-status -m "merge: docs/w68-14th-batch-a1-plans-status-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-a2-w71-w72-survey -m "merge: docs/w68-14th-batch-a2-w71-w72-survey-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-a3-w70-w71-backlog-v2 -m "merge: docs/w68-14th-batch-a3-w70-w71-backlog-v2-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-a4-qa-bench-d8 -m "merge: docs/w68-14th-batch-a4-qa-bench-d8-2026-07-24"

# B 路线 (4 分支: B-1~B-4)
git merge --no-ff origin/docs/w68-14th-batch-b1-drive-pr17 -m "merge: docs/w68-14th-batch-b1-drive-pr17-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-b2-drive-pr18 -m "merge: docs/w68-14th-batch-b2-drive-pr18-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-b3-mobile-v3.2-e2e -m "merge: docs/w68-14th-batch-b3-mobile-v3.2-e2e-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-b4-claudemd-discipline -m "merge: docs/w68-14th-batch-b4-claudemd-discipline-2026-07-24"

# C 路线 (3 分支: C-1~C-3)
git merge --no-ff origin/docs/w68-14th-batch-c1-qa-bench-d8-comprehensive -m "merge: docs/w68-14th-batch-c1-qa-bench-d8-comprehensive-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-c2-pwa-v80 -m "merge: docs/w68-14th-batch-c2-pwa-v80-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-c3-deploy-runbook -m "merge: docs/w68-14th-batch-c3-deploy-runbook-2026-07-24"

# D 路线 (4 分支: D-1~D-4)
git merge --no-ff origin/docs/w68-14th-batch-d1-prompt-template-v5 -m "merge: docs/w68-14th-batch-d1-prompt-template-v5-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-d2-doc-sync -m "merge: docs/w68-14th-batch-d2-doc-sync-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-d3-grand-closure -m "merge: docs/w68-14th-batch-d3-grand-closure-2026-07-24"
git merge --no-ff origin/docs/w68-14th-batch-d4-w71-decision -m "merge: docs/w68-14th-batch-d4-w71-decision-2026-07-24 (W68 第 14 批 grand closure memory + W71+W72 拍板)"

git push origin main
```

**铁律**: W68 第 8 批 §2.3 alembic 串单链纪律 — B-1 + B-2 是 alembic migration 分支, 必须按 alembic 链顺序 merge (B-1 在前, B-2 在后), 不能并行 merge。

### 步骤 2: alembic 链验证 (1 个 head)

**目的**: 验证 W68 第 14 批合并后 alembic 链单链, 无双头。

**操作**:
```bash
# 本地 verify (期望 1 个 head)
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
# 期望输出: ('080_drive_chunked_upload',)  # W68 第 14 批终点 head

# 云端 verify (期望 1 个 head)
docker exec microbubble-agent-app-1 alembic heads
# 期望输出: 080_drive_chunked_upload (head)
```

**异常处理**: 多个 head → 修 §5.1 alembic 双头回滚方案

### 步骤 3: baseline 71+7 守恒验证

**目的**: W68 第 14 批合并后 vitest + pytest baseline 不退化。

**操作**:
```bash
# 前端 baseline
cd /e/microbubble-agent/web && npx vitest run 2>&1 | tail -10
# 期望: Test Files 38 passed, Tests 71 passed, 7 skipped

# 后端 baseline
cd /e/microbubble-agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/ -v 2>&1 | tail -20
# 期望: pytest PASS 数与 W68 第 13 批一致
```

**异常处理**: 退化 → 修 §5.2 baseline 退化回滚方案

### 步骤 4: SSH 到云 server 真部署

**目的**: 把 W68 第 14 批 15 分支合并后的 main 部署到云 server。

**操作**:
```bash
# 主指挥 SSH 到云 server
ssh root@xxx

# 拉最新 main
cd /opt/microbubble-agent
git pull origin main

# 重启服务
docker compose restart app celery-worker

# 验证服务
docker ps | grep microbubble-agent
docker logs microbubble-agent-app-1 --tail 50 | grep "Application startup"
```

**异常处理**: 服务启动失败 → 修 §5.3 6 点 curl 502 修 nginx / SSH tunnel

### 步骤 5: 跑 12 scripts monitor

**目的**: W68 第 14 批 12 类 monitoring 脚本验证生产环境状态。

**操作**:
```bash
# 12 scripts (W68 第 11 批 D-3 已沉淀):
bash scripts/monitor_app_startup.sh
bash scripts/monitor_alembic_head.sh
bash scripts/monitor_baseline_vitest.sh
bash scripts/monitor_baseline_pytest.sh
bash scripts/monitor_drive_v2_endpoints.sh
bash scripts/monitor_qa_bench_d7.sh
bash scripts/monitor_pwa_manifest.sh
bash scripts/monitor_nginx_tunnel.sh
bash scripts/monitor_ssh_reverse_tunnel.sh
bash scripts/monitor_minio_health.sh
bash scripts/monitor_celery_beat.sh
bash scripts/monitor_redis_memory.sh

# 期望: 12/12 PASS
```

**异常处理**: 任意 monitor fail → 按 §5.1~§5.5 5 类失败回滚方案

### 步骤 6: 6 点 curl 验证

**目的**: 验证生产环境 HTTP 响应正确 (CLAUDE.md 永久锚点 nginx types 5 铁律)。

**操作**:
```bash
# 6 点 curl 验证
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://xxx/index.html
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://xxx/
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://xxx/dashboard
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://xxx/sw.js
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://xxx/pwa-192.png
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://xxx/manifest.{hash}.webmanifest

# 期望:
# 200 text/html (index.html)
# 200 text/html (/)
# 200 text/html (/dashboard SPA fallback)
# 200 application/javascript (sw.js)
# 200 image/png (pwa-192.png)
# 200 application/manifest+json (manifest.{hash}.webmanifest)
```

**异常处理**: 任何 502 / 504 / octet-stream → 修 §5.3 nginx / SSH tunnel 修复方案

### 步骤 7: PWA manifest 410 + 200 验证

**目的**: 验证 W68 第 14 批 PWA manifest 防护保留 (服务器 410) + hashed manifest 可访问 (200)。

**操作**:
```bash
# 服务器 410 (有意防护)
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/manifest.webmanifest
# 期望: 410

# hashed manifest 200
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/manifest.4f8d6b64.webmanifest
# 期望: 200
```

**异常处理**: 404 或非 410 → 修 §5.4 PWA manifest 404 npm run build 重 build

### 步骤 8: qa-bench smoke 200 题真跑

**目的**: 验证 W68 第 14 批 qa-bench 5 道防线 (W71 子 plan ② 启动前 baseline)。

**操作**:
```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/qa-bench/smoke_200.py -v --timeout=300
# 期望: 200 PASSED, 时长 < 5min
```

**异常处理**: < 200 PASSED → 修 §5.5 端到端 fail git revert + 派 hot-fix agent

### 步骤 9: Drive v2 PR5/17/18 端到端验证

**目的**: 验证 W68 第 14 批 Drive v2 续 (PR17 + PR18 + B-1 + B-2 alembic) 端到端 e2e。

**操作**:
```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/integration/test_drive_v2_e2e.py -v
# 期望: 所有 PASS

# 手动 smoke:
# - /drive 文件夹列表
# - /drive 上传 (chunked upload)
# - /drive 评论 + 删除 + audit log
# - /drive 回收站恢复
```

**异常处理**: fail → 修 §5.5 端到端 fail git revert + 派 hot-fix agent

### 步骤 10: 报告 main HEAD + 锚点范式守恒验证

**目的**: 主指挥在 W68 第 14 批 grand closure memory 报告 main HEAD + 锚点范式守恒。

**操作**:
```bash
# 报告 main HEAD
git log --oneline -1
# 期望: commit hash (W68 第 14 批 grand closure merge commit)

# 报告锚点范式守恒
echo "W68 第 14 批 grand closure 锚点范式: W68 第 13 批 168 → W68 第 14 批 183 (15 守恒, 15 agents 派工)"

# 沉淀 memory
# 主指挥写 memory/w68-route-14-d4-w71-decision-2026-07-24.md (D-4 本任务沉淀)
# 主指挥写 memory/w68-grand-closure-14th-batch-2026-07-24.md (D-3 grand closure)
```

**验收**: main HEAD + 锚点范式守恒验证报告完整 + memory 沉淀完整

---

## 7️⃣ 派工前提 (主指挥拍板决策表)

### 7.1 主拍建议汇总

| 周 | 选项 | agents | 工期 | 锚点 | 风险 | 主推 |
|----|------|--------|------|------|------|------|
| **W71** | **A** | 5 | 2 周 | 178 (+10) | 🟡 中 | **✅ 推荐** |
| W71 | B | 8 | 3 周 | 188 (+20) | 🟠 中-高 | 可选 (跨主题并行) |
| W71 | C | 4 | 2 周 | 184 (+16) | 🟡 中 | 保守 (跳过 KB 闭环) |
| W71 | D | 0 | 0 周 | 168 (0) | 🟢 极低 | 商业化优先 |
| **W72** | **A** | 3 | 2 周 | 188 (+10) | 🟠 中-高 | **✅ 推荐** |
| W72 | B | 5 | 3 周 | 198 (+20) | 🟡 中 | 可选 (跨主题收口) |
| W72 | C | 0 | 0 周 | 178 (0) | 🟢 极低 | 商业化转阶段 |
| W72 | D | 6 | 3-4 周 | 198 (+20) | 🟠 中-高 | 长期演化 Drive v2 |

**主拍**: **W71 选项 A + W72 选项 A** = 累计 8 agents / 4 周 / 锚点范式 168 → 188 (20 守恒)

### 7.2 派工前提 (主指挥在 W71/W72 启动前 1 周拍板)

| # | 派工前提 | 验证方式 |
|---|----------|----------|
| 1 | **W71 选项 A 已拍板** | 主指挥在 W71 启动前 1 周 review 本文档 §2, 写 `docs/w71-option-a-decision-2026-07-31.md` (~30 行) 文档化拍板决策 |
| 2 | **W72 选项 A 已拍板** | 主指挥在 W72 启动前 1 周 review 本文档 §3, 写 `docs/w72-option-a-decision-2026-08-14.md` (~30 行) 文档化拍板决策 |
| 3 | **W71 子 plan ② 实施路径已确认** | 主指挥 review W69 子 plan ② §2.9 5 agents 派工预排 + 本文件 §2.1 选项 A 5 agents 详细任务 |
| 4 | **W72 子 plan ③ 实施路径已确认** | 主指挥 review W69 子 plan ③ §3.5 4 agents 派工预排 + 本文件 §3.1 选项 A 3 agents 详细任务 (裁剪到 3 agents) |
| 5 | **灰度发布开关 AUTO_KB_INTAKE_ENABLED=False 已确认** | W71 Agent #3 派工时必须确认 `app/config.py` 默认 False, 7 天手动审核期 |
| 6 | **Playwright baseline 重建流程已确认** | W72 Agent #3 派工时必须 `npx playwright test --update-snapshots` 重建 baseline + 自动 commit (CLAUDE.md v76 流程) |
| 7 | **10 步 deployment checklist 已确认** | 主指挥在 W71/W72 grand closure 前 1 天按 §6 10 步执行 |
| 8 | **W68 第 14 批 D-4 沉淀已 commit** | 本文件 + memory/w68-route-14-d4-w71-decision-2026-07-24.md 已 1 commit + push |

### 7.3 派工 prompt 模板 (W71 + W72 启动时使用)

```markdown
## W71 Agent #X 派工 prompt 模板

> **派工依据**: 主指挥拍板 W71 选项 A (累计 5 agents), 详见 `docs/w71-final-decision-2026-07-24.md` §2.1
> **前序 plan**: `C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md` §3.1 (子 plan ② qa-bench 7 维评分)
> **派工 prompt v5**: 5 段 prompt 升级 (alembic verify + PS 5.1 + plans 真验证 + 派工前提 + 失败回滚)
> **铁律**: 0 production code 改动 (本 agent scope 限定: `tests/qa-bench/` 新增 + `app/services/qa_bench_tasks.py` ~100 行 + `web/src/views/admin/QaBenchDashboard.vue` ~400 行 + `.github/workflows/` < 5 行)
> **基线 HEAD**: W68 第 14 批 grand closure merge 后
> **失败回滚**: 单 agent 回滚 (删除对应文件 + revert commit); 全部失败 → docs/CI 占位 (W67 第 47 步铁律)
> **派工前提**: 主指挥已拍板选项 A + 子 plan ② 实施路径已确认 + AUTO_KB_INTAKE_ENABLED=False 已确认
```

---

## 8️⃣ 与 W19 选项 A + 任务模式基调 + 锚点范式守恒的关系

### 8.1 与 W19 选项 A 的关系

**W19 选项 A**: 4 留未来 PR 不发起新排期 (已维持 8 批次 W68 第 6+7+8+9+10+11+12+13 批)

**冲突分析**:
- W71 子 plan ② qa-bench — W19 之前**已部分实施** (qa-bench-v3-w1-2026-06-30 已 PARTIAL) → 不算新排期, **算遗留闭环**
- W72 子 plan ③ UI redesign — **W19 之前未实施** (W19 4 留未来 PR 不含此) → **新增排期**
- **结论**: W71 闭环不违反 W19 选项 A; W72 UI redesign **轻微违反** (新增排期 1 项)

**主指挥建议**:
- W71: ✅ 派工 (闭环遗留)
- W72: ✅ 派工 (新增排期 1 项, 但与 W19 维护性 baseline 守恒 + 跨主题收口基调一致)

### 8.2 与任务模式基调 (plans 优先 + 小修搭配) 的关系

**基调**: 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅 (W68 第 4 批主指挥拍板, W68 第 9 批 D-3 升级 v2 加 5 拍板纪律 + 4 阶段流程 v2, W68 第 13 批 D-1 升级 v4 加 alembic verify + PS 5.1 + plans 真验证 3 段)

**符合性**:
- W71 选项 A: 5 agents 全部 plans 优先 (子 plan ② 5 agents) + 0 小修 → 完全符合
- W72 选项 A: 3 agents 全部 plans 优先 (子 plan ③ 3 组件) + 0 小修 → 完全符合
- **结论**: W71 + W72 选项 A 完全符合任务模式基调

### 8.3 与锚点范式守恒 (168 → 188 单调上升) 的关系

**W68 累计**: W68 第 1 批 30 → 第 8 批 102 → 第 13 批 168 (累计 +138 守恒, 13 批)

**W71 + W72 选项 A 累计**: 168 → 178 → 188 (累计 +20 守恒, 2 批 / 4 周)

**节奏对比**:
- W68 第 1-8 批: 平均每批 +12-15 守恒 (累计 +72 守恒 / 8 批)
- W68 第 9-13 批: 平均每批 +13 守恒 (累计 +66 守恒 / 5 批)
- W71 + W72 选项 A: 平均每批 +10 守恒 (累计 +20 守恒 / 2 批)
- **结论**: W71 + W72 选项 A 节奏略低于 W68 平均, 但**符合**节奏范围 (5-15 守恒/批)

**W19 选项 A 维持**: 4 留未来 PR 不发起新排期 → W71 + W72 选项 A 不触发 (Phase 8 + Phase 2 商业化启动前必做, 不算新排期)

---

## 9️⃣ 引用 + 前序决策

### 9.1 引用文档

- **W69 plan**: [`docs/chatgpt-structured-floyd-w69-plan.md`](./chatgpt-structured-floyd-w69-plan.md) (W68 第 8 批 B-4, 锚点范式第 90 守恒)
- **W70 backlog 决策**: [`docs/w70-plans-backlog-decision-2026-07-24.md`](./w70-plans-backlog-decision-2026-07-24.md) (W68 第 13 批 B-3, 锚点范式第 163 守恒)
- **W70-W71 调研 v2**: [`docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md`](./w70-w71-plans-backlog-survey-v2-2026-07-24.md) (W68 第 14 批 A-3, 待 A-3 完成)
- **qa-bench D8 调研**: [`docs/qa-bench-d8-comprehensive-survey-2026-07-24.md`](./qa-bench-d8-comprehensive-survey-2026-07-24.md) (W68 第 14 批 C-1, 调研中)
- **W69/W70 排期**: [`docs/w69-w70-roadmap-decision-2026-07-24.md`](./w69-w70-roadmap-decision-2026-07-24.md) (W68 第 9 批 D-5)
- **W72 商业化路线**: [`docs/w72-commercialization-roadmap-2026-07-24.md`](./w72-commercialization-roadmap-2026-07-24.md) (W68 第 12 批 D-4)

### 9.2 前序决策 (主指挥拍板记录)

- W68 第 4 批: plans 优先 + 小修搭配 (memory/w68-task-mode-paradigm-plans-first-2026-07-24.md)
- W68 第 9 批 D-3: 任务模式基调 v2 (5 拍板纪律 + 4 阶段流程 v2)
- W68 第 9 批 C-1: 14 plans 留 W69 排期 (锚点范式第 67 守恒)
- W68 第 12 批 D-4: W72 商业化季度排期 (24 人月)
- W68 第 13 批 B-3: 5 plans backlog 调研 (drive-todo 100% + 5 plans 4 已闭环 + 1 长期商业化)
- W68 第 13 批 D-2: 6 类文档同步 (锚点范式第 168 守恒)
- W68 第 13 批 D-1: 派工纪要 v4 升级 (alembic verify + PS 5.1 + plans 真验证)

### 9.3 后续步骤

1. 主指挥 review 本文档 §2 W71 4 选项矩阵 + §3 W72 4 选项矩阵
2. 主指挥在 W71 启动前 1 周 (2026-07-31) 拍板选项 A (推荐), 写 `docs/w71-option-a-decision-2026-07-31.md`
3. 主指挥在 W72 启动前 1 周 (2026-08-14) 拍板选项 A (推荐), 写 `docs/w72-option-a-decision-2026-08-14.md`
4. W71 第 1 批派工 prompt 必须含"派工依据 = `docs/w71-final-decision-2026-07-24.md`", Agent 按 §4 派工清单展开
5. W71 完成后启动 W72, W72 派工 prompt 同步引用本文件 + W71 grand closure memory
6. 失败时按 §5 失败回滚 + §6 10 步 deployment checklist 走

---

> **作者**: Claude Fable 5 (Agent D-4 / W68 第 14 批) · **HEAD**: main @ 9b7c0e8a9 (W68 第 13 批 grand closure merge 后) · **0 production code 改动铁律维持** · **W19 选项 A 维持** · **锚点范式第 183 守恒预测** · **任务模式基调维持 (plans 优先 + 小修搭配)**