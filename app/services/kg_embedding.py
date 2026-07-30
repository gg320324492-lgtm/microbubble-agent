"""实体向量生成 — PR8 知识图谱深度联动 (W94 +3)

## 定位

为 `kg_entities.embedding` 生成向量，供 `entity_link_recall` pgvector cosine 召回。

**必复用 PR1 `truncate_for_embedding`** (plan §3.12 接口契约 + PR8 派工 brief 段 2):
实体文本进 embedding 前必走同一截断策略，否则重算前后向量漂移
(plan §1.1 缺口 1 "3 档截断不一致" 的根因)。

## 与已有 `entity_service._generate_entity_embedding` 的区别

| 维度 | `entity_service._generate_entity_embedding` (已有) | `kg_embedding` (PR8 新增) |
|------|--------------------------------------------------|-------------------------|
| 目标表 | knowledge_entities (SPO 三元组) | **kg_entities** (扁平实体) |
| 文本构造 | `f"{subject} {predicate} {object}"` + condition | **entity_name + entity_type 上下文** |
| 截断 | **无截断** (缺口 1) | **truncate_for_embedding** (PR1 统一) |
| 批量 | 单条 (per entity_id) | 单条 + **批量去重复用** |

**0 production code 双门控守恒**: 纯新增文件, 0 改 `entity_service.py`,
0 改 `embedding_service.py` (PR1 已锁), 件 4a `^[+-]def` = 0。

## 本机可测性 (plan §3.7 + v11 新增 5)

`sentence_transformers` 未装时 `import embedding_service` 即崩。本模块策略:
- **纯逻辑层函数** (`build_entity_embedding_text` / `dedup_entity_texts`) 只依赖标准库
- `generate_kg_entity_embedding` 走**函数内 lazy import** — 不在模块顶部 import
  embedding_service, 保证本模块 import 永不崩
- 失败静默返 None (召回侧降级到精确名匹配路)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
"""
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("microbubble.kg_embedding")

# 实体 embedding 文本上限 — 实体名远短于文档, 但仍走 PR1 统一策略兜底
# 实际实体文本 ≈ 名(≤500) + 类型(≤32) + 分隔符, 远低于 MAX_EMBED_INPUT_CHARS=6000
KG_EMBED_TEXT_JOINER: str = " "

# 实体类型中文语境映射 — 给 embedding 提供类型语义 (纯文本, 不进 DB)
# 目的: "气泡" 作为 CONCEPT vs 作为 MATERIAL 生成不同向量
ENTITY_TYPE_CONTEXT: Dict[str, str] = {
    "PERSON": "人物",
    "ORG": "机构",
    "CONCEPT": "概念",
    "METHOD": "方法",
    "MATERIAL": "材料",
    "EQUIPMENT": "设备",
    "METRIC": "指标",
    "OTHER": "实体",
}


def build_entity_embedding_text(
    entity_name: str,
    entity_type: Optional[str] = None,
    *,
    context: Optional[str] = None,
) -> str:
    """构造实体 embedding 输入文本 (纯逻辑, 无外部依赖 — 本机可单测)

    格式: "<entity_name> <类型中文> <可选上下文>"
    然后必过 PR1 `truncate_for_embedding` (plan §3.12 接口契约)。

    抽取侧与召回侧必走同一函数, 否则向量空间不一致 → 召回漂移。
    """
    from app.services.embedding_truncation_policy import truncate_for_embedding

    if not entity_name:
        return ""
    parts: List[str] = [str(entity_name).strip()]
    type_ctx = ENTITY_TYPE_CONTEXT.get(
        (entity_type or "OTHER").strip().upper(), ENTITY_TYPE_CONTEXT["OTHER"]
    )
    parts.append(type_ctx)
    if context:
        parts.append(str(context).strip())
    joined = KG_EMBED_TEXT_JOINER.join(p for p in parts if p)
    # PR1 统一截断策略 (缺口 1 修复, 禁止另起硬截)
    return truncate_for_embedding(joined)


def dedup_entity_texts(
    entities: Sequence[Dict[str, Any]],
) -> Tuple[List[str], Dict[str, List[int]]]:
    """批量实体文本去重 — 同文本只算一次 embedding (纯逻辑, 可单测)

    返回 (unique_texts, text → [entity_index...] 映射)。
    同名同类型实体在 N 篇知识出现 → N 行, 但只需算 1 次向量。
    """
    texts: List[str] = []
    index: Dict[str, List[int]] = {}
    for i, ent in enumerate(entities):
        text = build_entity_embedding_text(
            ent.get("entity_name") or "", ent.get("entity_type")
        )
        if not text:
            continue
        if text not in index:
            index[text] = []
            texts.append(text)
        index[text].append(i)
    return texts, index


async def generate_kg_entity_embedding(
    text_or_name: str,
    entity_type: Optional[str] = None,
    *,
    for_query: bool = False,
) -> Optional[List[float]]:
    """生成单个实体向量 — lazy import 保证本模块 import 永不崩

    Args:
        text_or_name: 实体名 (或已构造好的 embedding 文本)
        entity_type: 实体类型 (None 时按 OTHER 处理)
        for_query: 检索侧走 query prefix (PR1 embedding_query_policy 生效路径)

    Returns:
        向量 List[float] (维度 KG_ENTITY_VECTOR_DIM=1024), 失败返 None
    """
    try:
        text = build_entity_embedding_text(text_or_name, entity_type)
        if not text:
            return None
        # lazy import — sentence_transformers 未装时不在模块 import 阶段崩
        from app.services.embedding_service import generate_embedding

        emb = await generate_embedding(text, for_query=for_query)
        return emb or None
    except Exception as e:
        logger.debug("实体向量生成跳过 (%s): %s", text_or_name, e)
        return None


async def backfill_kg_entity_embeddings(
    db: Any, *, batch_size: int = 50, max_batches: int = 20
) -> Dict[str, int]:
    """批量回填 kg_entities.embedding — 独立容错, 供 Celery / 脚本调用

    只处理 embedding IS NULL 的行, 幂等可重跑。
    返回 {"scanned": N, "updated": M, "skipped": K}
    """
    stats = {"scanned": 0, "updated": 0, "skipped": 0}
    try:
        from sqlalchemy import select

        from app.models.kg_entity import KGEntity

        for _ in range(max_batches):
            stmt = (
                select(KGEntity)
                .where(KGEntity.embedding.is_(None))
                .limit(batch_size)
            )
            result = await db.execute(stmt)
            rows = list(result.scalars().all())
            if not rows:
                break
            for entity in rows:
                stats["scanned"] += 1
                emb = await generate_kg_entity_embedding(
                    entity.entity_name, entity.entity_type
                )
                if emb:
                    entity.embedding = emb
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            await db.commit()
    except Exception as e:
        logger.warning("kg_entities embedding 回填失败: %s", e)
    return stats
