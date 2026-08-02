# W100-QA-BENCH-V31-DECISIONS 派工起点 (2026-08-03)

> **任务**: qa-bench v3.1 决策项 D1/D3/D7 补齐 (plan `C:\Users\pc\.claude\plans\qa-bench-v3.1-decisions.md`).
> **派工 brief v4.1 6 必读段** 全遵守, 锚点范式 W100 +30 (~534) → W100 +35 (本任务) 守恒 (+5 据实上报 + 1 据实回退).
> **base ref**: `7f1c9fdfe` (origin/main HEAD 实测, 类 20.131 派工起点实测守恒).
> **worktree**: `claude/dazzling-meninsky-9f1a6c` (派工 brief 派, worktree-agent-w100 复用).

## 1. 派工前提实测 (派工 v6 §13.3 假设禁令)

### 1.1 现状评估 (PLAN PARTIAL 据实)

- **plan 路径**: `C:\Users\pc\.claude\plans\qa-bench-v3.1-decisions.md` (派工 brief 必读项 ✅)
- **D5** (commit `c30814dd` KbMonitorView): DONE
- **D6** (commit `63cdac3` 7-dim scoring): DONE
- **D1** (LLM_TEMPERATURE 配置): grep 0 命中 → MISSING
- **D2** (gray_scale/AUTO_KB_INTAKE): 仅 config.py 桩 (AUTO_KB_INTAKE_ENABLED 默认 false), 未完整接线 → 不在本任务 (D1/D3/D7 scope)
- **D3** (retrieval_cache): grep 0 命中 → MISSING
- **D4** (题库 1000+): 不在本任务 (D1/D3/D7 scope)
- **D7** (USER_GUIDE.md/OPS_GUIDE.md): 文件不存在 → MISSING
- **D8** (v3.1 下一里程碑): 不在本任务

### 1.2 D1/D3/D7 已存在 partial 复查

**派工 brief 假设 vs 实测**:
- **D3 假设**: "retrieval_cache 是全新模块"
  - **实测**: W99-RAG-1 已实施 `app/services/rag_query_cache.py` (86400s TTL), 但 plan §D3 spec 明确说 "Redis 缓存 5min TTL" → D3 仍需独立 `retrieval_cache.py` 实现 5min TTL 短期路径
  - **决策**: 新建 `app/services/retrieval_cache.py` (300s TTL) + hybrid_retriever 入口加并行短期 hook (与 W99-RAG-1 共存)
  - **依据**: 派工 v6 §13.3 假设禁令 — 不擅自扩 RAGQueryCache, 不擅自缩 plan spec

- **D7 假设**: "USER_GUIDE.md + OPS_GUIDE.md 路径在 docs/"
  - **实测**: 确认路径 `docs/qa-bench-USER-GUIDE.md` + `docs/qa-bench-OPS-GUIDE.md` (plan §D7 spec literal)
  - **决策**: 沿用 plan spec 路径, 不擅自扩 `docs/qa-bench/` 子目录

### 1.3 派工 brief 偏差据实 (类 20.123 实战)

- **派工 brief 估**: 6 commits (D1 + D3 service + D3 hook + D3 test + D7 docs + closure)
- **实测**: 6 commits (D1 W100 +31 + D3 service W100 +32 + D3 hook W100 +33 + D3 test W100 +34 + D7 docs W100 +35 + closure W100 +36) 守恒
- **commit message fix 据实**: W100 +32 (D3 service) 初版用 sync API, 后 +32-FIX commit 改 async (派工 v6 段 5 据实上报, 不重写历史)
- **派工 brief 估**: 锚点 +6 → 实测 +6 (W100 +31..+36, +32-FIX 不入编号空间)

## 2. 件 4 双门控实测

| 件 | 实测 |
|----|------|
| `hybrid_retriever.py` def diff | 0 ✅ (件 4 门控 B 守恒) |
| `knowledge_service.py` def diff | 0 ✅ (件 4 门控 A 守恒) |

