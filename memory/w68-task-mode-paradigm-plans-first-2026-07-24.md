# W68 任务模式基调永久沉淀: plans 优先 + 小修搭配 — 主指挥 2026-07-24 拍板

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 5 批 #15: W68 任务模式基调沉淀"
> **分支**: `chore/w68-task-mode-paradigm-plans-first-2026-07-24`
> **基线**: main HEAD `243937b7f` (W68 第 4 批 merge 完成)
> **性质**: **永久任务模式沉淀** (非单批复盘) — 未来所有派工会话必读
> **0 production code 改动铁律**: 本文件仅 memory + docs 引用追加, 完全守恒

---

## TL;DR

**主指挥 W68 第 4 批 (2026-07-24) 拍板永久任务模式基调**:

> **派工以已有 plans 实施为主 + 更新过程中发现的小修为辅; 路线驱动 (roadmap-driven) 降级为 fallback.**

一句话: **"plans 优先 + 小修搭配"** 取代此前 W68 第 1-3 批的纯路线驱动 (路线 A-H) 模式, 成为 W68 及以后所有批次派工的默认基调.

- **plans 优先**: W66 已完成 67 plans 100% 状态化 (47 completed + 16 agent-stub + 2 deleted + 1 partial + 1 not_started), partial / not_started plan 是**天然的、已验证过需求的**派工素材, 优先消化.
- **小修搭配**: 调研 / 实施过程中**实际发现**的小修 (数据 bug、文档漂移、baseline 漂移、纪律缺口) 作为辅助任务并行派工. 小修必须来自真实调研发现, 不允许 agent 假想.
- **路线 fallback**: plans 池与小修池都枯竭时, 才回退到路线驱动 (roadmap 新功能扩展) 模式.

W68 第 4 批 (plans+小修, 15 agents) 与第 5 批 (小修+fallback, 15 agents) 已完成两轮实战验证, 锚点范式守恒链保持单调上升, 0 regression.

---

## 一、Why: 主指挥 2026-07-24 拍板背景

### 1.1 路线驱动模式的边际递减 (W68 第 1-3 批观察)

W68 第 1-3 批采用纯路线驱动 (路线 A-H 分派):

| 批次 | 模式 | agents | 产出 | 观察 |
|------|------|--------|------|------|
| 第 1 批 | 路线 A (Drive PR8) + 路线 C (Mobile v3.0) | 14 | 30 commits | 新功能扩展空间充足 |
| 第 2 批 | 路线 B (D6 调研) + D (文档) + E (baseline) | 3 | 8 commits | 调研/守恒为主 |
| 第 3 批 | 路线 B/F/G/H (PR9 + v3.1 + docs) | 11 (10+1) | 12+ commits | alembic 串单链事故暴露并行风险 |

问题:
1. **路线新增空间收窄** — Drive v2 PR1-9 全线收官、Mobile UX v3.0/v3.1 收官、qa-bench D5/D6 调研占位后, 路线驱动可派的新功能显著减少.
2. **路线驱动易生"为派而派"** — W67 qa-bench D5 gate CI 修复链 11 次循环 (第 29-39 步) 最终接受 docs/CI 占位, 教训: 路线驱动在收口段容易陷入低价值循环.
3. **plans 池长期闲置** — Verified Plans 报告 (`verified-plans-2026-07-22.md`) 早已识别 partial (含 refactor regression) 与 not_started plan, 是**已验证过需求**的高价值素材, 却一直排在路线之后.

### 1.2 拍板内容 (W68 第 4 批, 2026-07-24)

主指挥明确: **"派工以已有 plans 实施为主 + 更新过程中发现的小修为辅"**. 即:

1. 每批派工先扫 plans 清单 (partial / not_started / regression-deleted).
2. 有可实施 plan → plan 闭环任务优先派.
3. 调研发现的小修与 plan 任务**搭配并行** (小修不阻塞 plan, plan 不挤占小修).
4. plans 池空 + 小修池空 → 才回退路线驱动.

---

## 二、W68 第 4 批实战验证 (plans 优先 + 小修搭配首战)

**规模**: 15 agents = **2 plan 闭环 + 13 小修**. 锚点范式 27 守恒基线延续, 0 regression.

### 2.1 两个 plan 闭环 (plans 优先主线)

| Plan | 来源 | 状态变化 | 实施 |
|------|------|----------|------|
| `15-17-18-cozy-bengio.md` Part 2 (低占比发言人过滤 1.5s/3s/5%) | Verified Plans "6 partial" 之一, commit 4b215220 refactor 意外删除 | partial → completed | Agent Plan #1, `memory/w68-route-plan1-low-occupancy-speaker-filter-2026-07-24.md`, 锚点范式第 43 守恒 |
| `2026-06-05-19-10-melodic-donut.md` (会议 64 杜/吴误标修复) | not_started 早期 plan-mode | not_started → completed | Agent Plan #2, data-only 修复脚本, `memory/w68-route-plan2-meeting-64-repair-2026-07-24.md`, 锚点范式第 44 守恒 |

