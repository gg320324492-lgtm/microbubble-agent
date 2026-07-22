# qa-bench D5 1000 题 baseline 占位文档

## 状态: 待主指挥手动跑 (W67, 2026-07-23)

主指挥已决策: 因 worktree 无 API 凭据 (LLM_API_KEY / ANTHROPIC_API_KEY),
本次跳真实跑题. 待主指挥在 main 分支 + API 凭据就绪后, 手动跑:

```bash
cd tests/qa-bench
export ANTHROPIC_API_KEY=sk-...
python run_bench.py --rounds=3 --verdict-consensus=2 --include-extra     --full-1000 --output=baseline_d5_1000.json
```

## 预期指标 (基于 D4 700 题 baseline)

| 维度 | D4 700 题 (实际) | D5 1000 题 (待跑) |
|------|------------------|--------------------|
| pass rate | XX% (≥80% CI) | (待跑) |
| correctness | X.X | (待跑) |
| completeness | X.X | (待跑) |
| relevance | X.X | (待跑) |
| clarity | X.X | (待跑) |
| conciseness | X.X | (待跑) |
| coherence | X.X | (待跑) |
| citation | X.X | (待跑) |
| avg_latency_ms | XXX | (待跑) |
| total_tokens | XXXX | (待跑) |
| total_cost_usd | $X.XX | (待跑) |

## 6 维雷达图 (ASCII 占位)

```
             correctness
                  5
                 /|                / |                /  |       citation - -|- - - completeness
             3   |   3
            /    |               3 ----+---- 3
          /      |           clarity -- conciseness -- relevance
               5
```

(数据填入后画真实雷达图, 见 baseline_d4_700_summary.md 模板)
