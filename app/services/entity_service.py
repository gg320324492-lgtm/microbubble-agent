"""实体融合服务 — 跨文档实体解析、合并、查询"""

import logging
import asyncio
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text

from app.models.knowledge import Knowledge
from app.models.knowledge_entity import KnowledgeEntity, EntityCoOccurrence
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response
from app.services.embedding_service import generate_embedding

logger = logging.getLogger("microbubble.entity")


class EntityService:
    """实体融合服务"""

    FUSION_SIMILARITY_THRESHOLD = 0.78

    def __init__(self, db: AsyncSession):
        self.db = db

    async def merge_entities_from_document(self, knowledge_id: int):
        """从已分析文档提取 entities JSONB 并合并到 knowledge_entities 表"""
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id == knowledge_id)
        )
        kn = result.scalar_one_or_none()
        if not kn or not kn.entities:
            return

        doc_entities: List[dict] = kn.entities
        new_entity_ids = []

        for ent in doc_entities:
            merged_id = await self._merge_single_entity(ent, knowledge_id)
            if merged_id:
                new_entity_ids.append(merged_id)

        if len(new_entity_ids) >= 2:
            await self._write_co_occurrences(new_entity_ids, knowledge_id)

        logger.info(f"文档 {knowledge_id}: 处理 {len(doc_entities)} 实体, "
                     f"合并/新建 {len(new_entity_ids)} 条")

    async def search_entities(
        self, subject: Optional[str] = None, predicate: Optional[str] = None,
        object_q: Optional[str] = None, keyword: Optional[str] = None,
        page: int = 1, page_size: int = 20,
    ) -> dict:
        filters = []
        if subject:
            filters.append(KnowledgeEntity.subject.ilike(f"%{subject}%"))
        if predicate:
            filters.append(KnowledgeEntity.predicate.ilike(f"%{predicate}%"))
        if object_q:
            filters.append(KnowledgeEntity.object.ilike(f"%{object_q}%"))
        if keyword:
            filters.append(or_(
                KnowledgeEntity.subject.ilike(f"%{keyword}%"),
                KnowledgeEntity.predicate.ilike(f"%{keyword}%"),
                KnowledgeEntity.object.ilike(f"%{keyword}%"),
            ))

        base = select(KnowledgeEntity)
        if filters:
            base = base.where(and_(*filters))

        count_q = select(func.count()).select_from(KnowledgeEntity)
        if filters:
            count_q = count_q.where(and_(*filters))
        total = (await self.db.execute(count_q)).scalar() or 0

        query = base.order_by(desc(KnowledgeEntity.occurrence_count))
        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [self._entity_to_dict(e) for e in rows],
            "total": total, "page": page, "page_size": page_size,
        }

    async def get_entity_graph(self, entity_id: Optional[int] = None, limit: int = 50) -> dict:
        if entity_id:
            return await self._centered_graph(entity_id, limit)
        else:
            return await self._global_graph(limit)

    async def get_entity_detail(self, entity_id: int) -> Optional[dict]:
        result = await self.db.execute(
            select(KnowledgeEntity).where(KnowledgeEntity.id == entity_id)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            return None

        detail = self._entity_to_dict(entity)
        if entity.source_knowledge_ids:
            r = await self.db.execute(
                select(Knowledge.id, Knowledge.title, Knowledge.category)
                .where(Knowledge.id.in_(entity.source_knowledge_ids))
            )
            detail["sources"] = [
                {"id": row.id, "title": row.title, "category": row.category}
                for row in r.all()
            ]
        else:
            detail["sources"] = []
        return detail

    async def bulk_fuse_entities(self, batch_size: int = 50):
        """每日批量融合 — LLM 判定相似实体合并"""
        result = await self.db.execute(
            select(KnowledgeEntity.predicate, func.count(KnowledgeEntity.id).label("cnt"))
            .group_by(KnowledgeEntity.predicate)
            .having(func.count(KnowledgeEntity.id) > 1)
            .order_by(desc("cnt")).limit(20)
        )
        predicate_groups = result.all()
        merged_count = 0

        for pg in predicate_groups:
            rows = await self.db.execute(
                select(KnowledgeEntity).where(
                    KnowledgeEntity.predicate == pg.predicate
                ).order_by(desc(KnowledgeEntity.occurrence_count)).limit(batch_size)
            )
            entities = rows.scalars().all()
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    if await self._llm_judge_merge(entities[i], entities[j]):
                        if await self._do_merge(entities[i], entities[j]):
                            merged_count += 1

        logger.info(f"批量融合完成: 合并 {merged_count} 对实体")
        return {"merged_pairs": merged_count}

    # ── Internal ──

    async def _merge_single_entity(self, ent: dict, knowledge_id: int) -> Optional[int]:
        subject = ent.get("subject", "")
        predicate = ent.get("predicate", "")
        obj = str(ent.get("object", ""))
        condition = ent.get("condition")
        confidence = ent.get("confidence", 0.5)

        # Step 1: 精确匹配
        filters = [
            KnowledgeEntity.subject == subject,
            KnowledgeEntity.predicate == predicate,
            KnowledgeEntity.object == obj,
        ]
        if condition:
            filters.append(KnowledgeEntity.condition == condition)
        else:
            filters.append(KnowledgeEntity.condition.is_(None))

        r = await self.db.execute(
            select(KnowledgeEntity).where(and_(*filters)).limit(1)
        )
        exact = r.scalar_one_or_none()
        if exact:
            return await self._update_existing(exact, knowledge_id, confidence)

        # Step 2: embedding 语义匹配
        ent_text = f"{subject} {predicate} {obj}"
        embedding = await generate_embedding(ent_text)
        if embedding:
            try:
                stmt = (
                    select(KnowledgeEntity, 1 - KnowledgeEntity.embedding.cosine_distance(embedding))
                    .where(KnowledgeEntity.predicate == predicate)
                    .order_by(KnowledgeEntity.embedding.cosine_distance(embedding))
                    .limit(5)
                )
                sim_rows = await self.db.execute(stmt)
                candidates = [(row[0], float(row[1])) for row in sim_rows.all()
                              if row[1] is not None and row[1] >= self.FUSION_SIMILARITY_THRESHOLD]
                if candidates:
                    return await self._update_existing(candidates[0][0], knowledge_id,
                                                       max(confidence, candidates[0][1]))
            except Exception:
                logger.debug("实体 embedding 搜索失败，跳过语义匹配", exc_info=True)

        # Step 3: 新建
        return await self._create_new(ent, knowledge_id)

    async def _update_existing(self, entity: KnowledgeEntity, knowledge_id: int,
                               confidence: float) -> int:
        ids = entity.source_knowledge_ids or []
        if knowledge_id not in ids:
            entity.source_knowledge_ids = ids + [knowledge_id]
        entity.occurrence_count = (entity.occurrence_count or 0) + 1
        if confidence > (entity.confidence or 0):
            entity.confidence = confidence
        await self.db.commit()
        return entity.id

    async def _create_new(self, ent: dict, knowledge_id: int) -> int:
        entity = KnowledgeEntity(
            subject=ent.get("subject", ""),
            predicate=ent.get("predicate", ""),
            object=str(ent.get("object", "")),
            condition=ent.get("condition"),
            confidence=ent.get("confidence", 0.5),
            source_knowledge_ids=[knowledge_id],
            occurrence_count=1,
        )
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        asyncio.create_task(self._generate_entity_embedding(entity.id))
        return entity.id

    async def _write_co_occurrences(self, entity_ids: List[int], knowledge_id: int):
        for i in range(len(entity_ids)):
            for j in range(i + 1, len(entity_ids)):
                a, b = entity_ids[i], entity_ids[j]
                r = await self.db.execute(
                    select(EntityCoOccurrence).where(and_(
                        EntityCoOccurrence.entity_a_id == a,
                        EntityCoOccurrence.entity_b_id == b,
                        EntityCoOccurrence.knowledge_id == knowledge_id,
                    ))
                )
                existing = r.scalar_one_or_none()
                if existing:
                    existing.weight = (existing.weight or 1.0) + 0.5
                else:
                    self.db.add(EntityCoOccurrence(
                        entity_a_id=a, entity_b_id=b,
                        knowledge_id=knowledge_id, weight=1.0,
                    ))
        await self.db.commit()

    async def _generate_entity_embedding(self, entity_id: int):
        from app.core.database import async_session
        try:
            async with async_session() as db:
                r = await db.execute(
                    select(KnowledgeEntity).where(KnowledgeEntity.id == entity_id)
                )
                entity = r.scalar_one_or_none()
                if not entity:
                    return
                text = f"{entity.subject} {entity.predicate} {entity.object}"
                if entity.condition:
                    text += f" ({entity.condition})"
                emb = await generate_embedding(text)
                if emb:
                    entity.embedding = emb
                    await db.commit()
        except Exception as e:
            logger.warning(f"实体 embedding 生成失败(entity_id={entity_id}): {e}")

    async def _centered_graph(self, entity_id: int, limit: int) -> dict:
        r = await self.db.execute(
            select(KnowledgeEntity).where(KnowledgeEntity.id == entity_id)
        )
        center = r.scalar_one_or_none()
        if not center:
            return {"nodes": [], "edges": []}

        nodes = {entity_id: self._entity_to_dict(center)}
        edges = []

        stmt = select(EntityCoOccurrence).where(or_(
            EntityCoOccurrence.entity_a_id == entity_id,
            EntityCoOccurrence.entity_b_id == entity_id,
        )).limit(limit * 2)
        co_rows = (await self.db.execute(stmt)).scalars().all()

        for co in co_rows:
            other_id = co.entity_b_id if co.entity_a_id == entity_id else co.entity_a_id
            if other_id not in nodes and len(nodes) < limit:
                r2 = await self.db.execute(
                    select(KnowledgeEntity).where(KnowledgeEntity.id == other_id)
                )
                other = r2.scalar_one_or_none()
                if other:
                    nodes[other_id] = self._entity_to_dict(other)
            edges.append({
                "source": co.entity_a_id, "target": co.entity_b_id,
                "knowledge_id": co.knowledge_id, "weight": co.weight,
            })
        return {"nodes": list(nodes.values()), "edges": edges}

    async def _global_graph(self, limit: int) -> dict:
        stmt = select(EntityCoOccurrence).order_by(
            desc(EntityCoOccurrence.weight)
        ).limit(limit)
        co_rows = (await self.db.execute(stmt)).scalars().all()
        nodes = {}
        edges = []
        for co in co_rows:
            for eid in (co.entity_a_id, co.entity_b_id):
                if eid not in nodes:
                    r = await self.db.execute(
                        select(KnowledgeEntity).where(KnowledgeEntity.id == eid)
                    )
                    ent = r.scalar_one_or_none()
                    if ent:
                        nodes[eid] = self._entity_to_dict(ent)
            edges.append({
                "source": co.entity_a_id, "target": co.entity_b_id,
                "knowledge_id": co.knowledge_id, "weight": co.weight,
            })
        return {"nodes": list(nodes.values()), "edges": edges}

    async def _llm_judge_merge(self, a: KnowledgeEntity, b: KnowledgeEntity) -> bool:
        """LLM 判断两实体是否指向同一事实（仅 subject/object 文本相似但非完全相同时调用）"""
        a_text = f"{a.subject} {a.predicate} {a.object}"
        b_text = f"{b.subject} {b.predicate} {b.object}"
        if a_text == b_text:
            return True
        prompt = (f'判断以下两个知识三元组是否描述同一科学事实：\n'
                  f'A: "{a.subject}" —[{a.predicate}]→ "{a.object}" (条件: {a.condition or "无"})\n'
                  f'B: "{b.subject}" —[{b.predicate}]→ "{b.object}" (条件: {b.condition or "无"})\n'
                  f'核心含义相同返回 {{"merge": true}}，不同事实或矛盾返回 {{"merge": false}}。严格JSON。')
        try:
            client = get_anthropic_client()
            resp = await client.messages.create(
                model=get_default_model(), max_tokens=200, timeout=15,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(resp)
            result = parse_llm_json(text)
            return result.get("merge", False)
        except Exception as e:
            logger.warning(f"LLM 合并判定失败: {e}")
            return False

    async def _do_merge(self, target: KnowledgeEntity, source: KnowledgeEntity) -> bool:
        try:
            existing = set(target.source_knowledge_ids or [])
            for sid in (source.source_knowledge_ids or []):
                if sid not in existing:
                    target.source_knowledge_ids = (target.source_knowledge_ids or []) + [sid]
                    existing.add(sid)
            target.occurrence_count = (target.occurrence_count or 0) + (source.occurrence_count or 0)
            target.confidence = max(target.confidence or 0, source.confidence or 0)

            await self.db.execute(
                text("UPDATE entity_co_occurrence SET entity_a_id = :t WHERE entity_a_id = :s"),
                {"t": target.id, "s": source.id}
            )
            await self.db.execute(
                text("UPDATE entity_co_occurrence SET entity_b_id = :t WHERE entity_b_id = :s"),
                {"t": target.id, "s": source.id}
            )
            await self.db.execute(
                text("DELETE FROM entity_co_occurrence WHERE entity_a_id = entity_b_id")
            )
            await self.db.delete(source)
            await self.db.commit()
            return True
        except Exception as e:
            logger.warning(f"实体合并失败({source.id} -> {target.id}): {e}")
            await self.db.rollback()
            return False

    @staticmethod
    def _entity_to_dict(e: KnowledgeEntity) -> dict:
        return {
            "id": e.id,
            "subject": e.subject,
            "predicate": e.predicate,
            "object": e.object,
            "condition": e.condition,
            "confidence": e.confidence,
            "source_count": len(e.source_knowledge_ids or []),
            "occurrence_count": e.occurrence_count,
            "created_at": str(e.created_at) if e.created_at else None,
            "updated_at": str(e.updated_at) if e.updated_at else None,
        }
