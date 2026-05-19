"""长期记忆服务"""

import logging
from datetime import datetime
from typing import List, Optional, Dict

from sqlalchemy import select, and_, or_, text, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory

logger = logging.getLogger("microbubble.memory")


class MemoryService:
    """长期记忆 CRUD + 语义搜索 + 提取"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_memory(
        self,
        user_id: int,
        memory_type: str,
        content: str,
        key: Optional[str] = None,
        importance: float = 0.7,
        source_session: Optional[str] = None
    ) -> Memory:
        """保存记忆，偏好类型按 (user_id, key) upsert"""
        # 偏好类型：按 key 去重更新
        if memory_type == "preference" and key:
            existing = await self._find_preference(user_id, key)
            if existing:
                existing.content = content
                existing.importance = importance
                await self.db.commit()
                await self.db.refresh(existing)
                await self._generate_embedding(existing, content)
                return existing

        memory = Memory(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            key=key,
            importance=importance,
            source_session=source_session,
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        # 后台生成嵌入
        await self._generate_embedding(memory, content)
        return memory

    async def _find_preference(self, user_id: int, key: str) -> Optional[Memory]:
        """查找已有的偏好记忆"""
        result = await self.db.execute(
            select(Memory).where(
                and_(
                    Memory.user_id == user_id,
                    Memory.memory_type == "preference",
                    Memory.key == key,
                    Memory.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def _generate_embedding(self, memory: Memory, content: str):
        """尝试生成向量嵌入，失败不阻塞"""
        try:
            from app.services.embedding_service import generate_embedding
            embedding = await generate_embedding(content)
            memory.embedding = embedding
            await self.db.commit()
            await self.db.refresh(memory)
        except Exception as e:
            logger.warning(f"记忆嵌入生成失败(memory_id={memory.id}): {e}")

    async def search_memories(
        self,
        user_id: int,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None
    ) -> List[dict]:
        """语义搜索用户记忆"""
        try:
            check = await self.db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if not check.scalar():
                return await self._search_keyword_fallback(user_id, query, top_k, memory_type)

            from app.services.embedding_service import generate_embedding
            query_embedding = await generate_embedding(query)

            stmt = select(
                Memory,
                Memory.embedding.cosine_distance(query_embedding).label("distance")
            ).where(
                and_(Memory.user_id == user_id, Memory.is_active == True)
            )
            if memory_type:
                stmt = stmt.where(Memory.memory_type == memory_type)
            stmt = stmt.order_by(Memory.embedding.cosine_distance(query_embedding))
            stmt = stmt.limit(top_k)

            result = await self.db.execute(stmt)
            rows = result.all()

            # 更新访问计数
            for row in rows:
                row.Memory.access_count += 1
                row.Memory.last_accessed_at = datetime.utcnow()
            await self.db.commit()

            return [
                {
                    "id": row.Memory.id,
                    "memory_type": row.Memory.memory_type,
                    "key": row.Memory.key,
                    "content": row.Memory.content,
                    "importance": row.Memory.importance,
                    "score": round(1.0 - row.distance, 4)
                }
                for row in rows
            ]
        except Exception:
            return await self._search_keyword_fallback(user_id, query, top_k, memory_type)

    async def _search_keyword_fallback(
        self, user_id: int, query: str, top_k: int = 5, memory_type: Optional[str] = None
    ) -> List[dict]:
        """关键词搜索回退"""
        stmt = select(Memory).where(
            and_(
                Memory.user_id == user_id,
                Memory.is_active == True,
                Memory.content.ilike(f"%{query}%")
            )
        )
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)
        stmt = stmt.order_by(desc(Memory.importance)).limit(top_k)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "memory_type": r.memory_type,
                "key": r.key,
                "content": r.content,
                "importance": r.importance,
                "score": 0.5
            }
            for r in rows
        ]

    async def get_active_memories(
        self,
        user_id: int,
        memory_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Memory]:
        """获取活跃记忆，按重要性排序"""
        stmt = select(Memory).where(
            and_(Memory.user_id == user_id, Memory.is_active == True)
        )
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)
        stmt = stmt.order_by(desc(Memory.importance)).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def forget_memory(self, user_id: int, memory_id: int) -> bool:
        """软删除记忆"""
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id == memory_id, Memory.user_id == user_id)
            )
        )
        memory = result.scalar_one_or_none()
        if not memory:
            return False
        memory.is_active = False
        await self.db.commit()
        return True

    async def update_memory(self, user_id: int, memory_id: int, content: str) -> Optional[Memory]:
        """更新记忆内容"""
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id == memory_id, Memory.user_id == user_id)
            )
        )
        memory = result.scalar_one_or_none()
        if not memory:
            return None
        memory.content = content
        await self.db.commit()
        await self.db.refresh(memory)
        await self._generate_embedding(memory, content)
        return memory

    async def list_memories(
        self,
        user_id: int,
        memory_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple:
        """列表查询，返回 (items, total)"""
        filters = [Memory.user_id == user_id, Memory.is_active == True]
        if memory_type:
            filters.append(Memory.memory_type == memory_type)

        count_result = await self.db.execute(
            select(func.count()).select_from(Memory).where(*filters)
        )
        total = count_result.scalar() or 0

        stmt = select(Memory).where(*filters)
        stmt = stmt.order_by(desc(Memory.importance), desc(Memory.created_at))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        items = result.scalars().all()
        return items, total

    async def extract_memories_from_conversation(
        self,
        user_id: int,
        messages: List[Dict],
        session_id: str
    ):
        """从对话中提取值得记忆的信息"""
        import anthropic
        import json
        from app.config import settings

        # 构建对话文本
        conversation = ""
        for msg in messages[-10:]:  # 最近10条
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            if isinstance(content, list):
                # 多模态消息，只取文本部分
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                )
            if content:
                conversation += f"{role}: {content}\n"

        if len(conversation) < 50:
            return  # 对话太短，跳过

        prompt = f"""分析以下对话，提取值得长期记忆的信息。返回严格的JSON数组（不要包含其他文字）。
