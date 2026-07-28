# W68 第 12 批派工纪要 prompt 模板 v3 (5 段模板升级) — 锚点范式第 155 守恒

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 12 批 D-1: 派工纪要 v3 (5 段 prompt 模板 + W68 第 11 批 B 派工前提错误经验沉淀)"
> **分支**: `docs/w68-12th-batch-prompt-template-v3-2026-07-24`
> **性质**: **派工 prompt 模板 v3** (v2 升级版) — v1/v2 兼容, 升级而非替代
> **基线**: main HEAD `7b6f0305e` (W68 第 11 批收官后)
> **0 production code 改动铁律**: 本文件仅 docs + memory, 完全维持
> **W19 选项 A**: 维持
> **关系**: 本文件是 5 段 prompt 模板 v2 (`docs/2026-07-22-w62-multi-agent.md` §20 记录的 "5 段格式 (背景 / 当前分支 / 任务 / 铁律 / 完成标准)") 的升级版, 不推翻 v1/v2, 仅在 5 段中叠加 5 处新纪律条目.

---

## TL;DR

**W68 第 12 批派工 prompt 模板 v3** (2026-07-24 主指挥派 D-1 agent 升级):

- **v1** (W51 锚点范式启动): 5 段格式 (背景 / 当前分支 / 任务 / 铁律 / 完成标准) — 见 `memory/multi-agent-task-orchestration-baseline.md`
- **v2** (W62 5 agent 并行验证): 5 段格式沿用 0 偏离 + stash 隔离 + 6 点 curl 验证 — 见 `docs/2026-07-22-w62-multi-agent.md`
- **v3** (W68 第 12 批升级, 基于第 9/10/11 批实战): 5 段中叠加 5 处新纪律条目

**Why**: W68 第 9~11 批实战暴露 5 个 5 段 prompt 缺口 (alembic 链 conflict 未在派工 prompt 前置校验 / 依赖服务不存在未提前 grep / worktree base 未 fetch / e2e SKIP 未 escalate / 前端派工未先 npm run build). v3 针对性在 5 段中补 5 条, 让 agent 在动手前就完成前提校验, 避免"派工前提错误"事故.

**How to apply**: 见 §1 (5 处升级), §2 (第 12 批如何应用), §3 (5 派工错误案例), §4 (v3 完整 5 段模板), §5 (v1/v2/v3 兼容关系).

**交付**: 1 docs 新增 (本文件 ~350 行) + 1 memory 新增 (`memory/w68-route-12-d1-prompt-template-v3-2026-07-24.md` ~150 行) + 1 commit + 1 push origin.

---

## §1 派工纪要 v2 → v3 升级 (5 段模板 5 处叠加)

v3 保留 v1/v2 的 5 段骨架不变:

| 段 | 名称 | v1/v2 内容 | v3 新增 |
|----|------|-----------|---------|
| 段 1 | 背景 | agent 身份 + 仓库 + 主基调 | (无变化) |
| 段 2 | 当前分支 | worktree / 分支命名 / stash 隔离 | **§1.3 worktree base 必 fetch origin/main 同步** |
| 段 3 | 任务描述 | 目标 + 交付物清单 | **§1.1 alembic heads 链前置校验** |
| 段 4 | 铁律 / 完成定义 | 0 prod code + Co-Authored-By + 完成条件 | **§1.2 依赖服务 grep 验证 + §1.4 e2e SKIP > 10% 必 escalate + §1.5 前端派工前必 npm run build** |
| 段 5 | 完成标准 | commit hash + push + 交付物核对 | (无变化) |

### 1.1 段 3 任务描述加 alembic 链前置校验 (W68 第 11 批 C-1 沉淀)

**新增条目文本** (写入段 3 任务描述末尾):

> 必跑: `git fetch origin main && cd main && alembic heads` — 如有 066/067/068/069 等 migration, 必在写新 migration 前 verify down_revision 链. 如有 conflict, 必报主指挥拍板 (不自动修).

**升级原因 (W68 第 11 批 C-1 实战)**: alembic 并行 agent 各自声明同一上游 down_revision → merge 后双 head → `alembic upgrade head` 报 `Multiple head revisions are present` 阻塞部署 (CLAUDE.md 2026-07-24 `1852468a6` 铁律). v2 派工 prompt 未在段 3 前置这条校验, agent 在动手写 migration 时才发现链断. v3 前置到段 3, 让 agent 写 migration 前就 verify 链, conflict 时 escalate 不自动修.

