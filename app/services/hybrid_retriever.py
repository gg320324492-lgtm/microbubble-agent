"""混合检索器 — 向量 + BM25 并发检索 + 合并去重 + 重排序

流程：
1. 向量检索（pgvector 语义搜索）和 BM25 关键词检索并发执行
2. 合并结果，同一文档保留最高分
3. 分数归一化（不同检索方式的分数尺度不同）
4. Cross-encoder 重排序
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.hybrid_retriever")


def _backfill_normalized_scores(results: List[dict]) -> None:
    """WP8 (2026-09-01): rerank 后把 rerank_score (cross-encoder logits, 无界)
    min-max 归一化回填 normalized_score, 供 temporal 乘子与 QA 置信度阈值分级
    使用统一 [0,1] 语义。无 rerank_score 时退回原 score。原地修改。
    """
    if not results:
        return
    scores = [
        float(r["rerank_score"]) if r.get("rerank_score") is not None
        else float(r.get("score") or 0.0)
        for r in results
    ]
    mx = max(scores)
    mn = min(scores)
    rng = (mx - mn) or 1.0
    for r, s in zip(results, scores):
        r["normalized_score"] = round((s - mn) / rng, 4)


async def _timed_path(obs_trace: Any, name: str, coro) -> Any:
    """WP7 (2026-09-01): 单路召回计时埋点 — 耗时/命中数/异常写 trace,
    供 search_logs.per_path_* 落库 + grafana 按路面板。obs_trace 为
    None 或 _NullTrace 时行为不变 (写入被吞/跳过), 只多一次 perf_counter。
    """
    if obs_trace is None:
        return await coro
    t0 = time.perf_counter()
    try:
        out = await coro
    except Exception as e:
        try:
            obs_trace.per_path_latency_ms[name] = round((time.perf_counter() - t0) * 1000, 3)
            obs_trace.per_path_error[name] = obs_trace.per_path_error.get(name, 0) + 1
        except Exception:
            pass
        raise
    try:
        obs_trace.per_path_latency_ms[name] = round((time.perf_counter() - t0) * 1000, 3)
        obs_trace.per_path_count[name] = len(out) if isinstance(out, list) else 0
    except Exception:
        pass
    return out


class _CitationList(list):
    """list 子类 — 携带 .citations 附件 (WP3, 2026-09-01)

    plain list 不支持属性赋值 (AttributeError), 类 20.133 的 "final attach"
    曾因此在生产静默失败 (citation 永远为空)。调用方通过
    getattr(results, "citations", []) 读取, 契约不变。
    """

    citations: List[Dict[str, Any]] = []


def _finalize_obs_trace(obs_trace: Any, results: List[dict]) -> None:
    """WP7: 终态埋点 — 实际返回数 + top_ids (ctr/click 关联用)"""
    try:
        obs_trace.top_k_actual = len(results)
        obs_trace.top_ids = [
            r.get("id") for r in (results or [])
            if isinstance(r, dict) and r.get("id") is not None
        ][:20]
    except Exception:
        pass


class HybridRetriever:
    """混合检索器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_graph: bool = True,
        enable_rerank: bool = True,
    ) -> List[dict]:
        """混合检索 (W93 PR7 B-7: observability hook 包裹原逻辑, 原 10 def 签名不变)"""
        # W93 PR7 B-7: observability hook — 仅添加包裹, 原 retrieve() body 字面照搬到 _retrieve_impl (不删不改)
        from app.services.recall_observability import RecallObserver
        observer = RecallObserver.get()
        async with observer.observe(caller_path="hybrid_retriever", for_query=True, has_query_prompt=False, original_query=query) as obs_trace:
            return await self._retrieve_impl(query=query, top_k=top_k, category=category, enable_vector=enable_vector, enable_bm25=enable_bm25, enable_graph=enable_graph, enable_rerank=enable_rerank, obs_trace=obs_trace)

    async def _retrieve_impl(
        self,
        query: str,
        top_k: int,
        category: Optional[str],
        enable_vector: bool,
        enable_bm25: bool,
        enable_graph: bool,
        enable_rerank: bool,
        obs_trace: Any = None,
    ) -> List[dict]:
        """原 retrieve() body — W93 PR7 B-7 拆分点, 不改任何逻辑/不动 4 路开关"""
        # 候选集数量（重排序前多取一些）
        # 2026-07-01 BGE m3: top_k * 5 → 25 candidates before rerank (从 15 扩到 25)
        # 理由: cross-encoder 对更大候选集更稳定, GPU 推理 30ms 可忽略
        candidate_k = top_k * 5 if enable_rerank else top_k

        # WP7: 候选数埋点
        try:
            obs_trace.candidate_k = candidate_k
            obs_trace.top_k = top_k
        except Exception:
            pass

        # W99 P2 性能优化 (commit +5): 预计算 query embedding 并行化
        # 原行为: _vector_search 内串行 await generate_embedding (CPU/IO bound)
        # 优化: 把 embedding 计算提到 gather 之前, 与 BM25 并发执行
        # 关键: 这是 asyncio.create_task (非阻塞), gather 仍负责收齐结果
        vector_query_embedding_task = None
        if enable_vector:
            try:
                from app.services.embedding_service import get_or_compute_query_embedding
                vector_query_embedding_task = asyncio.create_task(
                    get_or_compute_query_embedding(query, has_query_prompt=True)
                )
            except Exception as e:
                logger.debug(f"[W99 P2] precompute embedding skip: {e}")

        # 并发执行三路检索 (WP7: 每路计时埋点)
        tasks = []
        task_names = []
        if enable_vector:
            tasks.append(_timed_path(obs_trace, "vector", self._vector_search(query, candidate_k, category)))
            task_names.append("vector")
        if enable_bm25:
            tasks.append(_timed_path(obs_trace, "bm25", self._bm25_search(query, candidate_k, category)))
            task_names.append("bm25")
        if enable_graph:
            tasks.append(_timed_path(obs_trace, "graph", self._graph_search(query, candidate_k)))
            task_names.append("graph")

        if not tasks:
            return []

        # chunk 路结果容器 (1.1 修复: 先初始化, 防异常路径 UnboundLocal;
        # 原实现在 try 块后无条件重置 → _chunk_late_recall 结果永远被丢弃)
        chunk_results: List[dict] = []
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # W99 P2: 消费预计算的 embedding task (若有), 不影响主流程
        if vector_query_embedding_task is not None:
            try:
                query_embedding = await vector_query_embedding_task  # cache primed + chunk recall input
                if query_embedding is not None:
                    chunk_results = await self._chunk_late_recall(
                        query_embedding, candidate_k, category
                    )
            except Exception as e:
                logger.debug(f"[late-chunking] embedding consume skip: {e}")

        vector_results = []
        bm25_results = []
        graph_results = []
        for i, (result, name) in enumerate(zip(results_list, task_names)):
            if isinstance(result, Exception):
                logger.warning(f"检索方式 {name} 失败: {result}")
                continue
            if name == "vector":
                vector_results = result
            elif name == "bm25":
                bm25_results = result
            elif name == "graph":
                graph_results = result

        # 合并去重（三路 + late-chunking）
        merged = self._merge_results(vector_results, bm25_results, graph_results)
        if chunk_results:
            merged = self._merge_results(merged, chunk_results)

        if not merged:
            return []

        # 分数归一化
        normalized = self._normalize_scores(merged)

        # 重排序 (2026-07-01 BGE m3: rerank_async 不阻塞 event loop)
        if enable_rerank and len(normalized) > 1:
            from app.services.reranker_service import get_reranker_service
            reranker = get_reranker_service()
            _t0 = time.perf_counter()
            reranked = await reranker.rerank_async(query, normalized, top_k=top_k)
            try:
                obs_trace.per_path_latency_ms["rerank"] = round((time.perf_counter() - _t0) * 1000, 3)
                if reranked:
                    obs_trace.rerank_score = reranked[0].get("rerank_score")
            except Exception:
                pass
            # WP8: rerank 后按 rerank_score 重算归一化分 (原 normalized_score
            # 基于混合尺度的 pre-rerank 分数, 对 rerank 后顺序已失真)
            _backfill_normalized_scores(reranked)
            _finalize_obs_trace(obs_trace, reranked)
            return reranked

        # 不重排序时按归一化分数排序
        normalized.sort(key=lambda x: x.get("normalized_score", 0), reverse=True)
        _final = normalized[:top_k]
        _finalize_obs_trace(obs_trace, _final)
        return _final

    async def _vector_search(
        self, query: str, top_k: int, category: Optional[str]
    ) -> List[dict]:
        """向量检索（复用现有 KnowledgeService.search_semantic）"""
        try:
            from app.services.knowledge_service import KnowledgeService
            svc = KnowledgeService(self.db)
            results = await svc.search_semantic(query=query, top_k=top_k, category=category)
            for r in results:
                r["retrieval_method"] = "vector"
            return results
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")
            return []

    async def _bm25_search(
        self, query: str, top_k: int, category: Optional[str] = None
    ) -> List[dict]:
        """BM25 关键词检索

        2026-09-01 重构: 改用 BM25IncrementalIndex (O(M) 增量), 修复两个生产 bug:
        1. legacy BM25Service 单例只在首次查询时建索引 → 之后新增/更新文档不可见
        2. legacy 按 category 建索引 → 语料被首次查询的 category 污染
        现在索引为空时全量 build (kb + 未删除 + team/public), 之后由写入侧
        _incremental_add_document 增量同步 (knowledge_service Step-1 hook)。
        """
        try:
            from app.services.bm25_incremental import get_bm25_incremental_index

            idx = get_bm25_incremental_index()
            if len(idx) == 0:
                await self._refresh_bm25_incremental_index(idx, category)

            results = idx.search(query, top_k=top_k, category=category)
            return results
        except Exception as e:
            logger.warning(f"BM25 检索失败: {e}")
            return []

    async def _refresh_bm25_incremental_index(
        self, idx, category: Optional[str] = None
    ) -> None:
        """从数据库全量构建 BM25 增量索引 (冷启动)"""
        from sqlalchemy import select
        from app.models.knowledge import Knowledge

        # 与 search_semantic 同款可见性硬边界:
        # kb 模式 + 未软删除 + team/public (private/drive 不入检索语料)
        stmt = select(Knowledge).where(
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "kb",
            Knowledge.visibility.in_(["team", "public"]),
        )
        if category:
            # 冷启动只带 category 过滤会污染全局语料 — 全量构建,
            # category 过滤交给 search() 运行时后过滤
            logger.debug("[bm25] 冷启动忽略 category 过滤, 全量构建 (运行时后过滤)")
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        documents = [
            {
                "id": r.id,
                "title": r.title or "",
                "content": r.content or "",
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
                "created_at": r.created_at,
            }
            for r in rows
        ]
        idx.build_from_docs(documents)
        logger.info(f"BM25 增量索引冷启动完成: {len(documents)} 条")

    async def retrieve_per_method(
        self,
        query: str,
        candidate_k: int = 25,
        category: Optional[str] = None,
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_graph: bool = True,
    ) -> Dict[str, List[dict]]:
        """按检索路分组的并发召回 (WP1.7: 供 retrieve_with_weights 做 RRF 合并)

        WP7: observability hook 包裹原逻辑, 原 body 字面照搬到
        _retrieve_per_method_impl (与 retrieve()/_retrieve_impl 同模式)。
        """
        from app.services.recall_observability import RecallObserver
        observer = RecallObserver.get()
        async with observer.observe(
            caller_path="hybrid_retriever.per_method",
            for_query=True,
            has_query_prompt=True,
            original_query=query,
        ) as obs_trace:
            return await self._retrieve_per_method_impl(
                query=query,
                candidate_k=candidate_k,
                category=category,
                enable_vector=enable_vector,
                enable_bm25=enable_bm25,
                enable_graph=enable_graph,
                obs_trace=obs_trace,
            )

    async def _retrieve_per_method_impl(
        self,
        query: str,
        candidate_k: int = 25,
        category: Optional[str] = None,
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_graph: bool = True,
        obs_trace: Any = None,
    ) -> Dict[str, List[dict]]:
        """原 retrieve_per_method body — WP7 拆分点, 不改任何逻辑"""
        try:
            obs_trace.candidate_k = candidate_k
        except Exception:
            pass

        tasks: List = []
        names: List[str] = []
        if enable_vector:
            tasks.append(_timed_path(obs_trace, "vector", self._vector_search(query, candidate_k, category)))
            names.append("vector")
        if enable_bm25:
            tasks.append(_timed_path(obs_trace, "bm25", self._bm25_search(query, candidate_k, category)))
            names.append("bm25")
        if enable_graph:
            tasks.append(_timed_path(obs_trace, "graph", self._graph_search(query, candidate_k)))
            names.append("graph")

        out: Dict[str, List[dict]] = {}
        if not tasks:
            return out

        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        for result, name in zip(results_list, names):
            if isinstance(result, Exception):
                logger.warning(f"retrieve_per_method 路 {name} 失败: {result}")
                out[name] = []
            else:
                out[name] = result

        # chunk 向量路 (RRF 第 4 路): 复用预计算 embedding
        if enable_vector:
            _t_chunk = time.perf_counter()
            try:
                from app.services.embedding_service import get_or_compute_query_embedding
                from sqlalchemy import select as _sel
                from app.models.knowledge import Knowledge as _K

                query_embedding = await get_or_compute_query_embedding(
                    query, has_query_prompt=True
                )
                if query_embedding is not None:
                    chunk_hits = await retrieve_chunks_by_vector(
                        db=self.db,
                        query_embedding=query_embedding,
                        top_k=candidate_k,
                    )
                    # chunk-only 命中补父文档字段 (title/content/created_at)
                    parent_ids = {h["knowledge_id"] for h in chunk_hits}
                    parents: Dict[int, dict] = {}
                    if parent_ids:
                        rows = (
                            await self.db.execute(
                                _sel(_K).where(_K.id.in_(list(parent_ids)))
                            )
                        ).scalars().all()
                        for r in rows:
                            parents[r.id] = r
                    enriched: List[dict] = []
                    for h in chunk_hits:
                        p = parents.get(h["knowledge_id"])
                        if p is None:
                            # 父文档已被删除/不可见 → retrieve_chunks_by_vector 已过滤,
                            # 这里防御跳过
                            continue
                        enriched.append({
                            "id": h["knowledge_id"],
                            "title": p.title or "",
                            "content": h["content"],
                            "category": p.category,
                            "tags": p.tags,
                            "source": p.source,
                            "created_at": p.created_at,
                            "score": h["similarity"],
                            "chunk_id": h["chunk_id"],
                            "char_start": h["char_start"],
                            "char_end": h["char_end"],
                            "chunk_content": h["content"],
                            "retrieval_method": "chunk_vector",
                        })
                    out["chunk"] = enriched
            except Exception as e:
                logger.warning(f"retrieve_per_method chunk 路失败: {e}")
                out["chunk"] = []
            try:
                obs_trace.per_path_latency_ms["chunk"] = round((time.perf_counter() - _t_chunk) * 1000, 3)
                obs_trace.per_path_count["chunk"] = len(out.get("chunk") or [])
            except Exception:
                pass

        # WP7: 终态埋点 — top_ids 取各路 union (vector 优先), 供 search_logs
        try:
            _union_ids: List[int] = []
            for _m in ("vector", "bm25", "graph", "chunk"):
                for _r in out.get(_m) or []:
                    _rid = _r.get("id")
                    if _rid is not None and _rid not in _union_ids:
                        _union_ids.append(_rid)
            obs_trace.top_ids = _union_ids[:20]
            obs_trace.top_k_actual = len(_union_ids[:20])
        except Exception:
            pass
        return out

    async def _refresh_bm25_index(
        self, bm25_service, category: Optional[str] = None
    ) -> None:
        """从数据库刷新 BM25 legacy 索引 (保留: agent_retriever._bm25_only 兜底用)"""
        from sqlalchemy import select
        from app.models.knowledge import Knowledge

        # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL + storage_mode='kb' 过滤
        # drive 模式原始文件不入 BM25 索引, 软删除条目不索引
        # PR2.10 课题组网盘: 加 visibility IN ('team','public') 过滤 (硬边界, 防止 private 漏出)
        stmt = select(Knowledge).where(
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "kb",
            Knowledge.visibility.in_(["team", "public"]),
        )
        if category:
            stmt = stmt.where(Knowledge.category == category)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        documents = [
            {
                "id": r.id,
                "title": r.title or "",
                "content": r.content or "",
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
            }
            for r in rows
        ]
        bm25_service.build_index(documents)
        logger.info(f"BM25 索引刷新完成: {len(documents)} 条")

    def _merge_results(
        self,
        vector_results: List[dict],
        bm25_results: List[dict],
        graph_results: List[dict] = None,
    ) -> List[dict]:
        """合并去重：同一文档保留最高分，记录所有来源"""
        merged = {}

        for r in vector_results:
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["vector"]}
            else:
                existing = merged[doc_id]
                if r.get("score", 0) > existing.get("score", 0):
                    existing.update(r)
                existing.setdefault("retrieval_methods", []).append("vector")

        for r in bm25_results:
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["bm25"]}
            else:
                existing = merged[doc_id]
                existing.setdefault("retrieval_methods", []).append("bm25")

        for r in (graph_results or []):
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["graph"]}
            else:
                existing = merged[doc_id]
                existing.setdefault("retrieval_methods", []).append("graph")
                # 图谱分数作为加成
                existing["score"] = existing.get("score", 0) + r.get("score", 0) * 0.3

        return list(merged.values())

    async def _graph_search(
        self, query: str, top_k: int
    ) -> List[dict]:
        """图谱检索 — 从查询中提取实体关键词，在 Neo4j 中搜索关联知识"""
        try:
            from app.services.neo4j_service import get_neo4j_service
            from app.models.knowledge import Knowledge
            from sqlalchemy import select

            neo4j = get_neo4j_service()

            # 从查询中提取关键词（简单分词）
            from app.services.bm25_service import BM25Service
            tokenizer = BM25Service()
            keywords = tokenizer._tokenize(query)
            if not keywords:
                return []

            # 在 Neo4j 中搜索匹配的实体
            graph_knowledge_ids = set()
            for keyword in keywords[:3]:  # 取前 3 个关键词
                entities = neo4j.search_entities(keyword, limit=5)
                for entity in entities:
                    for kid in entity.get("knowledge_ids", []):
                        graph_knowledge_ids.add(kid)

            if not graph_knowledge_ids:
                return []

            # 从数据库获取知识条目
            # 2026-09-01 可见性硬边界 (与 search_semantic 同款):
            # 软删除 / drive / private 文档不可经图谱路召回
            stmt = (
                select(Knowledge)
                .where(
                    Knowledge.id.in_(list(graph_knowledge_ids)),
                    Knowledge.deleted_at.is_(None),
                    Knowledge.storage_mode == "kb",
                    Knowledge.visibility.in_(["team", "public"]),
                )
                .limit(top_k)
            )
            result = await self.db.execute(stmt)
            rows = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "title": r.title or "",
                    "content": (r.content or "")[:500],
                    "category": r.category,
                    "tags": r.tags,
                    "source": r.source,
                    "created_at": r.created_at,
                    "score": 0.7,  # 图谱匹配给固定分数
                    "retrieval_method": "graph",
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"图谱检索失败: {e}")
            return []

    def _normalize_scores(self, results: List[dict]) -> List[dict]:
        """分数归一化到 [0, 1]"""
        if not results:
            return results

        scores = [r.get("score", 0) for r in results]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        for r in results:
            r["normalized_score"] = round((r.get("score", 0) - min_score) / score_range, 4)

        return results

    async def _chunk_late_recall(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        category: Optional[str] = None,
    ) -> List[dict]:
        """追加的 late-chunking 召回；失败时返回空集，不影响父级检索。

        W-N-OBS: 失败必须显式记录 + 计数器 +1 (不允许静默吞掉),
        但仍 best-effort 返回空集不阻塞主流程.
        """
        import time
        from sqlalchemy import text

        stmt = text(
            """
            SELECT kc.knowledge_id, min(v <=> CAST(:query_embedding AS vector)) AS distance
            FROM knowledge_chunks AS kc
            CROSS JOIN LATERAL unnest(kc.chunk_embedding) AS vectors(v)
            JOIN knowledge AS k ON k.id = kc.knowledge_id
            WHERE kc.chunk_embedding IS NOT NULL
              AND (CAST(:category AS varchar) IS NULL OR k.category = CAST(:category AS varchar))
            GROUP BY kc.knowledge_id
            ORDER BY distance
            LIMIT CAST(:top_k AS integer)
            """
        )
        start = time.perf_counter()
        try:
            result = await self.db.execute(
                stmt,
                {"query_embedding": query_embedding, "category": category, "top_k": top_k},
            )
            rows = result.fetchall()
            elapsed_ms = round((time.perf_counter() - start) * 1000, 3)

            # W-N-OBS: 成功路径也记录 (延迟 + 计数), 供 grafana panel 1 (P95) / panel 2 (命中率) 使用
            try:
                from app.services.recall_observability import RecallObserver
                observer = RecallObserver.get()
                observer.record_chunk_late_recall(
                    success=True,
                    latency_ms=elapsed_ms,
                    result_count=len(rows),
                )
            except Exception as obs_exc:
                logger.debug(f"[W-N-OBS] observer record_chunk_late_recall skip: {obs_exc}")

            return [
                {
                    "id": row.knowledge_id,
                    "score": float(1.0 - row.distance),
                    "retrieval_method": "chunk_late",
                }
                for row in rows
            ]
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
            error_msg = f"{type(exc).__name__}: {exc}"

            # W-N-OBS 铁律: 失败必须显式 logger.warning + 计数器 +1, 不允许静默吞掉
            logger.warning(
                "chunk_late_recall FAILED latency_ms=%.3f category=%s top_k=%d error=%s",
                elapsed_ms,
                category,
                top_k,
                error_msg,
            )

            # W-N-OBS: 调用 RecallObserver 计数器 (失败路径, +1)
            try:
                from app.services.recall_observability import RecallObserver
                observer = RecallObserver.get()
                observer.record_chunk_late_recall(
                    success=False,
                    latency_ms=elapsed_ms,
                    result_count=0,
                    error_msg=error_msg,
                )
            except Exception as obs_exc:
                # 观测失败不阻断主流程 (best-effort)
                logger.debug(f"[W-N-OBS] observer record_chunk_late_recall skip: {obs_exc}")

            # 仍返回空集, 不 raise 阻塞父级检索 (best-effort 设计守恒)
            return []

    async def evaluate(
        self,
        eval_set: List[Dict],
        top_k: int = 5,
        ablations: Optional[Dict] = None,
    ) -> Dict:
        """RAG 检索评估

        Args:
            eval_set: [{query, relevant_ids: List[int]}]
            top_k: 评估 top_k
            ablations: 消融配置，如 {"vector_only": {"enable_bm25": False, "enable_graph": False}}

        Returns:
            {
                "recall@5": float, "precision@5": float, "mrr": float,
                "per_query": [...],
                "ablations": {name: {...}}
            }
        """
        async def _run_one(query: str, relevant: set, **config) -> Dict:
            config.setdefault("top_k", top_k)
            retrieved = await self.retrieve(query, **config)
            retrieved_ids = {r["id"] for r in retrieved if "id" in r}
            hits = retrieved_ids & relevant
            recall = len(hits) / len(relevant) if relevant else 0
            precision = len(hits) / len(retrieved_ids) if retrieved_ids else 0
            mrr = 0.0
            for i, r in enumerate(retrieved):
                if r.get("id") in relevant:
                    mrr = 1 / (i + 1)
                    break
            return {"recall": recall, "precision": precision, "mrr": mrr,
                    "retrieved_count": len(retrieved), "hits": list(hits)}

        async def _aggregate(per_query: List[Dict]) -> Dict:
            n = len(per_query)
            if n == 0:
                return {"recall@5": 0, "precision@5": 0, "mrr": 0, "per_query": []}
            return {
                "recall@5": sum(p["recall"] for p in per_query) / n,
                "precision@5": sum(p["precision"] for p in per_query) / n,
                "mrr": sum(p["mrr"] for p in per_query) / n,
                "per_query": per_query,
            }

        # 默认四路全开
        per_query = []
        for case in eval_set:
            relevant = set(case.get("relevant_ids", []))
            if not relevant:
                # 无标注 relevant_ids 时跳过（避免除零）
                per_query.append({"id": case.get("id"), "recall": 0, "precision": 0, "mrr": 0, "skipped": True})
                continue
            one = await _run_one(case["query"], relevant)
            per_query.append({"id": case.get("id"), **one})
        results = await _aggregate(per_query)

        # 消融
        if ablations:
            abl_results = {}
            for name, config in ablations.items():
                abl_per_query = []
                for case in eval_set:
                    relevant = set(case.get("relevant_ids", []))
                    if not relevant:
                        continue
                    one = await _run_one(case["query"], relevant, **config)
                    abl_per_query.append({"id": case.get("id"), **one})
                abl_results[name] = await _aggregate(abl_per_query)
            results["ablations"] = abl_results

        return results