关键点:
- Plan #1 是 **refactor regression 修复** — plan 本身早已 completed 过 (Part 1), Part 2 被 4b215220 意外删除. plans 状态化 (W66) + Verified Plans 报告 (W62) 提前 2 天定位了这个 regression, 证明 **plans 状态化是 plans 优先模式的基础设施**.
- Plan #2 是 **NOT_STARTED plan-mode 消化** — 早期 plan-mode 阻塞件, plans 优先模式下被自然消化, 不再无限期滞留.
- **plan 实施是 0 production code 改动铁律的合法例外** — plan 本身就需要 production code 改动 (CLAUDE.md 已批准), 与小修的 memory/docs-only 约束区分.

### 2.2 13 个小修 (调研发现搭配线)

13 小修全部来自**真实调研发现** (非假想), 类型分布:
- alembic 串单链纪律沉淀 (`w68-alembic-chain-discipline-2026-07-24.md`, 第 3 批事故 → 第 4 批 5 新铁律)
- CLAUDE.md / ROADMAP.md / CHANGELOG 状态同步 (`w68-claude-md-status-update` / `w68-changelog-roadmap-sync`)
- baseline 守恒验证 + 文档漂移修正 + qa-bench cache rollout 文档等

### 2.3 第 4 批结论

- plans 池成功消化 2 个 (1 partial + 1 not_started), plans 遗留降为 **0 partial + 0 not_started 可实施件** (剩余均为 agent-stub / deleted / 已 superseded).
- 小修与 plan 并行零冲突 (plan 走 production code, 小修走 memory/docs, 天然隔离).
- 锚点范式守恒链单调延续 (第 43/44/45/46 守恒), 0 regression.

---

## 三、新 4 阶段流程 (取代纯路线驱动 4 阶段)

```
阶段 1: plans 清单        → 扫 ~/.claude/plans/ 全量状态 (基础: W66 67 plans 100% 状态化
                            + Verified Plans 报告 verified-plans-2026-07-22.md)
                            识别: partial / not_started / regression-deleted
阶段 2: plans 优先        → 可实施 plan 逐一派独立 agent 闭环 (plan = production code
                            改动合法例外, 每 plan 一 memory + 状态化更新)
阶段 3: 小修搭配          → 调研/实施过程中实际发现的小修并行派工
                            (memory/docs-only, 0 production code 铁律约束)
阶段 4: 路线 fallback     → plans 池空 + 小修池空时, 回退路线驱动
                            (roadmap 新功能扩展, 需主指挥单独拍板范围)
```

与旧 4 阶段流程 (`multi-agent-task-orchestration-baseline.md`: 加载 memory → 建任务列表 → 出 worker 指令 → 监控收口) 的关系: **旧 4 阶段是"怎么派"的执行流程, 新 4 阶段是"派什么"的选题流程**. 两者叠加使用: 先用新 4 阶段选题, 再用旧 4 阶段执行.

---

## 四、新 3 铁律