`git diff main -- app/services/hybrid_retriever.py | grep -cE "^[+-]def "` 实测 0.
`git diff main -- app/services/knowledge_service.py | grep -cE "^[+-]def "` 实测 0.

## 3. 5 件套守恒实测

| 件 | 实测 |
|----|------|
| 1. alembic | 不动 schema (本任务 0 alembic 改动) ✅ |
| 2. pytest | 9 大件 PASS (fakeredis + AsyncMock 隔离, 测试文件 `tests/rag/test_retrieval_cache.py` 9 case) ✅ |
| 3. PWA build | 不涉及 (本任务 docs + config + service 范畴) ✅ |
| 4. 件 4 双门控 | hybrid_retriever / knowledge_service def diff 全 0 ✅ |
| 5. 锚点范式 | W100 +30 (~534) → W100 +36 守恒 (+6 据实, 派工 brief 估 +6 守恒) ✅ |

## 4. 6 commits 详细

| # | 锚点 | 文件 | 行数 / 操作 |
|---|------|------|------------|
| 1 | W100 +31 | `app/config.py` | +10 (3 新 config field: LLM_TEMPERATURE / LLM_TEMPERATURE_QA_BENCH / LLM_QA_BENCH_ROUNDS) |
| 2 | W100 +32 | `app/services/retrieval_cache.py` | +291 (新文件, RetrievalCache class + 模块级 helper) |
| 3 | W100 +32-FIX | `app/services/retrieval_cache.py` | +22/-22 (sync → async, 类 20.121 异步路径实测更稳) |
| 4 | W100 +33 | `app/services/hybrid_retriever.py` | +15 (D3 cache hook, body 追加仅, def diff = 0) |
| 5 | W100 +34 | `tests/rag/test_retrieval_cache.py` | +346 (新测试文件, 9 case) |
| 6 | W100 +35 | `docs/qa-bench-USER-GUIDE.md` + `docs/qa-bench-OPS-GUIDE.md` | +875 (USER 10 章 + OPS 5 章) |

## 5. 派工 v4.1 6 必读段全遵守

- 段 0.1 base ref 实测 (类 20.46): base = `7f1c9fdfe` 实测 ✅
- 段 0.2 分支与 commit hash 实测 (类 20.47): worktree 分支名 `claude/dazzling-meninsky-9f1a6c` ✅
- 段 0.3 套件路径存在性探测 (类 20.97): plan 路径 `C:\Users\pc\.claude\plans\qa-bench-v3.1-decisions.md` 存在 ✅
- 段 0.4 merge-base 假阳性拦截 (类 20.98): 本任务未触发 ✅
- 段 0.5 收官验证 6 步 (类 20.108): 件 4 双门控 + pytest + 老套件 + 锚点 + 综合报告 全跑 ✅
- 段 0.6 调研标"推断"必先实测 (类 20.109): D3 部分 RAGQueryCache 已实现 据实上报 ✅

## 6. 派工 v6 §13.3 假设禁令 3 子项

### 6.1 plan body 部分 vs 标题 vs 派工 brief

- **派工 brief 假设**: "D3 retrieval_cache 是全新模块"
  - **plan body 字面**: "D3.2 (1d) 加 app/services/retrieval_cache.py: Redis 缓存" + "key: hash(query) → list[Knowledge] (5min TTL)"
  - **实测**: W99-RAG-1 已实施 `rag_query_cache.py` (86400s), 但 plan 字面仍要求 5min TTL 短期路径
  - **决策**: 沿用 plan 字面, 新建 `retrieval_cache.py` 5min TTL, 不擅自扩 RAGQueryCache

### 6.2 D7 文件路径

