"""假设生成引擎 — 从知识空白和实体关系中推导可验证假设"""

import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.knowledge import KnowledgeGap
from app.models.knowledge_entity import KnowledgeEntity
from app.models.knowledge_hypothesis import KnowledgeHypothesis
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

logger = logging.getLogger("microbubble.hypothesis")

HYPOTHESIS_PROMPT = """你是微纳米气泡课题组的科研假设生成助手。基于已知事实、知识空白和关系模式，生成可验证的科学假设。

## 已知事实（实体三元组）
{entities_text}

## 知识空白（未覆盖的查询）
{gaps_text}

## 生成要求
每条假设应包含：
1. statement: 清晰可验证的假设陈述
2. rationale: 基于哪些已知事实推导出来
3. suggested_experiment: 如何设计实验验证
4. confidence: 基于现有证据的置信度 0-1
5. priority: high/medium/low

返回严格JSON格式（不要其他文字）：
{{"hypotheses": [
  {{"statement": "...", "rationale": "...", "suggested_experiment": "...", "supporting_entity_subjects": ["主体1"], "confidence": 0.7, "priority": "high", "tags": ["臭氧"]}}
]}}"""


class HypothesisService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_hypotheses(self, topic: Optional[str] = None, count: int = 3) -> List[dict]:
        entities_text = await self._collect_entities(topic, limit=30)
        gaps_text = await self._collect_gaps(topic, limit=10)

        if not entities_text.strip():
            logger.warning("无足够实体数据生成假设")
            return []

        prompt = HYPOTHESIS_PROMPT.format(
            entities_text=entities_text,
            gaps_text=gaps_text or "暂无明确的知识空白记录",
        )
        if topic:
            prompt += f"\n\n重点关注领域: {topic}"

        try:
            client = get_anthropic_client()
            response = await client.messages.create(
                model=get_default_model(), max_tokens=2000, timeout=45,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            result = parse_llm_json(text)
            hypotheses = result.get("hypotheses", [])

            saved = []
            for h in hypotheses[:count]:
                entity_ids = await self._resolve_entity_ids(
                    h.get("supporting_entity_subjects", [])
                )
                hyp = KnowledgeHypothesis(
                    statement=h["statement"],
                    rationale=h.get("rationale", ""),
                    suggested_experiment=h.get("suggested_experiment", ""),
                    supporting_entity_ids=entity_ids,
                    confidence=h.get("confidence", 0.5),
                    priority=h.get("priority", "medium"),
                    tags=h.get("tags", []),
                    status="proposed",
                )
                self.db.add(hyp)
                saved.append(hyp)

            await self.db.commit()
            for hyp in saved:
                await self.db.refresh(hyp)

            logger.info(f"生成 {len(saved)} 条假设")
            return [self._hypothesis_to_dict(h) for h in saved]
        except Exception as e:
            logger.error(f"假设生成失败: {e}")
            return []

    async def list_hypotheses(self, status: Optional[str] = None,
                              priority: Optional[str] = None,
                              page: int = 1, page_size: int = 20) -> dict:
        filters = []
        if status:
            filters.append(KnowledgeHypothesis.status == status)
        if priority:
            filters.append(KnowledgeHypothesis.priority == priority)

        base = select(KnowledgeHypothesis)
        count_base = select(func.count()).select_from(KnowledgeHypothesis)
        if filters:
            base = base.where(*filters)
            count_base = count_base.where(*filters)

        total = (await self.db.execute(count_base)).scalar() or 0
        query = base.order_by(desc(KnowledgeHypothesis.confidence))
        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [self._hypothesis_to_dict(h) for h in rows],
            "total": total, "page": page, "page_size": page_size,
        }

    async def validate_hypothesis(self, hypothesis_id: int, status: str,
                                  validation_note: Optional[str] = None) -> Optional[dict]:
        from app.models.base import utcnow
        result = await self.db.execute(
            select(KnowledgeHypothesis).where(KnowledgeHypothesis.id == hypothesis_id)
        )
        hyp = result.scalar_one_or_none()
        if not hyp:
            return None

        hyp.status = status
        hyp.validated_at = utcnow()
        if validation_note:
            hyp.rationale = (hyp.rationale or "") + f"\n[验证备注] {validation_note}"
        await self.db.commit()
        await self.db.refresh(hyp)
        return self._hypothesis_to_dict(hyp)

    async def get_hypothesis_detail(self, hypothesis_id: int) -> Optional[dict]:
        result = await self.db.execute(
            select(KnowledgeHypothesis).where(KnowledgeHypothesis.id == hypothesis_id)
        )
        hyp = result.scalar_one_or_none()
        if not hyp:
            return None

        detail = self._hypothesis_to_dict(hyp)
        if hyp.supporting_entity_ids:
            rows = await self.db.execute(
                select(KnowledgeEntity).where(
                    KnowledgeEntity.id.in_(hyp.supporting_entity_ids)
                )
            )
            detail["supporting_entities"] = [
                {"id": e.id, "subject": e.subject, "predicate": e.predicate,
                 "object": e.object}
                for e in rows.scalars().all()
            ]
        else:
            detail["supporting_entities"] = []
        return detail

    # ── Private ──

    async def _collect_entities(self, topic: Optional[str], limit: int) -> str:
        query = select(KnowledgeEntity).order_by(
            desc(KnowledgeEntity.occurrence_count)
        ).limit(limit)
        if topic:
            query = query.where(
                KnowledgeEntity.subject.ilike(f"%{topic}%") |
                KnowledgeEntity.object.ilike(f"%{topic}%")
            )
        rows = (await self.db.execute(query)).scalars().all()
        lines = []
        for e in rows[:limit]:
            cond = f" (条件: {e.condition})" if e.condition else ""
            lines.append(
                f"- {e.subject} —[{e.predicate}]→ {e.object}{cond} [置信度:{e.confidence}]"
            )
        return "\n".join(lines)

    async def _collect_gaps(self, topic: Optional[str], limit: int) -> str:
        query = select(KnowledgeGap).where(KnowledgeGap.filled == False).limit(limit)
        if topic:
            query = query.where(KnowledgeGap.query.ilike(f"%{topic}%"))
        rows = (await self.db.execute(query)).scalars().all()
        lines = [f"- {g.query} (领域: {g.area or '未分类'})" for g in rows]
        return "\n".join(lines)

    async def _resolve_entity_ids(self, subjects: List[str]) -> List[int]:
        if not subjects:
            return []
        ids = []
        for s in subjects[:10]:
            r = await self.db.execute(
                select(KnowledgeEntity.id).where(
                    KnowledgeEntity.subject.ilike(f"%{s}%")
                ).limit(1)
            )
            eid = r.scalar_one_or_none()
            if eid:
                ids.append(eid)
        return ids

    @staticmethod
    def _hypothesis_to_dict(h: KnowledgeHypothesis) -> dict:
        return {
            "id": h.id,
            "statement": h.statement,
            "rationale": h.rationale,
            "suggested_experiment": h.suggested_experiment,
            "supporting_entity_ids": h.supporting_entity_ids or [],
            "confidence": h.confidence,
            "priority": h.priority,
            "status": h.status,
            "tags": h.tags or [],
            "validated_at": str(h.validated_at) if h.validated_at else None,
            "created_at": str(h.created_at) if h.created_at else None,
        }
