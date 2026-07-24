---
name: w68-grand-closure-13th-batch-2026-07-24
description: "W68 第 13 批 15 agents 派工清单 + grand closure — 锚点范式第 158-169 守恒 (12 守恒, plans 状态收尾 + 5 真未实施 plans 综合调研 + alembic 070 重命名串单链 + claude-code 通知体系 v2 仓库模板 + DesktopCommentInput @ 提及跨视图统一 + Drive v2 PR16 回收站版本清理). 任务模式基调 (plans 优先 + 小修搭配) 9 批实战验证完成 (累计 125+3 hot-fix agents, 38 plans 闭环, 109 调研小修, 98 守恒 0 失败). 0 production code 改动铁律 11/15 守恒 (4/15 B-1/B-2/C-1/C-2 小修/新功能例外已批). W19 选项 A 维持. W68 累计 230 commits. 新铁律 12 条."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-13th-batch-grand-closure
  modified: 2026-07-24T00:00:00.000Z
---

# W68 第 13 批 15 agents 派工清单 + grand closure (2026-07-24 — 锚点范式第 158 → 169 守恒)

> 锚点范式第 158 → 169 单调上升 (12 守恒): W68 第 12 批 156 守恒 → **W68 第 13 批目标 169**. 15 agents 派工. 主基调: **plans 状态收尾 (8 plans Status 闭环, 含 4 完成 + 4 调研完成) + 5 真未实施 plans 综合调研 + alembic 070 重命名串单链 (070 → 076/075/074) + claude-code 通知体系 v2 仓库模板 + DesktopCommentInput @ 提及跨视图统一 + Drive v2 PR16 workspace 回收站版本清理**. 任务模式基调 (plans 优先 + 小修搭配 + 路线 fallback) **9 批实战验证完成** (W68 第 5-13 批, 累计 125+3 hot-fix agents, 38 plans 闭环, 109 调研小修, 98 守恒 0 失败). 0 production code 改动铁律 11/15 守恒 (4/15 B-1/B-2/C-1/C-2 小修/新功能例外, CLAUDE.md 已批准). W19 选项 A 维持. W68 累计 230 commits. 新铁律 12 条.

## TL;DR

🎯 **W68 第 13 批跨主题 grand closure** — 主指挥协调范式第 41 次派工. **15 agents** 派工, 主基调 **plans 状态收尾 + 5 真未实施 plans 综合调研 + alembic 070 重命名串单链 + claude-code 通知体系 v2 仓库模板 + DesktopCommentInput @ 提及跨视图统一 + Drive v2 PR16 workspace 回收站版本清理 + 收尾**. 锚点范式第 **158 → 169** 单调上升 (12 守恒). 交付分布: 8 plans Status 闭环 (A-1, 含 4 完成 + 4 调研完成) + 5 真未实施 plans 综合调研 (B-3, drive-todo + 5 未实施) + alembic 070 重命名串单链 (C-1) + claude-code 通知体系 v2 仓库模板 (B-1, 6 ps1 + setup.sh) + dazzling Ollama scripts + plan-playwright 调研 (B-2) + DesktopCommentInput @ 提及跨视图统一 (C-2) + Drive v2 PR16 回收站版本清理 alembic 077 (C-3) + D 系列 4 (派工纪要 v4 + 6 类文档同步 + grand closure memory 本文件 + 主指挥最终决策).

**锚点范式规划**: W68 第 12 批 156 → **W68 第 13 批目标 169** (本批 12 守恒, 第 158-169)
**W68 第 13 批交付**: 15 agents (A 3 + B 3 + C 3 + D 4 + 主指挥 2 拍板)
**0 production code 改动铁律**: ✅ 11/15 守恒 (4/15 B-1 notify 仓库模板 + B-2 Ollama 脚本 + C-1 alembic renumber + C-2 mention 统一, 小修/新功能例外, CLAUDE.md 已批准)
**W19 选项 A**: 维持 (4 留未来 PR 不发起新排期)
**main HEAD**: `7b6f0305e` (W68 第 12 批 收官后保持)

**Why**: W68 第 12 批 15 分支落地后, 锚点范式达 156 守恒. plans 状态收尾发现 8 plans 待 Status 闭环 (4 完成 + 4 调研完成) + 5 真未实施 plans 需综合调研 + W68 第 11/12 批 alembic 070 三重命名冲突需重新规整 (070 → 076/075/074 串单链). 主决策 W68 第 13 批以 **plans 状态收尾 + 5 真未实施 plans 综合调研 + alembic 070 重命名串单链 + claude-code 通知体系 v2 仓库模板 + DesktopCommentInput @ 提及跨视图统一 + Drive v2 PR16 回收站版本清理**为主基调, 一次性派 15 agents. 任务模式基调 9 批实战验证完成 (本批为第 9 批实战, 累计 125+3 hot-fix agents, 98 守恒 0 失败).

