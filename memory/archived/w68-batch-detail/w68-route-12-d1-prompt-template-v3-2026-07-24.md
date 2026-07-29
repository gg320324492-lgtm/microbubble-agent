---
name: w68-route-12-d1-prompt-template-v3-2026-07-24
description: "W68 第 12 批 D-1: 派工纪要 prompt 模板 v3 (5 段模板升级) — 锚点范式第 155 守恒. v2 (5 段格式: 背景/当前分支/任务/铁律/完成标准) 基础上叠加 5 处新纪律条目 (alembic 链前置校验 / grep 依赖验证 / worktree base fetch / e2e SKIP escalate / 前端 npm run build), 基于 W68 第 9~11 批实战暴露的 5 个派工前提错误. v1/v2/v3 兼容, 升级而非替代."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-12th-batch-d1-prompt-template-v3
  modified: 2026-07-24T00:00:00.000Z
---

# W68 第 12 批 D-1: 派工纪要 prompt 模板 v3 (5 段模板升级) — 锚点范式第 155 守恒

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 12 批 D-1: 派工纪要 v3 (5 段 prompt 模板 + W68 第 11 批 B 派工前提错误经验沉淀)"
> **分支**: `docs/w68-12th-batch-prompt-template-v3-2026-07-24`
> **基线**: main HEAD `7b6f0305e` (W68 第 11 批收官后)
> **0 production code 改动铁律**: 完全维持 (本批纯 docs + memory)
> **W19 选项 A**: 维持

---

## TL;DR

**W68 第 12 批 D-1 agent 完成派工 prompt 模板 v2 → v3 升级**:

- **v1** (W51 锚点范式启动): 5 段格式骨架 (背景 / 当前分支 / 任务 / 铁律 / 完成标准)
- **v2** (W62 5 agent 并行): 5 段沿用 0 偏离 + stash 隔离 + 6 点 curl 验证
- **v3** (本批升级, 1 docs + 1 memory): 5 段中叠加 5 处新纪律条目

**Why**: W68 第 9~11 批实战暴露 5 个"派工前提错误" (陈旧估值 / 文件名写错 / 重复声明阻塞 build / 文档格式错 / e2e SKIP 虚高), v2 未在 5 段中前置这些前提校验. v3 针对性在段 2/3/4 中插入 5 条, 让 agent 动手前完成前提校验.

**How to apply**: 见下方 5 处升级 / 第 12 批应用表 / 5 派工错误案例 / v1/v2/v3 兼容. 完整版见 `docs/w68-12th-batch-prompt-template-v3-2026-07-24.md`.

**交付**: 1 docs 新增 (`docs/w68-12th-batch-prompt-template-v3-2026-07-24.md` ~350 行) + 1 memory 新增 (本文件) + 1 commit + 1 push origin.

---

## 1. 5 段模板 v2 → v3 的 5 处升级

v3 保留 v1/v2 的 5 段骨架不变 (背景 / 当前分支 / 任务 / 铁律 / 完成标准), 仅在段 2/3/4 中插入 5 条:

| # | 段 | 新增条目 | 来源 (实战批次) |
|---|----|---------|-----------------|
| 5.1 | 段 3 任务描述 | `git fetch origin main && cd main && alembic heads` 前置校验, conflict 必报主指挥 (不自动修) | W68 第 11 批 C-1 |
| 5.2 | 段 4 完成定义 | `grep -rn <service_name> app/` 验证依赖存在, 不存在则新分支 (新功能例外) 或 escalate | W68 第 11 批 B-3 |
| 5.3 | 段 2 分支 | worktree base 必 fetch origin/main 同步, 避免陈旧 HEAD merge 冲突 | W68 第 11 批 C-2 |
| 5.4 | 段 4 完成定义 | e2e SKIP > 10% 必显式 escalate, 不得静默当 PASS | W68 第 10 批 C-1 |
| 5.5 | 段 4 完成定义 (仅前端) | 前端派工前必 `cd web && npm run build` 验证, 前后双跑 | W68 第 11 批 B-2 |

---

## 2. W68 第 12 批派工如何应用 v3

按派工性质选择性应用 (不是每个 agent 全部 5 条):

| 派工组 | 应用的 v3 条目 |
|--------|---------------|
| A-1 (plans 闭环) | 5.1 + 5.2 |
| B-1/B-2/B-3/B-4 (路线驱动) | 5.1 + 5.3 |
| C-1/C-2/C-3 (CI/测试/部署) | 5.1 + 5.4 |
| 留 W70 (前端 UI PR) | 5.5 |