async def retrieve_chunks_by_vector(
    db: AsyncSession,
    query_embedding: List[float],
    top_k: int = 10,
    knowledge_id: Optional[int] = None,
    strategy: Optional[str] = None,
):
    """W88 +14: hybrid_retriever 新增 chunk-level 召回入口

    parent-child retrieval (PR2 §11.2):
    - 输入: query embedding (调用方已有, PR1 一致化后)
    - 输出: chunk-level 命中 (含 knowledge_id + char_start + char_end)
    - 调用方拼 parent 上下文 window: text[char_start-WIN_BACK:char_end+WIN_FWD]

    Args:
        db: async session
        query_embedding: 已生成的 query 向量 (1024 维)
        top_k: 返回 chunk 数
        knowledge_id: 可选过滤 (None = 全库)
        strategy: 可选策略过滤 ('paragraph'/'heading'/'window')

    Returns:
        List[dict] 每条 {knowledge_id, chunk_id, chunk_index, content, char_start, char_end,
                        char_count, strategy, similarity, retrieval_method='chunk_vector'}

    Constraints (RAG v1.1 PR2 门禁):
    - chunk-level 召回 P95 ≤ 80ms (10w chunk) — pgvector HNSW 保证
    - chunk FK 100% 完整 (alembic 088 ON DELETE CASCADE)
    """
    from sqlalchemy import select

    from app.models.knowledge import Knowledge
    from app.models.knowledge_chunk import KnowledgeChunk

    stmt = select(
        KnowledgeChunk.id,
        KnowledgeChunk.knowledge_id,
        KnowledgeChunk.chunk_index,
        KnowledgeChunk.content,
        KnowledgeChunk.char_start,
        KnowledgeChunk.char_end,
        KnowledgeChunk.char_count,
        KnowledgeChunk.strategy,
        KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance"),
    ).join(
        Knowledge, Knowledge.id == KnowledgeChunk.knowledge_id
    )

    # chunk 必须有 embedding (召回前)
    stmt = stmt.where(KnowledgeChunk.embedding.is_not(None))

    # 2026-09-01 可见性硬边界 (与 search_semantic 同款过滤):
    # 软删除 / drive 模式 / private 文档的 chunk 不可召回
    stmt = stmt.where(
        Knowledge.deleted_at.is_(None),
        Knowledge.storage_mode == "kb",
        Knowledge.visibility.in_(["team", "public"]),
    )

    if knowledge_id is not None:
        stmt = stmt.where(KnowledgeChunk.knowledge_id == knowledge_id)
    if strategy is not None:
        stmt = stmt.where(KnowledgeChunk.strategy == strategy)

    # cosine 距离越小越相似, 取 top_k
    stmt = stmt.order_by("distance").limit(top_k)

    try:
        result = await db.execute(stmt)
        rows = result.fetchall()
    except Exception as e:
        logger.warning(f"chunk 向量检索失败: {e}")
        return []

    out = []
    for row in rows:
        out.append({
            "knowledge_id": row.knowledge_id,
            "chunk_id": row.id,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "char_start": row.char_start,
            "char_end": row.char_end,
            "char_count": row.char_count,
            "strategy": row.strategy,
            "similarity": float(1.0 - row.distance),  # 距离 → 相似度
            "score": float(1.0 - row.distance),
            "retrieval_method": "chunk_vector",
        })
    return out