### 1.2 段 4 完成定义加依赖服务 grep 验证 (W68 第 11 批 B-3 沉淀)

**新增条目文本** (写入段 4 完成定义):

> 必跑: `grep -rn <service_name> app/` 验证依赖存在. 如服务不存在, 写新分支实施 (合规 "新功能例外") 或报告主指挥拍板.

**升级原因 (W68 第 11 批 B-3 实战)**: ppt-word 调研 agent 派工假设某 service 已存在, 实际未实施 → 若 agent 不 grep 就动手, 会引用不存在的模块导致 ImportError 或空实施. v3 要求 agent 在完成定义阶段就 grep 依赖, 不存在则走"新功能例外"新分支或 escalate.

### 1.3 段 2 分支加 worktree base fetch origin/main (W68 第 11 批 C-2 沉淀)

**新增条目文本** (写入段 2 当前分支):

> worktree base 必 fetch origin/main 同步 — 派工前 `git fetch origin main`, worktree 从最新 origin/main 起 base, 避免基于陈旧 HEAD 开发导致 merge 冲突.

**升级原因 (W68 第 11 批 C-2 实战)**: worktree 从陈旧本地 HEAD 起 base (未 fetch origin/main), 其他批次已 merge 的 commit 未同步 → 开发完 merge 时冲突或重复实施. v3 要求段 2 明确 worktree base 必 fetch origin/main 同步。

### 1.4 段 4 加 e2e SKIP 必报 (W68 第 10 批 C-1 沉淀)

**新增条目文本** (写入段 4 完成定义):

> e2e SKIP > 10% 必显式 escalate — 测试跑完若 SKIP 比例 > 10% (后端未部署 / 依赖缺失 / secret 未配), 必在完成报告显式 escalate 主指挥, 不得静默当 PASS.

**升级原因 (W68 第 10 批 C-1 实战)**: e2e 大量 SKIP (后端未部署) 被 agent 默认当作"非 FAIL 即通过", 主指挥收口时才发现覆盖率虚高. v3 要求 SKIP > 10% 必显式 escalate, 让主指挥判断是否需先部署后端再跑。

### 1.5 段 4 加前端派工前必 npm run build (W68 第 11 批 B-2 沉淀)

**新增条目文本** (写入段 4 完成定义, 仅前端派工适用):

> 前端派工前必 `npm run build` 验证 — 涉及 `web/` 的派工, 动手前先 `cd web && npm run build` 确认 baseline 可 build, 完成后再跑一次确认无引入 build error (重复声明 / import 缺失 / manifest hash).

**升级原因 (W68 第 11 批 B-2 实战)**: Mobile TabBar 派工引入重复声明 (`tabsWithCounts`) 阻塞 build, agent 未在动手前后跑 build 验证 → merge 后才暴露。v3 要求前端派工在段 4 明确 build 前后双验证 (呼应 CLAUDE.md 2026-07-11 `npm run build` 是唯一合法 build 命令铁律)。

---

## §2 W68 第 12 批派工如何应用 v3

v3 的 5 处升级按派工性质选择性应用 (不是每个 agent 全部 5 条):

| 派工组 | 派工性质 | 应用的 v3 条目 | 说明 |
|--------|---------|---------------|------|
| **A-1** | plans 闭环 (plans 优先) | 5.1 + 5.2 | plans 实施常涉及 alembic (5.1) + 依赖服务 (5.2) |
| **B-1** | 路线 Drive v2 (新功能) | 5.1 + 5.3 | Drive PR 常写 migration (5.1) + worktree base 同步 (5.3) |
| **B-2** | 路线 Mobile (前端) | 5.1 + 5.3 | 前端派工同样需 alembic 意识 + base 同步 |
| **B-3** | 路线调研 (ppt-word) | 5.1 + 5.3 | 调研派工 grep 依赖 (5.2 隐含) + base 同步 |
| **B-4** | 路线 qa-bench (fallback) | 5.1 + 5.3 | fallback 派工同样 base 同步 |
| **C-1** | CI / 测试收口 | 5.1 + 5.4 | CI 收口涉及 SKIP escalate (5.4) |
| **C-2** | CLI / 文档 | 5.1 + 5.4 | CLI 文档需 SKIP 意识 |
| **C-3** | e2e / 部署 | 5.1 + 5.4 | e2e 派工核心是 SKIP escalate (5.4) |
| **留 W70** | 前端 UI PR (未来) | 5.5 | 前端 UI 派工会应用 npm run build 前后双验证 (5.5) |