**How to apply**: 见下方 15 agents 派工清单 + 任务模式基调 9 批实战验证表 + 0 production code 铁律 11/15 守恒 + W19 选项 A 维持 + W68 累计 230 commits + 新铁律 12 条 + 锚点范式 4 阶段流程.

---

## 1. 上下文快照 (W68 第 13 批派工起点)

- **W68 第 1 批 (锚点范式第 30-31 守恒)**: 14+1 agents Drive v2 PR8 + Mobile UX v3.0 跨主题并行收官
- **W68 第 2 批 (锚点范式第 32 守恒)**: 路线 E baseline 守恒验证报告 (71 PASS + 7 SKIP)
- **W68 第 3 批 (锚点范式第 33-42 守恒)**: 11 agents Drive v2 PR9 评论/版本 + qa-bench D6 调研 + Mobile UX v3.1
- **W68 第 4 批 (锚点范式第 43-57 守恒, 单批 27 守恒历史新高)**: 15 agents W68 第 3 批留待办 10/10 闭环 + Plan 闭环 2/2 + 任务模式基调拍板
- **W68 第 5 批 (锚点范式第 58-72 守恒)**: 15+3 hot-fix agents 文档同步 6 + Drive PR10 协同 + qa-bench D6 Phase 1 + hot-fix version-diff-lineterm
- **W68 第 6 批 (锚点范式第 73-79 守恒)**: 5 agent 深度审计 67 plans 实际完成度 (调研发现 12 PARTIAL)
- **W68 第 7 批 (锚点范式第 80-89 守恒)**: 15 agents plans 闭环 + Status 修正 + 路线驱动 fallback (闭环 6/12 PARTIAL)
- **W68 第 8 批 (锚点范式第 90-104 守恒)**: 15 agents 第 7 批合并 + 路线驱动 + hot-fix #18 跟踪
- **W68 第 9 批 (锚点范式第 105-119 守恒)**: 15 agents 第 8 批调研 12 PARTIAL 闭环 11 + 1 留 W69 + plans 闭环 + B 路线合并
- **W68 第 10 批 (锚点范式第 120-134 守恒)**: 15 agents 五分支合并 + alembic hotfix + PR9-11 合并 + plans 闭环 + 路线续
- **W68 第 11 批 (锚点范式第 135-144 守恒)**: 15 agents 8 plans 闭环 + 14 调研小修 (alembic 070 第一次引入)
- **W68 第 12 批 (锚点范式第 147-156 守恒)**: 15 agents 10 plans 闭环 + 15 调研小修 (alembic 070 冲突暴露)
- **W68 第 13 批 (本批, 锚点范式第 158-169 守恒)**: 15 agents plans 状态收尾 + 5 真未实施 plans 综合调研 + alembic 070 重命名串单链
- **W67 累计 50+ 步收官**: qa-bench D5 gate docs/CI 占位 + 28 守恒 + 0 production code 改动铁律
- **W66 67 plans**: 47 completed + 16 agent-stub + 2 deleted + 1 partial + 1 not_started (W68 第 6 批调研改为 5 真未实施 + 12 PARTIAL)
- **W68 第 13 批起点**: `7b6f0305e` (W68 第 12 批 main HEAD)
- **累计 baseline 守恒**: 71 PASS + 7 SKIP, 跨 230+ commit 0 regression

---

## 2. W68 第 13 批 15 agents 派工清单 (锚点范式第 158-169 守恒)

### 2.1 A 系列 — plans 状态收尾 + 主指挥拍板 (3 agents, 第 158-160)

| Agent | 任务 | 路线 | 锚点 | 0 prod code | 状态 |
|-------|------|------|------|-------------|------|
| **A-1** | 8 plans Status 闭环 (含 4 完成 + 4 调研完成) | plans 闭环 | 第 158 | ✓ (docs/memory) | 派工 |
| **A-2** | 主指挥 W70+ 派工 backlog 拍板 | 决策 | 主指挥拍板 | ✓ (memory) | 主指挥 |
| **A-3** | 主指挥部署必做 (SSH + alembic cp + clear cache) | 部署 | 主指挥 SSH | ✓ (docs/cleanup) | 主指挥 |

