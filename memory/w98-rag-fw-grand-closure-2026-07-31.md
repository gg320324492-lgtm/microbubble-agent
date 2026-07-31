# W98 Hybrid RAG Stack GRAND-CLOSURE 完整沉淀 (2026-07-31)

> **任务**: Hybrid RAG Stack 8 项框架能力 (LangChain + LlamaIndex + LangFuse) 全线交付收口
> **agent**: RAG-FW-13 (docs/memory 范畴, 0 production code)
> **当前 main HEAD**: `8f3012d08` (MERGE-RAG-FW-ALL +9 收口)
> **锚点范式**: W97 477 → W98 +9 (10 分支合并) → 本任务 docs-only `[RAG-FW-13 W98 +0]` 守恒
> **alembic head**: `091_add_kg_entity` ✅ 1 head 守恒

---

## §1 交付时间线 (Day 1 基础设施 3 分支 + Day 2 能力 7 分支 + Day 3 收尾)

### Day 1 — 基础设施 3 分支 (RAG-FW-01..03)

| # | 分支 | commit | 内容 |
|---|------|--------|------|
| 01 | `chore/w98-rag-fw-infra-2026-07-31` | `d41ed413f` | app/rag/ 基础设施 3 文件 (config.py 8 项开关 + gate.py framework_gate + __init__.py) |
| 02 | `chore/w98-rag-fw-tests-2026-07-31` | `c6141133e` | tests/rag_framework 测试目录 + conftest 全 mock (CI 无需框架依赖) + framework_gate 5 场景 e2e |
| 03 | `chore/w98-rag-fw-docker-2026-07-31` | `be8de6689` | requirements.txt 框架依赖 + docker-compose langfuse 服务 (端口 3000) |

**MERGE-RAG-FW-BASE** (串行 3 merge, `[merge-rag-fw-base W98 +0/+1/+2]`):

| merge commit | 锚点 | 验证 |
|--------------|------|------|
| `f4a833f67` (RAG-FW-01) | +0 | alembic 1 head |
| `67317eabc` (RAG-FW-02) | +1 | alembic + gate 5 passed |
| `2c1df3de4` (RAG-FW-03) | +2 | alembic + docker compose config EXIT=0 |

### Day 2 — 能力 7 分支 (RAG-FW-04..10)

| # | 分支 | commit | 能力文件 |
|---|------|--------|----------|
| 04 | `chore/w98-rag-fw-tracing-2026-07-31` | `c197581b8` | lc_tracing.py — LangFuse 开源 Tracing (LangSmith 替代) |
| 05 | `chore/w98-rag-fw-query-2026-07-31` | `541beb5aa` | query_translator.py — MultiQuery + HyDE + QueryDecomposition |
| 06 | `chore/w98-rag-fw-multihop-2026-07-31` | `ddbceb042` | multi_hop_engine.py — LlamaIndex SubQuestionQueryEngine |
| 07 | `chore/w98-rag-fw-agent-2026-07-31` | `6019b2494` | agent_retriever.py — LangChain AgentExecutor 动态检索器选择 |
| 08 | `chore/w98-rag-fw-dense-2026-07-31` | `30a6ca9dd` | dense_sparse_routing.py — Dense/Sparse/Hybrid 一层切换 |
| 09 | `chore/w98-rag-fw-chunker-2026-07-31` | `f1f25f0dd` | semantic_chunker.py — Semantic Chunker 语义分块 |
| 10 | `chore/w98-rag-fw-multimodal-2026-07-31` | `4e2b11a0d` | multimodal_parser.py — 跨模态文档解析增强 |

**MERGE-RAG-FW-ALL** (串行 7 merge, `[merge-rag-fw-all W98 +3..+9]`):

| merge commit | 锚点 | 能力 |
|--------------|------|------|
| `e8a02c9e8` | +3 | RAG-FW-04 lc_tracing.py |
| `30941990c` | +4 | RAG-FW-05 query_translator.py |
| `b132a83ff` | +5 | RAG-FW-06 multi_hop_engine.py |
| `55ff32404` | +6 | RAG-FW-07 agent_retriever.py |
| `2ed8dae9f` | +7 | RAG-FW-08 dense_sparse_routing.py |
| `b017a6c8c` | +8 | RAG-FW-09 semantic_chunker.py |
| `8f3012d08` | +9 | RAG-FW-10 multimodal_parser.py |

### Day 3 — 收尾 (RAG-FW-11..13)

| # | 分支 | commit | 内容 |
|---|------|--------|------|
| 11 | `chore/w98-rag-fw-e2e-2026-07-31` | **0 commit 据实** | e2e-gate 能力已并入 RAG-FW-02 `test_gate_degradation.py` 5 场景 (worktree 停在 main HEAD `8f3012d08`) |
| 12 | `chore/w98-rag-fw-ci-2026-07-31` | **0 commit 据实** | `.github/workflows/rag-framework-ci.yml` 未落地 (worktree 停在 merge commit `30941990c`; main `.github/workflows/` 无 rag-framework-ci.yml, `git log --all` 无该文件 commit) |
| 13 | `chore/w98-rag-fw-closure-2026-07-31` | 本任务 | docs/memory 收口 5 件产出 `[RAG-FW-13 W98 +0]` |

## §2 4 层架构说明

