# W-N-OBS best-effort observability 起步 (2026-08-05)

## 派工 brief 复核
- **任务**: 强制 `_chunk_late_recall` 异常显式记录 + 加 recall observability 计数器 + Grafana 仪表盘加 panel
- **锚点**: W-N-OBS +0 / +1 / +2 / +3 (不撞 W-N-OBS 之外任何锚点)
- **铁律**: 0 改既有 4 路逻辑 (W-N-D 范畴) / 0 改 chat_engine.py (方案 C 6 铁律) / 锚点范式 W-N-OBS +0..+3 / 派工前 `git log --oneline -3` 验证 base head
- **commit 基线**: `1cc5362e2` (W-N-D++ +1/+2/+3 收口)
- **alembic head**: 暂存 `104_add_knowledge_chunk_late_embedding` (W-N-G+ 派工后可能是 105)

## 起步 6 项实测 (W73 铁律)

1. **base head 验证**: `git log --oneline -3` →
   - `1cc5362e2 feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档 (W-N-D++ +1/+2/+3)`
   - `ef44aa929 feat(web): DFT/MD 计算工作台 (W-N-D +3)`
   - `ce05da2ea docs(memory): W-N-MEM +2 索引扩展收口 (5 件套守恒实测 + 派工 brief 偏差据实上报)`
   - ✅ base = `1cc5362e2` 守恒

2. **alembic head 验证**: 工作树存在 `alembic/versions/105_fix_drift.py` (W-N-G+ 范畴 untracked), `python -m alembic heads` 暂不能跑 (W-N-G+ 范畴未完), 沿用 W-N-D++ base `104_add_knowledge_chunk_late_embedding` 守恒

3. **hybrid_retriever `_chunk_late_recall` 现状** (app/services/hybrid_retriever.py:312-349):
   - SQL: `SELECT kc.knowledge_id, min(v <=> :query_embedding) AS distance FROM knowledge_chunks AS kc CROSS JOIN LATERAL unnest(kc.chunk_embedding) AS vectors(v) JOIN knowledge AS k ON k.id = kc.knowledge_id WHERE kc.chunk_embedding IS NOT NULL AND (:category IS NULL OR k.category = :category) GROUP BY kc.knowledge_id ORDER BY distance LIMIT :top_k`
   - 失败 best-effort: try/except → `logger.warning("late chunking 召回失败: %s", exc)` → return `[]` (不影响父级检索)
   - **W-N-D+ 报告问题**: `_chunk_late_recall` 异常被吞, 路由层不知道路径失效 (chunk_results=[] 看起来"正常空集" 而非"路径坏了")
   - **本任务目标**: 显式 log + 计数器 +1 + 仍返回空集 (不 raise 影响主流程)

4. **recall_observability 现状** (app/services/recall_observability.py):
   - `RecallTrace` dataclass 字段: caller_path / for_query / has_query_prompt / original_len / truncated_len / latency_ms / retrieval_method / candidate_k / top_k / vector_score / bm25_score / graph_score / rerank_score / error_count / error_msg / slow_query / timestamp / per_path_latency_ms / per_path_count / per_path_error / cache_hit / cache_similarity / citation_count / image_score (24 字段)
   - `RecallObserver.get()` 单例, `_record` 滚动裁剪 1000
   - `per_path_latency_ms` / `per_path_count` / `per_path_error` 已存在 dict 字段
   - `_NullTrace` stub 在 `ENABLE_OBSERVABILITY=False` 时返回
   - **本任务目标**: 在 `RecallTrace` 加 `_chunk_late_recall_path` 字段 (latest chunk recall 专用追踪) + `RecallObserver` 加 `_chunk_late_recall_failures_total` 计数器

5. **Grafana 现状**: 工作树**无** `docs/grafana/` 目录, 派工 brief 要求新增 dashboard.json + README.md
   - 关联参考: W93 PR7 B-7 实施 (commit `4c0458387` 等), RecallObserver 6 面板已部署 (P50/P95/P99 + 按路耗时 + 召回候选数 + CTR + 错误率 + 慢查询)
   - **本任务目标**: 新增 chunk_recall 专用 3 panel (P95 延迟 / 召回命中率 / 失败计数器)

