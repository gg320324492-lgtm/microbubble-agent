# qa-bench baseline 对比 (D4 700 题 → D5 1000 题)

## 概览
- D4 700 题: 跑于 commit df75acd38 之前的 baseline
- D5 1000 题: 跑于 commit df75acd38 之后 (含 D4 题库 + 300 新题, 待主指挥手动跑)

## 题库扩展 (D4 → D5)
- D4: 700 题 (涵盖既有业务域类别)
- D5: 1000 题 (+ 300 新题, 涵盖扩展业务域类别)
- 题库文件: tests/qa-bench/questions_d4_categories.json + tests/qa-bench/questions_d4_extra_300.jsonl

## 预期影响
- pass rate: 持平或略降 (新题可能更难, ≥80% CI 门禁仍有效)
- 6 维评分: 持平或略波动
- avg_latency_ms: 持平 (题量增加不影响单题延迟)
- total_tokens: 增长 ~43% (700 → 1000)
- total_cost_usd: 增长 ~43%

## 数据填入
(主指挥跑完后填入真实数据)
