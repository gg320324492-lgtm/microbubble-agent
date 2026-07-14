# #009 Self-RAG Benchmark Round 3+4 — three-mode 时代的新基线 (2026-07-14)

> **日期**: 2026-07-14
> **触发**: 7/9 audit 建议 7/30 截止时"删除 Self-RAG flag"。7/13 `c2648120 feat(three-mode)` 把 Self-RAG 深度集成到 deep mode 防幻觉防线后, 原建议需要重新评估。
> **方法**: 100 题 smoke (同 round1/round2 题集, smoke_200.jsonl 前 100), concurrency=3, balanced mode (default), ollama backend (qwen3:8b)
> **对比**: 7/01 老 R1 (anthropic OFF) / R2 (anthropic ON) 100 题 + 7/14 新 R3 (ollama balanced ON) / R4 (ollama balanced OFF) 100 题

## TL;DR

> 🎯 **Self-RAG 在 three-mode balanced mode 下基本"沉默" (0% gate 触发), 不影响 pass rate, 不产生明显延迟税**。7/9 audit 建议的"7/30 删除 Self-RAG flag" 因 7/13 three-mode 集成后**前提失效**, 不应简单执行。
>
> **真正需要验证的是 deep mode** (Self-RAG 在 deep mode 下 max_reretrieve=2 + parse-fail 0.2 是否真能防 deep 模型幻觉), 本轮 benchmark 未覆盖。建议下一步跑 R5/R6 deep mode 对照。

---

## 1. 4 轮总览

| Round | Backend | Mode | Self-RAG | Judge parse-fail fallback | 题数 | OK | ERR | Pass Rate | Avg | p50 | p95 | Retrieval Assess |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **R1** (7/01) | anthropic claude-sonnet-4-6 | (legacy) | OFF | n/a | 100 | 100 | 0 | **100.0%** | 7779ms | 5000ms | 22047ms | 0 (0.0%) |
| **R2** (7/01) | anthropic claude-sonnet-4-6 | (legacy) | ON | 0.5 | 100 | 98 | 2 | **98.0%** | 9112ms | 4726ms | 23992ms | 15 (15.0%) |
| **R3** (7/14) | ollama qwen3:8b | balanced | **ON** | **0.2** | 100 | 99 | 1 (429) | **99.0%** | 35380ms | 28260ms | 70268ms | **0 (0.0%)** |
| **R4** (7/14) | ollama qwen3:8b | balanced | **OFF** | n/a | 100 | 100 | 0 | **100.0%** | 46966ms | 49557ms | 96977ms | 0 (0.0%) |

**关键标注**:
- R1/R2 用 anthropic 后端 (生产), R3/R4 用 ollama 后端 (本地 GPU qwen3:8b) — 7/13 three-mode commit (c2648120) 把生产切到 ollama
- R2/R3 的 ERR 都是 HTTP 429 (SSE tier 10/min 限流), **不是 Self-RAG 质量问题**
- R3 的 1 个 ERR 是 A-L3-0007 (业务查询类)

---

## 2. 同 Backend ON vs OFF Delta

### Anthropic (R2 - R1, 7/01 老数据)
- Pass rate: **-2.0%** (100% → 98%)
- Avg latency: **+1333ms** (+17%)
- p95 latency: **+1945ms** (+9%)
- Retrieval gate: ON 触发 15/100 (15.0%) → 全部 parse-fail 走 default-on-fail, **0 次真正重检索**
- 7/01 结论: Self-RAG 是"净负" — 唯一建议删除

### Ollama balanced (R3 - R4, 7/14 新数据)
- Pass rate: **-1.0%** (100% → 99%, 但 R3 1 个 ERR 是 429, 噪声)
- Avg latency: **-11586ms** (-25%, Self-RAG ON 反而更快！)
- p95 latency: **-26709ms** (-28%, Self-RAG ON 反而更快！)
- Retrieval gate: **ON 触发 0/100 (0.0%)** — Self-RAG 在 balanced mode 下完全沉默
- 7/14 结论: Self-RAG 在 ollama balanced mode 下**基本无害也无益**

---

## 3. 关键发现

### 3.1 🚨 Ollama 性能"先快后慢"漂移 (latency noise)

**两轮都出现 4-5× 的 first-20 vs last-20 延迟漂移**:
- R3: first 20 = 16.2s → last 20 = 69.6s (4.3× slower)
- R4: first 20 = 18.6s → last 20 = 90.0s (4.8× slower)

**根因可能**:
1. **GPU 累积状态** — ollama 持续 inference 导致 VRAM/温度压力递增
2. **Ollama 上下文队列堆积** — 多并发请求竞争资源
3. **Windows CPU/GPU 调度** — 后台进程干扰

