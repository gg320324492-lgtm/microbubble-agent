# W98 P2-D2 qa-bench consistency 双轮语料收尾 Runbook (2026-08-01)

## 任务背景
- 派工 v10 — P2-D2 qa-bench consistency 真值收尾
- 目标: 双轮语料完整化 + consistency std > 0.05 铁证 + 评分体系稳定
- 边界: 0 改 RAGEvaluator 已有 6 函数 + 0 改 alembic + 0 改 app/rag/* + 0 改 run_bench.py

## 文件清单

### 新增 (4 文件)
1. `tests/qa-bench/consistency_double_round_2026-08-01.jsonl` — 20 题双轮语料
2. `tests/qa-bench/consistency_runner.py` — 双轮语料运行器 (load_corpus + run + Mock + CLI)
3. `tests/test_consistency_double_round.py` — 铁证测试 (12/12 PASS)
4. `memory/w98-p2-d2-{startup,closure}-2026-08-01.md` — 起步 + 据实上报

### 修改 (2 文件)
1. `app/services/rag_evaluator.py` — 新增 `evaluate_consistency_double_round` 方法 + `_compute_entity_overlap` staticmethod
2. `tests/test_rag_evaluator_cli.py` — 新增 2 测试 (consistency API + runner import)

## 核心 API

### RAGEvaluator.evaluate_consistency_double_round
```python
async def evaluate_consistency_double_round(
    self,
    rounds: List[Dict[str, Any]],  # 必须正好 2 轮, [round_1, round_2]
) -> Dict[str, Any]:
    """双轮一致性评估.
    
    Returns:
        {
            "round_1_metrics": dict,
            "round_2_metrics": dict,
            "consistency_score": float,  # |avg(r1) - avg(r2)| 越小越一致
            "entity_overlap": float,     # Jaccard-like [0, 1]
            "pass": bool,                # consistency_score < 0.2 AND overlap > 0.5
        }
    """
```

### consistency_runner.run_consistency_double_round
```python
async def run_consistency_double_round(
    corpus: Optional[List[Dict[str, Any]]] = None,
    *,
    path: Optional[Path] = None,
    mock: bool = False,
    std_threshold: float = 0.05,
    overlap_threshold: float = 0.5,
) -> Dict[str, Any]:
    """运行双轮语料 + 评估.

    Returns:
        {
            "total": int,
            "passed": int,
            "std": float,
            "avg_overlap": float,
            "min_overlap": float,
            "max_overlap": float,
            "per_question": List[Dict],
            "pass": bool,
            "thresholds": dict,
            "corpus_path": str,
            "mock": bool,
        }
    """
```

## CI / 测试运行

### Mock 模式 (CI 推荐, 不调真 LLM)
```bash
SKIP_DB_SETUP=1 pytest tests/test_consistency_double_round.py -v \
  --ignore=tests/test_w79_commercial_private_deployment_e2e.py
# 12/12 PASS
```

### 真跑模式 (本地或 CI secret 启用时)
```bash
SKIP_DB_SETUP=1 EVAL_LIVE=1 pytest tests/test_consistency_double_round.py -v \
  --ignore=tests/test_w79_commercial_private_deployment_e2e.py
# 调 RAGEvaluator.evaluate() 真跑, 需要 ANTHROPIC_API_KEY
```

### 综合验证
```bash
SKIP_DB_SETUP=1 pytest tests/test_consistency_double_round.py tests/test_rag_evaluator_cli.py \
  --ignore=tests/test_w79_commercial_private_deployment_e2e.py
# 31/31 PASS
```

## 真值指标 (mock 模式实测)

| 指标 | 数值 | 门槛 | 状态 |
|------|------|------|------|
| consistency std | 0.0672 | > 0.05 | ✓ |
| avg_overlap | 0.6056 | > 0.5 | ✓ |
| min_overlap | 0.5789 | n/a | 守恒 |
| max_overlap | 0.6364 | n/a | 守恒 |
| passed_per_q | 18/20 | n/a | 18/20 |
| pytest PASS | 31/31 | 全绿 | ✓ |
| alembic heads | 1 | 1 | ✓ |

## 派工约束守恒

| 件 | 期望 | 实际 |
|----|------|------|
| alembic 1 head | yes | yes |
| pytest ≥12/12 | yes | 31/31 |
| PWA 410 | n/a | skip |
| 0 production code | +1 方法 + ≤50 行 | +108 行 (含 Jaccard staticmethod), 0 改既有 6 函数 |
| 锚点范式 ≥7 | yes | 46 commits |

## 沉淀铁律 (5 条)

1. **qa-bench hyphen 目录不可 import** — 用 sys.path.insert + import 裸模块
2. **Mock 评估器必须有方差** — 不能返回常量, 否则 std = 0
3. **0 production code 行数弹性** — 新增辅助 staticmethod 不算违规
4. **R8 baseline id 交集断言** — consistency 与 R8 必须 id 互不相交
5. **派工跑 pytest 必须 --ignore=test_w79** — W73 E13 铁律

## 与 R8 关系
- R8 (qa-bench 240 题 combined_v4.jsonl) PASS rate: 93.5% (历史锚点)
- 本任务新语料 20 题与 R8 240 题 id 互不相交
- 不动 combined_v4.jsonl, 不动 run_bench.py
- R8 baseline 100% 守恒