# QA-Bench 7-Dimension Scoring

> W68 第 10 批 B-1 / W69 派工子项 ② — 7 维评分算法. 仅 `tests/qa-bench/scoring/` + `tests/qa-bench/phase{2,3}_*.py` + docs + memory 改动. **0 production code 改动铁律维持**.

## 摘要

qa-bench v3.0 (W66 起) 一直用单一 pass rate (consensus pass / 总数) 作为门禁指标. W68 D6 后续 (W69 第 1 批派工) 引入 **7 维评分** 替代单点 pass rate, 把 pass rate 拆解为 7 个互补维度, 帮助定位模型失败根因 (答错 / 答不全 / 答不准 / 重复性 / 信息熵 / 时延), 不再被单维度均化掩盖. 7 维输出可直接喂给 D6 CI gate 作为门禁, 也可作为 D1 LLM config + D3 retrieval cache + D6 gate 的综合评判依据.

## 7 维算法公式

| 维度 | 公式 | 范围 | 含义 |
|---|---|---|---|
| 1. **Accuracy 准确率** | `hits / total` | [0, 1] | 答对轮次占总轮次比例 |
| 2. **Recall 召回率** | `hits / ground_truth_positive` | [0, 1] | 答对轮次占应有轮次比例 (是否有未答的) |
| 3. **Precision 精确率** | `hits / answered` | [0, 1] | 答出 (pass+fail) 轮次中真答对的比例 (是否乱猜) |
| 4. **F1** | `2*P*R / (P+R)` | [0, 1] | P/R 调和均值 (综合指标) |
| 5. **Consistency 一致性** | `mean(majority_share)` per question | [0, 1] | 多 rounds 答案一致程度 (1=完全一致, 1/rounds=完全分散) |
| 6. **Entropy 信息熵** | `mean(Σ -p log p)` per question | [0, log N] | 答案分布的不确定性. 同时输出 `entropy_normalized = entropy / log(max_rounds)` 归一化到 [0, 1] |
| 7. **Latency 时延** | `avg / p50 / p95 / p99` per round | ms | 单轮 wall-clock, 含 linear-interpolated percentile |

**answered verdict** 集合 = `{pass, fail}` (模型明确回答). **declined verdict** 集合 = `{empty, error, skipped}` (模型未回答). `unknown` 计入总数但不参与命中率.

### 衍生指标

- **confidence_high / confidence_low**: 每题 v2 consensus 的 confidence 计数. confidence = `1 - entropy / max_entropy`, >= 0.5 视为高 confidence (answered), < 0.5 视为低 confidence (declined).
- **per_intent slice**: 按 business intent 拆解 (knowledge / task / meeting / member / project / drive) + chat intent (explain_concept / data / deep / action / search_info / casual). 每 intent 一份 4 维 (accuracy / recall / precision / F1) + avg_latency_ms.

## 阈值建议 (W69 派工拍板指南)

| 维度 | 警告阈值 | 失败阈值 | 备注 |
|---|---|---|---|
| accuracy | < 0.85 | < 0.75 | W66 v3.0 baseline 0.78, W67 round 9 0.94 |
| recall | < 0.80 | < 0.70 | recall 低 = 模型不答 (empty 多) |
| precision | < 0.85 | < 0.75 | precision 低 = 模型乱猜 (fail 多但 positive) |
| F1 | < 0.82 | < 0.72 | 综合维度 |
| consistency | < 0.80 | < 0.65 | consistency 低 = 模型不确定, 多 rounds 答案漂移 |
| entropy_normalized | > 0.50 | > 0.70 | entropy 高 = 模型行为发散 |
| latency p99 | > 5 s | > 10 s | 与 W68 D3 retrieval cache 联调 |

**D6 CI gate 复合判定**: 任意 1 维失败即 FAIL (防止单维度掩盖). 警告阈值会写入 `extra_notes` 但不阻塞 promote.

## 与已有 D1/D3/D6 集成

### D1 LLM config (`tests/qa-bench/llm_config.py` 等)

LLM config 切换模型 (mimo-v2.5 / qwen3:8b / future) 时, 7 维评分会在 `per_intent` 表里呈现各 intent 在不同模型下的差异, 帮助 LLM 选型 (W67 Round 8-9 实证: BGE m3 + openai_compat 提升 pass rate 0.935 → recall 不变 → precision 提升 → F1 上升).

### D3 retrieval cache (`tests/qa-bench/retrieval_cache.py`)

Retrieval cache 命中 / 未命中会直接影响 latency (cache hit 缩短 P50/P95) + accuracy (cache 内容稳定 → F1 稳定). 7 维输出按 cell 拆分 (`mimo/mimo-v2.5/hit/r3` vs `miss`) 便于 W68 D6 matrix 跑 A/B.

### D6 CI gate (`.github/workflows/qa-bench-ci.yml`)

W67 D5 gate 当前用 pass rate 单一门禁. W69 第 1 批规划: D6 gate 升级为 **复合门禁** — 读 `7d_score.json` 校验 7 维全部 >= 失败阈值才 PASS. CI step summary 会按 7 维拆解报告, 而不是单一 pass rate 数字.