**应用原则**:
- 5.1 (alembic 链) — 几乎所有派工默认应用 (不写 migration 时校验为跳过)
- 5.2 (grep 依赖) — plans / 调研派工重点
- 5.3 (worktree base fetch) — 所有 worktree 派工默认
- 5.4 (e2e SKIP escalate) — CI / e2e / 部署派工重点
- 5.5 (npm run build) — 仅前端 (`web/`) 派工

---

## 3. W68 第 12 批 5 派工错误案例 (v2 → v3 增量驱动)

| # | 案例 | 事实 | 驱动升级 |
|---|------|------|---------|
| 3.1 | B-3 ppt-word 调研 | 87.5% 真实施 (W66 估 30-40% 错) | 5.2 grep 真验证, 不信陈旧估值 |
| 3.2 | B-2 Mobile TabBar | 仓库实际文件 `MobileDashboard.vue`, 派工文字写错 | 5.5 前端 build + 5.2 grep 文件真名 |
| 3.3 | C-1 tabsWithCounts | 重复声明阻塞 build | 5.5 前端 npm run build 前后双验证 |
| 3.4 | C-2 CLI | Markdown vs JSON 文档错误 | 5.4 SKIP 意识 + 5.2 真跑 CLI 核对 |
| 3.5 | C-3 22 SKIP | 后端未部署 | 5.4 e2e SKIP > 10% 必 escalate |

**5 案例聚合**: 5 个派工前提错误驱动 v2 → v3 的 5 处 5 段升级.

---

## 4. v1 / v2 / v3 兼容关系 (升级而非替代)

| 版本 | 触发 | 核心 | 关系 |
|------|------|------|------|
| v1 | W51 锚点范式启动 | 5 段格式骨架 | 基线 |
| v2 | W62 5 agent 并行 | 5 段沿用 + stash 隔离 + 6 点 curl | v1 骨架不变, 扩展并发 |
| v3 | W68 第 12 批 | 5 段叠加 5 处新纪律 | v1/v2 骨架完全不变, 段 2/3/4 内插入 5 条 |

**升级而非替代的证据**:
1. 5 段骨架 0 改动 (段数/段名/段序不变)
2. 5 处新条目是"插入"而非"重写", 老条目全保留
3. 向后兼容 (历史 v1/v2 agent 完成标准不变)
4. 选择性应用 (后端/docs 派工可不涉及 5.5)

---

## 5. 5 新铁律

1. **5 段 prompt 升级 v3** — 派工 prompt 模板从 v2 (5 段格式) 升级 v3 (5 段中叠加 5 处新纪律条目: alembic 链前置 / grep 依赖 / worktree base fetch / e2e SKIP escalate / 前端 npm run build). 5 段骨架贯穿 v1/v2/v3 三代不变.
2. **plans 调研必 run** — plans / 调研派工必 `grep -rn <service_name> app/` + `git fetch origin main && alembic heads` 真验证依赖 / 已实施率 / 链状态, 不信陈旧 audit 估值 (W68 第 11 批 B-3 ppt-word 87.5% vs W66 估 30-40% 教训).
3. **派工前提错误经验沉淀** — W68 第 9~11 批 5 个派工前提错误 (陈旧估值 / 文件名写错 / 重复声明 / 文档格式错 / SKIP 虚高) 必沉淀到 prompt 模板对应段, 让后续批次动手前完成前提校验.
4. **W70 派工应用** — W70 派工按 §2 表选择性应用 v3 5 条, 前端 UI PR 派工重点应用 5.5 (npm run build 前后双验证).
5. **v1/v2/v3 兼容** — v3 是"升级而非替代": 5 段骨架 0 改动 + 5 条是插入非重写 + 向后兼容 + 选择性应用. 未来 v4 演化同样保持 5 段骨架 + 选择性应用原则.

---

## 6. 锚点范式第 155 守恒

- W68 第 11 批收官 → 锚点范式累计至第 154 守恒 (估算)
- W68 第 12 批 D-1 本 agent = 第 155 守恒
- 0 production code 改动铁律维持 (本批纯 docs + memory)
- 单调上升: W68 第 9 批 119 → 第 10/11 批 → 第 12 批 155

---

_本文件是 W68 第 12 批 D-1 agent 的派工 prompt 模板 v3 沉淀。完整 5 段模板 + 应用表 + 错误案例见 `docs/w68-12th-batch-prompt-template-v3-2026-07-24.md`。_