只提取用户明确表达的偏好、重要的事实信息、人员-项目-成果关系。
不要提取临时性信息。如果没有值得记忆的内容，返回空数组 []。

对话内容:
{conversation[:2000]}

返回格式:
[
  {{"type": "preference", "key": "偏好描述", "content": "具体内容", "importance": 0.8}},
  {{"type": "entity", "content": "实体关系描述", "importance": 0.7}}
]"""

        try:
            client = anthropic.AsyncAnthropic(
                api_key=settings.CLAUDE_API_KEY,
                base_url=settings.CLAUDE_BASE_URL or None,
            )
            response = await client.messages.create(
                model=settings.CLAUDE_MODEL or "mimo-v2.5",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content = block.text
                    break

            text_content = text_content.strip()
            if text_content.startswith("```"):
                text_content = text_content.split("\n", 1)[-1]
                if text_content.endswith("```"):
                    text_content = text_content[:-3]
                text_content = text_content.strip()

            memories = json.loads(text_content)
            if not isinstance(memories, list):
                return

            for mem in memories:
                if not isinstance(mem, dict) or "content" not in mem:
                    continue
                await self.save_memory(
                    user_id=user_id,
                    memory_type=mem.get("type", "entity"),
                    content=mem["content"],
                    key=mem.get("key"),
                    importance=mem.get("importance", 0.7),
                    source_session=session_id,
                )
            logger.info(f"从对话中提取了 {len(memories)} 条记忆(user_id={user_id})")
        except json.JSONDecodeError:
            logger.warning("记忆提取返回非JSON格式")
        except Exception as e:
            logger.error(f"记忆提取失败: {e}")


# Celery 定时任务：记忆维护
try:
    from celery import shared_task

    @shared_task(name="app.services.memory_service.maintenance_task")
    def maintenance_task():
        """每小时执行：衰减重要性，停用低重要性记忆"""
        import asyncio
        asyncio.run(_maintenance_async())

    async def _maintenance_async():
        from app.core.database import async_session
        from sqlalchemy import update
        async with async_session() as db:
            # 衰减重要性 (×0.99)
            await db.execute(
                update(Memory)
                .where(Memory.is_active == True)
                .values(importance=Memory.importance * 0.99)
            )
            # 停用低重要性记忆
            await db.execute(
                update(Memory)
                .where(Memory.is_active == True, Memory.importance < 0.1)
                .values(is_active=False)
            )
            await db.commit()
            logger.info("记忆维护完成：重要性衰减 + 低重要性停用")
except ImportError:
    pass  # Celery 不可用时跳过