# 全局工厂
def get_hybrid_retriever(db: AsyncSession) -> HybridRetriever:
    """获取混合检索器实例"""
    return HybridRetriever(db)


# =====================================================================
# PR4 (W90 +6..+8) 新增辅助函数 — 仅追加, 不改原 10 个 def 签名
# 派工 brief 要求: 不动 retrieve / _vector_search / _bm25_search /
# _graph_search / _refresh_bm25_index / _merge_results / _normalize_scores /
# evaluate / __init__ / get_hybrid_retriever
# 这些辅助函数是 HybridRetriever.retrieve 之外的"扩展 API"
# =====================================================================


async def _apply_weights(
    query: str,
    results_by_method: dict,
    weights: Optional["object"] = None,
    top_k: int = 10,
) -> List[dict]:
    """PR4 (W90 +6): 应用权重合并多路结果

    输入格式:
        results_by_method = {
            "vector": [{"id": 1, "score": 0.9, ...}, ...],
            "bm25":   [{"id": 5, "score": 12.3, ...}, ...],
            "graph":  [{"id": 3, "score": 0.7, ...}, ...],
            "rerank": [{"id": 1, "rerank_score": 0.95, ...}, ...],
        }

    合并规则: RRF (Reciprocal Rank Fusion) 归一化 + 权重加权
        RRF_score(doc) = Σ_m weight_m / (k + rank_m(doc))
        k = 60 (Cormack 2009 经典常数)

    Args:
        query: 原始查询 (保留参数供将来埋点, 当前未使用)
        results_by_method: 各路结果 dict
        weights: HybridWeights 实例, None 走默认权重
        top_k: 最终返回条数

    Returns:
        按 rrf_score 降序排的 top_k 列表
    """
    # 延迟 import (避免循环 + 0 production code diff 要求不动 hybrid_retriever 顶部 import)
    from app.services.hybrid_weight_config import (
        HybridWeights,
        apply_weights,
        DEFAULT_WEIGHTS,
    )

    if weights is None:
        weights = HybridWeights(**DEFAULT_WEIGHTS)

    return apply_weights(results_by_method, weights, top_k=top_k)


