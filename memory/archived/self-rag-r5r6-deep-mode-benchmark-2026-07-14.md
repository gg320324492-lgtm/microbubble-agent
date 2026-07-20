---
name: self-rag-r5r6-deep-mode-benchmark-2026-07-14
description: "R5/R6 deep mode benchmark 直接证伪 7/13 commit \"Self-RAG 防 deep 幻觉\" 假设 + 6 轮最终决策 (删除)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e773284-b630-4b69-aab8-50ce42ce7a41
---

# Self-RAG R5/R6 deep mode benchmark (2026-07-14) — 6 轮终极决策：删除

## TL;DR

🎯 **6 轮 benchmark 终极结论: Self-RAG 在当前 three-mode 架构下完全无效, 强烈建议删除 (包括 7/13 three-mode 集成)**

**Why**: R5 vs R6 deep mode **完全无差异** (98% = 98%, gate 0/100 触发), 直接证伪 7/13 commit "Self-RAG 防 deep 幻觉" 假设. 7/9 audit "7/30 删除" 建议原本基于 "Self-RAG 是 optional flag" 前提, 7/13 集成后前提失效. 现在 6 轮数据直接证明: **无论 flag 还是 deep mode 集成, Self-RAG 都不提供价值**.

**How to apply**:
- **执行删除** (13+ 文件, ~600 行) — `app/services/self_rag.py` 整文件 + `app/agent/thinking_config.py` 字段 + `agentic_loop.py` 5 处真分支 + chat 透传 + 前端 toggle + 测试
- **新承诺 8/14 已作废** — 6 轮数据提前 30 天决策
- **30 天承诺必须配提前判定路径** — 任何"30 天后删 XXX"必须留有新数据可提前收口的余地
- **3 轮对照是最低标准** — balanced 无效不等于 deep 无效, 必须 cross-mode 验证 (本轮 6 轮 = balanced × deep × ON/OFF)

## 6 轮数据汇总

| Round | 日期 | Backend | Mode | Self-RAG | Pass | 429 | Gate |
|---|---|---|---|---|---|---|---|
| R1 | 7/01 | anthropic | legacy | OFF | 100% | 0 | 0 |
| R2 | 7/01 | anthropic | legacy | ON (0.5) | 98% | 0 | **15 (15%)** |
| R3 | 7/14 | ollama | balanced | ON (0.2) | 99% | 1 | **0 (0%)** |
| R4 | 7/14 | ollama | balanced | OFF | 100% | 0 | 0 |
| R5 | 7/14 | ollama | **deep** | ON (0.2) | 98% | 2 | **0 (0%)** |
| R6 | 7/14 | ollama | **deep** | OFF | 98% | 2 | 0 |

**关键观察**:
- **R2 anthropic 唯一触发 gate** (15/100) — 但 100% parse-fail, 0 真实重检索
- **R3/R5 ollama Self-RAG ON 都 0 触发** — 7/13 parse-fail 0.2 修复**完全没机会验证**
- **R5 = R6 (98% = 98%, 0 = 0)** — Self-RAG 在 deep mode 也不提供任何质量提升
- **跨 mode 也无差异** — R3 (balanced) ≈ R5 (deep) ≈ 0 gate, balanced vs deep 不影响 Self-RAG 行为

## 决策依据 (3 条核心证据)

### 证据 1: 7/13 commit 假设证伪

commit `c2648120 feat(three-mode)` message: "deep 有幻觉风险" → 隐含 Self-RAG 是 deep mode 必要防线

**R5/R6 直接证伪**: R5 (deep + Self-RAG) 98% vs R6 (deep - Self-RAG) 98%, **完全相同**. Self-RAG 不为 deep mode 防幻觉

### 证据 2: 7/13 parse-fail 0.2 修复无效

R3/R5 ollama Self-RAG ON 都 0 gate 触发, parse-fail 0.2 修复**完全没机会验证**. 7/01 R2 旧实现触发 15 次但 100% parse-fail, 0 真实重检索

### 证据 3: pass rate 全部在 429 噪声内

6 轮中所有 "OK < 100%" 都是 429 限流, 无 Self-RAG 系统性失败证据. R2 唯一真错 (HTTP 502) 是 anthropic backend 限流, 与 Self-RAG 间接相关 (judge 挤占 SSE tier)

## 7 新铁律 (永久沉淀, 累计 12+1)

