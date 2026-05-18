from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text
from typing import List, Optional
import json

from app.models.knowledge import Knowledge


class KnowledgeService:
    """知识库服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_knowledge(self, knowledge_id: int) -> Optional[Knowledge]:
        """获取单条知识"""
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id == knowledge_id)
        )
        return result.scalar_one_or_none()

    async def get_knowledge_list(
        self,
        category: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[Knowledge]:
        """查询知识列表"""
        query = select(Knowledge)
        filters = []

        if category:
            filters.append(Knowledge.category == category)
        if keyword:
            filters.append(or_(
                Knowledge.title.ilike(f"%{keyword}%"),
                Knowledge.content.ilike(f"%{keyword}%")
            ))

        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(Knowledge.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_knowledge(
        self,
        title: str,
        content: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        source_type: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Knowledge:
        """创建知识条目"""
        knowledge = Knowledge(
            title=title,
            content=content,
            category=category,
            tags=tags,
            source=source,
            source_type=source_type,
            created_by=created_by,
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        return knowledge

    async def update_knowledge(self, knowledge_id: int, **kwargs) -> Optional[Knowledge]:
        """更新知识条目"""
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return None

        for key, value in kwargs.items():
            if hasattr(knowledge, key) and value is not None:
                setattr(knowledge, key, value)

        await self.db.commit()
        await self.db.refresh(knowledge)
        return knowledge

    async def delete_knowledge(self, knowledge_id: int) -> bool:
        """删除知识条目"""
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return False

        await self.db.delete(knowledge)
        await self.db.commit()
        return True

    async def search_semantic(self, query: str, top_k: int = 5, category: Optional[str] = None) -> List[dict]:
        """语义搜索 - 使用pgvector余弦距离（如果可用）"""
        try:
            # 检查 pgvector 扩展是否可用
            check = await self.db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            if not check.scalar():
                # pgvector 不可用，回退到关键词搜索
                return await self._search_keyword_fallback(query, top_k, category)

            from app.services.embedding_service import generate_embedding
            query_embedding = await generate_embedding(query)

            from pgvector.sqlalchemy import Vector
            stmt = select(
                Knowledge,
                Knowledge.embedding.cosine_distance(query_embedding).label("distance")
            )

            if category:
                stmt = stmt.where(Knowledge.category == category)

            stmt = stmt.order_by(Knowledge.embedding.cosine_distance(query_embedding))
            stmt = stmt.limit(top_k)

            result = await self.db.execute(stmt)
            rows = result.all()

            return [
                {
                    "id": row.Knowledge.id,
                    "title": row.Knowledge.title,
                    "content": row.Knowledge.content[:500],
                    "category": row.Knowledge.category,
                    "tags": row.Knowledge.tags,
                    "source": row.Knowledge.source,
                    "score": round(1.0 - row.distance, 4)
                }
                for row in rows
            ]
        except Exception:
            # pgvector 不可用，回退到关键词搜索
            return await self._search_keyword_fallback(query, top_k, category)

    async def _search_keyword_fallback(self, query: str, top_k: int = 5, category: Optional[str] = None) -> List[dict]:
        """关键词搜索回退"""
        stmt = select(Knowledge).where(or_(
            Knowledge.title.ilike(f"%{query}%"),
            Knowledge.content.ilike(f"%{query}%")
        ))
        if category:
            stmt = stmt.where(Knowledge.category == category)
        stmt = stmt.limit(top_k)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "content": r.content[:500],
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
                "score": 0.5
            }
            for r in rows
        ]
