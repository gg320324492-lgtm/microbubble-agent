---
name: w68-route-14-d1-prompt-template-v6-2026-07-24
description: "W68 第 14 批 D-1 派工纪要 v6 模板升级 — 锚点范式第 180 守恒, 段 5 升级 6 项必填 + 段 7 派工前提错误复盘, 5 大派工前提错误沉淀, 7 新铁律."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-14th-batch-D-1
  modified: 2026-07-24T00:00:00.000Z
---

# W68 Route 14 D-1：Prompt Template v6

日期：2026-07-24
范围：仅 docs + memory；0 production code 改动。
锚点范式：第 180 守恒。

## 交付与背景

本路线新增 `docs/w68-dispatch-candidates-v6-2026-07-24.md`，将 W68 第 14 批派工纪要 v5 升级为 v6：保留 v5 全部 6 段门禁与段 5 反馈 + 段 6 合并顺序两段，仅在段 5 升级必填 6 项 + 新增段 7 派工前提错误复盘 + 段 4 显式 web build 约束。v6 对 v5 是纯增量，不破坏既有 v1/v2/v3/v4/v5 派工的可追溯性。

## v5 → v6 增量结构

| 段 | v5 内容 | v6 增量 |
|---|---|---|
| 段 1 | 角色、范围、不变量 | 不变 |
| 段 2 | 交付物、操作边界 | 不变 |
| 段 3 | 任务描述、前置验证、风险门禁（含 Alembic 双头 + plans 真验证）| 不变 |
| 段 4 | 完成定义、测试、PS 5.1 binding | **新增 "web 改动必须 `npm run build`，禁止 vite build 直跑" 约束** |
| 段 5 | 经验反馈循环（3 项必填）| **升级为 6 项必填**：有效段 / 多余段 / 新增段 7 候选 / 旧段升级建议 / 派工前提错误 / 锚点范式变化 |
| 段 6 | 主指挥合并顺序表 | 不变 |
| 段 7 | （无）| **新增 "派工前提错误复盘"**：24h 内必填 5 大类前提表格 + 沉淀规则 |

## 7 条新铁律

1. **段 5 反馈必填 6 项**——agent 完工回传必须含段 5 六类（有效段 / 多余段 / 新增段 7 候选 / 旧段升级建议 / 派工前提错误 / 锚点范式变化），每项需具体句子/短语，缺一不可。
2. **段 6 合并顺序表必含 alembic 串单链位置 + 跨 PR 部署 checklist**——`base=<上游 revision> down_revision=<上游 revision>` 必填，agent 不得擅自修改；跨 PR 部署必含"docker cp + clear cache + upgrade + restart" 4 步。
3. **v6 默认应用从 W68 第 15 批开始**——W71 派工默认 v6；W72 调研任务**必须**用 v6。
4. **段 7 派工前提错误必 24h 内回填**——agent 完工后 24h 内必填段 7（5 大类前提表格 + 真实案例引用 + 沉淀位置），未填视为派工流程违规。
5. **段 7 5 大派工前提错误必含**——alembic 串单链 / PS 5.1 / plans 真验证 / web `npm run build` / baseline 守恒。每类必回填"假设/实际/修正"3 段。
6. **web 改动必须 `npm run build`，禁止 vite build 直跑**——v6 段 4 显式写入。违反者按 PWA manifest 410 铁律（commit `59187ce8`）处理。
7. **v6 段 5 第 6 项必填"锚点范式变化"**——agent 完工后必须显式声明本批推进锚点范式数字、推进多少、为什么。主指挥 grand closure 据此核对四维度。

## v5 → v6 升级路径

- **段 1–4**：完全沿用 v5，不改任何字。
- **段 4**：补一句 "web 改动必须 `npm run build`"。
- **段 5**：从 3 项必填升级为 6 项必填（每项需具体句子/短语）。
- **段 6**：完全沿用 v5，不改任何字。
- **段 7**：全新段，24h 内必填 5 大类前提错误表格。

## W68 第 14 批 15 agents 应用 v5 → v6 实战反馈

W68 第 14 批 15 agents（A-1 ~ A-4 + B-1 ~ B-3 + C-1 ~ C-4 + D-1 ~ D-3）在派工时已应用 v5。本任务基于以下实战反馈起草 v6：

- **段 5 不充分**：5/15 agents 仅写"全部有效"，8/15 颗粒度粗，2/15 未填。v6 升级为 6 项必填。
- **段 6 有效**：合并顺序表让 B-1/B-2/B-3 alembic 串单链顺序明确，主指挥按 Step 顺序合并节省沟通时间。v6 保留 + 升级（跨 PR 部署 checklist）。
- **段 4 web 约束缺失**：C-2/C-3 web 改动需走 postbuild 链路，但 v5 未明示。v6 段 4 强制 `npm run build`。
- **段 7 缺失**：5 大派工前提错误（alembic 串单链 / PS 5.1 / plans 真验证 / web `npm run build` / baseline 守恒）需要显式沉淀。v6 新增段 7。

## v6 完整兼容矩阵

| 版本 | 段数 | 新增能力 | 适用 |
|---|---|---|---|
| v1 | 3 | 基本角色、范围、交付物 | 历史单 agent 小任务 |
| v2 | 4 | 增加测试、证据、分支边界 | 一般文档/前端任务 |
| v3 | 5 | 五段结构雏形、交接和回滚 | W68 第 12 批 |
| v4 | 5 | 完整五段、前置门禁、证据闭环（Alembic / PS 5.1 / plans 真验证）| W68 第 13 批 + W71 |
| v5 | 6 | v4 + 段 5 反馈 + 段 6 合并顺序 | W68 第 14 批 + W71+ |
| **v6** | **7** | **v5 + 段 5 升级 6 项 + 段 7 派工前提错误 + web build 约束 + 锚点范式显式追踪** | **W68 第 15 批 + W71+ + W72** |

## 验证与交接

本任务应验证 `docs/w68-dispatch-candidates-v6-2026-07-24.md` 文件存在、关键短语齐全、Markdown diff 无空白错误。`memory/w68-route-14-d1-prompt-template-v6-2026-07-24.md` 文件存在、字段齐全。

不得修改 production code，不动 `docs/w68-dispatch-candidates-v5-2026-07-24.md`（保持 v5 历史不被覆盖）。

提交信息末尾必须包含 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。

D7 baseline 守恒验证：`REDIS_URL=redis://localhost:6379/0 bash scripts/ci_qa_bench_baseline.sh` → 期望 71 PASS + 7 SKIP（不变）。

主指挥合并后需验证远端 ref、两个文件存在、单一 alembic head（本次不涉及迁移）。

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24