- **层 1 手写层** (7 服务, 0 修改): knowledge_qa_service / hybrid_retriever / bm25_service / embedding_service / chunking_service / file_parser_service / knowledge_graph_service — 本次 10 分支 0 改动 (`git diff main~7..main -- app/services/` grep `^[+-]def` = 0)
- **层 2 框架层** (`app/rag/` 8 文件): 7 能力文件 + gate.py, 全部 On by default (激进模式)
- **层 3 回退门控** (`framework_gate` 装饰器): 开关关闭 / ImportError / 运行时异常 3 级自动回退; fallback_fn=None 时不擅自降级 (调用方自行决定)
- **层 4 基础设施**: PostgreSQL + pgvector HNSW (只读复用 knowledge 表, 0 新 alembic) + SQLAlchemy async + langfuse 自托管 (docker-compose 端口 3000, trace 落自有 PostgreSQL)

## §3 回退门控设计 (framework_gate)

```python
@framework_gate(feature_flag, fallback_fn=None)
async def wrapper(*args, **kwargs):
    if not feature_flag:          # 开关关闭 → 回退
    try: return await func(...)   # 框架路径
    except ImportError:           # 依赖未安装 → logger.warning + 回退
    except Exception:             # 运行时异常 → logger.error(exc_info) + 回退
```

各能力回退目标: ① Tracing → recall_observability 日志 ② Query 翻译 → 原 query 直传 ③ Multi-hop → knowledge_qa_service 单轮 ④ Agent Router → vector 单路 → hybrid 4 路 ⑤ Dense/Sparse → hybrid_retriever 4 路 ⑥ Chunker → chunking_service 3 规则 ⑦ Multimodal → file_parser_service + OCR

## §4 5 件套守恒实测

1. **alembic 1 head** = `091_add_kg_entity` ✅ (本任务复验 `python -m alembic heads`)
2. **pytest baseline** = 3272 collected ≥ 3230 (merge-base 实测, 含 6 新增 rag_framework; 1 既有 ERROR `tests/axe_violation_x19` 与 W92 遗留, merge 前基线同样 ERROR 据实)
3. **rag_framework 测试** = `SKIP_DB_SETUP=1 pytest tests/rag_framework/ -q` 74 passed (test_lc_tracing 12 + test_query_translator 24 + test_agent_retriever 8 + test_dense_sparse_routing 14 + test_semantic_chunker 4 + test_multimodal_parser 3 + test_gate_degradation 5 + test_multi_hop_engine 4; CI 无需框架依赖 — conftest 全 mock)
4. **件 4a** = `git diff main~7..main -- app/services/ | grep -cE "^[+-]def"` = 0
5. **merge commit 标识** = 10 merge commits 各含 `[merge-rag-fw-base W98 +N]` / `[merge-rag-fw-all W98 +N]` ✅

## §5 类 20 实战新增实例 (RAG-FW-13 据实上报)

**类 20 实战 21: 派工 brief 假设 RAG-FW-11/12 为已交付能力, 实测 0 commit**

- brief 背景写 "8 项能力全部交付", 其中 RAG-FW-11 (e2e-gate) 与 RAG-FW-12 (CI workflow) 隐含为独立交付
- 实测: `rag-fw-e2e` worktree = 0 commit (停在 main HEAD `8f3012d08`), e2e-gate 能力实际并入 RAG-FW-02 `test_gate_degradation.py` (5 场景, 4 断言组); `rag-fw-ci` worktree = 0 commit (停在 `30941990c`), `.github/workflows/rag-framework-ci.yml` 全仓库无此文件 (`git log --all` 无 commit)
- 处置: 不擅自扩也不擅自缩 — docs 按实测写 (8 项能力表含 gate.py 第 8 项回退门控), CI workflow 未落地据实记录, 测试覆盖据实写 "74+ mock 测试" (conftest 的 rag_integration mark 已预留可选集成测试通道)
- 纪律: 收口类文档必须真验证分支 commit 状态 (git log 分支 + git diff vs main), 不能照 brief 假设填时间线

## §6 关键设计约束 (RAG-FW 系列沉淀)

1. **只读复用 pgvector**: PGVectorStore perform_setup=False — 不建表/不建索引/不 UPSERT, 复用 knowledge.embedding HNSW, 0 新 alembic
2. **0 改老文件**: 仅 import app/services/*, 不改动; layer 1 7 服务 0 修改
3. **中文语料适配**: LangChain SemanticChunker 默认 sentence_split_regex 只覆盖英文标点, 必须显式注入中文句读 `(?<=[。！？!?；;])\s*` 否则语义分块失效
4. **HyDE recall 提升 +15-25%**: 用户 query → LLM 生成假设文档 → 嵌入假设文档检索
5. **agent_retriever 与 agentic_loop 共存**: Phase 0 决定"搜不搜" (固定 tool 列表), Agent Router 决定"怎么搜" (检索器级路由)
6. **回退门控 fail-loud**: ImportError logger.warning / Exception logger.error(exc_info=True), 不静默吞
7. **git 提交纪律**: 每分支 1 commit, merge --no-ff 串行, 锚点 +N 递增守恒

## §7 5 件产出清单 (RAG-FW-13)

| # | 路径 | 行数 | 性质 |
|---|------|------|------|
| 1 | `docs/rag/HYBRID-RAG-STACK.md` | 全览 | 新建 |
| 2 | `docs/rag/HYBRID-RAG-STACK-ARCHITECTURE.md` | 4 层架构 + 回退路径 | 新建 |
| 3 | `memory/w98-rag-fw-grand-closure-2026-07-31.md` (本文件) | 完整沉淀 | 新建 |
| 4 | `docs/rag/W98-HYBRID-RAG-STACK-ANCHOR.md` | CLAUDE.md 镜像 | 新建 |
| 5 | `CHANGELOG.md` append 一行摘要 | +1 行 | 追加 |

commit: `[RAG-FW-13 W98 +0]` (docs/memory 范畴, 锚点守恒 0 增量)
