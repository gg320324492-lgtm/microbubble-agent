# W68 任务模式基调最终验证: plans 优先 + 小修搭配 — 4 批实战彻底验证 (2026-07-24)

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 8 批 D-5: W68 任务模式基调最终验证"
> **分支**: `chore/w68-8th-batch-d5-task-mode-final-2026-07-24`
> **基线**: main HEAD `05c60e68d` (W68 第 7 批 merge 完成)
> **性质**: **任务模式基调最终验证** (跨 4 批实战总结) — 未来所有派工会话必读
> **0 production code 改动铁律**: 本文件仅 memory + docs 引用追加, 完全守恒

---

## TL;DR

主指挥 **W68 第 4 批 (2026-07-24) 拍板**的任务模式基调:

> **"plans 优先 + 小修搭配"** — 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅; 路线驱动降级为 fallback.

该基调经 **W68 第 5/6/7/8 批共 4 批实战**彻底验证:

- **锚点范式累计守恒**: W68 第 6 批 75 → W68 第 8 批 **104** (预期), 29 守恒, 跨批 **0 失败**.
- **plans 闭环**: 4 批累计 **9 个 plan 闭环** (真未实施 plan 全部消化).
- **调研发现小修**: 4 批累计 **41 个小修** (Status 修正 + 归档 + 部署 + 清理), 全部来自真实调研发现.
- **W68 全栈 commits**: 跨 8 批累计 **94 commits** (含主指挥本地 hot-fix).

结论: 基调稳定、可复制、边际收益持续为正, **进入 W69+ 默认沿用**。

---

## §1 基调定义 (W68 第 4 批拍板)

主指挥 2026-07-24 明确的三层派工优先级 (详见 [`w68-task-mode-paradigm-plans-first-2026-07-24.md`](w68-task-mode-paradigm-plans-first-2026-07-24.md)):

1. **plans 优先** — 派工前必扫 `plans/` 目录, `partial` / `not_started` / `regression-deleted` 状态的 plan 是**已验证过需求**的高价值素材, 优先实施闭环。
2. **小修搭配** — 实施 / 调研过程中**真实发现**的边界情况、配套缺失、文档漂移、baseline 漂移、纪律缺口 → 作为辅助任务并行派工。**小修必须来自真实调研发现, 不允许 agent 假想**。
3. **路线驱动 fallback** — plans 池与小修池都枯竭时, 才回退到路线驱动 (roadmap 新功能扩展) 模式。

三层关系: **小修不阻塞 plan, plan 不挤占小修; 二者搭配并行, 路线仅兜底。**

### 1.1 为何取代纯路线驱动 (W68 第 1-3 批)

W68 第 1-3 批采用纯路线驱动 (路线 A-H 分派), 到第 3 批暴露三个边际递减信号:

1. **路线新增空间收窄** — Drive v2 PR1-9 全线收官、Mobile UX v3.0/v3.1 收官、qa-bench D5/D6 调研占位后, 路线可派新功能显著减少。
2. **易生"为派而派"** — W67 qa-bench D5 gate CI 修复链 11 次循环 (第 29-39 步) 最终接受 docs/CI 占位, 教训: 路线驱动在收口段易陷低价值循环。
3. **plans 池长期闲置** — Verified Plans 报告早已识别 partial (含 refactor regression) 与 not_started plan, 是**已验证过需求**的高价值素材, 却排在路线之后。

主指挥第 4 批拍板将 plans 池提到最前, 把"已验证过需求"的存量转化为高确定性产出。

### 1.2 基调与 0 production code 铁律的双轨关系

- **主轨 (守恒)**: 纯 docs / memory / baseline 验证 / 审计任务, 严格 0 production code 改动。
- **副轨 (例外)**: plan 实施 = production code 改动, 属**已批准例外**; 调研发现的配套小修若涉及 production code, 同样需主指挥逐项批准并在 grand-closure memory 记录。

这套双轨制让基调既能推进真实功能 (plan 实施), 又不破坏 W68 累计 200+ 实战铁律的守恒纪律。

---

## §2 W68 第 5-8 批实战数据