async def _apply_synonyms(query: str) -> str:
    """PR4 (W90 +4): 查询改写 — 用同义词字典展开

    例:
        "微气泡的 zeta 电位" → "microbubble的 zeta_potential"
        "Microbubble in water treatment" → "Microbubble in water_treatment"

    Args:
        query: 原始查询

    Returns:
        改写后查询 (canonical form)
    """
    # 延迟 import 同上
    from app.services.synonym_dict import expand_query
    return expand_query(query)


async def retrieve_with_weights(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    weights: Optional["object"] = None,
    enable_synonym_expansion: bool = True,
    enable_vector: bool = True,
    enable_bm25: bool = True,
    enable_graph: bool = True,
    enable_rerank: bool = True,
) -> List[dict]:
    """PR4 (W90 +5): 带权重 + 同义词扩展的检索入口 (新 API, 不动原 retrieve)

    WP7 (2026-09-01): observability hook 包裹原逻辑, 原 body 字面照搬到
    _retrieve_with_weights_impl (与 retrieve()/_retrieve_impl 同模式)。
    search_knowledge 工具的 RRF 主检索路径由此获得 search_logs 落库。
    """
    from app.services.recall_observability import RecallObserver
    observer = RecallObserver.get()
    async with observer.observe(
        caller_path="retrieve_with_weights",
        for_query=True,
        has_query_prompt=True,
        original_query=query,
    ) as obs_trace:
        return await _retrieve_with_weights_impl(
            db=db,
            query=query,
            top_k=top_k,
            category=category,
            weights=weights,
            enable_synonym_expansion=enable_synonym_expansion,
            enable_vector=enable_vector,
            enable_bm25=enable_bm25,
            enable_graph=enable_graph,
            enable_rerank=enable_rerank,
            obs_trace=obs_trace,
        )


