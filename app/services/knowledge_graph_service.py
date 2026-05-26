"""知识图谱服务 — 自动发现并维护知识条目之间的关联"""

import json
import logging
from typing import List, Optional

from sqlalchemy import select, or_, and_, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Knowledge, KnowledgeRelation
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

logger = logging.getLogger("microbubble.knowledge_graph")


class KnowledgeGraphService:
    """知识图谱服务 — 自动发现并维护知识之间的关联"""

    SIMILARITY_THRESHOLD = 0.65  # 余弦相似度阈值

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_relations_for(self, knowledge_id: int):
        """为新入库的知识条目自动建立关联关系 — LLM 判定具体关系类型"""
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id == knowledge_id)
        )
        source = result.scalar_one_or_none()
        if not source:
            return

        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id != knowledge_id)
        )
        targets = result.scalars().all()

        if not targets:
            logger.info(f"知识库尚无其他条目，跳过关联(knowledge_id={knowledge_id})")
            return

        # 1. 用 embedding 相似度筛选候选对
        candidates = []
        for target in targets:
            sim_score = await self._calc_similarity(source, target)
            if sim_score is None:
                sim_score = self._tag_similarity(source, target)
            if sim_score and sim_score >= self.SIMILARITY_THRESHOLD:
                candidates.append((target, sim_score))

        if not candidates:
            logger.info(f"无相似候选(knowledge_id={knowledge_id})")
            return

        # 2. LLM 批量判定关系类型
        llm_relations = await self._classify_relations_llm(source, candidates)

        # 3. 写入关系
        relations = []
        for rel in llm_relations:
            relations.append({
                "source_id": knowledge_id,
                "target_id": rel["target_id"],
                "relation_type": rel["type"],
                "score": round(rel["confidence"], 4),
                "reason": rel["reason"],
                "created_by": "llm"
            })

        await self._bulk_create_relations(relations)

        # 建立双向关联
        reverse_relations = [
            {
                "source_id": r["target_id"],
                "target_id": r["source_id"],
                "relation_type": r["relation_type"],
                "score": r["score"],
                "reason": r["reason"],
                "created_by": "llm"
            }
            for r in relations
        ]
        await self._bulk_create_relations(reverse_relations)

        if relations:
            types = set(r["relation_type"] for r in relations)
            logger.info(f"建立 {len(relations)} 对知识关联(knowledge_id={knowledge_id}), 类型: {types}")

    async def _classify_relations_llm(self, source: Knowledge, candidates: list) -> List[dict]:
        """用 LLM 批量判定源条目与候选条目的关系类型

        Args:
            source: 源知识条目
            candidates: [(target_knowledge, sim_score), ...] (最多 8 个)

        Returns:
            [{"target_id": int, "type": str, "reason": str, "confidence": float}, ...]
        """
        if not candidates:
            return []

        # 构建候选条目文本
        candidate_texts = []
        for i, (target, sim_score) in enumerate(candidates):
            summary = (target.summary or target.content or "")[:200]
            concepts = ", ".join(target.key_concepts[:4]) if target.key_concepts else "无"
            candidate_texts.append(
                f"[{i}] 标题: {target.title}\n"
                f"    摘要: {summary}\n"
                f"    核心概念: {concepts}\n"
                f"    余弦相似度: {sim_score:.2%}"
            )

        source_summary = (source.summary or source.content or "")[:200]
        source_concepts = ", ".join(source.key_concepts[:4]) if source.key_concepts else "无"

        prompt = f"""你是微纳米气泡课题组的AI知识管理助手。分析源文档与各候选文档之间的关系类型。

源文档:
标题: {source.title}
摘要: {source_summary}
核心概念: {source_concepts}

候选文档:
{chr(10).join(candidate_texts)}

对每个候选文档，判断与源文档的关系类型（可多个），从以下选择：
- supports: 两者实验数据或结论互相支持
- contradicts: 两者发现或结论互相矛盾
- method_inherits: 前者使用或扩展了后者的方法（或反之）
- cites: 前者直接引用或参考了后者
- prerequisite: 理解前者需要先了解后者的基础概念
- compares: 两者明确对比或比较方法/条件
- supplements: 前者补充了后者未涉及的方面
- extends: 前者在后者的基础上进行了扩展
- similar: 主题相似但没有明确的深层关系

返回严格的JSON格式（不要其他文字）：
{{
  "relations": [
    {{"candidate_index": 0, "types": [{{"type": "supports", "reason": "具体理由", "confidence": 0.85}}]}},
    {{"candidate_index": 1, "types": [{{"type": "similar", "reason": "具体理由", "confidence": 0.7}}]}}
  ]
}}"""

        try:
            client = get_anthropic_client()
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=1500,
                timeout=45,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            result = parse_llm_json(text)

            if not isinstance(result, dict) or "relations" not in result:
                # 回退：全部用 similar + embedding 分数
                logger.warning("LLM 关系分类返回格式异常，使用 similar 回退")
                return [
                    {"target_id": target.id, "type": "similar",
                     "reason": f"语义相似度 {sim_score:.2%}", "confidence": sim_score}
                    for target, sim_score in candidates
                ]

            # 解析结果
            relations = []
            for rel_entry in result["relations"]:
                idx = rel_entry.get("candidate_index", -1)
                if idx < 0 or idx >= len(candidates):
                    continue
                target, sim_score = candidates[idx]
                types = rel_entry.get("types", [])
                if not types:
                    # LLM 未识别出具体关系，回退 similar
                    relations.append({
                        "target_id": target.id, "type": "similar",
                        "reason": f"语义相似度 {sim_score:.2%}", "confidence": sim_score
                    })
                else:
                    for t in types:
                        relations.append({
                            "target_id": target.id,
                            "type": t.get("type", "similar"),
                            "reason": t.get("reason", f"语义相似度 {sim_score:.2%}"),
                            "confidence": t.get("confidence", sim_score),
                        })

            return relations

        except Exception as e:
            logger.warning(f"LLM 关系分类失败，使用 similar 回退: {e}")
            return [
                {"target_id": target.id, "type": "similar",
                 "reason": f"语义相似度 {sim_score:.2%}", "confidence": sim_score}
                for target, sim_score in candidates
            ]

    async def _calc_similarity(self, a: Knowledge, b: Knowledge) -> Optional[float]:
        """计算两个条目的语义相似度"""
        try:
            if a.embedding is None or b.embedding is None:
                return None

            # Use pgvector cosine_distance via SQLAlchemy column expression
            stmt = select(
                1 - Knowledge.embedding.cosine_distance(b.embedding)
            ).where(Knowledge.id == a.id)
            result = await self.db.execute(stmt)
            row = result.one_or_none()
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            logger.debug(f"相似度计算失败: {e}")
            return None

    def _tag_similarity(self, a: Knowledge, b: Knowledge) -> Optional[float]:
        """基于标签重叠计算相似度回退（embedding 不可用时的备用方案）"""
        a_tags = set(t.lower() for t in (a.tags or []))
        b_tags = set(t.lower() for t in (b.tags or []))
        if not a_tags or not b_tags:
            return None
        overlap = len(a_tags & b_tags)
        if overlap < 2:
            return None
        return min(0.5 + overlap * 0.1, 0.85)

    def _concept_overlap(self, a: Knowledge, b: Knowledge) -> List[str]:
        """计算两个条目的概念重叠"""
        a_concepts = set(a.key_concepts or [])
        b_concepts = set(b.key_concepts or [])
        return list(a_concepts & b_concepts)

    def _list_overlap(self, a: Optional[List], b: Optional[List]) -> List[str]:
        """计算两个列表的重叠"""
        a_set = set(a or [])
        b_set = set(b or [])
        return list(a_set & b_set)

    async def _bulk_create_relations(self, relations: List[dict]):
        """批量创建关系（去重）"""
        for rel in relations:
            # 检查是否已存在相同关系
            result = await self.db.execute(
                select(KnowledgeRelation).where(and_(
                    KnowledgeRelation.source_id == rel["source_id"],
                    KnowledgeRelation.target_id == rel["target_id"],
                    KnowledgeRelation.relation_type == rel["relation_type"],
                ))
            )
            existing = result.scalar_one_or_none()
            if existing:
                # 更新分数（取最高值）
                if rel["score"] > existing.score:
                    existing.score = rel["score"]
                    existing.reason = rel["reason"]
                continue

            relation = KnowledgeRelation(**rel)
            self.db.add(relation)

        await self.db.commit()

    async def get_related(self, knowledge_id: int,
                          relation_types: Optional[List[str]] = None,
                          limit: int = 10) -> List[dict]:
        """获取与指定条目关联的知识"""
        stmt = select(
            KnowledgeRelation, Knowledge
        ).join(
            Knowledge, KnowledgeRelation.target_id == Knowledge.id
        ).where(
            KnowledgeRelation.source_id == knowledge_id
        ).order_by(
            KnowledgeRelation.score.desc()
        ).limit(limit)

        if relation_types:
            stmt = stmt.where(KnowledgeRelation.relation_type.in_(relation_types))

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": row.Knowledge.id,
                "title": row.Knowledge.title,
                "category": row.Knowledge.category,
                "summary": row.Knowledge.summary,
                "relation_type": row.KnowledgeRelation.relation_type,
                "score": row.KnowledgeRelation.score,
                "reason": row.KnowledgeRelation.reason,
            }
            for row in rows
        ]

    async def get_knowledge_graph(self, center_id: Optional[int] = None,
                                  depth: int = 2, limit: int = 50) -> dict:
        """获取知识图谱数据（用于前端可视化）"""
        nodes = {}
        edges = []

        if center_id:
            # 从中心节点展开
            visited = set()
            queue = [(center_id, 0)]

            while queue and len(nodes) < limit:
                current_id, current_depth = queue.pop(0)
                if current_id in visited or current_depth > depth:
                    continue
                visited.add(current_id)

                # 获取节点信息
                result = await self.db.execute(
                    select(Knowledge).where(Knowledge.id == current_id)
                )
                kn = result.scalar_one_or_none()
                if kn:
                    nodes[current_id] = {
                        "id": kn.id,
                        "title": kn.title[:30],
                        "category": kn.category or "未分类",
                        "size": 1,
                    }

                # 获取关联关系
                result = await self.db.execute(
                    select(KnowledgeRelation, Knowledge).join(
                        Knowledge, KnowledgeRelation.target_id == Knowledge.id
                    ).where(
                        KnowledgeRelation.source_id == current_id
                    ).limit(limit)
                )
                for row in result.all():
                    edges.append({
                        "source": current_id,
                        "target": row.Knowledge.id,
                        "type": row.KnowledgeRelation.relation_type,
                        "score": row.KnowledgeRelation.score,
                    })
                    if row.Knowledge.id not in visited:
                        queue.append((row.Knowledge.id, current_depth + 1))

            # BFS 未找到任何关联节点时，至少返回中心节点自身
            if not nodes and center_id:
                result = await self.db.execute(
                    select(Knowledge).where(Knowledge.id == center_id)
                )
                kn = result.scalar_one_or_none()
                if kn:
                    nodes[center_id] = {
                        "id": kn.id,
                        "title": kn.title[:30],
                        "category": kn.category or "未分类",
                        "size": 1,
                    }

        else:
            # 全局图谱：获取最活跃的关联
            result = await self.db.execute(
                select(KnowledgeRelation, Knowledge).join(
                    Knowledge, KnowledgeRelation.target_id == Knowledge.id
                ).order_by(
                    KnowledgeRelation.score.desc()
                ).limit(limit)
            )
            for row in result.all():
                source_id = row.KnowledgeRelation.source_id
                target_id = row.KnowledgeRelation.target_id

                # 确保两个节点都在 nodes 中
                for nid in [source_id, target_id]:
                    if nid not in nodes:
                        r = await self.db.execute(
                            select(Knowledge).where(Knowledge.id == nid)
                        )
                        kn = r.scalar_one_or_none()
                        if kn:
                            nodes[nid] = {
                                "id": kn.id,
                                "title": kn.title[:30],
                                "category": kn.category or "未分类",
                                "size": 1,
                            }

                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "type": row.KnowledgeRelation.relation_type,
                    "score": row.KnowledgeRelation.score,
                })

            # 全局图谱无关联时，返回最近知识作为孤立节点
            if not nodes:
                result = await self.db.execute(
                    select(Knowledge).order_by(Knowledge.created_at.desc()).limit(limit)
                )
                for kn in result.scalars().all():
                    nodes[kn.id] = {
                        "id": kn.id,
                        "title": kn.title[:30],
                        "category": kn.category or "未分类",
                        "size": 1,
                    }

        # 计算节点度数（关联数）
        for edge in edges:
            sid, tid = edge["source"], edge["target"]
            if sid in nodes:
                nodes[sid]["size"] = nodes[sid].get("size", 1) + 0.5
            if tid in nodes:
                nodes[tid]["size"] = nodes[tid].get("size", 1) + 0.5

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    async def get_dynamic_categories(self) -> List[dict]:
        """获取动态分类列表（从实际数据中聚合）"""
        stmt = select(
            Knowledge.category,
            func.count(Knowledge.id).label("count")
        ).where(
            Knowledge.category.isnot(None),
            Knowledge.category != ""
        ).group_by(
            Knowledge.category
        ).order_by(
            func.count(Knowledge.id).desc()
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return [{"name": row.category, "count": row.count} for row in rows]

    async def get_tag_cloud(self, min_freq: int = 1, limit: int = 50) -> List[dict]:
        """获取标签云（频率排序）"""
        stmt = text("""
            SELECT unnest(tags) AS tag, COUNT(*) AS freq
            FROM knowledge
            WHERE tags IS NOT NULL
            GROUP BY tag
            HAVING COUNT(*) >= :min_freq
            ORDER BY freq DESC
            LIMIT :limit
        """)
        result = await self.db.execute(stmt, {"min_freq": min_freq, "limit": limit})
        rows = result.all()
        return [{"name": row.tag, "count": row.freq} for row in rows]

    async def get_knowledge_stats(self) -> dict:
        """获取知识库统计"""
        # 总数
        result = await self.db.execute(select(func.count(Knowledge.id)))
        total = result.scalar() or 0

        # 各类型的数量
        result = await self.db.execute(
            select(
                Knowledge.knowledge_type,
                func.count(Knowledge.id).label("count")
            ).where(
                Knowledge.knowledge_type.isnot(None),
                Knowledge.knowledge_type != ""
            ).group_by(Knowledge.knowledge_type).order_by(func.count(Knowledge.id).desc())
        )
        type_rows = result.all()
        types = {row.knowledge_type: row.count for row in type_rows}

        # 分析状态统计
        result = await self.db.execute(
            select(
                Knowledge.analysis_status,
                func.count(Knowledge.id).label("count")
            ).group_by(Knowledge.analysis_status)
        )
        status_rows = result.all()
        statuses = {row.analysis_status: row.count for row in status_rows}

        # 关联数统计
        result = await self.db.execute(select(func.count(KnowledgeRelation.id)))
        relation_count = result.scalar() or 0

        # 自动研究条目数
        result = await self.db.execute(
            select(func.count(Knowledge.id)).where(
                Knowledge.auto_researched == True
            )
        )
        auto_researched = result.scalar() or 0

        return {
            "total": total,
            "types": types,
            "analysis_status": statuses,
            "relations": relation_count,
            "auto_researched": auto_researched,
        }