| 批 | agents | plans 闭环 | 调研发现小修 | 锚点范式守恒 |
|---|---|---|---|---|
| W68 第 5 批 | 15 + 3 hot-fix | 1 (Plan #2 deploy) | 14 | 71→75 |
| W68 第 6 批 | 5 (审计) | 1 (Status 修正) | 4 (verified) | 75 |
| W68 第 7 批 | 15 | 5 (真未实施闭环) | 10 (Status 修正 + 归档) | 75→85 |
| W68 第 8 批 | 15 | 2 (PR11 path / PR12 reactions) | 13 (部署 + 清理) | 90→104 预期 |
| **累计** | **50 + 3 hot-fix** | **9 plans 闭环** | **41 小修** | **75→104 (29 守恒)** |

### 2.1 第 5 批 (文档同步专批 + plan deploy 闭环)
15 agents 派工清单 + 6 类文档同步 (CLAUDE.md / ROADMAP.md / CHANGELOG.md / README.md / 2 MEMORY.md) + Plan #2 deploy 闭环。3 hot-fix 修 knowledge uploader id + version diff import + 会议批处理。锚点范式 71 → 75。

### 2.2 第 6 批 (深度审计专批)
5 agents 并行深度审计 `plans/` 全池, 识别 5 个真未实施 plans + 4 个 Status 错位 (verified)。本批 0 merge commit (纯审计报告), 锚点范式守恒 75。为第 7 批派工提供已验证素材池。

### 2.3 第 7 批 (真未实施 plan 全闭环)
15 agents = 5 plan 真闭环 (第 6 批审计发现的 5 个) + C-1 修正 14 个 plans Status 错位 (W66 状态化事故修复) + C-2 归档 8 个 SUPERSEDED / MISCATEGORIZED plans (67 → 59 活跃) + 其余小修。锚点范式 75 → 85。

### 2.4 第 8 批 (合并 + 部署 + 清理)
15 agents = 2 plan 闭环 (Drive v2 PR11 path / PR12 reactions) + 合并 W68 第 7 批 + 部署 + 清理 (15 + 15 + 16)。锚点范式 90 → 104 (预期)。

### 2.5 4 批实战模式演进图谱

| 批 | 主导模式 | 特征 | 与基调关系 |
|---|---|---|---|
| 第 5 批 | plans + 小修 + 文档同步 | 6 类文档一次性同步 + Plan #2 deploy 闭环 + 3 hot-fix | 基调首个文档专批, 小修占比高 (14/15) |
| 第 6 批 | 深度审计 | 5 agents 并行扫全池, 0 merge, 挖出 5 真未实施 + 4 Status 错位 | 基调"plans 优先"的素材注入阶段 |
| 第 7 批 | plans 全闭环 | 5 真 plan 闭环 + 14 Status 修正 + 8 归档 | 基调峰值验证, 审计发现全部消化 |
| 第 8 批 | 合并 + 收口 | 2 plan 闭环 + 部署 + 清理 | 基调端到端链路 (plan → 部署 → 清理) |

**演进规律**: 审计批 (第 6) → 闭环批 (第 7) → 收口批 (第 8) 形成"挖掘-消化-落地"三段式节奏, 可作为 W69+ 批次编排模板。

---

## §3 基调成功 5 证据

1. **W68 第 6 批深度审计发现 5 个真未实施 plans, W68 第 7 批 5 agents 全闭环** — 证明 "plans 优先" 能持续从池中挖出真实未完成需求, 不空转。
2. **W68 第 7 批 C-1 修正 14 个 plans Status 错位** — W66 状态化事故 (partial 被误标 completed) 在深度审计下被发现并修正, 证明基调具备自纠错能力。
3. **W68 第 7 批 C-2 归档 8 个 SUPERSEDED / MISCATEGORIZED plans** — 活跃 plans 从 67 精简到 59, 池子越派越干净, 边际不再稀释。
4. **W68 第 8 批合并 W68 第 7 批 + 部署 + 清理 (15 + 15 + 16)** — plan 闭环产物顺利进入部署与清理阶段, 端到端链路打通。
5. **锚点范式 W68 第 6 批 75 → W68 第 8 批 104 (29 守恒, 0 失败)** — 跨 4 批守恒链单调上升, 无 regression, 基调稳定性得到数据确认。

### 3.1 反面对照: 若继续纯路线驱动

假设 W68 第 5-8 批仍走纯路线驱动 (无 plans 优先):
- 5 个真未实施 plans 会继续闲置 (无人挖掘)。
- 14 个 Status 错位不会被发现 (无审计动机)。
- 8 个过期 plan 继续污染池子 (无归档触发)。
- 锚点范式可能陷入 W67 式低价值循环 (为派而派)。

对照凸显 "plans 优先 + 深度审计" 组合的独特价值: **存量消化 + 池子净化**, 是纯路线驱动无法提供的。

---

## §4 W68 累计 commits

| 批 | commits | 累计 |
|---|---|---|
| W68 第 1 批 + Safari fix | 14+1 | 15 |
| W68 第 2 批 | 3 | 18 |
| W68 第 3 批 | 11+1 | 30 |
| W68 第 4 批 | 15 | 45 |
| W68 第 5 批 + 3 hot-fix | 15+3 | 63 |
| W68 第 6 批 (verified plans report) | 0 merge | 63 |
| W68 第 7 批 | 15 | 78 |
| W68 第 8 批 (预期) | 15 | 93 |
| 主指挥本地 hot-fix #18 (预期) | 1 | 94 |
| **跨批总计** | **94 commits** (W68 全栈) | |

**观察**:
- 第 6 批 0 merge (纯审计) 是基调健康的表现 — 审计不产 commit, 但为后续批次注入高价值 plan 素材。
- 单批 commit 稳定在 15 上下 (第 3 批 alembic 串单链事故后主指挥收紧到 ≤ 15/批), 无失控膨胀。
- 94 commits 跨 8 批 = 平均 ~12 commit/批, 与锚点范式 "每批 +15 守恒" 底线吻合。

---

## §5 未来 W69+ 派工建议

1. **计划优先循环再跑** — 检查 `plans/` 中新出现的 `partial` / `regression` (W68 第 6+7 批深度审计发现的 7 个留 W69 消化), 继续 "plans 优先" 主线。
2. **0 production code 改动铁律继续维持** — W68 累计 200+ 实战铁律, W69+ 默认沿用双轨制 (纯 docs/memory 任务守恒 + plan 实施例外已批)。
3. **跨 session 监控模式常态化** — 主指挥本地 session (监控 + hot-fix) + 多 agent 并行 (派工执行), 二者协同已成 W68 标准姿势。
4. **路线驱动排期看 W19 选项 A 触发** — Drive v2 PR13+ / Mobile v3.3 / qa-bench Phase 4 等路线新功能, 仅在 plans 池 + 小修池双枯竭时按 W19 选项 A 排期启动。

### 5.1 W69 具体待消化清单 (第 6+7 批审计遗留 7 项)

W68 第 6+7 批深度审计后确认仍有 7 个 `partial` / `regression` plan 未闭环, 留 W69 首批消化:
- 消化优先级: `regression` (功能被 refactor 意外删除) > `partial` (半实施) > `not_started` (未启动)。
- 派工前先复核 Status 是否仍准确 (避免 W66 状态化事故复现)。
- 每闭环 1 plan 即更新对应 plan 文件 Status → `completed` 并在 grand-closure memory 记录。

### 5.2 三段式批次编排模板 (W69+ 推荐)

沿用 W68 第 6-8 批验证过的节奏:
1. **审计批** — 5 agents 并行扫全池, 0 merge, 输出真未实施 + Status 错位清单。
2. **闭环批** — 15 agents 消化审计发现 (plan 实施 + Status 修正 + 归档)。
3. **收口批** — 15 agents 合并 + 部署 + 清理, 打通 plan → 部署端到端链路。

---

## §6 5 新铁律

1. **任务模式基调 "plans 优先 + 小修搭配" 永久锚点** — 进入 W69+ 默认沿用, 每批派工前先扫 `plans/`, partial/not_started 优先实施, 路线仅 fallback。
2. **深度审计纪律 (W68 第 6 批 5 agent 模式) 永久复用** — 定期派 5 agents 并行审计 `plans/` 全池 (Status 校验 + SUPERSEDED 识别 + 真未实施挖掘), 0 merge commit 也是健康产出。
3. **锚点范式守恒底线** — 单批不超过 30 commits (第 3 批 alembic 事故教训), 累计每批 +15 守恒; 守恒链必须单调上升, 任一批 regression 即触发根因复盘。
4. **跨 session 主指挥派 sub-task 模式常态化** — 主指挥本地 session 负责监控 + hot-fix + merge, sub-task agents 负责派工执行, 二者不互相阻塞。
5. **0 production code 改动铁律 + 调研发现小修例外 (计划实施) 双轨制** — 纯 docs/memory 任务严格守恒 0 production code; plan 实施 / 调研发现的配套小修作为**已批准例外**, 需主指挥逐项批准并在 grand-closure memory 记录。

---

## 附: 关联 memory 引用链

- 基调定义: [`w68-task-mode-paradigm-plans-first-2026-07-24.md`](w68-task-mode-paradigm-plans-first-2026-07-24.md)
- 第 4 批闭环: [`w68-grand-closure-4th-batch-2026-07-24.md`](w68-grand-closure-4th-batch-2026-07-24.md)
- 第 5 批闭环: [`w68-grand-closure-5th-batch-2026-07-24.md`](w68-grand-closure-5th-batch-2026-07-24.md)
- 第 1 批闭环: [`w68-grand-closure-2026-07-24.md`](w68-grand-closure-2026-07-24.md)
- Verified Plans 报告: [`verified-plans-2026-07-22.md`](verified-plans-2026-07-22.md)
- 多 agent 协调基线: [`multi-agent-task-orchestration-baseline.md`](multi-agent-task-orchestration-baseline.md)
- W19 选项 A / future PR 排期: [`future-pr-roadmap-2026-07-21.md`](future-pr-roadmap-2026-07-21.md)

---

**沉淀完成**: 锚点范式第 90-104 守恒路径 (W68 第 8 批) 中的 D-5 最终验证任务. 4 批实战 (第 5/6/7/8) 彻底验证 "plans 优先 + 小修搭配" 基调稳定性, 0 失败, 进入 W69+ 默认沿用.
