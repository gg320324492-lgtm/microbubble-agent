"""MicroBubbleAgent — 主类（v2 架构）

设计：
- 主类只做依赖装配（~150 行）
- 所有 chat 逻辑委托给 ChatEngine
- 向后兼容旧的 MicroBubbleAgent 接口（chat/chat_stream/clear_session）

对外接口（保持与旧 core.py 一致）：
- agent = MicroBubbleAgent()  单例
- await agent.chat(message, session_id, db, user_id, ...) -> dict
- async for event in agent.chat_stream(message, session_id, db, user_id, ...): ...
- await agent.clear_session(session_id)
"""

import asyncio
import base64
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from app.agent.chat_engine import ChatEngine
from app.agent.prompts import (
    _is_meeting_transcript_query,
    get_meeting_analyzer_prompt,
    get_system_prompt,
)
from app.agent.protocol import StreamEvent
from app.agent.session_manager import session_manager
from app.agent.tracing import TraceCollector
from app.config import settings
from app.models.base import BEIJING_TZ

logger = logging.getLogger("microbubble.agent")


class MicroBubbleAgent:
    """微纳米气泡课题组 Agent 主类（v2 架构）"""

    def __init__(self):
        self.engine = ChatEngine()
        logger.info("MicroBubbleAgent v2 初始化完成")

    # =========================================================================
    # 公开 API
    # =========================================================================

    async def chat(
        self,
        message: str,
        session_id: str = "default",
        history: Optional[List[Dict]] = None,
        db=None,
        image_data: Optional[bytes] = None,
        image_media_type: str = "image/png",
        user_id: Optional[int] = None,
        channel_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """对话接口（非流式）

        返回 dict 兼容旧接口：
        {
            "content": str,  # brief 文本
            "content_blocks": list,
            "tool_calls": list,
            "tool_results": list,
            "rich_blocks": list,  # 新增
            "tool_trace": list,   # 新增
            "usage": dict,        # 新增
            "duration_ms": int,   # 新增
        }
        """
        # 1. 加载 session
        messages = await session_manager.get_messages(session_id)
        if history:
            messages = history

        # 2. 构造 user content（图片 or 文本）
        content = self._build_user_content(
            message, image_data, image_media_type
        )
        messages.append({"role": "user", "content": content})

        # 3. 构造 system prompt
        system = await self._build_system_prompt(user_id, message, db)

        # 4. 调用 ChatEngine
        result = await self.engine.chat_with_brief_and_detail(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
        )

        # 5. 持久化 session（截断到 window size）
        if history is None:
            messages.append({"role": "assistant", "content": result["content"]})
            if len(messages) > settings.SESSION_WINDOW_SIZE:
                messages = messages[-settings.SESSION_WINDOW_SIZE:]
            await session_manager.save_messages(session_id, messages)
            await session_manager.update_meta(session_id, user_id=user_id)

        # 6. 异步后台：记忆 + 知识提取
        if user_id and db:
            asyncio.create_task(self._extract_memories_bg(user_id, messages, session_id))
            asyncio.create_task(self._extract_knowledge_bg(user_id, messages, session_id))

        return result

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        db=None,
        image_data: Optional[bytes] = None,
        image_media_type: str = "image/png",
        user_id: Optional[int] = None,
        channel_user_id: Optional[str] = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式对话接口

        yield StreamEvent 序列
        """
        # 1. 加载 session
        messages = await session_manager.get_messages(session_id)

        # 2. 构造 user content
        content = self._build_user_content(message, image_data, image_media_type)
        messages.append({"role": "user", "content": content})

        # 3. 构造 system prompt
        system = await self._build_system_prompt(user_id, message, db) if user_id else get_system_prompt()

        # 4. 调用 ChatEngine 流式
        async for event in self.engine.chat_stream(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
        ):
            yield event

    async def clear_session(self, session_id: str):
        """清除会话历史（保留 dirty flag 行为不变）

        新行为：只删 session 内容，不动 meta。WS 断连时用 mark_dirty。
        """
        await session_manager.delete(session_id)

    # =========================================================================
    # 内部方法
    # =========================================================================

    def _build_user_content(
        self,
        message: str,
        image_data: Optional[bytes],
        image_media_type: str,
    ) -> Any:
        """构造 user 消息 content（图 or 文本）"""
        if image_data:
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
            return [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": message or "请描述这张图片"},
            ]
        # 纯文本：注入当前时间
        now = datetime.now(BEIJING_TZ)
        time_tag = f"[当前时间: {now.strftime('%Y-%m-%d %H:%M')}] "
        return time_tag + message

    async def _build_system_prompt(
        self,
        user_id: Optional[int],
        query: str,
        db=None,
    ) -> str:
        """构造系统提示词（用户身份 + 记忆 + 会议转录检测）"""
        # 1. 基础 prompt（DB 有自定义模板时优先用）
        base = None
        if db:
            try:
                from app.services.prompt_service import PromptTemplateService
                svc = PromptTemplateService(db)
                base = await svc.get_active_template("default")
            except Exception:
                pass
        if not base:
            base = get_system_prompt()

        if not user_id or not db:
            return base

        parts = [base]

        # 2. 用户身份
        try:
            from app.models.member import Member
            member = await db.get(Member, user_id)
            if member:
                role_map = {"admin": "管理员", "leader": "组长", "member": "普通成员"}
                role_label = role_map.get(member.role, member.role)
                parts.append(f"\n当前用户信息:\n- 姓名: {member.name}\n- 角色: {role_label}")
                if member.role in ("admin", "leader"):
                    parts.append("- 该用户拥有管理员权限")
                if member.custom_instructions:
                    parts.append(f"\n用户自定义指令:\n{member.custom_instructions}")
        except Exception as e:
            logger.warning(f"注入用户身份失败: {e}")

        # 3. 长期记忆
        try:
            from app.services.memory_service import MemoryService
            mem_svc = MemoryService(db)
            memories = await mem_svc.search_memories(user_id, query, top_k=5)
            if memories:
                memory_text = "\n".join(
                    f"- [{m['memory_type']}] {m['content']}" for m in memories
                )
                parts.append(f"\n关于用户的长期记忆:\n{memory_text}")
        except Exception as e:
            logger.warning(f"构建记忆提示词失败: {e}")

        # 4. 会议转录检测
        if _is_meeting_transcript_query(query):
            parts.append(get_meeting_analyzer_prompt())

        return "\n".join(parts)

    # =========================================================================
    # 后台任务
    # =========================================================================

    async def _extract_memories_bg(self, user_id: int, messages: List[Dict], session_id: str):
        """后台记忆提取"""
        from app.core.database import async_session
        try:
            async with async_session() as db:
                from app.services.memory_service import MemoryService
                mem_svc = MemoryService(db)
                await mem_svc.extract_memories_from_conversation(
                    user_id=user_id, messages=messages, session_id=session_id
                )
        except Exception as e:
            logger.error(f"后台记忆提取失败: {e}")

    async def _extract_knowledge_bg(self, user_id: int, messages: List[Dict], session_id: str):
        """后台知识提取（从对话中）

        2026-06-14 方案 C Stage 5：原本 delegate 给 legacy core.py.MicroBubbleAgent
        现把 _extract_and_save_knowledge 逻辑直接搬到本方法内（独立可移植）
        """
        from app.core.database import async_session
        from app.core.llm import get_anthropic_client, get_default_model
        try:
            # 构建对话文本（仅最近 10 条）
            conversation = ""
            for msg in messages[-10:]:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                    )
                if content:
                    conversation += f"{role}: {content}\n"

            if len(conversation) < 100:
                return  # 太短不提取

            prompt = f"""分析以下对话，判断是否包含值得保存到知识库的专业知识。
只保存：实验方法、研究发现、技术方案、经验总结、专业概念解释、操作步骤。
不保存：闲聊、简单问答、临时性信息、任务安排、会议通知。

对话内容:
{conversation[:3000]}

如果没有值得保存的知识，返回 {{"save": false}}
如果有，返回严格的JSON格式（不要包含其他文字）：
{{"save": true, "title": "知识标题", "content": "整理后的完整知识内容", "category": "基础/方法/文献/FAQ", "tags": ["标签1", "标签2"]}}"""

            client = get_anthropic_client()
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )

            # 2026-06-14 Stage 5 收尾：兼容 mimo 等思考型模型只返 thinking block
            from app.core.llm import extract_text_from_response
            text = extract_text_from_response(response).strip()

            import json as _json
            try:
                result = _json.loads(text)
            except _json.JSONDecodeError:
                # 尝试剥 markdown 包裹
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines and lines[-1].strip() == "```":
                        text = "\n".join(lines[1:-1])
                    else:
                        text = "\n".join(lines[1:])
                    result = _json.loads(text)
                else:
                    raise

            if not result.get("save"):
                return

            # 写入 knowledge_items 表
            from app.core.database import KnowledgeItem
            async with async_session() as session:
                item = KnowledgeItem(
                    title=result["title"],
                    content=result["content"],
                    category=result.get("category", "基础"),
                    tags=result.get("tags", []),
                    source="conversation",
                    session_id=session_id,
                    user_id=user_id,
                )
                session.add(item)
                await session.commit()
                logger.info(f"知识提取成功: {result['title'][:50]}")
        except Exception as e:
            logger.error(f"后台知识提取失败: {e}")


# 全局单例
agent = MicroBubbleAgent()