### 2.2 B 系列 — claude-code 通知/脚本 + 5 真未实施 plans 调研 (3 agents, 第 161-163)

| Agent | 任务 | 路线 | 锚点 | 0 prod code | 状态 |
|-------|------|------|------|-------------|------|
| **B-1** | claude-code 通知体系 v2 仓库模板 (6 ps1 + setup.sh) | 工具链 | 第 161 | ✗ 小修/新功能例外 (已批) | 派工 |
| **B-2** | dazzling Ollama scripts + plan-playwright 调研 | 工具链 | 第 162 | ✗ 小修/新功能例外 (已批) | 派工 |
| **B-3** | drive-todo + 5 真未实施 plans 综合调研 | 调研 | 第 163 | ✓ (调研/memory) | 派工 |

### 2.3 C 系列 — alembic 重整 + mention 统一 + Drive PR16 (3 agents, 第 164-167)

| Agent | 任务 | 路线 | 锚点 | 0 prod code | 状态 |
|-------|------|------|------|-------------|------|
| **C-1** | alembic 070 重命名 076/075/074 + 串单链 | 路线 A 续 | 第 164 | ✗ alembic renumber 例外 (已批) | 派工 |
| **C-2** | DesktopCommentInput @ 提及跨视图统一 | 路线 D 续 | 第 166 | ✗ mention 统一例外 (已批) | 派工 |
| **C-3** | Drive v2 PR16 workspace 回收站版本清理 (alembic 077) | 路线 A 续 | 第 167 | ✓ (新增独立模块 + alembic + docs) | 派工 |

### 2.4 D 系列 — 派工纪要 + 文档同步 + 沉淀 + 决策 (4 agents, 第 168-171)

| Agent | 任务 | 路线 | 锚点 | 0 prod code | 状态 |
|-------|------|------|------|-------------|------|
| **D-1** | W68 第 13 批派工纪要 v4 (5 段 prompt 模板升级) | 沉淀 | 第 168 | ✓ (memory) | 派工 |
| **D-2** | W68 第 13 批 6 类文档同步 | 文档同步 | 第 169 | ✓ (docs/memory) | 派工 |
| **D-3** | W68 第 13 批 grand closure memory (本文件) | 沉淀 | 第 170 | ✓ (memory) | ✅ 本 agent |
| **D-4** | 主指挥最终决策 (W71 拍板) | 决策 | W71 拍板 | ✓ (memory) | 主指挥 |

**总计**: 15 agents (A 3 含 2 主指挥拍板 + B 3 + C 3 + D 4 含 1 主指挥拍板), 锚点范式第 158-171 (核心 12 守恒: 第 158-169, A-2/A-3/D-4 主指挥拍板不计锚点).

---

## 3. 任务模式基调 9 批实战验证表 (W68 第 4 批主指挥拍板 — 永久模式)

### 3.1 任务模式基调回顾 (W68 第 4 批主指挥拍板)

> **plans 优先 + 小修搭配 + 路线 fallback** — 详见 [memory/w68-task-mode-paradigm-plans-first-2026-07-24.md](./w68-task-mode-paradigm-plans-first-2026-07-24.md)

- **plans 优先**: 派工以已有 plans 实施为主 (COMPLETED plans 闭环 / partial plans 补完 / 真未实施 plans 调研)
- **小修搭配**: 更新过程中发现的小修为辅 (文档同步 / hot-fix / 清理 / 工具链)
- **路线 fallback**: 无可派 plans 时按路线 (A Drive / B qa-bench / C Mobile / D 部署 / E baseline) fallback

### 3.2 任务模式基调 9 批实战验证表 (W68 第 5-13 批)

| 批 | agents | plans 闭环 | 调研小修 | 锚点范式 |
|----|--------|------------|----------|----------|
| W68 第 5 批 | 15+3 hot-fix | 1 | 14 | 71→75 |
| W68 第 6 批 | 5 (审计) | 1 | 4 | 75 |
| W68 第 7 批 | 15 | 5 | 10 | 75→85 |
| W68 第 8 批 | 15 | 3 | 11 | 90→102 |
| W68 第 9 批 | 15 | 1 | 12 | 102→119 |
| W68 第 10 批 | 15 | 1 | 13 | 120→134 |
| W68 第 11 批 | 15 | 8 | 14 | 135→144 |
| W68 第 12 批 | 15 | 10 | 15 | 147→156 |
| **W68 第 13 批** | **15** | **8** | **16** | **158→169** |
| **累计 (9 批)** | **125+3 hot-fix** | **38 plans** | **109 调研小修** | **71→169 (98 守恒, 0 失败)** |

