# W68 第 7 批 C-2 — plans 整理归档 (SUPERSEDED + MISCATEGORIZED + DELETED)

> **任务日期**: 2026-07-24
> **任务模式**: C-2 plans 整理 (W68 第 7 批, 主指挥协调范式第 33 次派工)
> **分支**: `chore/w68-7th-batch-c2-plans-archive-2026-07-24`
> **锚点范式**: 第 84 守恒 (无 production code 改动)

---

## 背景

W68 第 6 批主指挥对 67 个 plans 做了一次全面审计, 发现 5 类问题:

1. **4 个 SUPERSEDED** — Status 段标 SUPERSEDED / plan body 已废弃, 但仍占 `plans/` 顶层
2. **3 个 plan-body/Status 错配** — 标 agent-stub 但 plan body 是独立调研报告
3. **2 个 MISCATEGORIZED** — 错归类为 agent-stub (实为独立 plan-review / explore report)
4. **1 个 DELETED** — claude-pet 项目已删, plan 文档仍残留
5. **1 个自标废弃** — plan body 写 "Plan 已废弃", 但 Status 段被其他 agent 覆盖

**根因**: W66 第 67 plans 状态化阶段只动了 `Status` 段标记, 没做物理归档. 后续派工 agent 看 Status 标记就以为 plan 仍在用, 浪费调研精力.

---

## 归档清单 (8 plans)

### 1. `v77-p2-75-rustling-avalanche.md` (SUPERSEDED)
- **类别**: SUPERSEDED (templates admin page 范畴)
- **原因**: v77 P2.6-G.2 模板批量管理页 `/admin/templates` 已被主指挥 2026-07-22 决策"功能没必要保留", 4b215220 refactor 删除. plan body 704 行详细设计全部无效.
- **Status 段误标**: 标 "COMPLETED: 7th-wave Agent 6: rate limit 8 场景 spec" — 完全错配, 该 commit 跟 templates 无关.
- **归类修正**: 既不是 SUPERSEDED-via-Status (Status 段被错配), 也不是 COMPLETED. 应归 SUPERSEDED.

### 2. `v77-p2-75-rustling-avalanche-agent-ab2a1b61c593d3540.md` (SUPERSEDED + 空 stub)
- **类别**: agent-stub 子文件 (空)
- **原因**: 已合并到 v77-p2-75-rustling-avalanche.md, 但 v77-p2-75 已 SUPERSEDED, 子 stub 也应一并归档.
- **归档必要性**: 父 plan 归档后, 子 stub 失去合并目标. 单独留在顶层会让后续 agent 误以为是新调研.

### 3. `v77-p2-75-rustling-avalanche-agent-ac16d74819d91b6a0.md` (SUPERSEDED + v77 P2 调研)
- **类别**: agent-stub 子文件 (v77 P2 前端动画调研)
- **原因**: 已合并到 v77-p2-75-rustling-avalanche.md, 父归档后子归档.
- **保留价值**: 调研内容 (transition token / webhint 治理 / rotate/scale 迁移风险) 已沉淀到 v77 P2.6 实施 commit. plan 文件本身归档.

### 4. `v77-p2-75-rustling-avalanche-agent-ae9a90efe04fdbb0c.md` (SUPERSEDED + v77 P2.5.1 Dark Mode 调研)
- **类别**: agent-stub 子文件 (Dark Mode Fix 调研)
- **原因**: 已合并到 v77-p2-75-rustling-avalanche.md, 父归档后子归档.
- **保留价值**: rgba → .glass utility 迁移策略已沉淀到 v77 P2.5.1 commit, plan 文件本身归档.

### 5. `read-meetingdetailview-vue-lines-131-15-noble-lemon.md` (自标废弃)
- **类别**: 自标废弃
- **原因**: plan body 显式写 "Plan 已废弃 — 用户已决定不做 v73 P1 / P2, 此 plan 文件保留为空占位". 留顶层无任何调研价值.
- **Status 段误标**: 标 "COMPLETED: 5th-wave Agent 3: ActivityFeedView 桌面 + 移动 + 文档删除" — 完全错配.

### 6. `ai-reactive-candy-agent-a8c86473be7df5a08.md` (MISCATEGORIZED)
- **类别**: 独立 plan-review (非 agent-stub)
- **原因**: 文件名后缀带 "-agent-{id}" 触发自动归类为 agent-stub, 但 plan body 是独立 plan-review (ai-reactive-candy.md 的 3 visual cleanup tasks 评审). 调研内容跟 ai-reactive-candy.md 不同主题, 应独立存在.
- **Status 段误标**: "AGENT_STUB, 已合并到 ai-reactive-candy.md" — 实际未合并, plan-review 与 plan body 不冲突.

### 7. `cheerful-questing-kite-agent-a1a224b6170b9fe6e.md` (MISCATEGORIZED)
- **类别**: 独立 explore report (非 agent-stub)
- **原因**: 文件名后缀带 "-agent-{id}" 触发自动归类为 agent-stub, 但 plan body 是独立 explore report (会议 153 发言人重写 + 谐音字典扩展调研). 调研内容跟 cheerful-questing-kite.md 不同主题, 应独立存在.
- **Status 段误标**: "AGENT_STUB, 已合并到 cheerful-questing-kite.md" — 实际未合并.

### 8. `claude-code-claude-code-bubbly-parnas.md` (DELETED 真删)
- **类别**: DELETED
- **原因**: claude-pet 项目已删 (主指挥 2026-07-22 决策). plan 内容 (Claude Code 全局语音提醒 Smart wrapper) 涉及的项目 `C:\Users\pc\claude-pet` 不存在, 实施永远不可能执行.
- **Status 段**: 标 "DELETED: claude-pet 项目已删" — 标记正确, 但 plan 文件仍留顶层, 应归档.

