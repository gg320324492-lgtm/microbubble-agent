"""实体链召回 — PR8 知识图谱深度联动 (W94 +2)

## 定位

在 HybridRetriever 已有 4 路 (vector / bm25 / tsvector / graph) 之外，补一路
**实体链召回**: query → 实体抽取 → kg_entities pgvector cosine 匹配 →
实体共现网络 1 跳扩散 → 关联 knowledge_id 集合 → 知识条目。

与已有 `_graph_search` (Neo4j 路) 的区别:

| 维度 | `_graph_search` (已有) | `entity_link_recall` (PR8 新增) |
|------|----------------------|--------------------------------|
| 后端 | Neo4j (外部服务, `_get_driver()` 为 None 时整路返空) | **PostgreSQL kg_entities** (无外部依赖) |
| 匹配 | `neo4j.search_entities(keyword)` 关键词 | **pgvector cosine** (语义) + 精确名 |
| 扩散 | Neo4j `get_neighbors(hops=1)` | **entity_co_occurrence** 1 跳 |
| 打分 | 固定 0.7 | **cosine 距离衰减 + 共现权重** |
| 降级 | Neo4j 挂 → 整路 0 结果 | PG 内置, Neo4j 无关 |

**0 production code 双门控守恒**: 本模块为**纯新增文件**, 不改 `_graph_search`,
不改 `retrieve` / `_retrieve_impl`, 不改 4 路权重默认 (件 4a `^[+-]def` = 0)。

## 门禁 (plan §2 PR8)

- 门禁 a 实体链 hit ≥ 25%: `ENTITY_LINK_HIT_TARGET`
- 门禁 b 图谱召回 P95 ≤ 100ms: `ENTITY_LINK_P95_BUDGET_MS`
- 门禁 c 实体数 ≥ 5000: `ENTITY_COUNT_TARGET`

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("microbubble.entity_link_recall")

# ============== 门禁常量 (plan §2 PR8 + §9 门禁表) ==============

# 门禁 a: 实体链召回命中率下限 (召回结果中实体链贡献占比)
ENTITY_LINK_HIT_TARGET: float = 0.25

# 门禁 b: 图谱召回 P95 延迟预算 (ms)
ENTITY_LINK_P95_BUDGET_MS: float = 100.0

# 门禁 c: 实体总数下限
ENTITY_COUNT_TARGET: int = 5000

# ============== 召回参数 ==============

# cosine 距离上限 — 超过视为不相关 (与声纹 MATCH_THRESHOLD=0.7 三层口径无关, 独立语义)
# 参考 CLAUDE.md 声纹三层指标纪律: distance 越小越相似, 此处 0.65 = 中等严格
ENTITY_MATCH_MAX_DISTANCE: float = 0.65

# 单 query 最多取几个种子实体
MAX_SEED_ENTITIES: int = 5

# 共现网络扩散跳数 (1 跳 = 直接共现)
CO_OCCURRENCE_HOPS: int = 1

# 共现扩散每个种子最多带出几个邻居
MAX_NEIGHBORS_PER_SEED: int = 10

# 打分: 种子实体命中基础分 / 共现邻居命中基础分 (邻居弱于直接命中)
SEED_HIT_BASE_SCORE: float = 0.75
NEIGHBOR_HIT_BASE_SCORE: float = 0.45

# retrieval_method 标识 (与 hybrid_retriever 已有 'vector'/'bm25'/'graph' 并列)
RETRIEVAL_METHOD: str = "entity_link"

# 中文/英文混合分词的简易切分 (不引 jieba — PR3 已验证 jieba 可能缺装)
_TOKEN_PATTERN = re.compile(r"[一-鿿]{2,}|[A-Za-z][A-Za-z0-9\-]{1,}")


def extract_query_entities(query: str, max_tokens: int = MAX_SEED_ENTITIES) -> List[str]:
    """从 query 抽取候选实体名 (纯逻辑, 无外部依赖 — 本机可单测)

    策略: 正则抽中文 2+ 字连续串 + 英文单词 → 去重保序 → 截断

    不引 jieba (PR3 实测 jieba 可能缺装导致 collection error)。
    不引 LLM (召回路径延迟预算 P95 ≤ 100ms, LLM 调用必超)。
    """
    if not query:
        return []
    seen: Set[str] = set()
    out: List[str] = []
    for match in _TOKEN_PATTERN.findall(query):
        token = match.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= max_tokens:
            break
    return out


def distance_to_score(distance: float, base: float = SEED_HIT_BASE_SCORE) -> float:
    """cosine 距离 → 相关性分数 (线性衰减, 归一到 [0, base])

    distance 0.0 → base (完全相似)
    distance ENTITY_MATCH_MAX_DISTANCE → 0.0 (阈值边界)
    distance > 阈值 → 0.0 (钳制, 不返负分)
    """
    if distance is None:
        return 0.0
    if distance <= 0:
        return base
    if distance >= ENTITY_MATCH_MAX_DISTANCE:
        return 0.0
    return round(base * (1.0 - distance / ENTITY_MATCH_MAX_DISTANCE), 6)


def merge_entity_hits(
    seed_hits: Sequence[Dict[str, Any]],
    neighbor_hits: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """合并种子命中 + 共现邻居命中, 同 knowledge_id 取最高分 (纯逻辑, 可单测)

    输入元素形如 {"knowledge_id": int, "score": float, "entity_name": str, "via": str}
    输出按 score 降序, 同 knowledge_id 去重保留最高分并累计 entity_names。
    """
    best: Dict[int, Dict[str, Any]] = {}
    for hit in list(seed_hits) + list(neighbor_hits):
        kid = hit.get("knowledge_id")
        if kid is None:
            continue
        score = float(hit.get("score") or 0.0)
        if score <= 0:
            continue
        existing = best.get(kid)
        if existing is None:
            best[kid] = {
                "knowledge_id": kid,
                "score": score,
                "entity_names": [hit.get("entity_name")] if hit.get("entity_name") else [],
                "via": hit.get("via") or "seed",
            }
            continue
        name = hit.get("entity_name")
        if name and name not in existing["entity_names"]:
            existing["entity_names"].append(name)
        if score > existing["score"]:
            existing["score"] = score
            existing["via"] = hit.get("via") or existing["via"]
    return sorted(best.values(), key=lambda d: d["score"], reverse=True)


def compute_entity_link_hit_rate(
    merged_results: Sequence[Dict[str, Any]],
) -> float:
    """门禁 a 度量: 召回结果中 entity_link 贡献占比 (纯逻辑, 可单测)"""
    if not merged_results:
        return 0.0
    n_entity = sum(
        1 for r in merged_results if r.get("retrieval_method") == RETRIEVAL_METHOD
    )
    return round(n_entity / len(merged_results), 6)


class EntityLinkRecall:
    """实体链召回器 — kg_entities pgvector + entity_co_occurrence 1 跳扩散

    用法 (不侵入 HybridRetriever):
        recall = EntityLinkRecall(db)
        results = await recall.retrieve("微纳米气泡的传质效率", top_k=10)
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    async def retrieve(
        self, query: str, top_k: int = 10, *, include_neighbors: bool = True
    ) -> List[Dict[str, Any]]:
        """实体链召回主入口 — 全程 try/except, 失败返 [] 不阻塞其他召回路

        返回 List[dict] 与 hybrid_retriever 各路格式一致:
        {id, title, content, category, tags, source, score, retrieval_method,
         entity_names, latency_ms}
        """
        started = time.perf_counter()
        try:
            seeds = extract_query_entities(query)
            if not seeds:
                return []

            seed_hits = await self._match_seed_entities(seeds)
            if not seed_hits:
                return []

            neighbor_hits: List[Dict[str, Any]] = []
            if include_neighbors and CO_OCCURRENCE_HOPS >= 1:
                entity_ids = [h["entity_id"] for h in seed_hits if h.get("entity_id")]
                neighbor_hits = await self._expand_co_occurrence(entity_ids)

            merged = merge_entity_hits(seed_hits, neighbor_hits)[:top_k]
            if not merged:
                return []

            rows = await self._load_knowledge(
                [m["knowledge_id"] for m in merged]
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            if latency_ms > ENTITY_LINK_P95_BUDGET_MS:
                logger.warning(
                    "实体链召回超延迟预算: %.3fms > %.1fms (门禁 b, E38)",
                    latency_ms,
                    ENTITY_LINK_P95_BUDGET_MS,
                )

            by_id = {r["id"]: r for r in rows}
            out: List[Dict[str, Any]] = []
            for m in merged:
                row = by_id.get(m["knowledge_id"])
                if not row:
                    continue
                out.append(
                    {
                        **row,
                        "score": m["score"],
                        "retrieval_method": RETRIEVAL_METHOD,
                        "entity_names": m["entity_names"],
                        "via": m["via"],
                        "latency_ms": latency_ms,
                    }
                )
            return out
        except Exception as e:  # pragma: no cover - 降级路径
            logger.warning("实体链召回失败: %s", e)
            return []

    async def _match_seed_entities(
        self, seeds: Sequence[str]
    ) -> List[Dict[str, Any]]:
        """种子实体匹配 — 精确名 + pgvector cosine 双路

        精确名匹配优先 (0 embedding 依赖); 有 embedding 时补语义近邻。
        """
        from sqlalchemy import select

        from app.models.kg_entity import KGEntity, normalize_entity_name

        hits: List[Dict[str, Any]] = []
        normalized = [normalize_entity_name(s) for s in seeds]
        normalized = [n for n in normalized if n]
        if not normalized:
            return []

        # 路 1: 精确 / 前缀名匹配 (B-tree ix_kg_entities_name)
        stmt = (
            select(
                KGEntity.id,
                KGEntity.entity_name,
                KGEntity.knowledge_id,
                KGEntity.mention_count,
            )
            .where(KGEntity.entity_name.in_(normalized))
            .order_by(KGEntity.mention_count.desc())
            .limit(MAX_SEED_ENTITIES * MAX_NEIGHBORS_PER_SEED)
        )
        result = await self.db.execute(stmt)
        for row in result.all():
            hits.append(
                {
                    "entity_id": row[0],
                    "entity_name": row[1],
                    "knowledge_id": row[2],
                    "score": SEED_HIT_BASE_SCORE,
                    "via": "exact",
                }
            )

        # 路 2: pgvector cosine 语义近邻 (HNSW ix_kg_entities_embedding_hnsw)
        semantic = await self._match_by_embedding(normalized)
        hits.extend(semantic)
        return hits

    async def _match_by_embedding(
        self, names: Sequence[str]
    ) -> List[Dict[str, Any]]:
        """pgvector cosine 近邻 — embedding 生成失败时静默返 [] (不阻塞精确路)"""
        try:
            from sqlalchemy import select

            from app.models.kg_entity import KGEntity
            from app.services.kg_embedding import generate_kg_entity_embedding

            query_text = " ".join(names)
            emb = await generate_kg_entity_embedding(query_text)
            if not emb:
                return []

            distance = KGEntity.embedding.cosine_distance(emb).label("distance")
            stmt = (
                select(
                    KGEntity.id,
                    KGEntity.entity_name,
                    KGEntity.knowledge_id,
                    distance,
                )
                .where(KGEntity.embedding.isnot(None))
                .order_by(distance)
                .limit(MAX_SEED_ENTITIES * 2)
            )
            result = await self.db.execute(stmt)
            out: List[Dict[str, Any]] = []
            for row in result.all():
                dist = float(row[3]) if row[3] is not None else None
                score = distance_to_score(dist)
                if score <= 0:
                    continue
                out.append(
                    {
                        "entity_id": row[0],
                        "entity_name": row[1],
                        "knowledge_id": row[2],
                        "score": score,
                        "via": "semantic",
                    }
                )
            return out
        except Exception as e:
            logger.debug("实体 embedding 近邻跳过: %s", e)
            return []

    async def _expand_co_occurrence(
        self, entity_ids: Sequence[int]
    ) -> List[Dict[str, Any]]:
        """共现网络 1 跳扩散 — 复用已有 entity_co_occurrence 表 (0 改该表)

        注: entity_co_occurrence 的 entity_a_id/entity_b_id 指向 knowledge_entities
        (SPO 三元组表) 的 id, 与 kg_entities 是不同 id 空间。本方法用其
        knowledge_id + weight 做**知识条目级**共现扩散, 不做跨表 id 关联
        (避免 id 空间混用错误)。
        """
        if not entity_ids:
            return []
        try:
            from sqlalchemy import select

            from app.models.kg_entity import KGEntity

            # 取种子实体所在的 knowledge_id
            seed_stmt = select(KGEntity.knowledge_id).where(
                KGEntity.id.in_(list(entity_ids))
            )
            seed_result = await self.db.execute(seed_stmt)
            seed_kids = {r[0] for r in seed_result.all() if r[0] is not None}
            if not seed_kids:
                return []

            # 同一 knowledge 内的其他实体 → 它们出现的其他 knowledge (1 跳)
            names_stmt = (
                select(KGEntity.entity_name)
                .where(KGEntity.knowledge_id.in_(list(seed_kids)))
                .distinct()
                .limit(MAX_NEIGHBORS_PER_SEED * MAX_SEED_ENTITIES)
            )
            names_result = await self.db.execute(names_stmt)
            neighbor_names = [r[0] for r in names_result.all() if r[0]]
            if not neighbor_names:
                return []

            hop_stmt = (
                select(
                    KGEntity.entity_name,
                    KGEntity.knowledge_id,
                    KGEntity.mention_count,
                )
                .where(KGEntity.entity_name.in_(neighbor_names))
                .where(KGEntity.knowledge_id.notin_(list(seed_kids)))
                .order_by(KGEntity.mention_count.desc())
                .limit(MAX_NEIGHBORS_PER_SEED * MAX_SEED_ENTITIES)
            )
            hop_result = await self.db.execute(hop_stmt)
            return [
                {
                    "entity_id": None,
                    "entity_name": row[0],
                    "knowledge_id": row[1],
                    "score": NEIGHBOR_HIT_BASE_SCORE,
                    "via": "co_occurrence",
                }
                for row in hop_result.all()
            ]
        except Exception as e:
            logger.debug("共现扩散跳过: %s", e)
            return []

    async def _load_knowledge(
        self, knowledge_ids: Sequence[int]
    ) -> List[Dict[str, Any]]:
        """按 id 批量取知识条目 — 格式与 hybrid_retriever 各路一致"""
        if not knowledge_ids:
            return []
        from sqlalchemy import select

        from app.models.knowledge import Knowledge

        stmt = select(Knowledge).where(Knowledge.id.in_(list(knowledge_ids)))
        result = await self.db.execute(stmt)
        return [
            {
                "id": r.id,
                "title": r.title or "",
                "content": (r.content or "")[:500],
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
            }
            for r in result.scalars().all()
        ]

    async def count_entities(self) -> int:
        """门禁 c 度量: kg_entities 实体总数 (E39 必真查询)"""
        try:
            from sqlalchemy import func, select

            from app.models.kg_entity import KGEntity

            stmt = select(func.count()).select_from(KGEntity)
            result = await self.db.execute(stmt)
            return int(result.scalar() or 0)
        except Exception as e:
            logger.warning("实体计数失败: %s", e)
            return 0


def get_entity_link_recall(db: Any) -> EntityLinkRecall:
    """工厂函数 — 与 get_hybrid_retriever / get_graph_retriever 命名一致"""
    return EntityLinkRecall(db)