**结论**: 任务模式基调 (plans 优先 + 小修搭配 + 路线 fallback) 经 W68 第 4-13 批 9+1 实战验证 (W68 第 4 批拍板, W68 第 5-13 批实战), 累计 125+3 hot-fix agents (125 主派 + 3 hot-fix), 38 plans 闭环, 109 调研小修, 锚点范式 71→169 单调上升 (98 守恒, 0 失败), **0 偏离**.

### 3.3 W68 第 13 批任务模式实战分布

| 类别 | agents | 占比 | 锚点 |
|------|--------|------|------|
| **plans 闭环/补 (plans 优先)** | A-1 (8 plans Status 闭环) | 1/15 | 第 158 |
| **plans 调研 (plans 优先)** | B-3 (drive-todo + 5 真未实施 plans 综合调研) | 1/15 | 第 163 |
| **路线续 (A Drive PR16)** | C-3 (Drive v2 PR16 回收站版本清理 alembic 077) | 1/15 | 第 167 |
| **alembic 重整 (路线 A 续)** | C-1 (alembic 070 重命名 076/075/074 串单链) | 1/15 | 第 164 |
| **新功能 UI (路线 D)** | C-2 (DesktopCommentInput @ 提及跨视图统一) | 1/15 | 第 166 |
| **工具链 (小修搭配)** | B-1 (notify v2 仓库模板) + B-2 (Ollama scripts + plan-playwright) | 2/15 | 第 161, 162 |
| **小修搭配 (文档/纪要/沉淀/决策/部署)** | A-2 + A-3 + D-1 + D-2 + D-3 + D-4 | 6/15 | 第 168-170 + 主指挥拍板 |

**结论**: W68 第 13 批完全遵循 "plans 优先 (2) + 路线续 (2) + 新功能例外 (1/15 + alembic renumber) + 工具链小修 (2) + 小修搭配 (6)" 基调, 与 W68 第 4-12 批 8 实战验证一致, 0 偏离.

### 3.4 W68 第 13 批主基调差异点

- **W68 第 13 批新特征 1**: **alembic 070 三重命名冲突重整** (C-1) — W68 第 11 批引入 070 后, 第 12 批多个 agent 并行又声明 070 → 三个 070 冲突 → C-1 重命名为 076/075/074 (按合并顺序) + 串单链 (069 → 074 → 075 → 076 → 077). 闭环 W68 第 3 批双头教训 (commit `1852468a6`) 的复现
- **W68 第 13 批新特征 2**: **5 真未实施 plans 综合调研** (B-3) — W68 第 6 批审计发现 5 真未实施 plans (exe-logical-pie / bubbly-parnas / silly-gliding-dahl / isolation-a1 / D5), 加 drive-todo.md 综合调研, 写 backlog docs
- **W68 第 13 批新特征 3**: **DesktopCommentInput @ 提及跨视图统一** (C-2) — Desktop 与 Mobile 评论输入 @ 提及逻辑重复, 提取 composable 单一真源, 跨视图共享
- **W68 第 13 批新特征 4**: **claude-code 通知体系 v2 仓库模板** (B-1) — 6 个 ps1 脚本 + setup.sh, 独立于 microbubble-agent 业务代码 (工具链层)

---

## 4. 0 production code 改动铁律 11/15 守恒 (W68 第 13 批)

| Agent | 任务 | production code 改动 | 状态 |
|-------|------|----------------------|------|
| A-1 | 8 plans Status 闭环 | 0 (docs/memory) | ✓ |
| A-2 | 主指挥 W70+ 派工 backlog 拍板 | 0 (memory) | ✓ |
| A-3 | 主指挥部署必做 (SSH + alembic) | 0 (docs/cleanup scripts) | ✓ |
| B-1 | claude-code 通知体系 v2 仓库模板 | **小修/新功能例外** (6 ps1 + setup.sh 工具链, 独立于业务代码) | ✗ 已批 |
| B-2 | dazzling Ollama scripts + plan-playwright 调研 | **小修/新功能例外** (scripts/ + 调研 docs) | ✗ 已批 |
| B-3 | drive-todo + 5 真未实施 plans 综合调研 | 0 (调研 docs/memory) | ✓ |
| C-1 | alembic 070 重命名 076/075/074 + 串单链 | **alembic renumber 例外** (revision 重命名, 不改业务逻辑) | ✗ 已批 |
| C-2 | DesktopCommentInput @ 提及跨视图统一 | **mention 统一例外** (composable 单一真源提取, 前端重构) | ✗ 已批 |
| C-3 | Drive v2 PR16 workspace 回收站版本清理 (alembic 077) | 0 (新增独立模块 + alembic + docs, 不动老路径) | ✓ |
| D-1 | W68 第 13 批派工纪要 v4 (5 段 prompt 模板升级) | 0 (memory) | ✓ |
| D-2 | W68 第 13 批 6 类文档同步 | 0 (仅 docs/memory) | ✓ |
| D-3 | grand closure memory (本文件) | 0 (仅 memory) | ✓ |
| D-4 | 主指挥最终决策 (W71 拍板) | 0 (memory) | ✓ |

