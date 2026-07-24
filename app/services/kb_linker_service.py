"""KB linker — 通过 pgvector 余弦相似度建 KB 关联 (W68 第 10 批 B-4, 2026-07-24)

## 背景

qa-bench 自动入库的 KB 卡片, 跟已有 KB 之间**完全无关联**, 检索时只能依赖关键词/向量匹配,
但缺持久化的"KB 与 KB 之间的关联边" (`kb_links` 表). 这导致:
- RAG 检索时不能跨 KB 联合召回
- 知识图谱视图 (`KnowledgeGraphView.vue`) 只有 entity 共现, 无 KB 整体相似度
- 用户问"微纳米气泡相关 KB"时只能 search 不能 browse

本服务在 KB 入闭环的 **标注** stage 跑 top-3 vector search → 写 `kb_links` 表.

## 设计

- `link_kb_to_top_k(knowledge_id, top_k=3)` → 找最相似的 K 个 KB → 写 `kb_links`
- `find_related(knowledge_id, limit=10)` → 读 `kb_links` 反查关联 KB
- 相似度算法: pgvector `<=>` 余弦距离, score = 1 - distance
- 同对 KB 只写 1 次 (UNIQUE knowledge_id_a + knowledge_id_b, service 层强制 a < b)

## 依赖

- knowledge.embedding 列 (pgvector Vector(1024), v29 Qwen3-Embedding-0.6B)
- pgvector 已 enable (main.py 启动时自动安装)
- `kb_links` 表 (alembic 072)

## 调用方

- `app/services/kb_closed_loop_service.py` stage=STAGE_LABELING 时调
- 后续 PR: KnowledgeGraphView.vue 用 `find_related` 渲染关联边

## 纪律

- 0 production code 改动铁律 (W68 第 10 批): 本服务 + 配套表全部新增, 不动老路径
- 跨 event loop 安全 (CLAUDE.md 519/527 行铁律): db session 通过参数注入
- 禁全表 LIKE (CLAUDE.md 2026-06 经验): 只走 embedding 向量检索, 不做关键词模糊匹配
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_link import (
    KbLink,
    LINK_TYPE_AUTO,
    LINK_TYPE_DERIVED,
    LINK_TYPE_MANUAL,
    VALID_LINK_TYPES,
)
from app.models.knowledge import Knowledge

logger = logging.getLogger("microbubble.kb_linker_service")


# ============== 配置常量 ==============

# top-k 关联数 (默认 3, 与 plan 一致)
DEFAULT_TOP_K = 3
MAX_TOP_K = 10

# 相似度阈值 (低于此值不写关联)
MIN_SIMILARITY_SCORE = 0.65

# 排除自己 (knowledge_id)
SELF_EXCLUDE_ID = -1


# ============== 异常 ==============

class KbLinkerError(Exception):
    """KB linker 业务异常 (对外暴露, 不暴露 SQLAlchemy 内部)"""


# ============== 核心: 自动建关联 ==============

async def link_kb_to_top_k(
    db: AsyncSession,
    knowledge_id: int,
    *,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = MIN_SIMILARITY_SCORE,
) -> List[KbLink]:
    """为指定 KB 找最相似的 top_k 个 KB → 写 kb_links 表

    算法:
    1. 拿 knowledge.embedding (pgvector Vector(1024))
    2. 算 embedding <=> other.embedding 距离 (其他 KB, 排除自己)
    3. 取 top_k 最低距离 → score = 1 - distance
    4. 过滤 score >= min_score → 写 kb_links (UNIQUE a < b)

    Args:
        db: AsyncSession (调用方注入, 跨 loop 安全)
        knowledge_id: 主 KB id
        top_k: 取前 K 个 (默认 3, 上限 10)
        min_score: 最低相似度阈值 (默认 0.65, 低于此值不写关联)

    Returns:
        新写入的 KbLink 列表 (空 list 表示无关联)

    Raises:
        KbLinkerError: KB 不存在或无 embedding
    """
    if top_k < 1:
        top_k = DEFAULT_TOP_K
    if top_k > MAX_TOP_K:
        top_k = MAX_TOP_K

    # 1. 拿主 KB
    main_kb = await db.get(Knowledge, knowledge_id)
    if main_kb is None:
        raise KbLinkerError(f"Knowledge id={knowledge_id} 不存在")
    if main_kb.embedding is None:
        raise KbLinkerError(
            f"Knowledge id={knowledge_id} 无 embedding, 需先跑 polling"
        )

    # 2. pgvector 余弦距离算 top_k
    #    pgvector.cosine_distance(a, b) = 1 - cosine_similarity(a, b)
    #    score = 1 - distance = cosine_similarity
    distance_col = Knowledge.embedding.cosine_distance(main_kb.embedding).label(
        "distance"
    )
    score_col = (1 - distance_col).label("similarity_score")

    stmt = (
        select(Knowledge, score_col)
        .where(
            Knowledge.id != knowledge_id,
            Knowledge.deleted_at.is_(None),  # 排除软删
            Knowledge.embedding.is_not(None),  # 必须有 embedding
            Knowledge.storage_mode == "kb",  # 只关联 KB, 排除 drive 文件
        )
        .order_by(distance_col.asc())  # 距离升序 (相似度降序)
        .limit(top_k * 3)  # 多取几倍, 过滤阈值后再 limit
    )

    result = await db.execute(stmt)
    rows = result.all()  # [(Knowledge, similarity_score), ...]

    # 3. 过滤 + 写表
    written: List[KbLink] = []
    for other_kb, score in rows:
        if score < min_score:
            break  # 已排序, 后面的 score 更低, 直接 break
        if len(written) >= top_k:
            break

        a_id, b_id = sorted([knowledge_id, other_kb.id])  # 强制 a < b
        # UNIQUE 约束兜底: 已存在则跳过
        existing = await db.execute(
            select(KbLink).where(
                KbLink.knowledge_id_a == a_id,
                KbLink.knowledge_id_b == b_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug(
                "kb_linker 已存在 a=%s b=%s, 跳过", a_id, b_id,
            )
            continue

        link = KbLink(
            knowledge_id_a=a_id,
            knowledge_id_b=b_id,
            similarity_score=float(score),
            link_type=LINK_TYPE_AUTO,
        )
        db.add(link)
        written.append(link)

    if written:
        await db.commit()
        logger.info(
            "kb_linker knowledge_id=%s → 新建 %d 条关联 (top_k=%d, min_score=%.2f)",
            knowledge_id, len(written), top_k, min_score,
        )
    return written


# ============== 读: 反查关联 KB ==============

async def find_related(
    db: AsyncSession,
    knowledge_id: int,
    *,
    limit: int = 10,
    link_types: Optional[Tuple[str, ...]] = None,
) -> List[Tuple[Knowledge, float, str]]:
    """找与指定 KB 关联的其他 KB (读 kb_links 表)

    Args:
        db: AsyncSession
        knowledge_id: 主 KB id
        limit: 返回上限
        link_types: 过滤 link_type (默认全部, 可选 ("auto",) / ("manual",) / ("derived",))

    Returns:
        [(related_kb, similarity_score, link_type), ...] 按 score 降序
    """
    if link_types is None:
        link_types = VALID_LINK_TYPES

    stmt = (
        select(Knowledge, KbLink.similarity_score, KbLink.link_type)
        .join(
            KbLink,
            or_(
                and_(
                    KbLink.knowledge_id_a == Knowledge.id,
                    KbLink.knowledge_id_b == knowledge_id,
                ),
                and_(
                    KbLink.knowledge_id_b == Knowledge.id,
                    KbLink.knowledge_id_a == knowledge_id,
                ),
            ),
        )
        .where(Knowledge.deleted_at.is_(None))
        .where(KbLink.link_type.in_(link_types))
        .order_by(KbLink.similarity_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [(row[0], float(row[1]), row[2]) for row in result.all()]


# ============== 维护: 删旧关联 ==============

async def unlink_pair(
    db: AsyncSession,
    knowledge_id_a: int,
    knowledge_id_b: int,
) -> bool:
    """删指定一对 KB 关联 (人工 review 后清理误关联用)

    Returns:
        True 表示删了 1 行, False 表示无关联
    """
    a_id, b_id = sorted([knowledge_id_a, knowledge_id_b])
    link = await db.execute(
        select(KbLink).where(
            KbLink.knowledge_id_a == a_id,
            KbLink.knowledge_id_b == b_id,
        )
    )
    found = link.scalar_one_or_none()
    if found is None:
        return False
    await db.delete(found)
    await db.commit()
    return True


async def unlink_all_for_kb(
    db: AsyncSession,
    knowledge_id: int,
) -> int:
    """删指定 KB 的所有关联 (KB 硬删除前清理)

    Returns:
        删除的行数
    """
    links = await db.execute(
        select(KbLink).where(
            or_(
                KbLink.knowledge_id_a == knowledge_id,
                KbLink.knowledge_id_b == knowledge_id,
            )
        )
    )
    rows = links.scalars().all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return len(rows)


# ============== 工具函数 ==============

def build_linker_summary(links: List[KbLink]) -> Dict[str, Any]:
    """kb_links 列表 → 闭环 log meta_data 摘要 (供 kb_closed_loop_service 用)

    Returns:
        {"linked_count": int, "top_score": float, "avg_score": float, "ids": [...]}
    """
    if not links:
        return {"linked_count": 0, "top_score": 0.0, "avg_score": 0.0, "ids": []}
    scores = [l.similarity_score for l in links]
    ids: List[int] = []
    for l in links:
        ids.extend([l.knowledge_id_a, l.knowledge_id_b])
    return {
        "linked_count": len(links),
        "top_score": round(max(scores), 3),
        "avg_score": round(sum(scores) / len(scores), 3),
        "ids": sorted(set(ids)),
    }