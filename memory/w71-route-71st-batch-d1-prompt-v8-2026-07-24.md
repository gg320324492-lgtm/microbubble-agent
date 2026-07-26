---
name: w71-route-71st-batch-d1-prompt-v8
description: "W71st batch D-1 派工纪要 v8 (锚点范式第 204 守恒) — v7 → v8 升级链路: 段 3 升级 SubAgent 编排接口 type hint 实战 + 段 4 升级 SubAgent type hint 编译产物 grep + 段 5 升级 9 → 12 项必填 (+SubAgent 编排 / 派生新任务真验证 / B 路线 5 agents 接口契约 3 项) + 段 6 升级 B 路线 5 agents Celery 串行约束 + 段 7 升级 10 → 13 类派工前提错误 (+跨 agent 接口契约 / SubAgent type hint / 派生新任务真验证 3 类) + 新增段 8 W72 子 plan ③ 起步纪律 (4 项必含 + 4 项派工必写 + 3 项 24h 必填). W71 batch 实战暴露 v7 对 B 路线 5 agents 接口协调 + SubAgent 编排 + 派生新任务真验证 3 类纪律 0 覆盖, v8 必含. 派工纪要本身纯 docs, 0 production code 改动铁律维持. 派工前提 5/5 守恒. 1 commit defer."
metadata:
  node_type: memory
  type: project
  originSessionId: W71st-batch-D-1
  modified: 2026-07-24T00:00:00.000Z
---

# W71st batch D-1: 派工纪要 v8 (W71 实战反馈: B 路线 5 agents 接口协调 + SubAgent type hint + 派生任务真验证, 锚点范式第 204 守恒, 2026-07-24/27)

> 派工纪要 v8 是 v7 的纯增量升级 (派工 v8 第 4 条铁律: 不动 v1-v7 历史约束). 仅升级段 1/2/3/4/5/6/7 + 新增段 8.

## 1. v7 → v8 升级链路 (8 段联动)

- **段 1** (角色/范围/不变量): 在 v7 依赖 agent 行后新增"若本 agent 是 B 路线 5 agents 之一"小节, 必含接口契约文件路径 + 数据格式约定 + Celery 串行约束 + 派生新任务清单
- **段 2** (交付物/边界): 在 v7 "禁止" 后新增"SubAgent 编排接口必含 type hint"小节, type hint 强制约束
- **段 3** (前置验证/门禁): 在 v7 PWA / SW 状态检查 后新增 "SubAgent 编排接口 (v8 实战)" + "B 路线 5 agents 接口协调 (v8 实战)" 两类实战检查
- **段 4** (完成定义/PS 5.1): 在 v7 runtime 心跳/console 噪声 后新增 "SubAgent type hint 编译产物 grep (v8 实战)" 实战约束
- **段 5** (反馈循环): v7 9 项必填 → **v8 12 项必填**, 新增 3 项实战信号: SubAgent 编排 type hint / 派生新任务真验证 / B 路线 5 agents 接口契约 + Celery 串行
- **段 6** (合并顺序表): 在 v7 表格新增 "接口契约 / Celery 依赖" 列, 在三段串联后新增 "B 路线 5 agents 接口协调实战 (v8 新增)" 段
- **段 7** (派工前提错误): v7 10 大类 → **v8 13 大类**, 新增 3 类实战派工前提 (W71 B 路线 5 agents + SubAgent 编排 + 派生任务): 跨 agent 接口契约 / SubAgent type hint / 派生新任务真验证
- **段 8** (新增): W72 子 plan ③ 起步纪律 - 4 项起步前必含 + 4 项派工必写 + 3 项 24h 必填 (W71 D-1 实战升 v8 必备, 给 W72 派工提供"起步前必读"模板)

## 2. 派工纪要 v8 12 项段 5 反馈循环实战 (派工纪要 v8 §5)

v8 段 5 必填 12 项 = v7 9 项 + v8 新增 3 项:

| 新增项 | 适用场景 | 实战根因 |
|---|---|---|
| **第 10 项: SubAgent 编排 type hint** | SubAgent 串接 agent 必填 | C-2 sub-agent 编排 v2 沉淀时, 跨 agent 串接 Pydantic 校验报 `missing field` / runtime `AttributeError` |
| **第 11 项: 派生新任务真验证** | 主指挥口头追加子任务 agent 必填 | C-1 qa-bench D8 调研派工时, 主指挥口头追加"派生 7 项实施前置"子任务, agent 自报完成但 `git log` 显示派生任务实际未派工 |
| **第 12 项: B 路线 5 agents 接口契约 / Celery 串行** | B-1/B-2/B-3/B-4/B-5 必填 | B-1 `seven_dim.py` 接口签名与 B-2 `kb_queue/dedup.py` 输入格式冲突; B-3 Celery 串行约束与 B-4 audit 触发时序不齐; B-5 dashboard 数据源与 B-1 7 维权重 schema 不一致 |

## 3. 派工纪要 v8 13 类段 7 派工前提错误实战 (派工纪要 v8 §7)

v8 段 7 必填 13 大类 = v7 10 类 + v8 新增 3 类:

| 新增类 | 派工时假设 | 实际验证结果 | 修正方式 |
|---|---|---|---|
| **跨 agent 接口契约** | B-1 seven_dim.py 7 维权重 + B-2 dedup embedding 余弦各自定义 | B-2 输入依赖 B-1 输出, 权重 schema 不一致 → dashboard 数据源失败 | 段 5 必填接口契约表 + Celery 串行约束 + 段 6 合并顺序表新增列 |
| **SubAgent type hint** | SubAgent 输入/输出 dataclass 自动传递 | 跨 agent 串接时 Pydantic 校验报 `missing field` 或 runtime `AttributeError` | 段 3 强制 type hint grep + 段 4 编译产物 grep + 段 5 必填第 10 项 |
| **派生新任务真验证** | 主指挥口头追加子任务 → agent 自报完成 | `git log` 显示派生任务实际未派工 / 未实施 | 段 3 必先写 backlog docs + 段 5 必填第 11 项 + 真验证 3 段 |

## 4. 派工纪要 v8 段 8 W72 子 plan ③ 起步纪律 (派工纪要 v8 §8)

W72 子 plan ③ UI redesign (NavRail + ThinkingModeSwitch + ChatBreadcrumb) 派工前必读 4 项:
1. **W71 B 路线 5 agents 全部 commit + merge 后才启动 W72**:
   - B-1 seven_dim.py + weights.json 必须 main HEAD 可查
   - B-2 kb_queue/ 5 文件必须 main HEAD 可查
   - B-3 auto_intake_rollback_task.py + save_to_kb.py 重写必须 main HEAD 可查
   - B-4 audit_trigger.py + Celery beat 调度必须 main HEAD 可查
   - B-5 QaBenchDashboard.vue + smoke_200.py + qa-bench-smoke.yml 必须 main HEAD 可查
   - 验证命令: `git log --oneline main | grep -E "w71st-batch-(b1|b2|b3|b4|b5)"` 期望 ≥ 5 commits
2. **W71 子 plan ② 7 维评分数据 + KB 闭环验证**:
   - QaBenchDashboard 启动后必能拉取 7 维权重 schema 数据
   - KB 闭环审计触发后必能写入 audit log
   - baseline 71+7 守恒验证: pytest 新增 PASS = 0 + 新增 SKIP = 0
3. **W72 子 plan ③ UI redesign 三大件** (NavRail / ThinkingModeSwitch / ChatBreadcrumb):
   - 必先 W71 子 plan ② 数据可用后才动手 UI 改造
   - 任何 UI 改动必先 grep 看是否影响老 desktop / mobile 路由栈
   - NavRail 涉及路由级双栈必双端验证
   - ThinkingModeSwitch 涉及 chat engine 必须回归方案 C 6 条铁律
   - ChatBreadcrumb 涉及知识库 metadata 必回归 knowledge_service.py
4. **派工前提错误必含 W71 实战 13 类** (v7 10 + v8 3)

## 5. 派工前提错误复盘 (派工纪要 v8 段 7, 24h 内必填)

- **必先 commit partial diff** (派工 v6 第 1 条铁律): ✅ 派工前 `git status --short` 干净 (0 changes)
- **不动 v1-v7 历史约束** (派工 v6 第 4 条铁律): ✅ 段 8 新增, 段 1-7 仅升级, v1-v7 原文不动
- **段 5 必含 W71 实战新发现** (派工 v6 第 4 条铁律): ✅ 段 5 12 项必填含 3 项 v8 实战信号
- **0 production code 改动铁律** (派工 v6 永久): ✅ 本任务纯 docs/memory, 0 production code 改动
- **1 commit + defer message**: ✅ 1 commit `docs(w71st-batch-d1): ...`

## 6. 沉淀位置

- **派工纪要 v8 文档**: `docs/w71-dispatch-candidates-v8-2026-07-24.md` (~395 行, 含 v7→v8 diff 详表 + 段级 diff + 9 条新铁律 + 完整兼容矩阵 + 段 8 W72 起步纪律)
- **派工纪要 v8 memory**: 本文件 (~80 行, 锚点范式第 204 守恒)
- **派工纪要 v7 文档** (历史参考): `docs/w71-dispatch-candidates-v7-2026-07-24.md` (~445 行)
- **派工纪要 v7 memory**: `memory/w71-route-71st-batch-a2-prompt-v7-2026-07-24.md`
- **W71 B 路线 5 agents 子 plan ② 实施明细**:
  - B-1 qa-bench 7 维评分 (`tests/qa-bench/scoring/seven_dim.py` + `weights.json` + 单测)
  - B-2 KB 5 道防线 (`tests/qa-bench/kb_queue/dedup.py` + 4 文件)
  - B-3 Celery auto_intake_rollback_task + save_to_kb 重写
  - B-4 KB 闭环 (audit_trigger.py + Celery beat 调度)
  - B-5 QaBenchDashboard.vue + smoke_200.py + qa-bench-smoke.yml

## 7. 不要做的事 (本次守住)

- ❌ 不动 production code (web/src Vue / app/ FastAPI / alembic/versions) — 本任务纯 docs/memory
- ❌ 不删 v7 任何段原文 (派工纪要 v8 第 4 条铁律)
- ❌ 不在 main 工作 — 本任务在 worktree `E:/microbubble-agent/.worktrees/agent-w71st-d1-prompt-v8`
- ❌ 不拆 source/dist (本任务无 dist 改动)
- ❌ 不删 v7 9 项段 5 反馈循环原文 (v8 段 5 仅升级 9 → 12 项, 原文保留)
- ❌ 不删 v7 10 类段 7 派工前提错误原文 (v8 段 7 仅升级 10 → 13 类, 原文保留)

## 8. 锚点范式

锚点范式单调上升: W7 12 → ... → W68 第 14 批 175 → W71st batch 实际收束 ~184 → **W71st batch D-1 v8 沉淀后预测 204** (本任务 D-1 仅 1 锚点 + v7→v8 升级沉淀的实际锚点跃迁)

**Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**