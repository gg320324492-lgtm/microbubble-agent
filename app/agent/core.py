import asyncio
import base64
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.base import utcnow, BEIJING_TZ
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

from app.config import settings
from app.agent.prompts import get_system_prompt, get_detail_prompt, _weekdays
from app.agent.tools import TOOLS
from app.services.task_service import TaskService
from app.services.member_service import MemberService
from app.services.meeting_service import MeetingService
from app.services.project_service import ProjectService
from app.services.knowledge_service import KnowledgeService
from app.services.search_service import search_service
from app.core.redis import session_store

logger = logging.getLogger("microbubble.agent")


def _serialize_content(content) -> Any:
    """将 Claude SDK content blocks 转为可 JSON 序列化的格式"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        result = []
        for block in content:
            if hasattr(block, "model_dump"):
                result.append(block.model_dump())
            elif isinstance(block, dict):
                result.append(block)
            else:
                result.append(str(block))
        return result
    return str(content)


class MicroBubbleAgent:
    """微纳米气泡课题组Agent核心"""

    def __init__(self):
        self.client = get_anthropic_client()
        self.model = get_default_model()
        self.tools = TOOLS
        self._sessions: Dict[str, List[Dict]] = {}

    async def _load_session(self, session_id: str) -> List[Dict]:
        if session_id in self._sessions:
            return self._sessions[session_id]
        messages = await session_store.get_messages(session_id)
        self._sessions[session_id] = messages
        return messages

    async def _save_session(self, session_id: str, messages: List[Dict]):
        self._sessions[session_id] = messages
        await session_store.save_messages(session_id, messages)

    async def _build_system_prompt(self, user_id: Optional[int], query: str, db=None) -> str:
        """构建系统提示词，注入用户身份和相关长期记忆"""
        # 尝试从数据库加载自定义模板
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

        # 注入当前用户身份
        try:
            from app.models.member import Member
            member = await db.get(Member, user_id)
            if member:
                role_map = {"admin": "管理员", "leader": "组长", "member": "普通成员"}
                role_label = role_map.get(member.role, member.role)
                parts.append(f"\n当前用户信息:\n- 姓名: {member.name}\n- 角色: {role_label}")
                if member.role in ("admin", "leader"):
                    parts.append("- 该用户拥有管理员权限，可以分配任务给任何人、管理所有成员和项目")
                # 注入用户自定义指令
                if member.custom_instructions:
                    parts.append(f"\n用户自定义指令:\n{member.custom_instructions}")
        except Exception as e:
            logger.warning(f"注入用户身份失败: {e}")

        # 注入相关长期记忆
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

        # 检测是否为会议转录，注入会议分析助手提示词
        if self._is_meeting_transcript(query):
            parts.append(self._get_meeting_analyzer_prompt())

        return "\n".join(parts)

    def _is_meeting_transcript(self, query: str) -> bool:
        """检测用户消息是否包含会议转录文字"""
        if not query:
            return False
        patterns = ["【", "转录", "会议记录", "发言内容", "发言："]
        return any(p in query for p in patterns)

    def _get_meeting_analyzer_prompt(self) -> str:
        """会议分析助手专用提示词"""
        return """

## 会议分析助手模式

检测到你正在处理会议转录文字。请按以下步骤执行：

1. **检测发言者**：调用 analyze_meeting_transcript 工具（不传 speaker_mapping），自动识别文本中的不同发言者
2. **确认映射**：将检测到的发言者列表展示给用户，询问是否需要调整映射关系
3. **完整分析**：确认映射后再次调用 analyze_meeting_transcript（传入 speaker_mapping），进行完整分析并自动创建会议和任务

### 发言者识别
- 识别【姓名】格式标签或"姓名说："格式
- 尝试将发言者名称与课题组成员匹配（通过 query_members）
- 不确定的映射关系应向用户确认

### 行动项识别要点
- 包含"负责"、"完成"、"安排"、"下次"、"尽快"、"记得"等关键词的发言内容
- 发言中明确指定了负责人的事项（如"张三负责这个"）
- 决策中需要执行的具体事项
- 每条行动项应标注来源发言人

### 任务创建规则
- 优先匹配转录中提到的负责人到课题组成员
- 截止日期：根据会议时间和事项性质合理推断（一般事项 1 周内，复杂事项 2-4 周）
- 优先级：根据事项的重要性和紧急性判断（涉及项目关键节点 → high）
- description 中标注"来源：XXX 会议"
- 如果无法确定负责人，任务分配给系统管理员

### 最终回复格式
- 发言者统计（每位发言者的发言次数/字数占比）
- 会议摘要（按 `2026.5.28 例行例会` 信息密度，3-6 句话，包含背景、过程、关键观点、结论和后续方向）
- 讨论要点（`【发言人】内容`，短会议至少 3 条，信息充足时 5-8 条）
- 决议事项（`【发言人/双方/全组】内容`，写清楚决定/共识和后续用途）
- 任务汇总表（负责人 | 任务内容 | 截止日期 | 优先级 | 置信度）