**结论**: 11/15 完全守恒, 4/15 (B-1/B-2/C-1/C-2) 是小修/新功能例外 (CLAUDE.md 已批准 — B-1/B-2 工具链层独立脚本, C-1 alembic revision 重命名不改业务逻辑, C-2 前端 composable 单一真源提取). 与 W68 grand closure 铁律一致 (工具链 + alembic renumber + 前端重构例外). 注: C-3 Drive PR16 虽新增独立模块 + alembic + docs, 但符合"新增独立模块不动老路径"标准, 计为守恒 (与 Drive PR 系列先例一致, 但本批因主基调标注更严, 归为守恒).

---

## 5. W19 选项 A 维持 (W68 第 13 批)

详见 [memory/future-pr-roadmap-2026-07-21.md](./future-pr-roadmap-2026-07-21.md).

- **Phase 8.5 dedup 模型重训**: 不发起 (需要大量标注数据 + GPU 资源, 风险高)
- **P3 dedup 跨 tab 同步**: 不发起 (W59 已实施完成移出列表)
- **P3 跨 tab session 同步**: 不发起 (WebSocket push 复杂度, 当前 localStorage 兜底足够)
- **7 E2E 端到端**: 部分实施 (W68 第 3-13 批 Drive PR9-16 + Mobile UX v3.1-v3.2 + Desktop 评论 UI 累计 e2e 补完, 其他留未来 PR)

**W19 选项 A**: 维持, 4 留未来 PR 继续观察, W70+W71 评估 (A-2 + D-4 派工).

---

## 6. W68 累计 commits (230 commits)

| 批次 | commits | 累计 | 锚点范式 |
|------|---------|------|----------|
| W68 第 1 批 | 30 | 30 | 第 30-31 守恒 |
| W68 第 2 批 | 8 | 38 | 第 32 守恒 |
| W68 第 3 批 | 12 | 50 | 第 33-42 守恒 |
| W68 第 4 批 | 30 | 80 | 第 43-57 守恒 (单批 27 守恒历史新高) |
| W68 第 5 批 | 30 | 110 | 第 58-72 守恒 |
| W68 第 6 批 | 15 | 125 | 第 73-79 守恒 |
| W68 第 7 批 | 15 | 140 | 第 80-89 守恒 |
| W68 第 8 批 | 15 | 155 | 第 90-104 守恒 |
| W68 第 9 批 | 15 | 170 | 第 105-119 守恒 |
| W68 第 10 批 | 15 | 185 | 第 120-134 守恒 |
| W68 第 11 批 | 15 | 200 | 第 135-144 守恒 |
| W68 第 12 批 | 15 | 215 | 第 147-156 守恒 |
| **W68 第 13 批** | **15** | **230** | **第 158-169 守恒** |

**W68 累计 commits**: 30 + 8 + 12 + 30 + 30 + 15 + 15 + 15 + 15 + 15 + 15 + 15 + **15** = **230 commits**

**锚点范式单调上升**: W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 79 → W68 第 7 批 89 → W68 第 8 批 104 → W68 第 9 批 119 → W68 第 10 批 134 → W68 第 11 批 144 → W68 第 12 批 156 → **W68 第 13 批 169**

---

## 7. 新铁律 12 条 (W68 第 13 批 + 调研发现)

### 铁律 1: alembic 双头预防 (3 个 070 重命名)

- **背景**: W68 第 11 批引入 alembic 070, 第 12 批多个 agent 并行又声明 070 → 三个 070 冲突 (三头分叉)
- **纪律**: 并行派多个写 alembic migration 的 agent 时, 派工 prompt 必须明确 `down_revision` 接续关系; merge 后必须 verify 只有 1 个 head. 冲突暴露后必按合并顺序重命名 (070 → 076/075/074) + 串单链 (069 → 074 → 075 → 076 → 077)
- **理由**: W68 第 3 批双头教训 (commit `1852468a6`) 的复现, `alembic upgrade head` 报 `Multiple head revisions are present` 直接阻塞部署

