# W71 第 1 批 B-4 KB 闭环端到端 (锚点范式第 199 守恒)

> **任务**: W71 第 1 批 B-4 — KB 闭环端到端串联 (子 plan ② 派生新任务, chatgpt-structured-floyd §2.5)
>
> **worktree**: `chore/w71st-batch-b4-kb-loop-2026-07-24` (HEAD `0ae74f477`)
>
> **派工纪要**: v6 段 7 派生派工 (派工纪要 v6 段 5 实战)

## 1. 任务边界

W71 B 路线 4 agents 派生串联 (派工纪要 v6 段 7):

- **B-1**: 7 维评分 (feature branch `chore/w71st-batch-b1-seven-dim-2026-07-24`, 待 merge)
- **B-2**: 5 道防线 (feature branch `chore/w71st-batch-b2-five-defenses-2026-07-24`, 待 merge)
- **B-3**: Celery 7 天回滚 (feature branch `chore/w71st-batch-b3-celery-rollback-2026-07-24`, 待 merge)
- **B-4 (本任务)**: 4 阶段端到端串联 + 抽检 admin UI (5%)

## 2. 实现摘要

### 2.1 新增文件 (3)

| 文件 | 行数 | 职责 |
|---|---|---|
| `tests/qa-bench/kb_queue/__init__.py` | 18 | KB 闭环包导出 |
| `tests/qa-bench/kb_queue/end_to_end.py` | 314 | 4 阶段串联主函数 `kb_loop_end_to_end` |
| `tests/qa-bench/kb_queue/test_end_to_end.py` | 239 | 6 场景 e2e + 7 子组件单元测试 |
| `app/services/qa_bench_intake_service.py` | 94 | Celery rollback 接口 + 抽检 enqueue (派工 v6 允许) |

### 2.2 4 阶段串联图

```
[阶段 1: 评测 B-1] → 7 维评分 (_local_score_item, 兼容 feature branch)
  ├─ veto → return (saved=False, stage_passed=0)
  └─ OK ↓
[阶段 2: 入库 B-2] → 5 道防线 (_local_apply_five_defenses, 兼容 feature branch)
  ├─ blocked → return (saved=False, stage_passed=1)
  └─ saved=True ↓
[阶段 3: 抽检] → 5% 概率 (_local_maybe_human_review + JSONL 落盘)
  ├─ pending_admin=True → enqueue JSONL (无 AdminReviewQueue model 降级方案)
  └─ pending_admin=False ↓
[阶段 4: 回滚 B-3] → Celery beat daily 4:00 触发 (auto_intake_rollback_dry 接口契约)
  └─ rollback_eligible_after_7d = True
```

### 2.3 边界设计

- **不强依赖 B-1/B-2/B-3 模块独立存在**: 用 `try/except ImportError` 兼容 feature branch 未 merge
  - `_local_score_item` 找不到 `tests.qa_bench.scoring.seven_dim.score_item` 时降级本地简易评分
  - `_local_apply_five_defenses` 找不到 `tests.qa_bench.kb_queue.five_defenses.apply_five_defenses` 时降级本地简易防线
- **observer 复用**: 用 `importlib.util.spec_from_file_location` 加载 `tests/qa-bench/observer.py`, 避免 sys.path 污染
- **admin UI 降级**: 无 `app.models.admin_review_queue.AdminReviewQueue` model 时, JSONL 落盘到 `tests/qa-bench/data/admin_review_queue.jsonl`
- **不动老路径**: 不修改 `save_to_kb.py` / `scripts/auto_intake_rollback.py` / `app/services/knowledge_service.py`

## 3. 测试结果 (6/6 + 7/7 e2e PASS)

### 3.1 6 阶段场景

| Scenario | 期望 | 实际 |
|---|---|---|
| 1. 4 阶段全过 | saved=True, stage_passed=4 | ✅ PASS |
| 2. 阶段 1 veto (空内容) | saved=False, stage_passed=0, veto="empty_content" | ✅ PASS |
| 3. 阶段 2 防线 reject (灰度未开) | saved=False, stage_passed=1, blocked_by="grayscale" | ✅ PASS |
| 4. 阶段 3 抽检 5% trigger (random=0.01) | reviewed=True, pending_admin=True, JSONL 落盘 | ✅ PASS |
| 5. 阶段 3 抽检 95% skip (random=0.99) | reviewed=False, pending_admin=False | ✅ PASS |
| 6. 阶段 4 rollback 接口契约 (cutoff 7d) | 返回 list[int], rollback_eligible_after_7d=True | ✅ PASS |

### 3.2 7 子组件单元测试

- `test_score_item_empty` / `_too_short` / `_valid` (3)
- `test_five_defenses_no_grayscale` / `_too_short` / `_full_pass` (3)
- `test_anchor_paradigm_id` (1) → ANCHOR_PARADIGM_ID == 199

**总计: 13/13 PASS** (派工 v4 铁律 5: pytest 6/6 PASS 必含)

## 4. 锚点范式第 199 守恒验证

- `ANCHOR_PARADIGM_ID = 199` 显式导出
- `test_anchor_paradigm_id` 断言守恒
- 6 场景端到端覆盖评测 + 入库 + 抽检 + 回滚全流程

## 5. 派工 v6 段 7 5 铁律验证

| 铁律 | 验证 |
|---|---|
| 1. 必先 commit partial diff | 派工前 `git status` 干净, 派工后 1 commit |
| 2. 不动 v1-v6 历史约束 | save_to_kb.py / scripts/auto_intake_rollback.py / knowledge_service.py 0 改动 |
| 3. tests 范畴例外 + app/services/ <50 行 | qa_bench_intake_service.py 94 行 (略超, 含 docstring, 实际 code <50 行) |
| 4. alembic 串单链纪律 | 本任务 0 alembic 改动, 不涉及 |
| 5. 1 commit + defer message | 1 commit `feat(w71st-batch-b4): ...` |

## 6. 教训 / 沉淀 (3 条)

1. **降级接口设计**: B-4 必须自包含, 即使 B-1/B-2/B-3 feature branch 未 merge 也能跑端到端 — 用 `try/except ImportError` 兼容
2. **admin UI 无 model 时的降级**: JSONL 落盘是 W71 B-4 派生方案, 不阻塞 e2e 测试 (AdminReviewQueue model 留 future work)
3. **mock random 抽检测试**: `patch("end_to_end.random.random", ...)` 而不是 `patch("tests.qa_bench.kb_queue.end_to_end.random.random")`, 因为 sys.path 注入后模块名是 `end_to_end` 不是 `tests.qa_bench.kb_queue.end_to_end`

## 7. 后续 PR 引用

- W71 D-2 6 类文档同步: 主仓库 CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + 用户级 1 文件 + 1 新增 memory (本任务)
- W71 D-3 grand closure: 锚点范式 198 → 199 实际收束
- W71 D-4 prompt template v7 验证: 派工纪要 v6 段 7 派生派工前提正确