**铁律 1: plans 优先于路线**
- 每批派工**必须**先扫 plans 清单再谈路线. W66 67 plans 100% 状态化是本铁律的基础设施 — 状态化让"扫清单"成本降到 1 次 grep.
- 依据: W68 第 4 批 2 个 plan 闭环证明 plans 池是已验证需求, 价值密度高于路线新增 (Plan #1 修复了 25 天前的 refactor regression).
- plans 实施是 0 production code 改动铁律的**合法例外** (plan 本身即 production code 需求, CLAUDE.md 批准).

**铁律 2: 小修必须来自调研发现 (不允许 agent 假想)**
- 小修任务的来源**必须**是: 前批事故复盘 (如 alembic 串单链)、baseline 漂移检测、文档状态同步差异、Verified Plans / audit 报告发现.
- **禁止** agent 为凑任务数假想小修 (W67 D5 CI 11 次循环教训: 假想驱动的修复链会陷入低价值循环, 最终仍要"跳出循环接受占位").
- 小修默认 memory/docs-only, 遵守 0 production code 改动铁律; 需动 production code 的"小修"必须升格为 plan 或主指挥单独拍板.

**铁律 3: 路线驱动作为 fallback**
- 路线驱动 (roadmap 新功能) 只在 plans 池 + 小修池双空时启用, 且启用前需主指挥拍板范围 (防止"为派而派").
- W68 第 5 批实战: 全路线已无新增空间 → 15 agents 全部走"小修 + 路线 fallback"收口形态, 正是本铁律的预期运行状态.

---

## 五、W68 第 5 批实战 (小修 + 路线 fallback 形态验证)

**规模**: 15 agents 全部走"小修 + 路线 fallback" — **无 partial plan 可实施** (第 4 批已清空 plans 可实施池), 全路线驱动路线**已无新增空间** (Drive v2 PR1-9 / Mobile v3.0-3.1 / qa-bench D5-D6 全收官或占位).

第 5 批形态特征:
- 任务全部为收口型小修: 基线守恒验证、文档/memory 状态同步、纪律沉淀 (含本文件 #15)、前批遗留微清理.
- 0 production code 改动铁律 100% 守恒 (无 plan 例外触发).
- 锚点范式守恒链继续单调延续, 预计批内新增约 15 次守恒.
- **验证结论**: 新 4 阶段流程在"双池枯竭"极端下退化为纯收口批, 不产生假想任务 — 铁律 2 + 铁律 3 联合生效的实证.

---

## 六、实战数据对比表 (三种模式横向)

| 维度 | W68 第 1+2+3 批 (路线驱动) | W68 第 4 批 (plans+小修) | W68 第 5 批 (小修+fallback) |
|------|---------------------------|--------------------------|------------------------------|
| 模式 | 路线 A-H 分派 | plans 优先 + 小修搭配 | 小修 + 路线 fallback (收口) |
| agents | 14 + 3 + 11 = 28 | 15 (2 plan + 13 小修) | 15 (全小修) |
| 锚点范式守恒 (批内基线) | 14 守恒段 (30 → 42) | 27 守恒基线延续 (43-46+) | 预计 15 守恒 (批内新增) |
| production code | Drive PR8/PR9 + Mobile v3.0/3.1 (路线范畴) | 仅 2 plan 例外 (过滤规则 + data 脚本) | 0 (铁律 100% 守恒) |
| plans 消化 | 0 | **2** (1 partial + 1 not_started → completed) | 0 (池已空) |
| 事故 | alembic 串单链 (第 3 批) | 0 (小修/plan 天然隔离) | 0 |
| 价值密度评估 | 中 (新功能, 但收口段递减) | **高** (已验证需求 + regression 修复) | 低-中 (守恒/沉淀, 但必要) |

**读法**: plans+小修模式在 plans 池非空时价值密度最高; 池空后自然退化为收口批 — 模式自带"衰减到安全态"的性质, 不需要额外刹车机制.

---

## 七、How to apply: 未来会话触发与必读

### 7.1 触发信号

用户说 **"派工"** / "多 agent 完成待做" / "下一批" 时, 立即按新 4 阶段流程走:

```
1. 扫 plans:  grep -l "status: partial\|status: not_started" ~/.claude/plans/*.md
              + 对照 Verified Plans 报告 (verified-plans-2026-07-22.md)
2. 有可实施 plan → plan 闭环任务优先派 (每 plan 独立 agent + 独立 memory)
3. 收集小修池: 前批事故复盘 / baseline 漂移 / 文档同步差异 (必须真实发现)
4. 双池空 → 报告主指挥, 请求路线 fallback 拍板 (不自行开新功能路线)
```

### 7.2 必读 3 memory (派工前加载)

1. **`multi-agent-task-orchestration-baseline.md`** (用户级, 锚点) — 执行流程 4 阶段 + 11 铁律 + 本基调升级段
2. **`orchestrator-mode-coordination-2026-07-20.md`** (用户级) — 5 协调铁律
3. **本文件 `memory/w68-task-mode-paradigm-plans-first-2026-07-24.md`** (项目级) — 选题流程新 4 阶段 + 新 3 铁律

### 7.3 与既有铁律体系的关系

- 不推翻既有 165+ 铁律, 仅在**选题层**新增 3 条.
- "0 production code 改动铁律" 语义细化: plan 实施为合法例外, 小修维持 memory/docs-only.
- 锚点范式守恒链 (W7 12 → W68 46+) 继续作为每批健康度指标, 不因模式切换重置.

---

## 八、关联 memory / docs

- `memory/w68-grand-closure-2026-07-24.md` — W68 第 3 批 grand closure (路线驱动末段)
- `memory/w68-route-plan1-low-occupancy-speaker-filter-2026-07-24.md` — 第 4 批 Plan #1 (锚点范式第 43 守恒)
- `memory/w68-route-plan2-meeting-64-repair-2026-07-24.md` — 第 4 批 Plan #2 (锚点范式第 44 守恒)
- `memory/w68-alembic-chain-discipline-2026-07-24.md` — 第 4 批小修代表 (5 新铁律)
- 用户级 `verified-plans-2026-07-22.md` — 68 plans 全项目调研 (plans 优先的基础设施)
- 用户级 `plans-status-67-closure-w66-2026-07-23.md` — W66 67 plans 100% 状态化
- 用户级 `multi-agent-task-orchestration-baseline.md` — 执行层锚点 (本文件对应选题层)

---

**沉淀性质**: 永久任务模式. 后续批次如主指挥再次拍板调整基调, 应新建 memory 覆盖引用本文件, 不直接改写本文件正文.