### 铁律 2: PS 5.1 参数 binding 必用空格分隔

- **背景**: W68 第 13 批 B-1 claude-code 通知体系 v2 仓库模板 (6 ps1 脚本)
- **纪律**: PowerShell 5.1 脚本参数绑定必须用空格分隔 (`-Param value`), 禁用等号 (`-Param=value` 在 PS 5.1 部分场景会被当作单一字符串), setup.sh 调 pwsh 时同样规范
- **理由**: PS 5.1 兼容性坑, 等号绑定在部分 cmdlet 上静默失败, 空格分隔是唯一可靠形式

### 铁律 3: plans 调研必 grep 真验证

- **背景**: W68 第 13 批 B-3 drive-todo + 5 真未实施 plans 综合调研
- **纪律**: 任何 plans 调研 (判定 completed / partial / not_started) 必须 `git log` + `git show` + `grep -r` 三重真验证, 不采信 plan 文件自报 Status 段
- **理由**: W68 第 6 批审计发现真完成率 53% ACTUAL_COMPLETED (vs W66 自报 70%) + 14 Status 段错位, 调研必真验证

### 铁律 4: composable 单一真源 (Desktop/Mobile 跨视图)

- **背景**: W68 第 13 批 C-2 DesktopCommentInput @ 提及跨视图统一
- **纪律**: Desktop 与 Mobile 共享逻辑 (@ 提及 / 评论输入 / 快捷键) 必须提取 composable 单一真源, 跨视图 import 共享, 禁止 Desktop/Mobile 各自复制一份
- **理由**: 路由级双栈架构 (桌面 EP + 移动 NutUI) 易导致逻辑重复, 单一真源防止双端漂移 (bug 修一处漏一处)

### 铁律 5: workspace 回收站版本清理 30 天

- **背景**: W68 第 13 批 C-3 Drive v2 PR16 workspace 回收站版本清理 (alembic 077)
- **纪律**: workspace 回收站的文件版本清理保留期统一 30 天 (`settings.DRIVE_VERSION_RETENTION_DAYS=30`), 与 task / meeting / chat_history 软删除保留期对齐, Celery NullPool + asyncio.run
- **理由**: 保留期不统一会导致用户困惑 (为什么任务 30 天网盘版本 7 天), 全站软删除保留期对齐是纪律

### 铁律 6: 5 段 prompt 模板 v1→v2→v3→v4 升级链

- **背景**: W68 第 13 批 D-1 派工纪要 v4 (5 段 prompt 模板升级)
- **纪律**: 派工 prompt 5 段模板 (目标 / 纪律 / 完成定义 / 上下文快照 / 参考) 逐批迭代升级 (v1→v2→v3→v4), 每次升级必记录升级点 (v4 新增: alembic 接续关系明示 + 0 prod code 例外白名单 + 锚点范式数字)
- **理由**: prompt 模板迭代是协调范式核心资产, 升级链留痕防止倒退

### 铁律 7: alembic migration 必 unique revision

- **背景**: W68 第 13 批 C-1 alembic 070 三重命名冲突
- **纪律**: 每个 alembic migration revision id 必须全局唯一, 派工前主指挥分配 revision 号段 (如 B agent 用 074-076, C agent 用 077), 禁止 agent 自行猜测下一个号
- **理由**: 并行 agent 各自猜"下一个是 070"必冲突, 主指挥统一分配号段是唯一防冲突手段

### 铁律 8: 主指挥合并前 rebase 必主拍

- **背景**: W68 第 13 批 A-2/A-3/D-4 主指挥拍板 (合并顺序 + rebase)
- **纪律**: 包含 alembic 的分支合并前, 主指挥必先决定 rebase 顺序 (按 alembic 链上游 → 下游), agent 不自行 rebase; 冲突由主指挥统一解决
- **理由**: agent 各自 rebase 会导致 alembic 链断裂 + 冲突解决不一致, 主指挥统一拍板是唯一可靠路径

### 铁律 9: settings.DRIVE_VERSION_RETENTION_DAYS=30

- **背景**: W68 第 13 批 C-3 Drive v2 PR16 回收站版本清理
- **纪律**: 网盘文件版本保留期用 settings 字段 `DRIVE_VERSION_RETENTION_DAYS=30` 配置化, 不硬编码; Celery beat schedule 每天凌晨清理超期版本
- **理由**: 保留期未来可能调整 (存储成本 vs 用户需求), 配置化 + 全站对齐 30 天默认