async def _retrieve_with_weights_impl(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    weights: Optional["object"] = None,
    enable_synonym_expansion: bool = True,
    enable_vector: bool = True,
    enable_bm25: bool = True,
    enable_graph: bool = True,
    enable_rerank: bool = True,
    obs_trace: Any = None,
) -> List[dict]:
    """原 retrieve_with_weights body — WP7 拆分点, 不改任何逻辑

    与 HybridRetriever.retrieve 区别:
        1. 支持 synonym 改写 (enable_synonym_expansion=True 默认)
        2. 支持权重配置 (weights=HybridWeights(...)), intent 推断的权重真实参与 RRF 合并
        3. 2026-09-01 完整 RRF 实现 (此前 step 3 直接返回原 retrieve 结果, weights 无消费):
           cache lookup → intent (miss 才调) → per-method 并发检索 → RRF 合并 →
           multimodal 折算 → 单次 rerank → rerank_score 归一化 → temporal 乘子 →
           citation 提取 + final attach → cache 写最终结果

    Args:
        db: AsyncSession
        query: 查询字符串
        top_k: 返回条数
        category: 分类过滤
        weights: HybridWeights, None 走默认/intent 推断
        enable_synonym_expansion: 是否启用同义词改写
        enable_vector/bm25/graph/rerank: 各路开关

    Returns:
        检索结果列表 (按 rerank/temporal 调整后分数降序)
    """
    # 0) W99-RAG-1: Query Cache hook — 提到最前 (2026-09-01: 原顺序 intent→cache
    # 导致每次 cache 命中仍白付一次 LLM intent 调用)。命中直接返回最终结果 (含 citations)。
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    try:
        from app.rag.config import RAG_QUERY_CACHE_ENABLED as _CFG_ENABLED
        from app.services.rag_query_cache import get_rag_query_cache
        if _CFG_ENABLED:
            _cache = get_rag_query_cache()
            _cached = await _cache.get(query, user_id=user_id, tenant_id=tenant_id)
            if _cached is not None and _cached.get("results"):
                logger.debug(f"[W99-RAG-1] query cache HIT (exact) for query={query[:30]}")
                _cached_results = _CitationList(_cached["results"])
                try:
                    obs_trace.cache_hit = True
                    obs_trace.cache_similarity = _cached.get("cache_similarity")
                except Exception:
                    pass
                _finalize_obs_trace(obs_trace, _cached_results)
                _cached_results.citations = _cached.get("citations") or []
                return _cached_results
    except Exception as _e:
        logger.debug(f"[W99-RAG-1] query cache lookup skip: {_e}")

    # 0b) qa-bench v3.1 D3: retrieval_cache 5min TTL 短期路径
    try:
        from app.config import settings as _cfg
        from app.services.retrieval_cache import get_retrieval_cache as _get_rc
        if getattr(_cfg, "LLM_QA_BENCH_ROUNDS", 0) >= 1 and getattr(_cfg, "LLM_TEMPERATURE_QA_BENCH", 0.0) == 0.0:
            _rc = _get_rc()
            _cached_rc = await _rc.get(query=query, user_id=user_id, tenant_id=tenant_id)
            if _cached_rc is not None and _cached_rc.get("results"):
                logger.debug(f"[W100-D3] retrieval_cache HIT (qa-bench, 5min TTL) for query={query[:30]}")
                return _cached_rc["results"]
    except Exception as _e:
        logger.debug(f"[W100-D3] retrieval_cache lookup skip: {_e}")

    # -1) W100-RAG-3: Intent hook — cache miss 才调 (2026-09-01 顺序修正 + 1.8 超时)
    # 推断 query 意图 → 决定 HybridWeights, 真实参与 RRF 合并
    if weights is None:
        try:
            from app.rag.config import INTENT_CLASSIFIER_ENABLED as _IC_ENABLED
            if _IC_ENABLED:
                from app.rag.intent_router import get_intent_router
                _router = get_intent_router()
                weights = await asyncio.wait_for(_router.route(query), timeout=3.0)
                logger.debug(f"[W100-RAG-3] intent-inferred weights attached: {weights}")
        except asyncio.TimeoutError:
            logger.debug("[W100-RAG-3] intent hook timeout (3s), 走默认 weights")
        except Exception as _e:
            logger.debug(f"[W100-RAG-3] intent hook skip: {_e}")

    # 1) 同义词改写
    expanded_query = await _apply_synonyms(query) if enable_synonym_expansion else query

    # 2) per-method 并发检索 + RRF 合并 (2026-09-01 完整实现)
    retriever = HybridRetriever(db)
    results_by_method = await retriever.retrieve_per_method(
        query=expanded_query,
        candidate_k=top_k * 5,
        category=category,
        enable_vector=enable_vector,
        enable_bm25=enable_bm25,
        enable_graph=enable_graph,
    )

    from app.services.hybrid_weight_config import HybridWeights, apply_weights
    if not isinstance(weights, HybridWeights):
        weights = HybridWeights()
    raw_results = apply_weights(results_by_method, weights, top_k=max(top_k * 2, 10))

    # WP7: 候选数埋点 (rerank 前各路 union)
    try:
        obs_trace.candidate_k = sum(len(v) for v in results_by_method.values())
    except Exception:
        pass

    # 3) W100-RAG-5: Multimodal Retriever 第 5 路 — rerank 前折算进 score
    # 注意: 在空判断之前执行 — 文本四路全空但图片命中时, standalone 图片结果仍应返回
    try:
        from app.rag import config as _rag_config

        if _rag_config.MULTIMODAL_RETRIEVER_ENABLED:
            from app.services.multimodal_retriever import MultimodalRetriever

            _image_weight = float(
                getattr(weights, "image", _rag_config.MULTIMODAL_RETRIEVER_WEIGHT)
            )
            if _image_weight > 0:
                _image_results = await MultimodalRetriever(db).search_images(
                    query=query,
                    top_k=top_k,
                )
                if _image_results:
                    try:
                        obs_trace.image_score = max(
                            float(_i.get("similarity") or 0.0) for _i in _image_results
                        )
                    except Exception:
                        pass
                    _merged_by_id = {
                        item.get("id"): dict(item)
                        for item in raw_results
                        if item.get("id") is not None
                    }
                    for _image in _image_results:
                        _knowledge_id = _image.get("knowledge_id")
                        if _knowledge_id is None:
                            continue
                        _weighted_image_score = float(_image.get("score") or 0.0) * _image_weight
                        _existing = _merged_by_id.get(_knowledge_id)
                        if _existing is None:
                            _standalone = dict(_image)
                            _standalone["score"] = _weighted_image_score
                            _standalone["image_score"] = float(_image.get("score") or 0.0)
                            _merged_by_id[_knowledge_id] = _standalone
                        else:
                            _existing["image_score"] = float(_image.get("score") or 0.0)
                            _existing["image_boost"] = _weighted_image_score
                            _existing.setdefault("image_matches", []).append(dict(_image))
                            _existing.setdefault("retrieval_methods", []).append("image")
                            _existing["score"] = float(_existing.get("score") or 0.0) + _weighted_image_score
                    raw_results = sorted(
                        _merged_by_id.values(),
                        key=lambda item: float(item.get("score") or 0.0),
                        reverse=True,
                    )[: max(top_k * 2, 10)]
                    logger.debug(
                        "[W100-RAG-5] multimodal hook applied: images=%d weight=%.3f",
                        len(_image_results),
                        _image_weight,
                    )
    except Exception as _e:
        logger.debug(f"[W100-RAG-5] multimodal hook skip: {_e}")

    if not raw_results:
        return []

    # 4) W100-RAG-4: Reranker v2 hook — 单次精排 (2026-09-01 去双跑)
    _did_rerank = False
    if enable_rerank:
        try:
            from app.rag.config import RERANKER_BACKEND as _RR_BACKEND
            from app.rag.config import RERANKER_MODEL as _RR_MODEL
            from app.rag.config import RERANKER_API_KEY as _RR_KEY
            from app.services.reranker_v2 import get_reranker_v2_instance

            _reranker = get_reranker_v2_instance(
                backend=_RR_BACKEND, model=_RR_MODEL, api_key=_RR_KEY
            )
            if _reranker is not None:
                for _idx, _c in enumerate(raw_results):
                    _c["original_index"] = _idx
                _reranked = await _reranker.rerank(
                    query=query, candidates=raw_results, top_k=top_k
                )
                if _reranked:
                    raw_results = _reranked
                    _did_rerank = True
                    logger.debug(f"[W100-RAG-4] reranker hook applied: backend={_RR_BACKEND}")
        except Exception as _e:
            logger.debug(f"[W100-RAG-4] reranker hook skip: {_e}")

    if not _did_rerank:
        # 未精排: 截断到 top_k (rerank 路径已截)
        raw_results = raw_results[:top_k]

    # 4a) WP8 (2026-09-01): rerank_score → normalized_score min-max 归一化回填
    # (cross-encoder logits 无界; RRF score 尺度 ~0.006 也与 [0,1] 阈值语义不符)
    _backfill_normalized_scores(raw_results)

    # 4b) W100-RAG-6: Temporal Retriever 时间衰减 — 最终乘子 (类 20.132 语义)
    # 2026-09-01: 各路结果已带 created_at (WP1.5), 衰减真实生效;
    # rerank 后改乘 normalized_score (WP8: rerank_score logits 无界)
    try:
        from app.rag.config import (
            TEMPORAL_DECAY_ENABLED as _T_ENABLED,
            TEMPORAL_BOOST_YEARS as _T_BOOST_YEARS,
            TEMPORAL_BOOST_FACTOR as _T_BOOST_FACTOR,
            TEMPORAL_DECAY_YEARS as _T_DECAY_YEARS,
            TEMPORAL_DECAY_FACTOR as _T_DECAY_FACTOR,
        )
        if _T_ENABLED and raw_results:
            from app.services.temporal_retriever import TemporalRetriever

            _temporal = TemporalRetriever()
            from app.models.base import utcnow as _utcnow
            _now = _utcnow()
            for _r in raw_results:
                _kid = _r.get("id")
                _created = _r.get("created_at")
                if _kid is None or _created is None:
                    _r["temporal_weight"] = 1.0
                    continue
                _t = _temporal.compute_temporal_weight(
                    created_at=_created,
                    now=_now,
                    boost_years=_T_BOOST_YEARS,
                    boost_factor=_T_BOOST_FACTOR,
                    decay_years=_T_DECAY_YEARS,
                    decay_factor=_T_DECAY_FACTOR,
                )
                _r["temporal_weight"] = round(_t, 4)
                _base = float(_r.get("normalized_score") or _r.get("score") or 0.0)
                _r["score"] = round(_base * _t, 6)
            raw_results = sorted(
                raw_results,
                key=lambda item: float(item.get("score", 0.0)),
                reverse=True,
            )[:top_k]
            logger.debug("[W100-RAG-6] temporal hook applied: %d results", len(raw_results))
    except Exception as _e:
        logger.debug(f"[W100-RAG-6] temporal hook skip: {_e}")

    # 5) W99-RAG-2: Citation hook — 在 rerank 之后 (结果已带 chunk_id, WP1.2)
    # 2026-09-01 增强: doc 级命中 (vector/bm25 路无 chunk_id) 从 chunk 路候选
    # 补挂最佳 chunk — citation 覆盖不再依赖 chunk 路进 final top-k, 0 额外查询
    _chunk_best: Dict[Any, dict] = {}
    for _c in (results_by_method.get("chunk") or []):
        _kid = _c.get("id")
        if _kid is not None and _kid not in _chunk_best:
            _chunk_best[_kid] = _c  # chunk 路候选已按相似度降序
    for _r in raw_results:
        if _r.get("chunk_id") is None:
            _c = _chunk_best.get(_r.get("id"))
            if _c is not None:
                _r["chunk_id"] = _c.get("chunk_id")
                _r["char_start"] = _c.get("char_start")
                _r["char_end"] = _c.get("char_end")

    _cached_citations: List[Dict[str, Any]] = []
    try:
        from app.rag.config import CITATION_ENABLED as _CIT_ENABLED
        from app.rag.config import CITATION_MAX_PER_RESULT as _CIT_MAX
        if _CIT_ENABLED and raw_results:
            from app.services.citation_extractor import CitationExtractor

            extractor = CitationExtractor(db)
            _cached_citations = await extractor.extract_citations(
                query=query,
                results=raw_results,
                max_per_result=_CIT_MAX,
            )
            try:
                obs_trace.citation_count = len(_cached_citations)
            except Exception:
                pass
    except Exception as _e:
        logger.debug(f"[W99-RAG-2] citation hook skip: {_e}")

    # 6) W99-RAG-1: 写缓存 — post-rerank + 含 citations (2026-09-01: 原写 pre-rerank 结果)
    if raw_results:
        try:
            from app.rag.config import RAG_QUERY_CACHE_ENABLED as _CFG_ENABLED
            from app.services.rag_query_cache import get_rag_query_cache
            if _CFG_ENABLED:
                _cache = get_rag_query_cache()
                _top_score = float(raw_results[0].get("score", 0.0)) if raw_results else 0.0
                _retrieval_method = raw_results[0].get("retrieval_method", "hybrid") if raw_results else "hybrid"
                await _cache.set(
                    query=query,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    result={
                        "results": raw_results,
                        "citations": _cached_citations,
                        "retrieval_method": _retrieval_method,
                        "score": _top_score,
                        "top_k": top_k,
                    },
                )
        except Exception as _e:
            logger.debug(f"[W99-RAG-1] query cache set skip: {_e}")

    # 7) citation final attach (类 20.133 机制保留)
    # 2026-09-01 P0 修复: plain list 不支持属性赋值, 原 attach 在生产静默
    # 失败 (AttributeError → debug log)。改用 _CitationList 子类承载。
    if not isinstance(raw_results, _CitationList):
        raw_results = _CitationList(raw_results)
    raw_results.citations = _cached_citations or []

    _finalize_obs_trace(obs_trace, raw_results)
    return raw_results


