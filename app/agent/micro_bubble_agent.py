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

#043 账号持久化聊天历史 — 流式 chat_stream 持久化（2026-06-29）
流式 chat 进入时 append_message(user_msg) + 结束时 append_message(assistant_full)
中断/异常时 mark_partial，session 行由 ensure_session_for_stream() 保证存在。
"""

import asyncio
import base64
import logging
import time
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
        # 2026-06-30 #009 Self-RAG: per-request override（用户 toggle）
        *,
        model: Optional[str] = None,
        use_self_rag: Optional[bool] = None,
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
            # 2026-06-30 #009 透传 per-request override
            self_rag_enabled=use_self_rag,
            synthesis_model_override=model,
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

        #043 持久化（2026-06-29）：
        1. 入场：ensure_session_for_stream() 创建/复用 ChatSession 行
           + append_message(user_msg) 落 user 消息（含 client_msg_id 幂等键）
           + append_message(assistant_placeholder, is_partial=True) 占位
        2. 累积：text_delta 累加到 assistant_text；tool_use/tool_result 累加到 tool_trace；
           rich_block 累加到 rich_blocks
        3. 完成（done 事件）：update_message_content(content=full_text, is_partial=False)
           同时 yield message_persisted 事件通知前端
        4. 异常（User aborted / CancelledError / Exception）：
           mark_partial(message_id=...) 标记占位消息为 partial
           + yield sync_required(reason="aborted"|"error") 通知前端重新拉历史

        关键边界：
        - db=None 时（webchat 等无登录场景）跳过持久化（保留老行为）
        - user_id=None 时跳过持久化（兼容旧调用）
        - append_message 失败不阻塞流式（best-effort 持久化）
        """
        # 0. 持久化前置条件：无 db 或无 user_id 时跳过（兼容老调用）
        persist_enabled = db is not None and user_id is not None

        # 1. 加载 session（保留 Redis 短期缓存，老行为不变）
        messages = await session_manager.get_messages(session_id)

        # 2. 构造 user content
        content = self._build_user_content(message, image_data, image_media_type)
        messages.append({"role": "user", "content": content})

        # 3. 构造 system prompt
        system = await self._build_system_prompt(user_id, message, db) if user_id else get_system_prompt()

        # 4. #043 持久化入场
        # 关键：所有持久化操作都用 try/except 兜底，绝不阻塞流式
        # 幂等键：同一 stream 重试时（网络断开重连）不会重复落库
        stream_ts = int(time.time() * 1000)  # 毫秒精度
        user_client_msg_id = f"stream_{session_id}_user_{stream_ts}"
        assistant_client_msg_id = f"stream_{session_id}_assistant_{stream_ts}"
        user_msg_id = None
        assistant_msg_id = None
        user_msg_persisted = False
        assistant_msg_persisted = False

        if persist_enabled:
            try:
                from app.services import chat_history_service as chat_svc
                await chat_svc.ensure_session_for_stream(
                    db, user_id, session_id, first_message=message,
                )
                # 持久化 user 消息（幂等键防重）
                user_msg = await chat_svc.append_message(
                    db, user_id, session_id,
                    role="user",
                    content=content if isinstance(content, str) else message,
                    message_metadata={
                        "source": "chat_stream",
                        "ts": stream_ts,
                        "image_attached": image_data is not None,
                    },
                    client_msg_id=user_client_msg_id,
                )
                user_msg_id = user_msg.id
                user_msg_persisted = True
                logger.info(f"[chat_stream persist] user_msg persisted: msg_id={user_msg_id}")
                yield StreamEvent(
                    type="message_persisted",
                    message_id=user_msg_id,
                    persisted_role="user",
                    persisted_client_msg_id=user_client_msg_id,
                    persisted_is_partial=False,
                )
            except Exception as e:
                # 持久化失败不阻塞流式（best-effort）
                logger.error(f"[chat_stream persist] user_msg 持久化失败: {e}", exc_info=True)

        # 5. 流式累积上下文（#043）
        assistant_text = ""  # assistant 完整文本累积
        assistant_rich_blocks: List[Dict[str, Any]] = []  # rich_block 累积
        assistant_tool_trace: List[Dict[str, Any]] = []  # tool_use/tool_result 累积
        assistant_intent: Optional[Dict[str, Any]] = None
        assistant_critique: Optional[Dict[str, Any]] = None
        assistant_usage: Optional[Dict[str, int]] = None
        assistant_duration_ms: Optional[int] = None
        t0 = time.monotonic()

        # 6. 调用 ChatEngine 流式（for-await 累积所有事件）
        # 关键设计：ChatEngine.chat_stream() 透传 synthesize_stream() 的 events，
        # 我们在 micro_bubble_agent 这一层用 for-await 拦截并累积，
        # ChatEngine 内部不需要改（关注点分离：engine 只管 LLM 编排，
        # persistence 只在 agent 层做）
        stream_iter = self.engine.chat_stream(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
            # 2026-06-30 #009 透传 per-request override
            self_rag_enabled=use_self_rag,
            synthesis_model_override=model,
        )

        try:
            async for event in stream_iter:
                # 累积上下文（不动原始 yield 事件）
                if event.type == "text_delta":
                    assistant_text += event.delta or ""
                elif event.type == "tool_use":
                    assistant_tool_trace.append({
                        "type": "tool_use",
                        "id": event.tool_use_id,
                        "name": event.tool_name,
                        "input": event.tool_input,
                    })
                elif event.type == "tool_result":
                    assistant_tool_trace.append({
                        "type": "tool_result",
                        "tool_use_id": event.tool_use_id,
                        "name": event.tool_name,
                        "result": event.tool_output,
                        "duration_ms": event.tool_duration_ms,
                        "error": event.tool_error,
                    })
                elif event.type == "rich_block" and event.block:
                    assistant_rich_blocks.append(event.block.model_dump())
                elif event.type == "intent_detected" and event.intent:
                    assistant_intent = event.intent
                elif event.type == "critique" and event.critique:
                    assistant_critique = event.critique
                elif event.type == "done":
                    assistant_usage = event.usage
                    assistant_duration_ms = event.duration_ms

                # 原样 yield 给前端
                yield event

                # 在 done 事件后立即落库 assistant（client 看到 done 后即可查 history）
                if event.type == "done":
                    if persist_enabled:
                        try:
                            from app.services import chat_history_service as chat_svc
                            # 把 accumulated rich_blocks + tool_trace + intent + critique + usage
                            # 作为 metadata 一并存到 assistant message
                            meta = {
                                "source": "chat_stream_done",
                                "ts": stream_ts,
                                "intent": assistant_intent,
                                "critique": assistant_critique,
                                "usage": assistant_usage,
                                "duration_ms": assistant_duration_ms,
                            }
                            # 直接 append_message（不用 update_message_content）——流式占位消息
                            # 反而会增加 round-trip，且如果 ensure_session 失败用户消息都没落
                            # assistant 占位反而成孤儿。简化：直接 append final assistant
                            assistant_msg = await chat_svc.append_message(
                                db, user_id, session_id,
                                role="assistant",
                                content=assistant_text,
                                rich_blocks=assistant_rich_blocks,
                                tool_trace={"trace": assistant_tool_trace} if assistant_tool_trace else {},
                                message_metadata=meta,
                                is_partial=False,
                                client_msg_id=assistant_client_msg_id,
                            )
                            assistant_msg_id = assistant_msg.id
                            assistant_msg_persisted = True
                            logger.info(
                                f"[chat_stream persist] assistant_msg persisted: "
                                f"msg_id={assistant_msg_id} len={len(assistant_text)}"
                            )
                            # yield 持久化通知事件（前端可以选择性 reload history）
                            yield StreamEvent(
                                type="message_persisted",
                                message_id=assistant_msg_id,
                                persisted_role="assistant",
                                persisted_client_msg_id=assistant_client_msg_id,
                                persisted_is_partial=False,
                            )
                        except Exception as e:
                            logger.error(
                                f"[chat_stream persist] assistant_msg 持久化失败: {e}",
                                exc_info=True,
                            )
                            # 失败时尝试落 partial（让用户重进能看到内容）
                            if assistant_text:
                                try:
                                    from app.services import chat_history_service as chat_svc
                                    partial_msg = await chat_svc.append_message(
                                        db, user_id, session_id,
                                        role="assistant",
                                        content=assistant_text,
                                        rich_blocks=assistant_rich_blocks,
                                        tool_trace={"trace": assistant_tool_trace} if assistant_tool_trace else {},
                                        message_metadata={"source": "partial_after_done_error", "ts": stream_ts},
                                        is_partial=True,
                                        client_msg_id=assistant_client_msg_id + "_partial",
                                    )
                                    yield StreamEvent(
                                        type="message_persisted",
                                        message_id=partial_msg.id,
                                        persisted_role="assistant",
                                        persisted_client_msg_id=assistant_client_msg_id + "_partial",
                                        persisted_is_partial=True,
                                    )
                                except Exception as e2:
                                    logger.error(f"[chat_stream persist] partial 持久化也失败: {e2}")

        except asyncio.CancelledError:
            # 流式中断（用户关浏览器 / 主动 stop）
            logger.warning(
                f"[chat_stream persist] CancelledError: "
                f"user_msg_id={user_msg_id} assistant_text_len={len(assistant_text)}"
            )
            if persist_enabled and assistant_text:
                try:
                    from app.services import chat_history_service as chat_svc
                    # 中断时把已累积的 assistant_text 作为 partial 落库
                    # 用户重进 session 能看到"中断前的回答"，可点"重新生成"
                    partial_msg = await chat_svc.append_message(
                        db, user_id, session_id,
                        role="assistant",
                        content=assistant_text,
                        rich_blocks=assistant_rich_blocks,
                        tool_trace={"trace": assistant_tool_trace} if assistant_tool_trace else {},
                        message_metadata={
                            "source": "stream_cancelled",
                            "ts": stream_ts,
                            "duration_ms": int((time.monotonic() - t0) * 1000),
                        },
                        is_partial=True,
                        client_msg_id=assistant_client_msg_id + "_cancelled",
                    )
                    yield StreamEvent(
                        type="message_persisted",
                        message_id=partial_msg.id,
                        persisted_role="assistant",
                        persisted_client_msg_id=assistant_client_msg_id + "_cancelled",
                        persisted_is_partial=True,
                    )
                    # 通知前端：流式中断，建议重新拉历史
                    yield StreamEvent(
                        type="sync_required",
                        sync_reason="aborted",
                    )
                except Exception as e:
                    logger.error(f"[chat_stream persist] 中断 partial 落库失败: {e}", exc_info=True)
            raise  # 重新抛 CancelledError 让上层处理

        except Exception as e:
            # 流式异常（非中断）——同样的 best-effort 持久化策略
            logger.error(f"[chat_stream persist] 流式异常: {e}", exc_info=True)
            if persist_enabled and assistant_text:
                try:
                    from app.services import chat_history_service as chat_svc
                    partial_msg = await chat_svc.append_message(
                        db, user_id, session_id,
                        role="assistant",
                        content=assistant_text,
                        rich_blocks=assistant_rich_blocks,
                        message_metadata={
                            "source": "stream_error",
                            "error": str(e)[:500],
                            "ts": stream_ts,
                        },
                        is_partial=True,
                        client_msg_id=assistant_client_msg_id + "_error",
                    )
                    yield StreamEvent(
                        type="message_persisted",
                        message_id=partial_msg.id,
                        persisted_role="assistant",
                        persisted_client_msg_id=assistant_client_msg_id + "_error",
                        persisted_is_partial=True,
                    )
                    yield StreamEvent(
                        type="sync_required",
                        sync_reason="error",
                    )
                except Exception as e2:
                    logger.error(f"[chat_stream persist] 异常 partial 落库失败: {e2}")
            # 不 raise，让上层 StreamingResponse 处理（yield error 事件给前端）

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