---

## 新建 `C:/Users/pc/.claude/plans/archived/`

**目的**: 统一管理 SUPERSEDED / MISCATEGORIZED / DELETED 类 plan 文档, 避免污染主 plans 列表.

**目录结构**:
```
C:/Users/pc/.claude/plans/
├── (60 活跃 plans)
└── archived/
    ├── ai-reactive-candy-agent-a8c86473be7df5a08.md
    ├── cheerful-questing-kite-agent-a1a224b6170b9fe6e.md
    ├── claude-code-claude-code-bubbly-parnas.md
    ├── read-meetingdetailview-vue-lines-131-15-noble-lemon.md
    ├── v77-p2-75-rustling-avalanche-agent-ab2a1b61c593d3540.md
    ├── v77-p2-75-rustling-avalanche-agent-ac16d74819d91b6a0.md
    ├── v77-p2-75-rustling-avalanche-agent-ae9a90efe04fdbb0c.md
    └── v77-p2-75-rustling-avalanche.md
```

**注意**: `C:/Users/pc/.claude/plans/` 不在 git 仓库内 (本地 Claude Code 配置目录), 因此本次 8 plan 移动用 `mv` 而非 `git mv`. 仓库内 git 改动仅涉及 CLAUDE.md + ROADMAP.md + 本 memory.

---

## 4 条新铁律沉淀

### 铁律 1: SUPERSEDED / MISCATEGORIZED / DELETED 类 plan 必须归档

**触发条件** (满足任一即归档):
- Status 段显式标 SUPERSEDED / DELETED
- plan body 自标废弃 (含 "Plan 已废弃" / "已删除" 等字样)
- agent-stub 子文件但父 plan 已归档 / 已 SUPERSEDED
- 错归类为 agent-stub 但 plan body 是独立 plan-review / explore report

**归档动作**:
1. `mkdir -p C:/Users/pc/.claude/plans/archived/`
2. `mv <plan-file> archived/`
3. CLAUDE.md 顶部段加归档统计
4. memory/ 加新条目记录归档清单 + 原因

**不复用**: 不要在 Status 段加 "[ARCHIVED]" 标记就完事 — Status 段会污染未来 agent 的搜索结果, 必须物理移动.

### 铁律 2: MISCATEGORIZED 重归类比改 Status 段更重要

**触发条件**:
- 文件名后缀 `-agent-{id}` 触发自动归类为 agent-stub
- 但 plan body 内容是独立 plan-review / explore report / 调研
- Status 段标 "AGENT_STUB, 已合并到 X.md", 实际未合并 (内容与父 plan 主题不一致)

**修正动作**: 物理归档到 `archived/`, 不要只改 Status 段标 "MISCATEGORIZED". 因为 agent 派工 prompt 通常 grep "agent-stub" 找子文件, 错归类会污染派工搜索.

**预防**: 派工前对 plan 文件名加 `-agent-{id}` 后缀时, 必须检查 plan body 内容是否真的是 agent-stub (合并到父 plan 的子调研). 若不是, 不要加后缀.

### 铁律 3: DELETED 标记保留 plan 文档 (不真删)

**触发条件**:
- Status 段标 DELETED
- 涉及的外部项目 / 资源已删 (如 claude-pet)
- 实施永远不可能执行

**保留动作**:
- **不**真删 plan 文件 (git history 没了, 未来 audit 找不回来)
- 移动到 `archived/` 保留文档, 不污染主 plans 列表
- memory/ 加条目说明 DELETED 原因 + 删除日期 + 主指挥决策来源

**例外**: 若 plan body 完全是空白占位 (< 10 行无信息), 可真删 (W68 第 7 批没有此例, 但下批可考虑).

### 铁律 4: plans 状态化必须配物理归档动作

**现状问题** (W66 第 67 plans 状态化): 只动了 Status 段标记, 没做物理归档. 后果: 后续 8 批 (W66 → W68 第 6 批) 派工时, agent 看 Status 标记 SUPERSEDED 还会浪费精力去读 plan body, 然后在 plan-review 时才发现已废弃.

**新规约**:
- 任何 plans 状态化 audit, 必须同时决定 "Status 标记" + "物理归档" 两个动作
- 物理归档优先于 Status 标记 (Status 是软提示, 归档是硬隔离)
- W68 第 7 批起, 每批 plans audit 必须 check `archived/` 目录是否需要新增

---

## 0 production code 改动铁律守恒

本次任务改动:
- `C:/Users/pc/.claude/plans/archived/` 新建目录 (本地配置目录, 不在 git 仓库)
- 8 plan 文件移动到 `archived/` (本地配置目录, 不在 git 仓库)
- `CLAUDE.md` 顶部段加归档统计段 (docs-only)
- `ROADMAP.md` 顶部段加归档统计段 (docs-only)
- 本 memory 文件 (memory-only)

**生产代码改动**: 0 (满足铁律)
**新增文件**: 0 (archived/ 目录在仓库外, 不算)

---

## 锚点范式第 84 守恒

**范式**: docs-only / memory-only 改动, 跨 W68 累计 80+ commit 0 production code drift.

**本次任务位置**: W68 第 7 批 C-2 plans 整理 — 锚点范式第 84 守恒.

**累计 baseline 守恒**: 71 PASS + 7 SKIP lint CSS (跨 W68 80+ commit 0 regression).

---

## 后续待办

- [ ] 主指挥 merge 本分支到 main
- [ ] 下次 plans 状态化 audit (W70?) 必须同时检查 archived/ 目录
- [ ] 派工 prompt grep 优化: 排除 `plans/archived/` 路径, 避免派工 agent 误读
- [ ] explore-agent 增强: 报告开头检查 `archived/` 目录避免重复调研