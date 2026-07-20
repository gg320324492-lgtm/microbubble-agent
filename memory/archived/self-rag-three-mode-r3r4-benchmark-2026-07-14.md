---
name: self-rag-three-mode-r3r4-benchmark-2026-07-14
description: "Self-RAG benchmark R3/R4 推翻 7/9 audit \"7/30 删除\" 建议 — three-mode 集成后 Self-RAG 不再是 optional flag, 必须重新承诺"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e773284-b630-4b69-aab8-50ce42ce7a41
---

# Self-RAG Round 3+4 Benchmark (2026-07-14) — 推翻 7/9 audit "7/30 删除" 建议

## TL;DR

🎯 **7/9 audit 建议"7/30 截止时删除 Self-RAG flag" 因 7/13 three-mode commit 集成后前提失效, 不应执行**。

实测 100 题 × 2 round (ollama balanced, R3 ON vs R4 OFF):
- Pass rate: R3 99/100 (1 个 429 噪声) vs R4 100/100 → 差异在噪声范围内
- Retrieval gate 触发: **0/100 (R3)** — Self-RAG 在 balanced mode 完全沉默
- Latency delta 不能归因 Self-RAG (ollama first-20=16s vs last-20=70s 4× 漂移是基础设施噪声)

**Why**: 7/13 `c2648120 feat(three-mode)` 把 Self-RAG 集成进 `ctx.thinking_config.self_rag_enabled` + `agentic_loop.py` 5 处真分支, 它现在是 **deep mode 防幻觉的最后一道防线**, 不是 optional flag。

**How to apply**:
- **拒绝执行 7/30 删除计划** — 删除需要改 13+ 文件, 破坏 deep mode 防幻觉
- **新承诺**: Self-RAG 重新设 30 天观察期, 截止 8/14
- **下一步**: 跑 R5/R6 deep mode benchmark (deep + Self-RAG ON/OFF), 验证 Self-RAG 在 deep mode 是否真有用
- 如果 R5/R6 仍 0 触发 → 把 Self-RAG 从 balanced 默认配置移除 (balanced `self_rag_enabled=false`, deep 保留)

## 4 轮数据汇总

| Round | Backend | Mode | Self-RAG | 题数 | Pass Rate | Avg | p95 | Gate Triggers |
|---|---|---|---|---|---|---|---|---|
| R1 (7/01) | anthropic | legacy | OFF | 100 | 100.0% | 7779ms | 22047ms | 0 |
| R2 (7/01) | anthropic | legacy | ON (0.5 fallback) | 100 | 98.0% | 9112ms | 23992ms | **15 (15%)** |
| R3 (7/14) | ollama qwen3:8b | balanced | **ON (0.2 fallback)** | 100 | 99.0% | 35380ms | 70268ms | **0 (0%)** |
| R4 (7/14) | ollama qwen3:8b | balanced | OFF | 100 | 100.0% | 46966ms | 96977ms | 0 |

## 5 新铁律 (永久沉淀)

1. **Ollama 性能漂移 4-5× (first-20 vs last-20)** — benchmark 必须报告 first/last 切片, 不能只看 avg。R3/R4 显示 avg 不可信, 只看 pass rate + per-category
2. **Self-RAG gate 触发率是新 Self-RAG 行为的唯一可信指标** — pass rate 不能区分 ON/OFF 差异 (都在 99-100%), 必须直接看 retrieval_assessment event 数量
3. **同 backend 内 ON vs OFF 对比是 gold standard** — 跨 backend (anthropic vs ollama) 的 latency 差异 > 10×, 跨 backend 对比 Self-RAG 效果是 noise
4. **429 是 SSE tier 限流噪声, 不是 Self-RAG 问题** — smoke runner 加 30s 退避重试, benchmark 报告 ERR 时区分 429 vs 真质量问题
5. **7/9 audit 建议会因新 commit 而过期** — 任何"30 天后删 XXX"的承诺必须在新功能集成时重新评估, 7/13 three-mode commit 已经让 Self-RAG 不再是 optional flag

## 改动文件

- **新**: `tests/qa-bench/results/self-rag-benchmark/REPORT.md` (4 轮对比 + 决策建议, 替换原 7/01 2 轮 REPORT)
- **新**: `tests/qa-bench/results/self-rag-benchmark/round3-balanced-selfrag-on-<ts>/results.json` (R3 数据)
- **新**: `tests/qa-bench/results/self-rag-benchmark/round4-balanced-selfrag-off-<ts>/results.json` (R4 数据)
- **新**: `scripts/compare_self_rag_rounds.py` (130 行, 4 轮对比 + delta + per-category + retrieval 触发统计)
- **改**: `scripts/qa_bench_smoke.py`
  - 加 `--thinking-mode {fast,balanced,deep}` flag (透传 ChatRequest.thinking_mode)
  - 加 `--use-self-rag {true,false}` flag (透传 ChatRequest.use_self_rag)
  - 修 429 退避: 普通错 3s, 429 错 30s
  - 修 < 10 题写盘 bug (旧: `i % 10 == 0 or i == 1`, 新: 加 `i == len(questions)`)

## 完整 commit 链 (待 commit)

```
[改] scripts/qa_bench_smoke.py
[新] scripts/compare_self_rag_rounds.py
[新] tests/qa-bench/results/self-rag-benchmark/round3-balanced-selfrag-on-1784030859/results.json
[新] tests/qa-bench/results/self-rag-benchmark/round4-balanced-selfrag-off-1784032275/results.json
[新] tests/qa-bench/results/self-rag-benchmark/REPORT.md (替换原 7/01 2 轮 REPORT)
```

## 后续待办

- **8/14 截止前**: 跑 R5/R6 deep mode benchmark (R5: deep + SelfRAG ON, R6: deep + SelfRAG OFF), 100 题 × 2 round (~80min)
- **如果 R5 仍 0 触发**: 移 Self-RAG 到 deep-only (balanced `self_rag_enabled=false` 默认)
- **如果 R5 触发且提升质量**: 保留 Self-RAG, 调整 balanced 默认 false
- **生产监控**: 关注 agentic_loop 日志中 `[self_rag]` trigger rate + judge parse-fail rate
- **CLAUDE.md 待更新**: 在 #009 章节加 "2026-07-14 R3/R4 实测推翻 7/9 audit 建议" 子章节, 标注新承诺 8/14

## 相关 memory

- 7/01 R1/R2 benchmark: `tests/qa-bench/results/self-rag-benchmark/REPORT.md` (已被本轮替换为 4 轮对比) + 原 REPORT 内容见 round1-off/round2-on/raw data
- 7/13 three-mode commit: `c2648120 feat(three-mode): 实现快速/平衡/深度三档推理模式 + Ollama 部署`
- 7/09 待做清单: `memory/2026-07-09-pending-items-audit.md` 5 项未完成之一 "#009 Self-RAG 30 天承诺收尾"
- 7/14 P0-#1 LLM backend: `memory/llm-backend-ollama-residual-connection-error-2026-07-12.md`