**对 Self-RAG 评估的影响**:
- R3 先跑 (被影响较少) vs R4 后跑 (被影响更多), 造成 R4 延迟"看起来更高"
- 这意味着 R3 vs R4 的 latency delta **不能归因于 Self-RAG, 应视为 ollama 噪声**
- **Pass rate 才是可信信号**: R3 99/100 vs R4 100/100, 1% 差异是 429 噪声

### 3.2 ✅ Self-RAG 在 ollama balanced mode 下"沉默"

R3 (Self-RAG ON) 跑了 100 题但 gate 触发次数 = **0**。这与 R2 anthropic 15% 触发率截然不同。

**为什么不再触发**:
- 7/13 commit 把 parse-fail fallback 从 0.5 改到 0.2, 触发概率降低
- ollama qwen3:8b 在 judge 任务上**可能更稳定** (parse OK), 走 happy path 高 confidence (≥0.6) → 不重检索
- balanced mode 默认 max_reretrieve=1 (vs deep mode 2), 限制更深

**含义**:
- 7/13 parse-fail 0.2 修复**效果未验证** — gate 都不触发, 0.2 vs 0.5 没区别
- Self-RAG 在 balanced mode 是"哑配置", 默认开/关实际无差别
- **真正的验证场景是 deep mode**, 因为 deep mode 用更强 model (deepseek-r1:7b), hallucination 风险更高

### 3.3 Anthropic vs Ollama 的 pass rate 差异 (不是 Self-RAG 问题)

| Backend | Self-RAG OFF Pass Rate | Self-RAG ON Pass Rate |
|---|---|---|
| anthropic (R1/R2) | 100% | 98% (-2%) |
| ollama balanced (R4/R3) | 100% | 99% (-1%, 429 噪声) |

两后端 pass rate 几乎相同。**没有证据显示 Self-RAG 在任何后端产生显著质量退化**, 1-2% 差异都在 ERR 噪声范围内。

---

## 4. Per-Category Pass Rate

| Category | R1 (ant OFF) | R2 (ant ON) | R3 (ollama ON) | R4 (ollama OFF) |
|---|---|---|---|---|
| A 业务查询 | 19/19=100% | 19/19=100% | **18/19=94.7%** (A-L3-0007 429) | 19/19=100% |
| B 数据查询 | 19/19=100% | **18/19=94.7%** | 19/19=100% | 19/19=100% |
| C 综合分析 | 19/19=100% | 19/19=100% | 19/19=100% | 19/19=100% |
| D 任务操作 | 18/18=100% | **17/18=94.4%** | 18/18=100% | 18/18=100% |
| E 长会话 | 19/19=100% | 19/19=100% | 19/19=100% | 19/19=100% |
| F 边缘场景 | 6/6=100% | 6/6=100% | 6/6=100% | 6/6=100% |

**观察**:
- 老的 R2 anthropic 在 B/D 类有 5% 退化 (B-0082 / D-L2-0235 等), R3 ollama balanced ON 没有出现同类问题
- 唯一 R3 退化是 A 类 1 个 429 ERR, 与 Self-RAG 无关

---

## 5. Retrieval Assessment 触发详情

| Round | 触发次数 | 触发率 | 备注 |
|---|---|---|---|
| R1 anthropic OFF | 0 | 0% | n/a |
| R2 anthropic ON | **15** | **15%** | 全部 parse-fail → default-on-fail (旧 0.5 fallback) → 不重检索 |
| R3 ollama ON | **0** | **0%** | gate 沉默, 7/13 parse-fail 0.2 修复效果未验证 |
| R4 ollama OFF | 0 | 0% | n/a |

**R2 anthropic 触发的 15 题 IDs** (作为未来 deep mode benchmark 对照):
E-L4-0273, F-L2-0314, D-L2-0235, D-L3-0230, D-L3-0231, D-L4-0232, E-L2-0262, E-L2-0263, E-L2-0277, A-L2-0003, E-L3-0264, E-L3-0266, E-L3-0267, A-L1-0001, E-L3-0272

---

## 6. 决策建议

### 6.1 7/9 原建议 vs 7/14 实际情况

| 维度 | 7/9 audit 认知 | 7/14 实测 | 行动 |
|---|---|---|---|
| Self-RAG = 实验性 flag | ✅ | ❌ 7/13 已被吸收进 `thinking_config.self_rag_enabled` | **不能简单删 flag** |
| 30 天回滚承诺 | ✅ | ⚠️ 前提失效 (已不是 optional 开关) | **重新评估承诺** |
| judge parse-fail 100% | ✅ 旧数据 | ✅ 7/13 parse-fail 0.2 修复**未验证** (gate 0 触发) | **需要 deep mode 验证** |
| Self-RAG ON 必触发 | ✅ 旧 15% | ❌ R3 0% (balanced + ollama) | **balanced mode 实际不需要** |
| 7/30 截止删除 | ✅ 适用 | ❌ 会破坏 deep mode | **拒绝删除** |