# ============================================================================
# PR8 (W94 +6): KG retrieval path — 模块级新增, 0 改 HybridRetriever 类方法
#
# 派工 brief 段 2: "hybrid_retriever.py —— 仅新增 KG retrieval path
#                  (不改 4 路开关默认)"
#
# 类 20 #35 据实上报 — brief 错配 #3 (graph path 已存在):
# brief 假设 "KG retrieval path" 为新增. 实测 HybridRetriever._graph_search
# (L218-267) 已存在 Neo4j 图谱路, retrieve/_retrieve_impl 4 路已含 enable_graph.
# 处置: **不改 _graph_search / retrieve / _retrieve_impl / 4 路权重默认**,
# 改为模块级新增第 5 路 (entity_link), 沿用 PR4 retrieve_with_weights 已批模式
# ("新 API, 不动原 retrieve"). 件 4a `^[+-]def` 计入模块级 def 但 brief 段 2
# 显式授权 (件 4b), 且 0 类方法改.
#
# 与已有 graph 路 (_graph_search) 的关系: **并列互补, 非替代**
# - graph 路 = Neo4j 后端 (外部服务, driver None 时整路返空)
# - entity_link 路 = PostgreSQL kg_entities (无外部依赖, PG 内置降级安全)
# 两路可同时开 (enable_graph + enable_entity_link), 结果合并去重.
# ============================================================================