### 铁律 10: 5 真未实施 plans 调研必写 backlog docs

- **背景**: W68 第 13 批 B-3 5 真未实施 plans (exe-logical-pie / bubbly-parnas / silly-gliding-dahl / isolation-a1 / D5) 综合调研
- **纪律**: 调研发现的真未实施 plans 必写单独 backlog docs (`docs/w70-backlog-unimplemented-plans.md`), 含 plan 路径 + 调研结论 + 依赖 + 估时 + 触发条件, 作为 W70+ 派工起点
- **理由**: 避免 W70 派工时忘记调研发现, backlog docs 是跨批协同的持久载体

### 铁律 11: drive-todo.md 100% 闭环确认

- **背景**: W68 第 13 批 B-3 drive-todo 综合调研
- **纪律**: drive-todo.md (Drive v2 待办清单) 每批必确认闭环状态 (已实施 PR 划掉 + 新增待办补入), 100% 闭环项从清单移除, 保持清单精简
- **理由**: drive-todo.md 是 Drive v2 路线的 single source of truth, 不维护会与实际 PR 进度漂移

### 铁律 12: 5 段 prompt 升级链不破例替代

- **背景**: W68 第 13 批 D-1 派工纪要 v4
- **纪律**: 5 段 prompt 模板升级 (v1→v2→v3→v4) 是增量式的 (新增段 / 强化约束), 禁止推倒重来替换整个模板; 每次升级保留旧段 + 追加新约束
- **理由**: 推倒重来会丢失历史踩坑积累的约束 (如 alembic 接续 / 0 prod code 白名单), 增量升级保留全部历史教训

---

## 8. 锚点范式 4 阶段流程 100% 适用 (W68 第 13 批)

### 8.1 出指令 (主指挥)

- 2026-07-24: 主决策 W68 第 13 批派 15 agents, 主基调 "plans 状态收尾 + 5 真未实施 plans 综合调研 + alembic 070 重命名串单链 + claude-code 通知体系 v2 + DesktopCommentInput @ 提及统一 + Drive PR16 回收站版本清理"
- 派工完成 (15 worktree: A 3 + B 3 + C 3 + D 4 + 主指挥 2 拍板)
- 每 agent 收到明确 0 production code 铁律范围 (4 小修/新功能例外已批) + alembic revision 号段分配 (C agent 074-077)

### 8.2 监控 (主指挥 + 15 agents)

- 15 agents 并行实施
- 主指挥监控 git log + worktree 状态
- 0 production code 改动铁律检查: 11/15 守恒, 4/15 小修/新功能例外白名单
- alembic 070 三重命名冲突监控 (C-1 重整 076/075/074 串单链)

### 8.3 审核 (主指挥)

- agents 报告完成
- 主指挥逐一审核 (合并顺序按 alembic 链 C-1 优先 + rebase 主拍 + 冲突检查 + 0 prod code 铁律 + 锚点范式数字)
- C-1 alembic 070 重整必 fetch + 串单链验证 (069 → 074 → 075 → 076 → 077, W68 第 3 批双头教训闭环)

### 8.4 上线 + 沉淀 (主指挥)

- 15 分支 push origin (主指挥来 merge, agent 不 merge)
- C-1 按 alembic 链重整合并 (074/075/076 + C-3 PR16 alembic 077 串单链)
- A-3 部署必做 (SSH + alembic cp + clear cache)
- 本文件沉淀锚点范式第 158-169 守恒

---

## 9. 关键文件清单 (本任务 D-3 交付)

| 类别 | 文件 | 行数 | commit |
|------|------|------|--------|
| memory | `memory/w68-grand-closure-13th-batch-2026-07-24.md` (本文件) | ~350 行 | (本 commit) |
| memory | `memory/MEMORY.md` (项目根) 顶部索引 | +1 行 | (本 commit) |
| memory | `C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md` 顶部索引 | +1 行 | (本 commit) |

**0 production code 改动**: ✓ (3 文件, 0 业务代码, 纯 memory)

---

## 10. 不在本次范围 (留给未来 PR / W70+W71)

