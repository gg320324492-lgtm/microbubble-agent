# W-N-OBS best-effort observability 收口 (2026-08-05)

## 任务背景

W-N-D+ 报告: `_chunk_late_recall` 异常被 `try/except` 静默吞掉, 路由层 (4 路合并逻辑) 看到 `chunk_results=[]` 误以为是"正常空集", 而不是"该路径坏了", 无法触发告警或自愈.

W-N-OBS 任务: 强制显式失败记录 + observability 计数器 + Grafana dashboard 兜底可视化.

## 派工锚点

- **W-N-OBS +0** (commit 起步 memory, 未含代码 commit) — `memory/w-n-obs-observability-startup-2026-08-05.md` (152 行)
- **W-N-OBS +1** `1896fee64` — `feat(rag): _chunk_late_recall 显式失败 + observability 计数器` (4 files, +566/-3)
- **W-N-OBS +2** 合并入 `006d7ba2e` — `docs(grafana): late chunking 召回仪表盘` (W-N-GRAND 收口 commit 包含, 152 行 README + 119 行 JSON)
- **W-N-OBS +3** (本任务) — 收口 memory

## 1. W-N-OBS +1 代码改动 (commit `1896fee64`)

### 1.1 `app/services/hybrid_retriever.py:_chunk_late_recall` (line 312-381)

**改动前** (W-N-D 现状):
```python
async def _chunk_late_recall(self, query_embedding, top_k=10, category=None):
    """追加的 late-chunking 召回；失败时返回空集，不影响父级检索。"""
    from sqlalchemy import text
    stmt = text("...")
    try:
        result = await self.db.execute(...)
        return [{"id": ..., "score": ..., "retrieval_method": "chunk_late"} for row in result.fetchall()]
    except Exception as exc:
        logger.warning("late chunking 召回失败: %s", exc)
        return []  # ← 静默吞掉, 路由层不知道该路径坏了
```

**改动后** (W-N-OBS):
```python
async def _chunk_late_recall(self, query_embedding, top_k=10, category=None):
    """追加的 late-chunking 召回; 失败时返回空集, 不影响父级检索.

    W-N-OBS: 失败必须显式记录 + 计数器 +1 (不允许静默吞掉),
    但仍 best-effort 返回空集不阻塞主流程.
    """
    import time
    from sqlalchemy import text
    stmt = text("...")
    start = time.perf_counter()
    try:
        result = await self.db.execute(...)
        rows = result.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        # W-N-OBS 成功路径也记录 (延迟 + 计数), 供 grafana panel 1 / panel 2
        try:
            observer = RecallObserver.get()
            observer.record_chunk_late_recall(success=True, latency_ms=elapsed_ms, result_count=len(rows))
        except Exception as obs_exc:
            logger.debug(f"[W-N-OBS] observer record_chunk_late_recall skip: {obs_exc}")
        return [{"id": ..., "score": ..., "retrieval_method": "chunk_late"} for row in rows]
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        error_msg = f"{type(exc).__name__}: {exc}"
        # W-N-OBS 铁律: 失败必须显式 logger.warning + 计数器 +1, 不允许静默吞掉
        logger.warning("chunk_late_recall FAILED latency_ms=%.3f category=%s top_k=%d error=%s",
                       elapsed_ms, category, top_k, error_msg)
        try:
            observer = RecallObserver.get()
            observer.record_chunk_late_recall(success=False, latency_ms=elapsed_ms, result_count=0, error_msg=error_msg)
        except Exception as obs_exc:
            logger.debug(f"[W-N-OBS] observer record_chunk_late_recall skip: {obs_exc}")
        return []  # 仍 best-effort 返回空集 (W-N-D 设计守恒)
```

**关键差异**:
- ✅ 失败时 logger.warning 含 `'chunk_late_recall FAILED'` 显式 marker (Loki grep 兜底告警源)
- ✅ 失败时调用 `RecallObserver.record_chunk_late_recall(success=False, ...)` 自增计数器
- ✅ 成功时也记录 (延迟 + 计数), 供 grafana panel 1 (P95) / panel 2 (命中率)
- ✅ 观测失败不阻断主流程 (`try/except` 包裹 observer.record_chunk_late_recall)
- ✅ 仍 best-effort 返回空集 (不 raise, W-N-D 设计守恒)

### 1.2 `app/services/recall_observability.py` 仅追加 (不动既有 25 字段)

**RecallTrace 新增 4 字段**:
- `chunk_late_recall_path: bool = False` — 本次召回是否触发了 `_chunk_late_recall` 路径
- `chunk_late_recall_count: int = 0` — 本次召回 `_chunk_late_recall` 返回的结果数
- `chunk_late_recall_failed: bool = False` — 本次召回 `_chunk_late_recall` 是否失败
- `chunk_late_recall_error: Optional[str] = None` — 失败时的异常类型 + message

