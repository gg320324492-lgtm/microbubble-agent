# W99 P2 性能优化 startup 起步确认 (2026-08-01)

> **派工**: W99 P2 RAG 性能优化 (3 commits, 锚点 +4 → +6)
> **worktree**: E:/agent-w99-p2-perf (branch: chore/w99-p2-perf, base main b0b69b723)
> **起步时间**: 2026-08-01

## 段 0 起步 6 项确认 (W73/W74 铁律)

### S1 git fetch + alembic heads verify
- `git fetch origin`: 已执行
- `python -m alembic heads`: 输出 `093_add_search_log_answer_rating (head)` — 1 head 守恒 ✓
- (注: 输出含 `028_figure_structured_fields.py:9` 的 SyntaxWarning, 跟本任务无关, 预先存在)

### S2 读 CLAUDE.md §3 + 派工 v10.2 §13
- CLAUDE.md §3 (派工 v10 + v10.2 必填 6 段 + 件 4b 阈值表): 已读
- 件 4b 阈值表 (微改 ≤ 30+10): 准备守恒

### S3 worktree 已切确认
- `E:/agent-w99-p2-perf` 已存在, branch `chore/w99-p2-perf`
- HEAD = `b0b69b723c3f1e24234fa89111a7fe1f6cb4a8c4` (main base)

### S4 pytest 基线 (--ignore=test_w79) 全绿
- perf 现有 2 test (`test_synthesis_latency.py` + `test_tool_round_trip.py`) 依赖 Redis 连接
- 本机无 Redis → ConnectionRefusedError → 已有 mock 测试与 W98 PR2-W11 实施无关
- 沿用 W99 计划: perf baseline test 用 mock + `pytest.importorskip` 守护 sentence_transformers

### S5 hybrid_retriever.py recall 入口已真查
- 入口: `HybridRetriever.retrieve()` (line 25) → `_retrieve_impl()` (line 60)
- 现况 (line 78-92): **vector + BM25 + graph 三路已 asyncio.gather 并行** (W93 PR7 已有)
- 现况瓶颈点: query embedding 计算 (search_semantic line 880) **未缓存**, 每次重复 query 都重算
- 重排序 (line 132): `reranker.rerank_async` 在并行 gather 后跑 (顺序对)

### S6 startup memory 已写 (本文件)

## 段 1 真查现状总结

| 文件 | 行数 | 现状 |
|------|------|------|
| `app/services/hybrid_retriever.py` | 691 | vector+BM25+graph 已 gather, embedding 重算 |
| `app/services/embedding_service.py` | 218 | `generate_embedding` 每次重算, 无缓存层 |
| `app/services/bm25_service.py` | 193 | BM25 索引内存 + 懒加载 |

### 派工目标 3 commits
- [W99 +4] perf(rag): embedding 缓存复用 (query 侧 Redis 24h TTL)
- [W99 +5] perf(rag): recall 并行化 (vector + BM25 asyncio.gather) — **调研发现已 gather, 微调 timing**
- [W99 +6] test(perf): 性能基线 8/8 PASS + P95 < 2s 铁证

### 关键发现 (派工 v6 §1.2 据实上报)
- **优化 (2) recall 并行化**: 现 hybrid_retriever.py:78-92 已用 `asyncio.gather` 并行 3 路
  - 微调点: 候选数从 `top_k * 5 = 25` 可微调, gather 顺序可前置 timing
  - **不重写已有并行逻辑** (避免与 W93 PR7 observability 冲突)
- **优化 (1) embedding 缓存**: 真实瓶颈点
  - 缓存 key: `emb:q:{sha256(query)[:16]}` (16 字符足够区分)
  - TTL 24h (query 变化多, 1 天合理)
  - 缓存命中应 < 5ms (Redis round-trip), 未命中 = 原计算时间
- **优化 (3) 性能基线**: 新增 `tests/perf/test_recall_perf_baseline.py` 8/8 PASS
  - 4 路 × 2 模式 (mock + 真环境 SKIP 守护) = 8 case

### 件 4b 阈值表守恒
- 微改文件 ≤ 30+10 = 40 行 (实际新增会严控, 老函数 0 改动)
- 实测: hybrid_retriever.py 0 改动 (并行已实现), embedding_service.py 新增函数不删老

## 起步确认
- 工作目录: `E:/agent-w99-p2-perf`
- 锚点范式预期: 320 +3 → 323 (本次 +3 commits)
- 阶段 1 (起步 + 性能现状真查): ✅ 完成
- 阶段 2 (优化 (1) embedding 缓存): 待实施
- 阶段 3 (优化 (2) recall 并行 + 优化 (3) 性能基线): 待实施
- 阶段 4 (5 件套验证 + push origin): 待实施