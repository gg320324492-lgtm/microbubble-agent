# W68 任务模式基调 v2 (基于 5 批实战升级) — 锚点范式第 117 守恒

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 9 批 D-3: W68 任务模式基调 v2 (基于 5 批实战)"
> **分支**: `chore/w68-9th-batch-d3-task-mode-v2-2026-07-24`
> **性质**: **永久任务模式基调 v2** (v1 升级版) — W68 第 4 批 v1 基础上叠加 W68 第 6+7+8+9 批实战
> **基线**: main HEAD `f14cb43c1` (W68 第 8 批 A-1 merge 后)
> **0 production code 改动铁律**: 本文件仅 docs + memory 引用追加, 完全守恒
> **关系**: 本文件是 v1 (`memory/w68-task-mode-paradigm-plans-first-2026-07-24.md`) 的升级版, 不推翻 v1, 仅叠加新纪律

---

## TL;DR

**W68 任务模式基调 v2** (2026-07-24 主指挥派 D-3 agent 升级):

v1 (W68 第 4 批拍板): **plans 优先 + 小修搭配 + 路线 fallback** (3 阶段)

v2 (W68 第 9 批升级, 基于第 4+5+6+7+8+9 批 6 轮实战):

> **plans 优先 + 小修搭配 + plans 留 W69 必须查 backlog docs + 调研发现必 document + 跨 session 协作常态化**

5 拍板纪律 (新): plans 查 backlog / 小修来源 / 调研必 document / 双 git log / grep 真验证.
4 阶段流程 (v2 升级): plans 清单 (含 backlog) / plans 优先 / 小修搭配 / 路线 fallback.

**为什么升级 v2**: W68 第 6 批派 5 agent 实战审计 67 plans, 发现 audit123 自报 47 completed 与实际 35 个状态不一致 (5 真未实施 + 12 PARTIAL_REGRESSION + 14 Status 错位) — v1 未规定"调研必 grep 真验证 + 调研发现必 document + plans 留后续批次必须查 backlog docs" 3 条, 是 v2 升级的核心原因.

---

## §1 v1 → v2 差异 (4 处升级)

### 1.1 v1 回顾 (W68 第 4 批拍板)