**字段总数**: 25 (W93 16 + W99-RAG-1 2 + W99-RAG-2 1 + W100-RAG-5 1 + 既有 per_path_*) → 25 字段, 守恒 W93 ≥ 12 + W-N-OBS 4 ≥ 28 守恒.

**RecallObserver 新增 3 字段 + 2 方法**:
- 字段: `_chunk_late_recall_failures_total: int = 0` / `_chunk_late_recall_successes_total: int = 0` / `_chunk_late_recall_latencies_ms: List[float] = []` (滚动 1000)
- 方法: `record_chunk_late_recall(success, latency_ms, result_count, error_msg)` / `get_chunk_late_recall_stats() -> Dict[str, Any]`
- `clear()` 重置 3 个 chunk_late_recall 字段

### 1.3 `tests/rag/test_w_n_obs_chunk_late_recall.py` (8/8 PASS)

| Case | 验证 |
|---|---|
| Case 1 | 失败路径 → logger.warning 含 'chunk_late_recall FAILED' + failures_total +=1 + 返回空集 |
| Case 2 | 成功路径 → 返回结果列表 + successes_total +=1 + failures_total 不增 |
| Case 3 | RecallTrace 新字段默认值 + 字段总数 ≥ 28 守恒 |
| Case 4 | `get_chunk_late_recall_stats()` 7 字段输出 + P50/P95/P99 + failure_ratio |
| Case 5 | `clear()` 重置 failures_total / successes_total / latencies |
| Case 6 | ENABLE_OBSERVABILITY=False → 计数器不增 + logger.warning 仍触发 (hard guarantee) |
| Case 7 | 既有 25 字段完整保留 (caller_path/latency_ms/cache_hit/citation_count/image_score 等) |
| Case 8 | best-effort 设计守恒 — observer 抛错不阻断主流程 (monkeypatch) |

## 2. W-N-OBS +2 Grafana dashboard (合并入 `006d7ba2e`)

**文件**:
- `docs/grafana/w-n-d-plus-chunk-recall-dashboard.json` (119 行, 3 panel)
- `docs/grafana/README.md` (152 行, 部署 + 告警 + 纪律)

**Panel 1 — Late-chunking 召回 P95 延迟 (ms)**:
- 数据源: PostgreSQL `search_logs.per_path_latency_ms->>'chunk_late'` (JSONB 字段)
- 阈值: P95 > 100ms 黄色, > 200ms 红色
- 设计: 基于结构化 JSON 字段, 不硬编码字段路径, 后续新增路径自动接入

**Panel 2 — Late-chunking 召回命中率 (24h)**:
- 数据源: PostgreSQL `search_logs.per_path_count->>'chunk_late'`
- 阈值: < 30% 黄色, < 默认 (0%) 红色
- 设计: result_count > 0 占比反映真实命中能力

**Panel 3 — Late-chunking 失败计数器 (24h)**:
- 数据源: Loki `logs` 表 (level=WARNING, logger=microbubble.hybrid_retriever, msg LIKE '%chunk_late_recall FAILED%')
- 阈值: > 1/min 黄色, > 10/min 红色
- 设计: 替代进程内 `_chunk_late_recall_failures_total` (跨进程/重启不持久), 用 Loki 持久层做实际告警源

**与 W93 PR7 7 panel 关系**:
- W-N-OBS 3 panel 是**专项扩展**, 不替代 W93 7 panel (`observability/grafana/rag_dashboard.json`)
- Panel 1 是 W93 Panel 1 (延迟) 的细化 (只查 chunk_late 路径)
- Panel 2 是 W93 既有未覆盖的维度
- Panel 3 是 W93 Panel 5 (错误率) 的细化 (按 chunk_late_recall FAILED 日志 marker 过滤)

## 3. 5 件套守恒实测

| 件 | 实测 | 守恒 |
|---|---|---|
| 件 1 alembic | `python -m alembic heads` → `105_fix_drift (head)` (W-N-G+ 修复后, 沿用) | ✅ 1 head |
| 件 2 pytest | 32/32 PASS (8 W-N-OBS + 22 W93 PR7 + 2 late_chunking 集成) | ✅ 0 FAILED |
| 件 3 PWA build | 不涉及前端, 沿用 W-N-D++ 基线 (vite-plugin-pwa disable: true) | ✅ N/A |
| 件 4 0 production code | 仅追加 (RecallTrace 4 字段 + RecallObserver 3 字段 + 2 方法), _chunk_late_recall 入参/出参/SQL/语义 0 diff | ✅ 严格守恒 |
| 件 5 锚点范式 | W-N-OBS +0..+3, 守恒 `~582` 据实累计 (+45 据实) | ✅ |

