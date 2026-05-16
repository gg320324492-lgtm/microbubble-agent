from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional

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
            created_by=created_by
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

    async def search_semantic(self, query: str, top_k: int = 5) -> List[dict]:
        """语义搜索（暂用关键词匹配，后续接入 pgvector）"""
        results = await self.get_knowledge_list(keyword=query)
        return [
            {
                "id": r.id,
                "title": r.title,
                "content": r.content[:500],
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
                "score": 0.8
            }
            for r in results[:top_k]
        ]