# 第 5 路默认权重 — 保守值, 低于 vector (0.5) 高于 graph (0.15)
# 注: 不改 hybrid_weight_config.py 的 4 路默认 (PR4 已锁), 本常量独立
ENTITY_LINK_DEFAULT_WEIGHT: float = 0.2


async def retrieve_with_entity_link(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    *,
    enable_entity_link: bool = True,
    entity_link_weight: float = ENTITY_LINK_DEFAULT_WEIGHT,
    enable_vector: bool = True,
    enable_bm25: bool = True,
    enable_graph: bool = True,
    enable_rerank: bool = True,
) -> List[dict]:
    """PR8 (W94 +6): 4 路 + 实体链第 5 路检索入口 (新 API, 不动原 retrieve)

    与 HybridRetriever.retrieve / retrieve_with_weights 的区别:
        1. 在原 4 路结果之上**并入** entity_link 第 5 路 (PostgreSQL kg_entities)
        2. 不改原 4 路开关默认 (enable_vector/bm25/graph/rerank 全部透传)
        3. entity_link 路失败时静默降级为纯 4 路结果 (0 regression)
        4. 委托给原 retrieve (不破坏既有行为, PR4 retrieve_with_weights 同模式)

    Args:
        db: AsyncSession
        query: 查询字符串
        top_k: 返回条数
        category: 分类过滤
        enable_entity_link: 第 5 路开关 (False 时行为与原 retrieve 完全一致)
        entity_link_weight: 第 5 路分数权重
        enable_vector/bm25/graph/rerank: 原 4 路开关 (原样透传, 默认不变)

    Returns:
        检索结果列表 (按 score 降序, 含 retrieval_method 标识路来源)
    """
    # 1) 原 4 路 — 完全委托, 0 行为改变
    retriever = HybridRetriever(db)
    base_results = await retriever.retrieve(
        query=query,
        top_k=top_k,
        category=category,
        enable_vector=enable_vector,
        enable_bm25=enable_bm25,
        enable_graph=enable_graph,
        enable_rerank=enable_rerank,
    )

    if not enable_entity_link:
        return base_results

    # 2) 第 5 路 entity_link — 失败静默降级 (0 regression 保证)
    try:
        from app.services.entity_link_recall import get_entity_link_recall

        recall = get_entity_link_recall(db)
        entity_results = await recall.retrieve(query, top_k=top_k)
    except Exception as e:
        logger.warning(f"[PR8] entity_link 第 5 路跳过: {e}")
        return base_results

    if not entity_results:
        return base_results

    # 3) 合并去重 — 同 id 取最高分, entity_link 分数按 weight 缩放
    merged: Dict[int, dict] = {}
    for r in base_results:
        rid = r.get("id")
        if rid is not None:
            merged[rid] = dict(r)

    for r in entity_results:
        rid = r.get("id")
        if rid is None:
            continue
        weighted_score = float(r.get("score") or 0.0) * entity_link_weight
        existing = merged.get(rid)
        if existing is None:
            new_row = dict(r)
            new_row["score"] = weighted_score
            merged[rid] = new_row
            continue
        # 已在 4 路结果中 → 实体链命中作为**加成**, 并标注双路命中
        existing["score"] = float(existing.get("score") or 0.0) + weighted_score
        existing["entity_link_boost"] = weighted_score
        if r.get("entity_names"):
            existing["entity_names"] = r["entity_names"]

    out = sorted(
        merged.values(), key=lambda d: float(d.get("score") or 0.0), reverse=True
    )
    return out[:top_k]


async def count_kg_entities(db: AsyncSession) -> int:
    """门禁 c 度量代理 (E39 必真查询) — 转调 entity_link_recall.count_entities"""
    try:
        from app.services.entity_link_recall import get_entity_link_recall

        return await get_entity_link_recall(db).count_entities()
    except Exception as e:
        logger.warning(f"[PR8] kg_entities 计数失败: {e}")
        return 0