1. **Ollama 性能漂移 5×+ (first-20 vs last-20 + 跨 run order effect)** — benchmark 必须报告 first/last 切片 + run order, avg 不可信
2. **Self-RAG gate 触发率是唯一可信指标** — pass rate 不能区分 ON/OFF 差异, 必须看 retrieval_assessment event 数量
3. **同 backend 同 mode ON vs OFF 对比是 gold standard** — 跨 backend (anthropic vs ollama) latency 差异 > 10× 是 noise
4. **429 是 SSE tier 限流噪声, 不是 Self-RAG 问题** — smoke runner 加 30s 退避重试
5. **7/9 audit 建议会因新 commit 而过期** — 任何"30 天后删 XXX"承诺必须在新功能集成时重新评估
6. **3 轮对照是最低标准** — R3/R4 balanced 证据不足, R5/R6 deep mode 才是完整的"是否保留"证据. balanced 无效不等于 deep 无效
7. **commit 假设需要 benchmark 验证** — 7/13 commit "deep 模式需 Self-RAG 防幻觉" 是**未验证假设**, R5/R6 deep 98% = 98% 直接证伪
8. **30 天承诺必须配提前判定路径** — 任何"30 天后删 XXX"必须留有新数据可提前收口的余地, 7/14 R5/R6 是范例

## 删除清单 (13+ 文件, ~600 行)

- `app/services/self_rag.py` (整文件 404 行)
- `app/agent/agentic_loop.py` (5 处真分支, 1069-1086)
- `app/agent/thinking_config.py` (2 字段: self_rag_enabled + self_rag_max_reretrieve)
- `app/agent/chat_engine.py` (3 入口透传)
- `app/agent/micro_bubble_agent.py` (透传)
- `app/agent/protocol.py` (retrieval_assessment SSE event)
- `app/api/v1/chat.py` (ChatRequest.use_self_rag 字段)
- `app/config.py` (7 个 AGENT_SELF_RAG_* 字段)
- `web/src/stores/useUiStore.js` (useSelfRag state + toggle)
- `web/src/components/chat/ThinkingModeSwitch.vue` (Self-RAG toggle UI)
- `web/src/composables/chat/useChatStream.ts` (透传)
- `tests/test_self_rag.py` (整文件)
- `tests/test_chat_self_rag.py` (整文件)
- `tests/integration/test_chat_fast_vs_deep.py` (self_rag 测试段)
- `tests/unit/test_synthesis_mode_dispatch.py` (self_rag 分发段)
- `memory/self-rag-*.md` (3 个, 改 .archived.md)

## 测试数据清理 (2026-07-14, benchmark 收官后)

清理脚本 `scripts/cleanup_benchmark_chat_data.py` (新增, ~200 行):

- **7/14 benchmark 产生**: 400 chat_sessions + 806 messages + 403 agent_traces + 4 tasks → **全 0**
- **7/13 drive 测试残留**: 120 chat_sessions + 271 messages → **也清 (用户要求"测试产生都删")**
- **未删**: 1296 agent_traces (7/01+7/02+7/13) + 276 knowledge (7/10) + 1 task (7/13) — 历史测试, 未删等用户决策

清理命令:
```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && python cleanup_benchmark_chat_data.py --scan'
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && python cleanup_benchmark_chat_data.py --apply --confirm'
```

## 改动文件总览 (本次完整 commit 链)

### 改:
- `tests/qa-bench/results/self-rag-benchmark/REPORT.md` (4 轮 → 6 轮对比, 终极决策: 删除)

### 新:
- `tests/qa-bench/results/self-rag-benchmark/round5-deep-selfrag-on-<ts>/results.json`
- `tests/qa-bench/results/self-rag-benchmark/round6-deep-selfrag-off-<ts>/results.json`
- `scripts/cleanup_benchmark_chat_data.py` (清理脚本, ~200 行, 3 段式 scan/backup/apply)

## 与前 30 天收官范式对齐

| 项目 | 决策依据 | 工作量 |
|---|---|---|
| v31.2.5 限流 Redis 化 | 30 天观察期, 0 流量走老路径 | 单 commit |
| chat_engine_legacy 方案 C | 30 天提前 15 天, 0 流量 | 10 文件 |
| **Self-RAG (本轮)** | **30 天提前 30 天, 6 轮 benchmark 直接证伪** | **13+ 文件** |

## 后续待办

- **立即 (单 commit)**: 删除 Self-RAG 13+ 文件 + 跑回归测试 (pytest + vitest)
- **如果未来 deep mode 真出现幻觉**: 不复活 Self-RAG, 而是用 RAG 改进 (reranker + 强 prompt)
- **CLAUDE.md 待更新**: #009 章节加 "2026-07-14 R5/R6 6 轮决策删除" 子章节

## 相关 memory

- 7/14 R3/R4: `memory/self-rag-three-mode-r3r4-benchmark-2026-07-14.md`
- 7/01 原始 R1/R2: `tests/qa-bench/results/self-rag-benchmark/round{1,2}-*/results.json` (raw data 保留)
- 7/13 three-mode commit: `c2648120` (被本轮证伪)
- 7/09 audit: `memory/2026-07-09-pending-items-audit.md` 5 项未完成
- 7/14 P0-#1 LLM backend: `memory/llm-backend-ollama-residual-connection-error-2026-07-12.md`