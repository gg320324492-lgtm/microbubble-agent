"""实体融合服务 — 跨文档实体解析、合并、查询"""

import logging
import asyncio
import time
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy import join as sqlalchemy_join
from sqlalchemy.orm import aliased

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

    async def bulk_fuse_entities(self, max_candidates: int = 500,
                                 max_llm_calls: int = 300, max_seconds: int = 900):
        """每日批量融合 — DB 侧预筛候选 + LLM 只判相似对 (2026-09-11 重做)

        旧版为 O(n²) 全对 LLM 判定 (20 predicate 组 × 50 实体 → 单组 1225 对,
        最坏 ~2.45 万次本地 27b 调用 = 2-3h 长任务), 且 `_do_merge` commit 后
        外层继续复用旧实体列表, 触发 MissingGreenlet。新版三层防御:

        1. 候选生成下推 DB: ① 完全重复组 (subject+predicate+object 全等) 直接合并
           零 LLM; ② 同 predicate 的 pgvector cosine 自连接 ≥ FUSION_SIMILARITY_THRESHOLD
           取 top-N。对数从 n² 降到有界 max_candidates (1092 条无 embedding 实体
           走 ① 精确路径覆盖, ② 只作用于有向量的 673 条)。
        2. 预算硬上限: LLM 调用数 max_llm_calls + 墙钟 max_seconds, 任一触顶即停
           (返回 partial=true), 保证任务时长可预估, 不再挤占 worker。
        3. 每对经 db.get 现取 (merge 后 source 已删 → None 自动跳过), 不再持有
           陈旧对象列表迭代; 配套 task 侧 expire_on_commit=False 的 NullPool session。
        """
        t0 = time.monotonic()
        merged = 0
        llm_calls = 0
        budget_hit = ""

        # ── Phase 1: 完全重复组 (subject+predicate+object+condition 全等, 零 LLM) ──
        dup_rows = await self.db.execute(
            select(
                func.array_agg(KnowledgeEntity.id).label("ids"),
            )
            .select_from(KnowledgeEntity)
            .group_by(KnowledgeEntity.subject, KnowledgeEntity.predicate,
                      KnowledgeEntity.object, KnowledgeEntity.condition)
            .having(func.count(KnowledgeEntity.id) > 1)
            .order_by(desc(func.count(KnowledgeEntity.id)))
            .limit(max_candidates)
        )
        merged_ids: set[int] = set()
        for row in dup_rows.all():
            # keep = 组内出现次数最高者 (并列取 id 最小, 确定性)
            members = (await self.db.execute(
                select(KnowledgeEntity.id, KnowledgeEntity.occurrence_count)
                .where(KnowledgeEntity.id.in_(row.ids))
                .order_by(desc(KnowledgeEntity.occurrence_count), KnowledgeEntity.id)
            )).all()
            if len(members) < 2:
                continue
            keep_id = members[0].id
            for m in members[1:]:
                if time.monotonic() - t0 > max_seconds:
                    budget_hit = "time"
                    break
                target = await self.db.get(KnowledgeEntity, keep_id)
                source = await self.db.get(KnowledgeEntity, m.id)
                if not target or not source:
                    continue
                if await self._do_merge(target, source):
                    merged += 1
                    merged_ids.add(m.id)
            if budget_hit:
                break

        # ── Phase 2: 相似候选对 (pgvector 自连接预筛, LLM 判定, 有预算) ──
        if not budget_hit:
            a = aliased(KnowledgeEntity, name="a")
            b = aliased(KnowledgeEntity, name="b")
            sim = 1 - a.embedding.cosine_distance(b.embedding)
            cand_stmt = (
                select(a.id.label("x"), b.id.label("y"))
                .select_from(sqlalchemy_join(a, b, and_(
                    b.predicate == a.predicate,
                    b.id > a.id,
                    b.embedding.isnot(None),
                )))
                .where(a.embedding.isnot(None))
                .where(sim >= self.FUSION_SIMILARITY_THRESHOLD)
                .order_by(sim.desc())
                .limit(max_candidates)
            )
            cands = (await self.db.execute(cand_stmt)).all()
            for c in cands:
                if c.x in merged_ids or c.y in merged_ids:
                    continue  # 已在 Phase 1 并入他主
                if llm_calls >= max_llm_calls:
                    budget_hit = "llm_calls"
                    break
                if time.monotonic() - t0 > max_seconds:
                    budget_hit = "time"
                    break
                ea = await self.db.get(KnowledgeEntity, c.x)
                eb = await self.db.get(KnowledgeEntity, c.y)
                if not ea or not eb:
                    continue
                llm_calls += 1
                if await self._llm_judge_merge(ea, eb):
                    # 保留出现次数多的一方作 target
                    if (ea.occurrence_count or 0) >= (eb.occurrence_count or 0):
                        ok = await self._do_merge(ea, eb)
                        gone = c.y
                    else:
                        ok = await self._do_merge(eb, ea)
                        gone = c.x
                    if ok:
                        merged += 1
                        merged_ids.add(gone)

        elapsed = round(time.monotonic() - t0, 1)
        out = {"merged_pairs": merged, "llm_calls": llm_calls, "elapsed_s": elapsed}
        if budget_hit:
            out["partial"] = True
            out["budget"] = budget_hit
        logger.info(f"批量融合完成: {out}"
                    + (" (预算触顶, 余量下轮继续)" if budget_hit else ""))
        return out

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

        # W86 mini-4 fix: 单次 JOIN 拉所有相关 entity, 避免 N+1 (派工 v4 铁律 3 真验证)
        # 老实现: 循环 co_rows 每条边触发 1-2 个 entity 查询 (50-100 个 query)
        # 新实现: 1 个 JOIN 拉所有 (co + entity) 对
        co_stmt = (
            select(EntityCoOccurrence, KnowledgeEntity)
            .join(
                KnowledgeEntity,
                or_(
                    EntityCoOccurrence.entity_a_id == KnowledgeEntity.id,
                    EntityCoOccurrence.entity_b_id == KnowledgeEntity.id,
                ),
            )
            .where(or_(
                EntityCoOccurrence.entity_a_id == entity_id,
                EntityCoOccurrence.entity_b_id == entity_id,
            ))
            .order_by(desc(EntityCoOccurrence.weight))
            .limit(limit * 2)  # 边 × 2 端点
        )
        rows = (await self.db.execute(co_stmt)).all()

        seen_co = set()
        for co, ent in rows:
            if co.id not in seen_co:
                seen_co.add(co.id)
                if len(edges) < limit:
                    edges.append({
                        "source": co.entity_a_id, "target": co.entity_b_id,
                        "knowledge_id": co.knowledge_id, "weight": co.weight,
                    })
            if ent.id not in nodes and len(nodes) < limit + 1:  # +1 for center
                nodes[ent.id] = self._entity_to_dict(ent)
        return {"nodes": list(nodes.values()), "edges": edges}

    async def _global_graph(self, limit: int) -> dict:
        # W86 mini-4 fix: 单次 JOIN 替代 N+1 (派工 v4 铁律 3 真验证)
        # 老实现: 每条 co 边触发 2 个 entity 查询 (limit=50 → 100 个 query)
        # 新实现: 1 个 JOIN 拉所有 (co + entity) 对, 服务端再 dedupe
        stmt = (
            select(EntityCoOccurrence, KnowledgeEntity)
            .join(
                KnowledgeEntity,
                or_(
                    EntityCoOccurrence.entity_a_id == KnowledgeEntity.id,
                    EntityCoOccurrence.entity_b_id == KnowledgeEntity.id,
                ),
            )
            .order_by(desc(EntityCoOccurrence.weight))
            .limit(limit * 2)  # 边 × 2 端点
        )
        rows = (await self.db.execute(stmt)).all()

        nodes = {}
        edges = []
        seen_co = set()
        for co, ent in rows:
            if co.id not in seen_co:
                seen_co.add(co.id)
                if len(edges) < limit:
                    edges.append({
                        "source": co.entity_a_id, "target": co.entity_b_id,
                        "knowledge_id": co.knowledge_id, "weight": co.weight,
                    })
            if ent.id not in nodes:
                nodes[ent.id] = self._entity_to_dict(ent)
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
        t, s = target.id, source.id
        try:
            existing = set(target.source_knowledge_ids or [])
            additions = [sid for sid in (source.source_knowledge_ids or []) if sid not in existing]
            if additions:
                target.source_knowledge_ids = list(existing.union(additions))
            target.occurrence_count = (target.occurrence_count or 0) + (source.occurrence_count or 0)
            target.confidence = max(target.confidence or 0, source.confidence or 0)

            # 2026-09-11: 原实现直接整列 UPDATE, 与 (entity_a_id,entity_b_id,knowledge_id)
            # 唯一键撞车 (实测 362→361 触发 UniqueViolation, 整对合并静默放弃,
            # 是"融合跑了但 merged=0"的真凶)。改为: 只迁移不与 target 现有边冲突的
            # 边, 冲突边 (语义即重复) 连同 source 残余边直接删除。
            await self.db.execute(
                text("""UPDATE entity_co_occurrence SET entity_a_id = :t
                        WHERE entity_a_id = :s
                          AND (entity_b_id, knowledge_id) NOT IN
                            (SELECT entity_b_id, knowledge_id FROM entity_co_occurrence
                             WHERE entity_a_id = :t)"""),
                {"t": t, "s": s},
            )
            await self.db.execute(
                text("DELETE FROM entity_co_occurrence WHERE entity_a_id = :s"), {"s": s})
            await self.db.execute(
                text("""UPDATE entity_co_occurrence SET entity_b_id = :t
                        WHERE entity_b_id = :s
                          AND (entity_a_id, knowledge_id) NOT IN
                            (SELECT entity_a_id, knowledge_id FROM entity_co_occurrence
                             WHERE entity_b_id = :t)"""),
                {"t": t, "s": s},
            )
            await self.db.execute(
                text("DELETE FROM entity_co_occurrence WHERE entity_b_id = :s"), {"s": s})
            await self.db.execute(
                text("DELETE FROM entity_co_occurrence WHERE entity_a_id = entity_b_id")
            )
            await self.db.delete(source)
            await self.db.commit()
            return True
        except Exception as e:
            logger.warning(f"实体合并失败({s} -> {t}): {e}")
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
