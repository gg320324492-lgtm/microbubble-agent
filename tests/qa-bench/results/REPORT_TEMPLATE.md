# qa-bench 报告模板

> **版本**: v3.1 (D7 文档交付)
> **配套**: [GUIDE.md § 5.7 维评分详解](../GUIDE.md) + [MILESTONES.md](../MILESTONES.md)
> **用途**: 单次跑测后粘贴此模板填写 / 或用 `tests/qa-bench/reports/trend.py` 自动生成 HTML

---

## 1. 摘要 (Executive Summary)

| 字段 | 值 |
|---|---|
| 跑测日期 | YYYY-MM-DD |
| Backend | anthropic / openai_compat / ollama (model 名) |
| 题数 | N (smoke=200 / 全量=780) |
| 通过率 | X% (PASS / total) |
| 总分 | X / 100 (加权) |
| 一票否决数 | N (veto_count) |
| CI 状态 | PASS / FAIL |
| 与 v3.0 baseline 对比 | ±% |

**一句话结论**: 跑测 [通过/未通过]，[优势维度]，[短板维度]，[建议行动]。

---

## 2. Pass Rate 趋势

| 版本 / 跑测 | 时间 | 题数 | Pass Rate | 7 维总分 |
|---|---|---|---|---|
| v3.0 baseline | 2026-06-30 | 200 | (smoke_5_run 平均) | — |
| 当前跑测 | YYYY-MM-DD | 200 | X% | Y |

---

## 3. 7 维评分

```mermaid
radarChart
    title qa-bench 7 维评分 (v3.1)
    axis "intent", "tool", "content", "rich", "defense", "perf", "consistency"
    curve "本轮" : [100, 88, 72, 95, 90, 85, 80]
    curve "v3.0 baseline" : [100, 90, 53, 100, 100, 87, 100]
    max 100
    min 0
```

| 维度 | 权重 | 本轮分 | baseline | 评级 |
|---|---|---|---|---|
| intent | 10% | — | 100 | — |
| tool | 25% | — | 100 | — |
| content | 30% | — | 53 | — |
| rich | 5% | — | 100 | — |
| defense | 15% | — | 100 | — |
| perf | 10% | — | 87 | — |
| consistency | 5% | — | 100 | — |
| **总分** | **100%** | — | — | — |

## 4. 类别分布
A 成员 19 / B 任务 19 / C 会议 19 / D 项目 18 / E 知识 19 / F 公式 18 / G 假设 18 / H 记忆 19 / K 横切 23 / M 多轮 19 / P 高级 9

## 10. 引用锚点
| 锚点 | 路径:行 |
|---|---|
| 7 维权重 | `tests/qa-bench/runner.py:429` |
| 1 票否决 | `tests/qa-bench/runner.py:464` |
| Baseline 文件 | `tests/qa-bench/data/regression_baseline_v3.0.json` |
| 5 道防线 | `tests/qa-bench/save_to_kb.py` (line 80-200) |
| Smart Filter | `tests/qa-bench/runner.py` (Round 9 commit `7e282f00`) |