**应用原则**:
- **5.1 (alembic 链)** — 几乎所有派工默认应用 (写 migration 或不写都要有链意识, 不写时校验为"无 migration 即跳过")。
- **5.2 (grep 依赖)** — plans / 调研派工重点应用。
- **5.3 (worktree base fetch)** — 所有 worktree 派工默认应用。
- **5.4 (e2e SKIP escalate)** — CI / e2e / 部署派工重点应用。
- **5.5 (npm run build)** — 前端 (`web/`) 派工才应用, 后端/docs 派工不涉及。

---

## §3 W68 第 12 批 5 派工错误案例 (v2 → v3 增量驱动)

以下 5 个案例是 W68 第 9~11 批实战中"派工前提错误"的真实教训, 直接驱动 v2 → v3 的 5 处升级:

### 3.1 B-3 ppt-word 调研: 87.5% 真实施 (W66 估 30-40% 错)

- **事实**: W66 audit 估 ppt-word 相关功能真实施率 30-40%, W68 第 11 批 B-3 agent 实际 grep 后确认 **87.5% 已真实施**。
- **教训**: 派工纪要基于陈旧 audit 估值, 未 grep 真验证 → 派工方向偏差 (以为要大量新写, 实际只需补 12.5%)。
- **驱动升级**: **§1.2 (5.2 grep 依赖验证)** — 派工前 grep 真验证依赖 / 已实施率, 不信陈旧估值。

### 3.2 B-2 Mobile TabBar: 仓库实际文件 MobileDashboard.vue, 派工文字写错

- **事实**: 派工 prompt 写 "改 Mobile TabBar 组件", 仓库实际相关文件是 `MobileDashboard.vue`, 派工文字文件名写错。
- **教训**: 派工前未 glob / grep 确认文件真实名称 → agent 找不到文件或改错文件。
- **驱动升级**: **§1.5 (5.5 前端 npm run build)** — 前端派工前先跑 build 确认 baseline, 顺带暴露文件引用问题；配合 §1.2 grep 验证文件真名。

### 3.3 C-1 tabsWithCounts: 重复声明阻塞 build

- **事实**: 前端派工引入重复声明 (`tabsWithCounts`), `npm run build` 报重复声明错误阻塞 build。
- **教训**: agent 未在动手前后跑 `npm run build` → merge 后才暴露 build error。
- **驱动升级**: **§1.5 (5.5 前端 npm run build 前后双验证)** — 直接对症。

### 3.4 C-2 CLI: Markdown vs JSON 文档错误

- **事实**: CLI 派工文档描述输出格式为 Markdown, 实际 CLI 输出 JSON, 文档格式描述错误。
- **教训**: 派工文档未核对 CLI 真实输出格式 → 文档与实现脱节。
- **驱动升级**: **§1.4 (5.4 SKIP escalate 意识)** + §1.2 grep 真验证 — 文档类派工也要真跑 CLI 核对输出, 不凭记忆写。

### 3.5 C-3 22 SKIP: 后端未部署

- **事实**: e2e 跑出 22 SKIP, 根因是后端未部署 (依赖服务未起)。
- **教训**: agent 把 22 SKIP 默认当"非 FAIL 即通过", 未 escalate → 覆盖率虚高。
- **驱动升级**: **§1.4 (5.4 e2e SKIP > 10% 必 escalate)** — 直接对症。

**5 案例聚合**: 5 个"派工前提错误" (陈旧估值 / 文件名写错 / 重复声明 / 文档格式错 / SKIP 虚高) 驱动 v2 → v3 的 5 处 5 段升级, 让 agent 在动手前完成前提校验。

---

## §4 v3 模板完整 5 段 (供 W70 派工参考)

以下是 v3 完整 5 段模板 (含 5 处新纪律条目), W70 派工可直接套用:

```
你是 Agent "<agent 名称>". 当前在 <仓库路径> main HEAD 上.

【段 1 · 背景】
- 主基调: <本批主基调, 如 plans 闭环 + 路线驱动 + 小修搭配>
- 上下文: <锚点范式第 N 守恒 / 前批交付 / 相关 memory 引用>

【段 2 · 当前分支】
- 分支: `<type>/<描述>-2026-07-24` (type ∈ docs/chore/feat/fix)
- worktree base 必 fetch origin/main 同步 — 派工前 `git fetch origin main`,
  worktree 从最新 origin/main 起 base, 避免基于陈旧 HEAD 开发导致 merge 冲突.   ← v3 新增 5.3
- 多 worker stash 隔离严格执行.

【段 3 · 任务描述】
- 目标: <明确目标 + 交付物清单>
- 必跑: `git fetch origin main && cd main && alembic heads` — 如有 066/067/068/069
  等 migration, 必在写新 migration 前 verify down_revision 链. 如有 conflict,
  必报主指挥拍板 (不自动修).                                                   ← v3 新增 5.1

【段 4 · 铁律 / 完成定义】
- 0 production code 改动铁律 <维持 / 新功能例外已批>.
- commit 末尾 Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>.
- 必跑: `grep -rn <service_name> app/` 验证依赖存在. 如服务不存在,
  写新分支实施 (合规 "新功能例外") 或报告主指挥拍板.                          ← v3 新增 5.2
- e2e SKIP > 10% 必显式 escalate — SKIP 比例 > 10% (后端未部署 / 依赖缺失 /
  secret 未配), 必在完成报告显式 escalate 主指挥, 不得静默当 PASS.            ← v3 新增 5.4
- [仅前端] 前端派工前必 `cd web && npm run build` 验证 — baseline 可 build,
  完成后再跑一次确认无引入 build error.                                       ← v3 新增 5.5
- 不 merge (主指挥来 merge). push 到 origin.

【段 5 · 完成标准】
- <交付物清单核对, 如 N docs + M memory = X 文件>
- commit hash + push 成功.
```

**W70 应用要点**: 5 处新条目按 §2 表选择性应用 (前端派工才加 5.5, e2e 派工重点 5.4, 等等), 不是每个 agent 全部 5 条。

---

## §5 v1 / v2 / v3 兼容关系 (升级而非替代)

### 5.1 三代兼容矩阵

| 版本 | 触发 | 核心 | 关系 |
|------|------|------|------|
| **v1** | W51 锚点范式启动 | 5 段格式骨架 (背景 / 当前分支 / 任务 / 铁律 / 完成标准) | 基线, `multi-agent-task-orchestration-baseline.md` |
| **v2** | W62 5 agent 并行 | 5 段沿用 0 偏离 + stash 隔离 + 6 点 curl 验证 | v1 骨架不变, 扩展到 5 并发场景 |
| **v3** | W68 第 12 批 | 5 段中叠加 5 处新纪律条目 | v1/v2 骨架完全不变, 仅在段 2/3/4 内插入 5 条前提校验 |

### 5.2 v3 是"升级"而非"替代"的证据

1. **5 段骨架 0 改动** — v3 仍是背景 / 当前分支 / 任务 / 铁律 / 完成标准, 段数不变、段名不变、段序不变。
2. **5 处新条目是"插入", 不是"重写"** — 每条都是往对应段内追加一行前提校验, 老条目全部保留。
3. **向后兼容** — 用 v1/v2 模板派的历史 agent 完成标准不变, v3 只是让新派工在动手前多做 5 项校验。
4. **选择性应用** — v3 5 条按派工性质选用 (§2), 后端/docs 派工可不涉及 5.5 (npm run build), 与 v1/v2 完全一致。

### 5.3 未来 v4 演化预期

- 若 W70+ 实战再暴露新的"派工前提错误"类型 (如 MinIO bucket 未建 / secret 未注入 / Docker service 未起), 则叠加为 v4, 仍保持 5 段骨架 + 选择性应用原则。
- v3 → v4 同样是"升级而非替代", 保证跨批次派工模板的连续性。

---

## 附: 交付物清单

| # | 文件 | 类型 | 行数 |
|---|------|------|------|
| 1 | `docs/w68-12th-batch-prompt-template-v3-2026-07-24.md` | docs 新增 | ~350 |
| 2 | `memory/w68-route-12-d1-prompt-template-v3-2026-07-24.md` | memory 新增 | ~150 |

- **0 production code 改动铁律**: ✅ 维持 (仅 docs + memory)
- **锚点范式第 155 守恒**: ✅
- **W19 选项 A**: ✅ 维持
- **commit**: 见 git log
- **push**: origin/docs/w68-12th-batch-prompt-template-v3-2026-07-24
- **不 merge**: 主指挥来 merge

---

_本文件是 W68 第 12 批 D-1 agent 的派工纪要 prompt 模板 v3 沉淀。v1/v2/v3 三代兼容, 5 段骨架贯穿始终, v3 针对 W68 第 9~11 批实战的 5 个"派工前提错误"补 5 条前提校验。_