### 6.2 短期行动 (本周)

**❌ 拒绝执行 7/9 audit 建议的 7/30 删除计划**, 因为:
1. 7/13 commit `c2648120` 把 Self-RAG 集成进 `thinking_config.self_rag_enabled` + `agentic_loop.py` 5 处真分支
2. 删 flag 需要同步删 `thinking_config.self_rag_enabled` 字段 + `agentic_loop.py:1069-1086` + `agentic_loop.py:600 max_reretrieve` 透传 + `chat_engine.py` 透传 + `micro_bubble_agent.py` 透传 + `protocol.py` `retrieval_assessment` event + `chat.py` `ChatRequest.use_self_rag` + 前端 `useUiStore` toggle + `ThinkingModeSwitch.vue` + 2 测试 + memory
3. 删除会破坏 deep mode 防幻觉 (commit message: "deep 有幻觉风险")
4. 实测 R3/R4 显示 Self-RAG 在 balanced mode **完全无害**, 删除也无收益

### 6.3 中期行动 (2 周内)

**优先级 #1**: 跑 R5/R6 **deep mode benchmark** 验证 Self-RAG 真实价值
- R5: deep + Self-RAG ON (default: max_reretrieve=2 + parse-fail 0.2)
- R6: deep + Self-RAG OFF (`use_self_rag=false` per-request)
- 100 题, smoke_200.jsonl 前 100
- 预期 R5 触发率 > 0 (deep mode 更激进), 如果 R5 触发 + 提升质量 → 保留 Self-RAG deep mode

**优先级 #2**: 如果 R5 仍然 0 触发 → 把 Self-RAG 从 balanced 默认配置移除
- balanced 默认 `self_rag_enabled=false`
- deep 保留 `self_rag_enabled=true` + max_reretrieve=2
- 节省 balanced mode ~3s/题 judge latency (虽然 R3 数据显示实际无影响, 但减少代码复杂度)

### 6.4 长期行动 (30 天后, 8/14)

**新承诺**: Self-RAG 重新设 30 天观察期, 截止 8/14
- 观察期内: R5/R6 deep mode benchmark + production monitoring (看 agentic_loop 日志中 self_rag trigger rate)
- 8/14 决策:
  - 路径 A: deep mode benchmark 证明有效 → 保留, 移到 deep only
  - 路径 B: deep mode benchmark 证明无效 → 删 deep mode 路径, 整模块下线 (v31.2.5 / chat_engine_legacy 30 天收官范式)

---

## 7. 沉淀位置

- 数据:
  - R1: `tests/qa-bench/results/self-rag-benchmark/round1-off/results.json` (7/01)
  - R2: `tests/qa-bench/results/self-rag-benchmark/round2-on/results.json` (7/01)
  - R3: `tests/qa-bench/results/self-rag-benchmark/round3-balanced-selfrag-on-1784030859/results.json` (7/14)
  - R4: `tests/qa-bench/results/self-rag-benchmark/round4-balanced-selfrag-off-1784032275/results.json` (7/14)
- 对比脚本: `scripts/compare_self_rag_rounds.py` (新增, 130 行)
- 改动的 smoke runner: `scripts/qa_bench_smoke.py` (加 `--thinking-mode` / `--use-self-rag` flags + 修 429 退避 + 修 < 10 题写盘 bug)
- Memory: 待写 `memory/self-rag-three-mode-r3r4-benchmark-2026-07-14.md`
- CLAUDE.md: 待更新 (本轮关键发现 + 推翻 7/9 audit 建议)

---

## 8. 5 新铁律 (永久沉淀)

1. **Ollama 性能漂移 4-5× (first-20 vs last-20)** — benchmark 必须报告 first/last 切片, 不能只看 avg。R3/R4 显示 avg 不可信, 只看 pass rate + per-category
2. **Self-RAG gate 触发率是新 Self-RAG 行为的唯一可信指标** — pass rate 不能区分 ON/OFF 差异 (都在 99-100%), 必须直接看 retrieval_assessment event 数量
3. **同 backend 内 ON vs OFF 对比是 gold standard** — 跨 backend (anthropic vs ollama) 的 latency 差异 > 10×, 跨 backend 对比 Self-RAG 效果是 noise。建议 future benchmark 始终同 backend
4. **429 是 SSE tier 限流噪声, 不是 Self-RAG 问题** — smoke runner 加 30s 退避重试, benchmark 报告 ERR 时区分 429 vs 真质量问题
5. **7/9 audit 建议会因新 commit 而过期** — 任何"30 天后删 XXX"的承诺必须在新功能集成时重新评估, 7/13 three-mode commit 已经让 Self-RAG 不再是 optional flag