## 部署必做 (W68 D6 / W69 第 1 批)

```bash
# 1. 跑测试
SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/scoring/ -v

# 2. dry-run 端到端 (无 LLM 也能跑)
python tests/qa-bench/phase2_dry_runner.py --dry-run --scoring 7d \
    --report-out /tmp/phase2_test.md
python tests/qa-bench/phase3_matrix_runner.py --dry-run --max-questions 50 \
    --scoring 7d --report-out /tmp/phase3_test.md

# 3. CLI 评分 (输入 JSONL, 输出 JSON)
python -m tests.qa-bench.scoring.seven_d_scoring \
    --input results.jsonl \
    --output 7d_score.json \
    --print
```

**输入 JSONL 格式** (`VerdictRecord` 一行一条):
```json
{"question_id": "Q-001", "verdict": "pass", "ground_truth_positive": true, "latency_ms": 1234.5, "intent": "data"}
{"question_id": "Q-001", "verdict": "pass", "ground_truth_positive": true, "latency_ms": 1180.0, "intent": "data"}
{"question_id": "Q-001", "verdict": "fail", "ground_truth_positive": true, "latency_ms": 1310.2, "intent": "data"}
```

**输出 JSON 结构** (与 phase2 report 同 schema):
```json
{
  "total_questions": 1000, "total_rounds": 3000,
  "accuracy": 0.8732, "recall": 0.8732, "precision": 0.9521, "f1": 0.9110,
  "consistency": 0.9133, "entropy": 0.4123, "entropy_max": 1.0986, "entropy_normalized": 0.3752,
  "latency": {"count": 3000, "avg_ms": 1832.4, "p50_ms": 1612.0, "p95_ms": 3210.5, "p99_ms": 4521.3, "max_ms": 6789.1},
  "per_intent": {...},
  "verdict_counts": {"pass": 2620, "fail": 130, "empty": 100, "error": 50, "unknown": 100},
  "confidence_high": 870, "confidence_low": 130
}
```

## 不动 production code 铁律

W68 D6 / W69 第 1 批 B-1 仅改:
- 新增: `tests/qa-bench/scoring/seven_d_scoring.py` (≈ 350 行)
- 新增: `tests/qa-bench/scoring/verdict_consensus_v2.py` (≈ 130 行)
- 新增: `tests/qa-bench/scoring/test_seven_d_scoring.py` (≈ 300 行, 11 test)
- 修改: `tests/qa-bench/phase2_dry_runner.py` (加 `--scoring 7d` flag + 7d overlay)
- 新增: `tests/qa-bench/phase3_matrix_runner.py` (≈ 600 行, 矩阵 driver + 同 `--scoring 7d`)

**绝对不修改**:
- `app/` (FastAPI 后端)
- `web/` (Vue 前端)
- `alembic/versions/` (任何 DB 迁移)
- `docker-compose*.yml` / `Dockerfile` (任何运行时)

派工时严格审查 diff, 任何 `app/` `web/` `alembic/` `docker*` 改动立即拒绝 (W68 0 production code 改动铁律第 12 批守恒).

## 实施检查表

- [x] `tests/qa-bench/scoring/seven_d_scoring.py` 落地
- [x] `tests/qa-bench/scoring/verdict_consensus_v2.py` 落地
- [x] `tests/qa-bench/scoring/test_seven_d_scoring.py` 11 场景全 PASS
- [x] `tests/qa-bench/phase2_dry_runner.py --scoring 7d` flag 落地
- [x] `tests/qa-bench/phase3_matrix_runner.py` 落地 + `--scoring 7d` 联动
- [x] 端到端 dry-run 测试通过 (phase2 + phase3 各输出 7d_score.json)
- [x] `python -m tests.qa-bench.scoring.seven_d_scoring` CLI 验证
- [x] 0 production code 改动铁律完全维持 (仅 tests/ + docs/ + memory/)
- [x] 5 新铁律沉淀 (见 memory/w68-route-10-b1-qa-bench-7d-scoring-2026-07-24.md)

## 关联文档

- [qa-bench-d5-future-roots.md](./qa-bench-d5-future-roots.md) — D5 5 路径调研 (W68 第 2 批)
- [qa-bench-d6-implementation-roadmap.md](./qa-bench-d6-implementation-roadmap.md) — D6 2000 题路线图
- [qa-bench-inprocess-runner-design.md](./qa-bench-inprocess-runner-design.md) — in-process runner 设计
- [qa-bench-isolation-stack.md](./qa-bench-isolation-stack.md) — test DB + Redis stack
- [qa-bench-ghcr-cache-design.md](./qa-bench-ghcr-cache-design.md) — GHCR cache hit 优化
- `memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md` — 调研汇总 + 锚点范式第 30 守恒
- `memory/w68-route-10-b1-qa-bench-7d-scoring-2026-07-24.md` — 7D 实施沉淀 + 5 新铁律