### 会议纪要标准
- 必须遵守 docs/meeting-minutes-standard.md
- 不允许只输出简单摘要
- 声纹或发言人无法确认时使用发言人A/B，不要强行猜姓名
"""

    async def _extract_and_save_memories(self, user_id: int, messages: List[Dict], session_id: str):
        """后台任务：从对话中提取记忆"""
        from app.core.database import async_session
        try:
            async with async_session() as db:
                from app.services.memory_service import MemoryService
                mem_svc = MemoryService(db)
                await mem_svc.extract_memories_from_conversation(
                    user_id=user_id,
                    messages=messages,
                    session_id=session_id
                )
        except Exception as e:
            logger.error(f"后台记忆提取失败: {e}")

    async def _extract_and_save_knowledge(self, user_id: int, messages: List[Dict], session_id: str):
        """后台任务：从对话中提取有价值的知识存入知识库"""
        from app.core.database import async_session
        try:
            # 构建对话文本
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
                return

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
                messages=[{"role": "user", "content": prompt}]
            )
            text_content = extract_text_from_response(response)
            result = parse_llm_json(text_content)
            if not result.get("save"):
                return

            async with async_session() as db:
                from app.services.knowledge_service import KnowledgeService
                kb_svc = KnowledgeService(db)
                await kb_svc.create_from_conversation(
                    title=result["title"],
                    content=result["content"],
                    category=result.get("category"),
                    tags=result.get("tags", []),
                    created_by=user_id,
                    session_id=session_id,
                )
                logger.info(f"从对话中提取知识: {result['title']}(user_id={user_id})")
        except json.JSONDecodeError:
            logger.warning("知识提取返回非JSON格式")
        except Exception as e:
            logger.error(f"对话知识提取失败: {e}")

    async def _generate_brief(self, messages: List[Dict], system: str, db=None, user_id=None, channel_user_id: Optional[str] = None) -> str:
        """生成【简要】回复（带工具调用）"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=system,
            tools=self.tools,
            messages=messages
        )
        # 处理工具调用（递归）
        processed = await self._process_response(response, "", db, messages, user_id=user_id, channel_user_id=channel_user_id)
        return processed.get("content", "")

    async def _generate_detail(self, messages: List[Dict], system: str) -> str:
        """生成【详细】回复（不带工具调用）"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=system,
            messages=messages
        )
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text
        return text

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
        """与Agent对话"""
        messages = await self._load_session(session_id)

        if history:
            messages = history

        # 构建消息内容
        if image_data:
            use_mcp_vision = getattr(settings, 'VISION_USE_MCP', False)
            if use_mcp_vision:
                # MCP 模式：通过 MCP 获取图片描述，再用文本和 LLM 对话
                image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
                from app.services.vision_service import VisionService
                vision_svc = VisionService()
                image_description = await vision_svc.analyze_image(
                    image_data,
                    f"请详细描述这张图片的内容，以便我回答用户关于这张图片的问题。用户的问题是：{message}"
                )
                # 图片转为文字描述发给 LLM（DeepSeek 等文本模型也能处理）
                content = (
                    f"[用户发送了一张图片，图片内容如下]\n"
                    f"{image_description}\n"
                    f"---\n用户消息: {message}"
                )
            else:
                # 直接模式：图片 base64 发给多模态 LLM
                image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
                content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": message
                    }
                ]
        else:
            # 纯文本消息，注入当前时间（北京时间）
            now = datetime.now(BEIJING_TZ)
            time_tag = f"[当前时间: {now.strftime('%Y-%m-%d %H:%M')}] "
            content = time_tag + message

        messages.append({"role": "user", "content": content})

        # 构建系统提示词（注入相关记忆）
        system = await self._build_system_prompt(user_id, message, db)

        # 并行发起两次调用（生成简要 + 生成详细）
        # 注意：_generate_brief 内部已处理工具调用，直接返回内容
        brief_task = asyncio.create_task(self._generate_brief(messages, system, db, user_id, channel_user_id))

        # 先等简要完成，立即返回
        brief_result = await brief_task

        # 更新 messages（简要回复已由 _generate_brief 处理工具调用）
        messages.append({
            "role": "assistant",
            "content": brief_result
        })

        # 后台等待详细回复并追加
        asyncio.create_task(self._append_detail(messages, session_id, db, user_id, channel_user_id))

        if len(messages) > settings.SESSION_WINDOW_SIZE:
            messages = messages[-settings.SESSION_WINDOW_SIZE:]

        await self._save_session(session_id, messages)

        # 后台提取记忆 + 知识
        if user_id and db:
            asyncio.create_task(
                self._extract_and_save_memories(user_id, messages, session_id)
            )
            asyncio.create_task(
                self._extract_and_save_knowledge(user_id, messages, session_id)
            )

        return {
            "content": brief_result,
            "content_blocks": [{"type": "text", "text": brief_result}],
            "tool_calls": [],
            "tool_results": []
        }

    async def _append_detail(self, messages: List[Dict], session_id: str, db, user_id: Optional[int], channel_user_id: Optional[str] = None):
        """后台任务：追加【详细】回复到会话"""
        try:
            # 获取带时间的详细 prompt
            now = datetime.now(BEIJING_TZ)
            today_str = f"{now.year}年{now.month}月{now.day}日（{_weekdays[now.weekday()]}）"
            time_str = now.strftime('%H:%M')
            system_detail = get_detail_prompt().format(today_str=today_str, time_str=time_str)

            detail_response = await self.client.messages.create(
                model=self.model,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=system_detail,
                messages=messages
            )

            detail_text = ""
            for block in detail_response.content:
                if block.type == "text":
                    detail_text += block.text

            if detail_text:
                # 保存详细回复到会话
                await session_store.append_message(session_id, {
                    "role": "assistant",
                    "content": detail_text
                })
                logger.info(f"追加【详细】回复到会话 {session_id}")
        except Exception as e:
            logger.error(f"生成【详细】回复失败: {e}")

    async def _process_response(self, response, session_id: str, db=None, messages: List[Dict] = None, user_id: Optional[int] = None, channel_user_id: Optional[str] = None, _continues_left: int = 3) -> Dict[str, Any]:
        """处理Claude响应"""
        if messages is None:
            messages = await self._load_session(session_id)

        content = []
        tool_calls = []
        tool_results = []

        for block in response.content:
            if block.type == "text":
                content.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })

        if tool_calls:
            for call in tool_calls:
                result = await self._execute_tool(call["name"], call["input"], db, user_id=user_id, channel_user_id=channel_user_id)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str)
                })

            messages = list(messages)
            messages.append({
                "role": "assistant",
                "content": _serialize_content(response.content)
            })
            messages.append({
                "role": "user",
                "content": tool_results
            })

            # 后续调用使用基础系统提示词（避免重复注入记忆）
            follow_up = await self.client.messages.create(
                model=self.model,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=get_system_prompt(),
                tools=self.tools,
                messages=messages
            )

            result = await self._process_response(follow_up, session_id, db, messages, user_id=user_id, channel_user_id=channel_user_id, _continues_left=_continues_left)
            return {
                "content": result["content"],
                "content_blocks": result["content_blocks"],
                "tool_calls": tool_calls,
                "tool_results": tool_results
            }

        # 截断检测：如果因 max_tokens 截断，自动续写
        if response.stop_reason == "max_tokens" and _continues_left > 0:
            logger.warning(f"回复因 max_tokens 截断，自动续写（剩余 {_continues_left} 次）")
            messages = list(messages)
            messages.append({"role": "assistant", "content": _serialize_content(response.content)})
            messages.append({"role": "user", "content": "请继续上一条回复的内容，不要重复已经写过的部分。"})

            continuation = await self.client.messages.create(
                model=self.model,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=get_system_prompt(),
                tools=self.tools,
                messages=messages
            )

            cont_result = await self._process_response(continuation, session_id, db, messages, user_id=user_id, _continues_left=_continues_left - 1)
            return {
                "content": "\n".join(content) + cont_result["content"],
                "content_blocks": list(response.content) + list(cont_result["content_blocks"]),
                "tool_calls": tool_calls + cont_result.get("tool_calls", []),
                "tool_results": tool_results + cont_result.get("tool_results", [])
            }

        return {
            "content": "\n".join(content) if content else "",
            "content_blocks": response.content,
            "tool_calls": tool_calls,
            "tool_results": tool_results
        }

    async def _execute_tool(self, name: str, input_data: Dict, db=None, user_id: Optional[int] = None, channel_user_id: Optional[str] = None) -> Any:
        """兼容旧 API：路由到 v2 装饰器注册表

        2026-06-12 v4 重构：原 794 行 20 个 if/elif 已被 @tool 装饰器 + 注册表取代
        此处只保留兼容壳 — 实际工具调用走 dispatch_tool（app/agent/tool_registry.py）
        """
        from app.agent.tool_registry import ToolContext, dispatch_tool
        ctx = ToolContext(
            db=db,
            user_id=user_id,
            channel_user_id=channel_user_id,
        )
        try:
            return await dispatch_tool(name, input_data, ctx)
        except Exception as e:
            return {"status": "error", "code": "TOOL_EXECUTION_ERROR", "message": f"工具 {name} 执行失败: {str(e)}"}

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        db=None,
        image_data: Optional[bytes] = None,
        image_media_type: str = "image/png",
        user_id: Optional[int] = None,
        channel_user_id: Optional[str] = None,
    ):
        """流式对话"""
        messages = await self._load_session(session_id)

        # 构建消息内容
        if image_data:
            use_mcp_vision = getattr(settings, 'VISION_USE_MCP', False)
            if use_mcp_vision:
                # MCP 模式：通过 MCP 获取图片描述，再用文本和 LLM 对话
                image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
                from app.services.vision_service import VisionService
                vision_svc = VisionService()
                image_description = await vision_svc.analyze_image(
                    image_data,
                    f"请详细描述这张图片的内容，以便我回答用户关于这张图片的问题。用户的问题是：{message}"
                )
                # 图片转为文字描述发给 LLM
                content = (
                    f"[用户发送了一张图片，图片内容如下]\n"
                    f"{image_description}\n"
                    f"---\n用户消息: {message}"
                )
            else:
                # 直接模式：图片 base64 发给多模态 LLM
                image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
                content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": message
                    }
                ]
        else:
            # 纯文本消息，注入当前时间（北京时间）
            now = datetime.now(BEIJING_TZ)
            time_tag = f"[当前时间: {now.strftime('%Y-%m-%d %H:%M')}] "
            content = time_tag + message

        messages.append({"role": "user", "content": content})

        system = await self._build_system_prompt(user_id, message, db) if user_id else get_system_prompt()

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=system,
            tools=self.tools,
            messages=messages
        ) as stream:
            full_text = ""
            tool_calls = []

            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        tool_calls.append({
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": {}
                        })
                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        full_text += event.delta.text
                        yield {"type": "text", "content": event.delta.text}
                    elif event.delta.type == "input_json_delta":
                        if tool_calls:
                            tool_calls[-1]["input_json"] = tool_calls[-1].get("input_json", "") + getattr(event.delta, "partial_json", "")

            response = await stream.get_final_message()

        if tool_calls:
            tool_results = []
            for call in tool_calls:
                input_data = call.get("input", {})
                if not input_data and "input_json" in call:
                    try:
                        input_data = json.loads(call["input_json"])
                    except (json.JSONDecodeError, TypeError):
                        input_data = {}
                result = await self._execute_tool(call["name"], input_data, db, user_id=user_id, channel_user_id=channel_user_id)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str)
                })

            messages = list(messages)
            messages.append({"role": "assistant", "content": _serialize_content(response.content)})
            messages.append({"role": "user", "content": tool_results})

            follow_up = await self.client.messages.create(
                model=self.model,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=system,
                tools=self.tools,
                messages=messages
            )

            follow_text = ""
            for block in follow_up.content:
                if block.type == "text":
                    follow_text += block.text
                    yield {"type": "text", "content": block.text}

            full_text += follow_text
            messages.append({
                "role": "assistant",
                "content": _serialize_content(follow_up.content)
            })

            # follow_up 截断续写
            if follow_up.stop_reason == "max_tokens":
                cont_text, cont_messages = await self._stream_continuation(messages, system)
                full_text += cont_text
                messages = cont_messages
        else:
            messages.append({
                "role": "assistant",
                "content": _serialize_content(response.content)
            })

            # 流式响应截断续写
            if response.stop_reason == "max_tokens":
                cont_text, cont_messages = await self._stream_continuation(messages, system)
                full_text += cont_text
                messages = cont_messages
                yield {"type": "text", "content": cont_text}

        if len(messages) > settings.SESSION_WINDOW_SIZE:
            messages = messages[-settings.SESSION_WINDOW_SIZE:]

        await self._save_session(session_id, messages)
        yield {"type": "done", "content": full_text}

    async def _stream_continuation(self, messages: List[Dict], system: str, _continues_left: int = 3) -> tuple:
        """流式响应截断后的续写，返回 (续写文本, 更新后的messages)"""
        if _continues_left <= 0:
            return "", messages

        logger.warning(f"流式回复因 max_tokens 截断，自动续写（剩余 {_continues_left} 次）")
        messages = list(messages)
        messages.append({"role": "user", "content": "请继续上一条回复的内容，不要重复已经写过的部分。"})

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=system,
            tools=self.tools,
            messages=messages
        )

        cont_text = ""
        for block in response.content:
            if block.type == "text":
                cont_text += block.text

        messages.append({
            "role": "assistant",
            "content": _serialize_content(response.content)
        })

        # 递归处理如果续写也被截断
        if response.stop_reason == "max_tokens":
            extra_text, messages = await self._stream_continuation(messages, system, _continues_left - 1)
            cont_text += extra_text

        return cont_text, messages

    async def clear_session(self, session_id: str):
        """清除会话历史"""
        self._sessions.pop(session_id, None)
        await session_store.delete(session_id)


agent = MicroBubbleAgent()
