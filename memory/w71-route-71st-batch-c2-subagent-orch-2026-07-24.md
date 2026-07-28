# W71-C-2 SubAgent 编排 5 Agents 接口契约 (2026-07-24)

> **派生新任务**: W71 派工 v6 段 6 实战, 防止 B 路线 5 agents 跨服务调用时类型不匹配 / 数据结构不一致。
> **目标锚点**: 锚点范式第 202 守恒。

## 任务基线

- **worktree**: `E:/microbubble-agent/.worktrees/agent-w71st-c2-subagent-orch`
- **branch**: `chore/w71st-batch-c2-subagent-orch-2026-07-24` (HEAD `0ae74f477`)
- **commit**: `1aa0225b1` (派生新任务 commit)
- **范围**: 仅 `docs/` + `tests/qa-bench/mocks/` 新增, 0 production code 改动

## 5 Agents 接口契约表 (实测代码)

| Agent | 实际函数位置 | 输出类型 |
|-------|------------|---------|
| **B-1** | `tests/qa-bench/runner.py:465 score_seven_dim` | `dict{dim_scores, total_score, grade, veto}` |
| **B-2** | `tests/qa-bench/save_to_kb.py:122 collect_candidates` | `list[dict{qa_id, question, content, score, intent}]` |
| **B-3** | `scripts/auto_intake_rollback.py:35 find_rollback_candidates` | `list[dict{id, title, source_type, created_at}]` |
| **B-4** | (设计契约, B-4 agent 待实施) | `dict{stage, score, defense, review, rollback_eligible}` |
| **B-5** | `tests/qa-bench/dashboard/gen_data.py:16 main` | (前端 HTML) |

## Mock 模板路径

| Mock | 文件 | 场景数 |
|------|------|-------|
| score_item | `tests/qa-bench/mocks/score_item.json` | 3 (pass/warn/veto) |
| defense | `tests/qa-bench/mocks/defense.json` | 3 (in_grayscale/filtered_out/wrong_intent) |
| rollback | `tests/qa-bench/mocks/rollback.json` | 3 (candidates/no_candidates/report) |
| kb_loop | `tests/qa-bench/mocks/kb_loop.json` | 3 (stage_2_pass/stage_5_rollback/state_machine) |
| loader | `tests/qa-bench/mocks/__init__.py` | `load_mock(name) + list_mocks()` |

## 派工顺序 (派工 v6 段 6 实战)

1. Day 1: 派 B-1 (其他 4 依赖) → merge
2. Day 2: 派 B-2 + B-3 并行 (接口独立) → merge
3. Day 3: 派 B-4 (端到端串联 B-1+B-2+B-3) → merge
4. Day 4: 派 B-5 (Dashboard 验收) → merge

## 铁律 (5 条, 派工纪要 v6 段 5 实战)

1. **必先 commit partial diff** — B-3 教训 (本任务派工前干净, 0 改动)
2. **不动 v1-v6 历史约束** (派工 v6 第 4 条铁律)
3. **0 production code 改动铁律** — 纯 docs + mocks
4. **接口必含 type hint** (派工 v6 段 6 实战: 171 文件 typing check 0 错)
5. **1 commit + defer message**

## 验证状态

- [x] partial diff 已 commit (派工前干净, `0ae74f477`)
- [x] docs/w71-batch-orchestration-2026-07-24.md 落盘 ~250 行
- [x] 5 mock JSON 模板落盘 + __init__.py loader (load_mock 实测 4 mock OK)
- [x] typing imports 0 错 (171 文件 scan pass)
- [x] 1 commit + push (commit `1aa0225b1`)
- [x] memory 沉淀 (本文件)

## 防接口不匹配 4 道关

1. 派工 prompt 必含接口契约表 (本 docs §2)
2. 每个 agent 完工后跑 mock 自验 (`load_mock(name)`)
3. typing imports 必跑 `bash scripts/check_typing_imports.sh`
4. 接口变更必更新本 docs (本任务维护责任)

## 证据索引

- commit `1aa0225b1`: 6 files / 575 insertions
- `tests/qa-bench/runner.py:465` — B-1 实际实施
- `tests/qa-bench/save_to_kb.py:122` — B-2 实际实施
- `scripts/auto_intake_rollback.py:35` — B-3 实际实施
- `tests/qa-bench/dashboard/gen_data.py:16` — B-5 实际实施
- `docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md` — W68 第 14 批 A-3 调研依据

> W71-C-2 派生新任务: docs-only + mocks-only; 目标锚点范式第 202 守恒。