6. **测试 + DB + 服务健康**:
   - tests/rag/test_pr7_e2e.py 22/22 PASS 模式 (RecallTrace 字段完整性 + observer 生命周期)
   - 工作树中 `tests/rag_eval/` (untracked, W-N-D++ 范畴)
   - `curl http://localhost:8000/health` → 沿用 W-N-D++ 验证 healthy

## 风险表

| 风险 | 控制 |
|---|---|
| `_chunk_late_recall` 异常 raise 阻塞主流程 | 不 raise, 显式 log + 计数器 +1 + return [] (best-effort 守恒) |
| `RecallTrace` 加字段破坏老 trace dataclass | 仅 ADD 字段, 默认值 None / 0, 兼容现有 24 字段 (W93 铁律) |
| Grafana panel SQL 引用错列名 | 参考 W93 PR7 6 panel SQL 命名 (recall_trace / per_path_latency_ms 等) |
| 既有 4 路逻辑被改 | 仅追加监控, 不动 _vector_search / _bm25_search / _graph_search / rerank_async |
| chat_engine.py 被改 | 仅 _chunk_late_recall 1 方法 + observability 1 文件 + Grafana 1 JSON + 2 memory |
| npm run build 副作用 | 实测 web/dist 改动已 git checkout 回退 (起步阶段已验证) |

## 验证策略

1. **失败路径显式记录**: 单元测试 mock `AsyncSession.execute` 抛错 → assert logger.warning 含 "_chunk_late_recall" + assert counter +=1
2. **成功路径不受影响**: 单元测试 mock 正常结果 → assert 返回列表 + counter 不增
3. **observability 集成**: 验证 RecallTrace 新字段 + RecallObserver counter 字段
4. **Grafana JSON 解析**: 验证 dashboard.json 结构 (panels / targets / gridPos)
5. **5 件套守恒**: alembic 1 head 守恒 (沿用 W-N-G+) / pytest 测试 PASS / 0 production code 守恒 / 锚点范式 W-N-OBS +0..+3 / 不改既有 4 路逻辑

## 失败回滚

每个 W-N-OBS 锚点独立提交:
- +1 commit 包含 hybrid_retriever 1 方法 + observability 1 文件字段追加 + 1 unit test
- +2 commit 包含 Grafana 1 JSON + 1 README
- +3 memory 沉淀 5 件套守恒实测

若 +1 验证失败 → revert commit (沿用 W-N-D++ revert 模式). 不擅自改 W-N-D 已有 logic.

## 锚点 +0..+3 commit 计划

- **W-N-OBS +0**: 本起步 memory (本任务)
- **W-N-OBS +1**: `feat(rag): _chunk_late_recall 显式失败 + observability 计数器` — 1 commit, hybrid_retriever 1 方法 + observability 1 文件 + 1 test
- **W-N-OBS +2**: `docs(grafana): late chunking 召回仪表盘` — 1 commit, dashboard.json + README.md
- **W-N-OBS +3**: 收口 memory `memory/w-n-obs-observability-closure-2026-08-05.md` (5 件套守恒实测)

## 类 20 沉淀 (W-N-OBS)

- **类 20.NEW (W-N-OBS +1)**: best-effort 路径异常必须显式记录 + 计数器 +1, 不允许被静默吞掉 (`_chunk_late_recall` 是 best-effort 加分项, 失败必须可见, 否则路由层不知道该路失效)
- **类 20.NEW (W-N-OBS +2)**: Grafana panel SQL 必须基于结构化 JSON 字段 (`per_path_latency_ms["chunk_late"]` / `per_path_error["chunk_late"]`), 不硬编码字段路径, 后续新增路径自动接入

## 不做清单 (W-N-OBS)

- ❌ 改 `app/services/chat_engine.py` (方案 C 6 铁律)
- ❌ 改 `_vector_search` / `_bm25_search` / `_graph_search` / `rerank_async` 4 路逻辑
- ❌ 改 `app/services/embedding_service.py`
- ❌ 改 `app/services/late_chunking_service.py`
- ❌ 改 `app/models/knowledge.py` / `knowledge_chunk.py`
- ❌ 改 `alembic/versions/` 任何迁移
- ❌ 改 `app/services/recall_observability.py` 既有字段 (仅追加)
- ❌ 跑生产 DB 写 (W-N-G+ 范畴, 不在 W-N-OBS 范围)
- ❌ 改 plan 文件
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+ commits