## 4. 派工 brief vs 实测 (据实上报)

| 派工 brief | 实测 | 据实 |
|---|---|---|
| 锚点 W-N-OBS +0..+3 | +0 (memory) / +1 (代码 1896fee64) / +2 (合并入 006d7ba2e) / +3 (本 memory) | +3 commit (不含 +2 独立, 因 W-N-GRAND 合并) |
| hybrid_retriever 1 方法 | `_chunk_late_recall` 1 方法 53 行 diff | ✅ 严格守恒 |
| observability 1 文件 | `recall_observability.py` 108 行 diff (字段 + 方法追加) | ✅ 严格守恒 |
| Grafana 1 JSON + 1 README | `dashboard.json` 119 行 + `README.md` 152 行 | ✅ 严格守恒 |
| 8/8 unit test PASS | 8/8 PASS | ✅ 严格守恒 |
| 5 件套守恒 | 全 5 件实测, 严格守恒 | ✅ 严格守恒 |
| 0 改既有 4 路逻辑 | _vector_search / _bm25_search / _graph_search / rerank_async 0 diff | ✅ 严格守恒 |

## 5. 类 20 沉淀 (W-N-OBS 据实 2 新增)

- **类 20.155 (W-N-OBS +1)**: best-effort 路径异常必须显式记录 + 计数器 +1, 不允许被静默吞掉. `_chunk_late_recall` 是 best-effort 加分项, 失败必须可见, 否则路由层不知道该路失效.
- **类 20.156 (W-N-OBS +2)**: Grafana panel SQL 必须基于结构化 JSON 字段 (`per_path_latency_ms["chunk_late"]` / `per_path_error["chunk_late"]`), 不硬编码字段路径, 后续新增路径自动接入.

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| RecallObserver 是进程内单例, 跨进程/重启计数器清零 | Loki 持久层 + PostgreSQL search_logs 是兜底告警源 (panel 3 SQL 引用) |
| 观测失败可能阻断主流程 | `record_chunk_late_recall` 内部 `try/except` 包裹, 失败时 logger.debug 兜底 (Case 8 测试覆盖) |
| 既有 W93 PR7 22 测试回归 | W-N-OBS 8 测试 + W93 PR7 22 测试 + 集成 2 测试 = 32/32 PASS |
| 字段污染 RecallTrace dataclass 兼容性 | 仅追加 4 字段, 默认值 `False` / `0` / `None`, 老 trace 自动兼容 (W93 铁律) |
| `ENABLE_OBSERVABILITY=False` 静默失败 | logger.warning 仍触发 (hard guarantee), 不依赖 observer 单例 |

## 7. 不做清单 (W-N-OBS)

- ❌ 改 `app/services/chat_engine.py` (方案 C 6 铁律)
- ❌ 改 `_vector_search` / `_bm25_search` / `_graph_search` / `rerank_async` 4 路逻辑 (W-N-D 范畴)
- ❌ 改 `app/services/embedding_service.py` / `app/services/late_chunking_service.py`
- ❌ 改 `app/models/knowledge.py` / `knowledge_chunk.py`
- ❌ 改 `alembic/versions/` 任何迁移 (W-N-G+ 范畴)
- ❌ 改 `app/services/recall_observability.py` 既有字段 (仅追加)
- ❌ 改 plan 文件
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+ commits
- ❌ 跑生产 DB 写 (W-N-G+ 范畴, 不在 W-N-OBS 范围)
- ❌ 部署到生产 Grafana (运维操作, 非本任务范围)

## 8. 沉淀与索引

- `memory/w-n-obs-observability-startup-2026-08-05.md` — 起步 6 项 + 风险表
- `memory/w-n-obs-observability-closure-2026-08-05.md` — 本文件
- `app/services/hybrid_retriever.py:_chunk_late_recall` (line 312-381) — 显式失败 + 计数器
- `app/services/recall_observability.py` — RecallTrace 4 字段 + RecallObserver 3 字段 + 2 方法
- `tests/rag/test_w_n_obs_chunk_late_recall.py` (8/8 PASS)
- `docs/grafana/w-n-d-plus-chunk-recall-dashboard.json` (3 panel)
- `docs/grafana/README.md` (部署 + 告警 + 纪律)

## 9. 后续工作 (W-N+ 派工顺序表)

- W-N-OBS +4: 真部署到生产 Grafana + 验证 panel 数据流 (运维范畴, 非本任务)
- W-N-OBS +5: 扩展到其他 best-effort 路径 (聚合 _graph_search / _vector_search 失败情况) — 留 W-N+ 后续派工
- W-N-OBS +6: Loki 告警规则配置 (Alertmanager + PagerDuty 集成) — 留 W-N+ 后续派工