| 维度 | v1 |
|------|------|
| 选题层 | plans 优先 + 小修搭配 + 路线 fallback |
| plans 池 | 扫 plans/*.md, 识别 partial/not_started |
| 小修来源 | 调研/实施过程中实际发现 |
| 调研发现沉淀 | memory only |
| 跨 session 协作 | (未规范) |
| 流程 | 4 阶段 (plans 清单 / plans 优先 / 小修搭配 / 路线 fallback) |

### 1.2 v2 升级 (W68 第 9 批基于 5 批实战)

| # | v1 → v2 | 升级原因 (实战数据) |
|---|---------|---------------------|
| 1 | plans 清单 → plans 清单 + **查 backlog docs** | W68 第 4 批 2 plan 闭环把池挖空, 第 6 批才通过深度审计发现 plan 真实状态. v2 规定 plans 留 W69/未来批次必须先查 `verified-plans-w68-2026-07-24.md` 等 backlog docs 才能选. |
| 2 | 小修来源 (调研发现) → 小修来源 (调研发现, **不允许假想**) | W67 qa-bench D5 CI 11 次循环教训: 假想驱动修复链会陷入低价值循环. v2 强化铁律 2: agent 必须真实 grep / 真验证. |
| 3 | 调研发现沉淀 (memory only) → **调研发现必 document (docs + memory)** | W68 第 6+7 批实战: 单 memory 沉淀时其他 agent 检索不到, 必须同步在 docs 留 anchor. v2 强化铁律 3. |
| 4 | 跨 session 协作 (未规范) → **跨 session 协作常态化** | W68 第 9 批 A-1 已示范: 主指挥本地 hot-fix 派 agent + 多 agent 派工 + 监控双 git log (本地 + main). v2 强化铁律 4. |

**v2 = v1 + 4 处升级**, 不推翻 v1 (plans 优先 + 小修搭配 + 路线 fallback) 主基调.

### 1.3 与 v1 的关系 (并存而非覆盖)

- 本文件 (`docs/w68-task-mode-paradigm-v2.md`) 是选题层 v2, 与执行层 v1 (`memory/w68-task-mode-paradigm-plans-first-2026-07-24.md`) 并存.
- v1 4 阶段流程是"怎么派"执行流程 (加载 memory → 建任务列表 → 出 worker 指令 → 监控收口), v2 4 阶段是"派什么"选题流程.
- 未来派工**双层叠加**: 先用 v2 选题, 再用 v1 执行.
- v2 不删除 v1, 因为 v1 仍承载 5 拍板纪律之外的所有执行细节.

---

## §2 5 拍板纪律 (新, 基于 W68 第 6+7+8+9 批实战)

### 拍板 1: plans 查 backlog 后再选派工

**触发**: W68 第 6 批 5 agent 实战审计 67 plans, 发现 audit123 (2026-07-22) 自报 47 completed 与实际 5 真未实施 + 12 PARTIAL_REGRESSION + 14 Status 错位不一致.

**实践**: 每批派工**必须**先查 backlog docs 再选 plan, 不能信 Status 段自报. backlog docs 列表:
- `C:/Users/pc/.claude/plans/` (主仓库) — 全部 59 plans 活跃 + 8 plans archived (W68 第 7 批归档)
- `memory/verified-plans-w68-2026-07-24.md` — W68 实战审计 14 个错位 plan 修正清单
- `memory/verified-plans-2026-07-22.md` — W62 68 plans 全项目调研 (W66 67 plans 100% 状态化基础)
- `memory/w68-grand-closure-{n}th-batch-2026-07-24.md` — 前批 grand closure, 含留待办清单

**反例 (W68 第 6 批踩坑)**: 信 audit123 报告派 47 plan 闭环 → 实际 35 个状态不一致 → 必须补派 5+12 修复批.

### 拍板 2: 小修来源 = 调研发现, 不允许 agent 假想

**触发**: W67 qa-bench D5 gate CI 修复链 11 次循环 (第 29-39 步), 最终接受 docs/CI 占位, 教训: 假想驱动的修复链会陷入低价值循环.

**实践**: 小修任务来源**必须**是:
1. **前批事故复盘** (如 W68 第 3 批 alembic 串单链 → W68 第 4 批 `w68-alembic-chain-discipline-2026-07-24.md`)
2. **baseline 漂移检测** (如 W68 第 6 批 53% ACTUAL_COMPLETED vs 自报 70%)
3. **文档状态同步差异** (CLAUDE.md / ROADMAP.md / CHANGELOG.md / README.md 漂移)
4. **Verified Plans / audit 报告发现** (如 W68 第 6 批 14 Status 错位)

**反例 (W67 D5 CI 教训)**: agent 假想"第 N 次尝试修复 → 失败 → 第 N+1 次"循环 11 次, 价值密度趋于 0.

### 拍板 3: 调研发现必写到 docs, 不只在 memory

**触发**: W68 第 6 批 5 agent 实战审计时, 单 memory 沉淀 (`memory/w68-route-{n}-c1-deep-audit-2026-07-24.md` 等) 不足以让后续 agent 检索到 (memory 是用户级, docs 是项目级索引).

**实践**: 任何调研发现 (审计 / audit / baseline 漂移) **必须**写到 docs 留 anchor:
- 项目级: `docs/{topic}-2026-07-24.md` (如 `docs/qa-bench-d6-implementation-roadmap.md`)
- 用户级: `C:/Users/pc/.claude/projects/E--microbubble-agent/memory/{topic}-2026-07-24.md` (如 `verified-plans-w68-2026-07-24.md`)
- 项目 memory: `memory/{w68-route-n}-{topic}-2026-07-24.md` (派工复盘)

**反例**: 单 memory 沉淀时其他 agent 检索不到, 必须同步在 docs 留 anchor 才能跨 session 检索.

### 拍板 4: 跨 session 监控必须含本地 + main 双 git log

**触发**: W68 第 9 批 A-1 (15 分支合并) 示范: 主指挥本地 worktree + 多 agent 派工 + monitor 阶段必须双 git log (本地 worktree HEAD + main HEAD) 才能验证 merge 成功.

**实践**: 主指挥监控派工时**必须**双 git log 跟踪:
- 本地 worktree: `git -C .claude/worktrees/{agent-id} log --oneline -5`
- main HEAD: `git -C .claude/worktrees/{main} log --oneline -5`
- 跨 worktree 冲突对比: `git -C .claude/worktrees/{agent-id} diff --stat main`

**反例**: 只监控 main HEAD, 错过 worktree 内 commit 未 push 情况 (W68 第 7 批 15 commits 已 push 未 merge).

### 拍板 5: 调研 agent 必 grep 真验证, 不能信 Status 段自报

**触发**: W68 第 6 批 5 agent 实战审计 67 plans, Status 段自报 47 completed, 实际 grep + diff + 实战测出 5 真未实施 + 12 PARTIAL_REGRESSION + 14 错位.

**实践**: 调研 agent 报告**必须**含真验证 grep 证据, 不能信 plans/*.md Status 段自报. 验证手段:
- `grep -l '{plan-name}' app/ web/ alembic/versions/ docs/ -r` (查实施痕迹)
- `git log --all --oneline --grep='{plan-name}'` (查 commit 链)
- 端到端跑 plan 描述的功能 (qa-bench / Drive / Mobile UX 等)

**反例**: 单信 Status 段就报"plan 已完成", 实际是 commit 4b215220 refactor 意外删除 / plan 文档误标 / never_implemented.

---

## §3 4 阶段标准流程 (v2 升级, 基于 §2 5 拍板纪律)

```
阶段 1: plans 清单 (含 backlog)
        → 扫 ~/.claude/plans/ + memory/verified-plans-w68-2026-07-24.md 
          + docs/{topic}-*.md + 前批 grand closure 留待办
        → 识别: partial / not_started / regression-deleted / Status 错位
        → 拍板 1 落地: 不信 Status 段自报, 必查 backlog docs
        → 拍板 5 落地: 调研 agent 必 grep 真验证

阶段 2: plans 优先
        → 可实施 plan 逐一派独立 agent 闭环 
          (plan = production code 改动合法例外, 每 plan 一 memory + Status 段更新)
        → 必须同步更新 docs + memory (拍板 3 落地)

阶段 3: 小修搭配
        → 调研/实施过程中**实际发现**的小修并行派工 
          (memory/docs-only, 0 production code 铁律约束)
        → 必须来自真实调研发现 (拍板 2 落地: 不允许假想)
        → 必须双 git log 监控 (拍板 4 落地)

阶段 4: 路线 fallback
        → plans 池空 + 小修池空时, 回退路线驱动 (roadmap 新功能扩展)
          (需主指挥单独拍板范围, 防止"为派而派")
        → 路线驱动需双 session 协作 (主指挥本地 + 多 agent 派工常态化, 拍板 4 落地)
```

### 3.1 与 v1 4 阶段流程的关系

| 阶段 | v1 | v2 升级 |
|------|-----|---------|
| 1 | 扫 plans/*.md | 扫 plans/*.md + **backlog docs (verified-plans-w68 + verified-plans + 前批 grand closure)** |
| 2 | plans 优先 | 不变, 但**必须同步更新 docs + memory** |
| 3 | 小修搭配 | 不变, 但**调研发现必须真实, 不允许假想** |
| 4 | 路线 fallback | 不变, 但**路线驱动必须双 session 协作** |

---

## §4 6 类文档主仓库优先 (新规范, 拍板 3 强化)

| 类型 | 优先级 | 例子 |
|------|--------|------|
| `~/.claude/plans/{plan-name}.md` | P0 (计划源头) | `15-17-18-cozy-bengio.md`, `2026-06-05-19-10-melodic-donut.md` |
| `docs/{topic}-2026-07-24.md` | P1 (项目级文档, 必读) | `docs/qa-bench-d6-implementation-roadmap.md`, `docs/drive-v2-pr9-deployment.md` |
| `C:/Users/pc/.claude/projects/.../memory/{topic}.md` | P2 (用户级文档, 跨项目共享) | `verified-plans-w68-2026-07-24.md`, `anchor-paradigm-21-day-validation-2026-07-22.md` |
| `memory/{w68-route-n}-{topic}-2026-07-24.md` | P3 (项目级派工复盘) | `memory/w68-route-9-d3-task-mode-v2-2026-07-24.md` |
| `memory/MEMORY.md` 索引 | P0 (一站式索引) | 含 ~80 条 2026 锚点范式条目 |
| `~/.claude/CLAUDE.md` | P0 (用户主偏好) | 主指挥行为规范 |

**主仓库优先**: P0 + P1 优先于 P2 + P3, 调研发现必先在 P0/P1 留 anchor 后再写 P3.

---

## §5 v2 锚点范式影响 (预计)

**锚点范式当前**: W68 第 8 批 90 (W68 第 8 批 A-1 merge 后)

**v2 影响**: 不直接提升锚点范式数字, 而是为后续批次提供更稳健的**拍板纪律** (5 拍板) + **选题流程** (4 阶段 v2). 预计 W68 第 9 批后续派工会比第 8 批更紧凑 / 价值密度更高 / 0 regression.

---

## §6 v2 与 W68 累计批次的对应关系

| 批次 | v1 (主基调) | v2 (新纪律) | 实战数据 |
|------|--------------|--------------|----------|
| W68 第 4 批 | ✅ 拍板 (v1 4 阶段) | - | 15 agents (2 plan + 13 小修) 单批 27 守恒 |
| W68 第 5 批 | ✅ 实证 (小修+fallback) | - | 15 agents (全小修) 0 production code 100% 守恒 |
| W68 第 6 批 | ✅ 实证 | 暴露拍板 1+2+5 缺口 | 5 agent 实战审计 67 plans (35 个状态不一致) |
| W68 第 7 批 | ✅ 实证 | 暴露拍板 3 缺口 | 15 agents (5 plan 闭环 + 12 PARTIAL_REGRESSION + 14 Status 错位 + 路线 fallback) |
| W68 第 8 批 | ✅ 实证 | 暴露拍板 4 缺口 | 15 branches merge (主指挥本地 hot-fix + 双 git log) |
| W68 第 9 批 | ✅ 实证 (本文件升级 v2) | ✅ 5 拍板 + 4 阶段 v2 全部署 | D-3 (本批) + 后续 D-1/D-2 等实战 |

**v2 来源**: W68 第 6+7+8 批暴露的 5 个 v1 缺口, 在 W68 第 9 批 D-3 拍板升级到 v2.

---

## §7 v2 实战预期 (W68 第 9+10+11 批)

### 7.1 W68 第 9 批 (本批, 锚点范式第 91+ 守恒)

- D-1: 8 小修跨主题 (`memory/w68-route-9-d1-8-smallfixes-2026-07-24.md` 等)
- D-2: 任务模式 v1 → v2 升级 (本文件)
- D-3: plans 状态收敛闭环 (`memory/w68-route-9-c2-plans-status-close-2026-07-24.md`)
- A-1: 15 分支合并 (W68 第 8 批已合并)

### 7.2 W68 第 10 批 (预计锚点范式第 92-95 守恒)

- plans 留 W69 backlog: `verified-plans-w68-2026-07-24.md` 中 14 Status 错位持续修正
- 路线 B/D/E 续: Drive PR11/12 + qa-bench D6 Phase 2 + 路线 E 留未来 PR 评估

### 7.3 W68 第 11+ 批 (节奏延续)

- v2 4 阶段流程稳定运行, 拍板 1-5 守住调研纪律 / 双 session 协作常态化
- 锚点范式单批约 5-10 守恒, 紧凑节奏延续

---

## §8 关联 memory / docs

- `memory/w68-task-mode-paradigm-plans-first-2026-07-24.md` — v1 基调 (本文件升级版)
- `memory/w68-grand-closure-7th-batch-2026-07-24.md` — W68 第 7 批 grand closure (5 真未实施 + 12 PARTIAL_REGRESSION + 14 Status 错位)
- `memory/verified-plans-w68-2026-07-24.md` — W68 实战审计 (W68 第 6 批 5 agent 发现)
- `memory/verified-plans-2026-07-22.md` — W62 68 plans 全项目调研 (W66 67 plans 100% 状态化基础)
- `memory/w68-grand-closure-{n}th-batch-2026-07-24.md` — 前批 grand closure (n=4,5,7,8)
- `memory/w68-alembic-chain-discipline-2026-07-24.md` — 拍板 1+2 案例
- `memory/w68-route-8-a1-merge-2026-07-24.md` — 拍板 4 案例 (双 git log)
- `memory/w68-route-9-d3-task-mode-v2-2026-07-24.md` — 本文件配套 memory 沉淀
- 用户级 `multi-agent-task-orchestration-baseline.md` — 执行层锚点 (本文件对应选题层)
- 用户级 `orchestrator-mode-coordination-2026-07-20.md` — 5 协调铁律

---

## §9 v2 沉淀性质

**永久任务模式基调 v2** (本文件, 项目级 docs).

- 后续批次如主指挥再次拍板调整基调, 应新建 `docs/w68-task-mode-paradigm-v3.md` 覆盖引用本文件, 不直接改写本文件正文.
- v1 memory 不删除, 与 v2 并存 (v1 执行层 / v2 选题层).
- v2 已沉淀 5 拍板纪律, 不再随批次迭代修订 (除非主指挥拍板).
- v2 = 基于 W68 第 4-9 批 6 轮实战, v3 升级预计在 W80+ 节奏.

---

**沉淀完毕**: W68 任务模式基调 v2 (基于 5 批实战). 锚点范式第 117 守恒 (v2 沉淀本身不直接提升, 但为后续批次提供纪律 + 流程保障).

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24
**Version**: W68 任务模式基调 v2.0
