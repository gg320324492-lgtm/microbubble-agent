# W71 C-1 — qa-bench D8 R8/R9 BGE m3 生产决策

> 日期: 2026-07-27  
> 分支: `chore/w71st-batch-c1-d8-survey-2026-07-24`  
> 范畴: `tests/qa-bench/` + memory，0 production code 改动  
> 锚点范式: 第 201 守恒

## 1. 任务来源

`docs/chatgpt-structured-floyd-w69-plan.md` 子 plan ②与
`docs/qa-bench-d8-comprehensive-survey-2026-07-24.md` 的真验证显示：
D5 Dashboard KB 监控、D6 CI 80% 门禁、D7 baseline CI 已实施，D8 的
R8/R9 BGE m3 生产决策仍缺可执行的测试侧策略模块。

W71 B-1 是 7 维评分前置依赖；本任务在它的排名结果上增加 BGE m3 top-1
一致性门禁，并定义 200 题、7 天的 R9 灰度契约。

## 2. 派工前真验证

- worktree 分支与 HEAD 匹配：`0ae74f477`。
- `git status --short` 空，未发现需要先提交的 partial diff。
- D5/D6/D7 物证存在：Dashboard、80% CI gate、baseline CI。
- `tests/qa-bench/RERANKER_DECISION_LOG.md` 记录 R8 187/200（93.5%）与
  R9 30 题再评估；历史生产结论为保留 BGE m3。
- `app/services/reranker_service.py` 已提供真实 BGE m3 cross-encoder
  `rerank_async`；派工草案所写 `get_bge_m3_embeddings` 当前不存在。
- W68 7 维评分真实文件名是 `seven_d_scoring.py`；派工草案的
  `tests.qa_bench.scoring.seven_dim.score_item` 当前不在本分支。

因此实现保留两套兼容入口，但默认使用真实 cross-encoder reranker；7 维
评分通过可注入 scorer 或 benchmark 显式候选分数接入，避免伪造不存在的 API。

## 3. 实施内容

### `tests/qa-bench/d8_bge_m3.py`

- `d8_r8_bge_m3_rerank`：运行 7 维候选评分与 BGE m3 重排序。
- top-1 一致时返回 `production`；不一致返回 `gradual`。
- 输出双方 top index、候选数与 0.0/1.0 一致率，便于审计。
- `d8_r9_production_rollout`：定义 200 题、7 天、BGE m3 + 7 维全量契约。
- `d5_d8_route_status`：提供 3 dashboard cards + 1 CI gate 的串联状态。
- 输入校验覆盖空 question、空 candidate、非法 reranker 返回值与 sample size。

### `tests/qa-bench/test_d8_bge_m3.py`

四个场景：

1. BGE m3 top-1 = 7d top-1 → production。
2. top-1 不一致 → gradual。
3. 200 题 rollout → completed、duration=7d。
4. D5-D8 串联通 → 3 dashboard cards + 1 CI gate。

## 4. 验证

```bash
SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/test_d8_bge_m3.py -q
```

结果：`4 passed in 0.04s`。

使用 `SKIP_DB_SETUP=1` 是因为四个场景均为纯策略测试；仓库根 conftest 默认
自动连接 PostgreSQL，而本次运行环境数据库未启动。该标志不会跳过任何 D8
断言，只禁用无关的全局建表 fixture。

Typing/import 验证：模块使用 `from __future__ import annotations`，所有
`Sequence`、`Mapping`、`Callable`、`Awaitable`、`Any` 均显式导入；测试收集与
执行通过。

## 5. D5-D8 串联通图

```text
D5 Dashboard KB monitoring
  └─ 3 cards: kb_intake / pass_rate / audit_pending
       ↓
D6 CI 80% gate
       ↓
D7 baseline CI
       ↓
D8 R8: BGE m3 top-1 ↔ seven-dimensional top-1
       ├─ match    → production
       └─ mismatch → gradual
                         ↓
D8 R9: 200 questions × 7 days, BGE m3 + 7d scoring
```

## 6. 守恒结论

- 只新增 tests 与 memory；未改 `app/`、`web/src/`、alembic。
- 不修改派工纪要 v1-v6 历史约束。
- D8 从调研状态升级为可执行、可测试、可审计的生产决策策略。
- 锚点范式第 201 守恒。