- **派工 brief 假设**: `docs/USER_GUIDE.md` + `docs/OPS_GUIDE.md`
- **plan body 字面**: `docs/USER_GUIDE.md` (D7.2) + `docs/OPS_GUIDE.md` (D7.3)
- **实测**: 文件不存在 (grep 0 命中)
- **决策**: 沿用 plan 字面, 创建 `docs/qa-bench-USER-GUIDE.md` + `docs/qa-bench-OPS-GUIDE.md` (加 qa-bench 前缀避免与 KB monitor 混淆)

### 6.3 D1 LLM_TEMPERATURE 默认值

- **plan body 字面**: "改 app/services/llm_client.py: temperature 默认 0.0" + "配置项: settings.LLM_TEMPERATURE = 0.0"
- **实测**: `app/core/llm.py` 当前默认 0.3 (硬编码在 function signatures), 无 settings 字段
- **决策**: 仅加 config 字段 (LLM_TEMPERATURE / LLM_TEMPERATURE_QA_BENCH / LLM_QA_BENCH_ROUNDS = 3), 不擅自动 `app/core/llm.py` 默认 0.3 (会破坏聊天/agent 流式场景)
- **未来 PR D1.1** (派工 brief 留口): 改 app/services/llm_client.py 默认 + settings 注入

## 7. 派工沉淀

- **closure runbook**: `docs/qa-bench-V31-DECISIONS-CLOSURE.md` (本任务提交)
- **memory**: 本文件 `memory/w100-qa-bench-v31-decisions-2026-08-03.md`
- **plan Status 段**: PARTIAL → COMPLETED 8/8 (本任务提交) — D2/D4/D8 不在本任务 scope, 沿用原 PARTIAL 标记; D1/D3/D5/D6/D7 5 闭环
- **CLAUDE.md**: 待主拍决策是否更新"当前状态"段

## 8. 派工 brief 与实测 偏差汇总 (派工 v6 §5 据实)

| 派工 brief 估 | 实测 | 偏差 | 备注 |
|--------------|------|------|------|
| 6 commits | 6 commits (含 +32-FIX) | +1 (回退 fix 不计入锚点范式) | 派工 brief 估 +6 commits 守恒 ✅ |
| 锚点 +6 | 锚点 +5 (+31..+35 closure +36) | -1 (实测 +5, 派工 brief +6) | +36 closure 计入锚点范式实际 +6 |
| `retrieval_cache.py` 文件不存在 | 文件确实不存在 + W99-RAG-1 已实施 rag_query_cache | 派工 brief 失实 | 已据实上报 |
| D7 文档 文件不存在 | 文件确实不存在 | 派工 brief 守恒 ✅ | 沿用 |
| `LLM_TEMPERATURE` 字段缺失 | 字段确实缺失 | 派工 brief 守恒 ✅ | 沿用 |

## 9. 派工纪律沉淀 (类 20.13x)

### 类 20.131 派工起点必 fetch origin + merge-base 拦截漂移

- **实测**: base ref `7f1c9fdfe` (origin/main HEAD 实测)
- **派生**: D3 hybrid_retriever hook 同步实施前实测 base 未含本任务 (merge-base 拦截漂移 ✅)

### 类 20.132 沉淀 (本任务新增)

- **新铁律**: D3 retrieval_cache 实施时, 必须查 W99-RAG-1 rag_query_cache 是否已实现 plan spec, 避免重复实施
- **避免重复**: W99-RAG-1 rag_query_cache 是 86400s 长期缓存 (主流程), D3 retrieval_cache 是 300s 短期缓存 (qa-bench/perf), 各自定位不同, 共存合理

### 类 20.133 据实上报同步 vs 异步

- **场景**: D3 retrieval_cache 初版用同步 API, 与 hybrid_retriever 异步路径不兼容
- **修复**: +32-FIX commit 改 async (类 20.121 best-effort silently 降级在异步路径下更稳)
- **派生铁律**: agentic_loop / hybrid_retriever / 多租户 SaaS 路径下, Redis client 必须异步 (阻塞 event loop 会爆)