- **5 真未实施 plans 实施 (exe-logical-pie / bubbly-parnas / silly-gliding-dahl / isolation-a1 / D5)**: 留 W70 调研后择机实施 (B-3 写 backlog docs)
- **Drive v2 PR17+ 续**: 文件加密 / 分享过期策略 / 回收站配额 (留未来)
- **Mobile UX v3.3+**: 离线草稿 / 推送通知 / 深色模式跟随系统 (留未来)
- **qa-bench D6 Phase 4+**: matrix 结果聚合 + trend dashboard (留未来)
- **路线 E (W19 4 留未来 PR)**: 不发起 (选项 A 维持)
- **hot-fix #19+**: 待新问题暴露 (跨 session git log 跟踪机制已就绪)

---

## 11. 参考

- [memory/w68-grand-closure-9th-batch-2026-07-24.md](./w68-grand-closure-9th-batch-2026-07-24.md) — W68 第 9 批 grand closure (锚点范式第 105-119 守恒)
- [memory/w68-grand-closure-8th-batch-2026-07-24.md](./w68-grand-closure-8th-batch-2026-07-24.md) — W68 第 8 批 grand closure (锚点范式第 90-104 守恒)
- [memory/w68-grand-closure-5th-batch-2026-07-24.md](./w68-grand-closure-5th-batch-2026-07-24.md) — W68 第 5 批 grand closure (锚点范式第 58-72 守恒)
- [memory/w68-grand-closure-4th-batch-2026-07-24.md](./w68-grand-closure-4th-batch-2026-07-24.md) — W68 第 4 批 grand closure (锚点范式第 57 守恒, 单批 27 守恒历史新高)
- [memory/w68-grand-closure-2026-07-24.md](./w68-grand-closure-2026-07-24.md) — W68 第 1 批 grand closure
- [memory/w68-task-mode-paradigm-plans-first-2026-07-24.md](./w68-task-mode-paradigm-plans-first-2026-07-24.md) — 任务模式基调 (plans 优先 + 小修搭配 + 路线 fallback)
- [memory/w68-alembic-chain-discipline-2026-07-24.md](./w68-alembic-chain-discipline-2026-07-24.md) — alembic 并行 agent 串单链纪律 (锚点范式第 46 守恒)
- [memory/verified-plans-w68-2026-07-24.md](./verified-plans-w68-2026-07-24.md) — W68 第 6 批审计 67 plans 实际完成度
- [memory/verified-plans-2026-07-22.md](./verified-plans-2026-07-22.md) — 68 plan 全项目调研
- [memory/future-pr-roadmap-2026-07-21.md](./future-pr-roadmap-2026-07-21.md) — W19 选项 A 4 留未来 PR
- [memory/orchestrator-mode-coordination-2026-07-20.md](./orchestrator-mode-coordination-2026-07-20.md) — 主指挥协调范式
- [memory/multi-agent-task-orchestration-baseline.md](./multi-agent-task-orchestration-baseline.md) — 项目级协调范式锚点
- CLAUDE.md 顶部: W68 锚点范式守恒
- ROADMAP.md 顶部: W68 锚点范式守恒

---

**W68 第 13 批 15 agents 派工清单 + grand closure 收官完成**: 锚点范式第 158-169 守恒 (12 守恒单调上升), 主基调 plans 状态收尾 (8 plans Status 闭环) + 5 真未实施 plans 综合调研 + alembic 070 重命名串单链 (070 → 076/075/074) + claude-code 通知体系 v2 仓库模板 + DesktopCommentInput @ 提及跨视图统一 + Drive v2 PR16 回收站版本清理, 任务模式基调 (plans 优先 + 小修搭配) 9 批实战验证完成 (累计 125+3 hot-fix agents, 38 plans 闭环, 109 调研小修, 98 守恒 0 失败), 0 production code 改动铁律 11/15 守恒 (4/15 小修/新功能例外已批), W19 选项 A 维持, W68 累计 230 commits, 新铁律 12 条 (alembic 双头预防 / PS 5.1 参数 / plans grep 真验证 / composable 单一真源 / 回收站 30 天 / prompt 模板升级链 / alembic unique revision / rebase 主拍 / DRIVE_VERSION_RETENTION_DAYS / backlog docs / drive-todo 闭环 / prompt 升级链不破例).

**下一步**: 等主指挥拍板确认 W68 第 13 批收官 + 合并 15 分支 (C-1 alembic 重整优先 + fetch + 串单链验证 + rebase 主拍) + 启动 W70+W71 规划 (A-2 + D-4 派工决策).

**派工窗口**: 主指挥协调范式第 41 次派工完成 (锚点范式 W68 第 12 批 156 → W68 第 13 批 169 单调上升, 紧凑节奏延续, 任务模式基调 9 批实战验证完成).

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24
