import asyncio
import base64
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
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

        return "\n".join(parts)

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

    async def _generate_brief(self, messages: List[Dict], system: str) -> str:
        """生成【简要】回复（带工具调用）"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=system,
            tools=self.tools,
            messages=messages
        )
        # 处理工具调用（递归）
        processed = await self._process_response(response, "", None, messages)
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
        user_id: Optional[int] = None
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
        brief_task = asyncio.create_task(self._generate_brief(messages, system))
        detail_task = asyncio.create_task(self._generate_detail(messages, system))

        # 先等简要完成，立即返回
        brief_result = await brief_task

        # 更新 messages（简要回复已由 _generate_brief 处理工具调用）
        messages.append({
            "role": "assistant",
            "content": brief_result
        })

        # 后台等待详细回复并追加
        asyncio.create_task(self._append_detail(messages, session_id, db, user_id))

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

    async def _append_detail(self, messages: List[Dict], session_id: str, db, user_id: Optional[int]):
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

    async def _process_response(self, response, session_id: str, db=None, messages: List[Dict] = None, user_id: Optional[int] = None, _continues_left: int = 3) -> Dict[str, Any]:
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
                result = await self._execute_tool(call["name"], call["input"], db, user_id=user_id)
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

            result = await self._process_response(follow_up, session_id, db, messages, user_id=user_id, _continues_left=_continues_left)
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

    async def _execute_tool(self, name: str, input_data: Dict, db=None, user_id: Optional[int] = None) -> Any:
        """执行工具调用，路由到对应 service 层"""
        try:
            # 联网搜索不需要数据库
            if name == "web_search":
                result = await search_service.search(
                    query=input_data["query"],
                    max_results=input_data.get("max_results", 5),
                )
                return result

            # 其他工具需要数据库
            if db is None:
                return {"status": "error", "message": "数据库连接不可用"}

            if name == "create_task":
                task_svc = TaskService(db)
                member_svc = MemberService(db)

                # 权限检查
                is_admin = False
                if user_id:
                    current_member = await member_svc.get_member(user_id)
                    is_admin = current_member and current_member.role in ("admin", "leader")

                assignee_id = None
                if input_data.get("assignee_name"):
                    member = await member_svc.get_member_by_name(input_data["assignee_name"])
                    if member:
                        assignee_id = member.id
                    else:
                        return {"status": "error", "message": f"未找到成员: {input_data['assignee_name']}"}
                elif user_id:
                    # 未指定负责人时默认为当前用户（"提醒我"场景）
                    assignee_id = user_id

                # 权限：普通成员只能给自己创建任务
                if not is_admin and assignee_id and user_id and assignee_id != user_id:
                    return {"status": "error", "message": "普通成员只能给自己创建任务"}

                project_id = None
                if input_data.get("project_name"):
                    proj_svc = ProjectService(db)
                    projects = await proj_svc.get_projects()
                    for p in projects:
                        if p.name == input_data["project_name"]:
                            project_id = p.id
                            break
                due_date = None
                beijing_tz = BEIJING_TZ
                if input_data.get("due_date"):
                    try:
                        beijing_dt = datetime.strptime(input_data["due_date"], "%Y-%m-%d %H:%M")
                    except ValueError:
                        beijing_dt = datetime.strptime(input_data["due_date"], "%Y-%m-%d").replace(hour=18, minute=0)
                    # 北京时间转UTC存储
                    due_date = beijing_dt.replace(tzinfo=beijing_tz).astimezone(timezone.utc).replace(tzinfo=None)

                # 解析自定义提醒
                reminders_data = None
                if input_data.get("reminders"):
                    reminders_data = []
                    for r in input_data["reminders"]:
                        rem_beijing = datetime.strptime(r["remind_at"], "%Y-%m-%d %H:%M")
                        rem_utc = rem_beijing.replace(tzinfo=beijing_tz).astimezone(timezone.utc).replace(tzinfo=None)
                        reminders_data.append({
                            "remind_at": rem_utc,
                            "remind_type": r.get("remind_type", "wechat")
                        })

                task = await task_svc.create_task(
                    title=input_data["title"],
                    assignee_id=assignee_id,
                    project_id=project_id,
                    priority=input_data.get("priority", "medium"),
                    due_date=due_date,
                    description=input_data.get("description"),
                    source="ai",
                    created_by=user_id,
                    reminders=reminders_data,
                )

                # 如果分配给了其他成员，立即通知负责人 + 通知创建人确认
                if assignee_id and user_id and assignee_id != user_id:
                    try:
                        from app.wechat.notifier import notifier
                        import logging as _logging
                        _notify_logger = _logging.getLogger("microbubble.notify")
                        assignee_member = await member_svc.get_member(assignee_id)
                        creator_member = await member_svc.get_member(user_id)

                        due_date_str = ""
                        if due_date:
                            beijing_tz_notify = BEIJING_TZ
                            due_date_beijing = due_date.replace(tzinfo=timezone.utc).astimezone(beijing_tz_notify)
                            due_date_str = due_date_beijing.strftime("%Y-%m-%d %H:%M")

                        # 通知负责人
                        if assignee_member and (assignee_member.wechat_id or assignee_member.external_userid):
                            result = await notifier.notify_task_assigned(
                                member=assignee_member,
                                task_title=input_data["title"],
                                due_date=due_date_str,
                                priority=input_data.get("priority", "medium"),
                                description=input_data.get("description", ""),
                                assigner=creator_member.name if creator_member else "管理员"
                            )
                            errcode = result.get("errcode", -1) if isinstance(result, dict) else -1
                            if errcode == 0:
                                _notify_logger.info(f"任务分配通知成功: {assignee_member.name} <- {input_data['title']}")
                            else:
                                _notify_logger.warning(f"任务分配通知失败: errcode={errcode}, result={result}, assignee={assignee_member.name}")
                        else:
                            _notify_logger.warning(f"跳过负责人通知: {assignee_member.name if assignee_member else assignee_id} 无微信标识")

                        # 通知创建人：任务已派发
                        if creator_member and creator_member.id != assignee_id:
                            if creator_member.wechat_id or creator_member.external_userid:
                                result2 = await notifier.notify_task_assigned_to_creator(
                                    creator=creator_member,
                                    task_title=input_data["title"],
                                    assignee_name=assignee_member.name if assignee_member else "未知",
                                    due_date=due_date_str,
                                    priority=input_data.get("priority", "medium"),
                                )
                                errcode2 = result2.get("errcode", -1) if isinstance(result2, dict) else -1
                                if errcode2 == 0:
                                    _notify_logger.info(f"派发确认通知成功: {creator_member.name} <- {input_data['title']}")
                                else:
                                    _notify_logger.warning(f"派发确认通知失败: errcode={errcode2}, result={result2}")
                    except Exception as notify_err:
                        import logging as _logging
                        _logging.getLogger("microbubble.notify").warning(f"任务分配通知异常: {notify_err}")

                return {"status": "success", "task_id": task.id, "title": task.title}

            elif name == "query_tasks":
                task_svc = TaskService(db)
                member_svc = MemberService(db)

                # 权限检查：普通成员只看自己的任务
                is_admin = False
                if user_id:
                    current_member = await member_svc.get_member(user_id)
                    is_admin = current_member and current_member.role in ("admin", "leader")

                assignee_id = None
                if input_data.get("assignee_name"):
                    member = await member_svc.get_member_by_name(input_data["assignee_name"])
                    if member:
                        assignee_id = member.id
                project_id = None
                if input_data.get("project_name"):
                    proj_svc = ProjectService(db)
                    projects = await proj_svc.get_projects()
                    for p in projects:
                        if p.name == input_data["project_name"]:
                            project_id = p.id
                            break

                # 非管理员且未指定负责人时，只查自己的任务
                if not is_admin and not assignee_id:
                    assignee_id = user_id

                tasks = await task_svc.get_tasks(
                    assignee_id=assignee_id,
                    status=input_data.get("status"),
                    project_id=project_id,
                    overdue=input_data.get("overdue", False)
                )

                # 批量获取负责人姓名
                assignee_ids = {t.assignee_id for t in tasks if t.assignee_id}
                members_map = {}
                if assignee_ids:
                    from app.models.member import Member as _Member
                    _result = await db.execute(select(_Member).where(_Member.id.in_(assignee_ids)))
                    members_map = {m.id: m.name for m in _result.scalars().all()}

                return {
                    "status": "success",
                    "count": len(tasks),
                    "tasks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "status": t.status,
                            "priority": t.priority,
                            "assignee_id": t.assignee_id,
                            "assignee_name": members_map.get(t.assignee_id, "未分配") if t.assignee_id else "未分配",
                            "due_date": t.due_date.strftime("%Y-%m-%d %H:%M") if t.due_date else None,
                            "progress": t.progress
                        }
                        for t in tasks
                    ]
                }

            elif name == "query_all_member_tasks":
                task_svc = TaskService(db)
                member_svc = MemberService(db)

                # 权限检查：仅管理员/组长可用
                is_admin = False
                if user_id:
                    current_member = await member_svc.get_member(user_id)
                    is_admin = current_member and current_member.role in ("admin", "leader")

                if not is_admin:
                    return {"status": "error", "message": "仅管理员或组长可以查看所有成员的任务状况"}

                # 获取所有成员工作量
                all_member_stats = await task_svc.get_all_members_workload()

                # 按状态分组
                in_progress_list = []
                todo_list = []
                done_list = []

                for member_data in all_member_stats:
                    member_name = member_data["member_name"]
                    for task in member_data["tasks"]:
                        task_info = {
                            "member": member_name,
                            "title": task.title,
                            "progress": task.progress,
                            "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
                        }
                        if task.status == "in_progress":
                            in_progress_list.append(task_info)
                        elif task.status == "todo":
                            todo_list.append(task_info)
                        elif task.status == "done":
                            done_list.append(task_info)

                # 构建固定格式输出
                lines = []
                lines.append("【进行中任务】（共 {} 个）".format(len(in_progress_list)))
                if in_progress_list:
                    for item in in_progress_list:
                        due = f"- 截止{item['due_date']}" if item['due_date'] else ""
                        lines.append(f"- {item['member']}：{item['title']} - {item['progress']}% {due}")
                else:
                    lines.append("- 无")

                lines.append("")
                lines.append("【待办任务】（共 {} 个）".format(len(todo_list)))
                if todo_list:
                    for item in todo_list:
                        due = f"- 截止{item['due_date']}" if item['due_date'] else ""
                        lines.append(f"- {item['member']}：{item['title']} {due}")
                else:
                    lines.append("- 无")

                lines.append("")
                lines.append("【已完成任务】（共 {} 个）".format(len(done_list)))
                if done_list:
                    for item in done_list:
                        lines.append(f"- {item['member']}：{item['title']} ✅")
                else:
                    lines.append("- 无")

                total = len(in_progress_list) + len(todo_list) + len(done_list)
                lines.append("")
                lines.append(f"共 {total} 个任务")

                return {
                    "status": "success",
                    "formatted_text": "\n".join(lines)
                }

            elif name == "update_task":
                task_svc = TaskService(db)
                task = await task_svc.get_task(input_data["task_id"])
                if not task:
                    return {"status": "error", "message": f"任务 {input_data['task_id']} 不存在"}

                # 权限检查：普通成员只能编辑自己创建或被分配的任务
                if user_id:
                    member_svc = MemberService(db)
                    current_member = await member_svc.get_member(user_id)
                    is_admin = current_member and current_member.role in ("admin", "leader")
                    if not is_admin and task.created_by != user_id and task.assignee_id != user_id:
                        return {"status": "error", "message": "只能编辑自己创建或被分配的任务"}

                updated = await task_svc.update_task_status(
                    task_id=input_data["task_id"],
                    status=input_data.get("status", "todo"),
                    progress=input_data.get("progress")
                )
                if updated:
                    # 更新截止日期（北京时间转UTC）
                    if input_data.get("due_date"):
                        try:
                            new_due_beijing = datetime.strptime(input_data["due_date"], "%Y-%m-%d %H:%M")
                        except ValueError:
                            new_due_beijing = datetime.strptime(input_data["due_date"], "%Y-%m-%d").replace(hour=18, minute=0)
                        beijing_tz = BEIJING_TZ
                        updated.due_date = new_due_beijing.replace(tzinfo=beijing_tz).astimezone(timezone.utc).replace(tzinfo=None)
                        await db.commit()
                    return {"status": "success", "task_id": updated.id, "new_status": updated.status}
                return {"status": "error", "message": f"任务 {input_data['task_id']} 更新失败"}

            elif name == "get_task_stats":
                task_svc = TaskService(db)
                member_id = None
                if input_data.get("member_name"):
                    member_svc = MemberService(db)
                    member = await member_svc.get_member_by_name(input_data["member_name"])
                    if member:
                        member_id = member.id
                if member_id:
                    stats = await task_svc.get_member_workload(member_id)
                    return {"status": "success", "stats": stats}
                tasks = await task_svc.get_tasks()
                from app.models.task import TaskStatus
                stats = {
                    "total": len(tasks),
                    "todo": sum(1 for t in tasks if t.status == TaskStatus.TODO.value),
                    "in_progress": sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS.value),
                    "blocked": sum(1 for t in tasks if t.status == TaskStatus.BLOCKED.value),
                    "review": sum(1 for t in tasks if t.status == TaskStatus.REVIEW.value),
                    "done": sum(1 for t in tasks if t.status == TaskStatus.DONE.value),
                    "cancelled": sum(1 for t in tasks if t.status == TaskStatus.CANCELLED.value),
                    "overdue": sum(1 for t in tasks if t.due_date and t.due_date < utcnow() and t.status not in [TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
                }
                return {"status": "success", "stats": stats}

            elif name == "query_members":
                member_svc = MemberService(db)
                members = await member_svc.get_members(
                    name=input_data.get("name"),
                    research_area=input_data.get("research_area"),
                    grade=input_data.get("grade")
                )
                return {
                    "status": "success",
                    "count": len(members),
                    "members": [
                        {
                            "id": m.id,
                            "name": m.name,
                            "grade": m.grade,
                            "research_area": m.research_area,
                            "email": m.email,
                            "role": m.role
                        }
                        for m in members
                    ]
                }

            elif name == "query_meetings":
                meeting_svc = MeetingService(db)
                date_from = None
                date_to = None
                if input_data.get("date_from"):
                    date_from = datetime.strptime(input_data["date_from"], "%Y-%m-%d")
                if input_data.get("date_to"):
                    date_to = datetime.strptime(input_data["date_to"], "%Y-%m-%d")
                meetings = await meeting_svc.get_meetings(
                    date_from=date_from,
                    date_to=date_to,
                    keyword=input_data.get("keyword")
                )
                return {
                    "status": "success",
                    "count": len(meetings),
                    "meetings": [
                        {
                            "id": m.id,
                            "title": m.title,
                            "start_time": m.start_time.strftime("%Y-%m-%d %H:%M") if m.start_time else None,
                            "status": m.status,
                            "summary": m.summary
                        }
                        for m in meetings
                    ]
                }

            elif name == "summarize_meeting_transcript":
                from app.services.meeting_service import MeetingService
                from app.services.memory_service import MemoryService
                from app.wechat.analyzer import ConversationAnalyzer

                if not user_id:
                    return {"status": "error", "message": "无法识别用户身份"}

                transcript_text = input_data["transcript_text"]

                # 1. 生成摘要
                summary = await MeetingService._generate_summary(None, transcript_text)

                # 2. 提取关键信息和行动项
                analyzer = ConversationAnalyzer()
                analysis = await analyzer.extract_action_items(transcript_text)

                key_points = []
                for t in analysis.get("tasks", []):
                    if t.get("title"):
                        assignee = t.get("assignee_name", "")
                        point = f"[任务] {t['title']}"
                        if assignee:
                            point += f" → {assignee}"
                        key_points.append(point)
                for d in analysis.get("decisions", []):
                    key_points.append(f"[决定] {d}")

                # 3. 存入 Agent 长期记忆（与项目记忆共用 memories 表）
                memory_svc = MemoryService(db)
                await memory_svc.save_memory(
                    user_id=user_id,
                    memory_type="summary",
                    content=f"【会议总结】\n\n摘要：{summary}\n\n要点：{'；'.join(key_points)}\n\n原始转录：{transcript_text[:3000]}",
                    importance=0.8
                )

                return {
                    "status": "success",
                    "summary": summary,
                    "key_points": key_points,
                    "decisions": analysis.get("decisions", []),
                    "tasks": analysis.get("tasks", [])
                }

            elif name == "create_meeting":
                meeting_svc = MeetingService(db)
                start_time_beijing = datetime.strptime(input_data["start_time"], "%Y-%m-%d %H:%M")
                beijing_tz = BEIJING_TZ
                start_time = start_time_beijing.replace(tzinfo=beijing_tz).astimezone(timezone.utc).replace(tzinfo=None)
                participant_ids = []
                if input_data.get("participants"):
                    member_svc = MemberService(db)
                    for name_str in input_data["participants"]:
                        member = await member_svc.get_member_by_name(name_str)
                        if member:
                            participant_ids.append(member.id)
                meeting = await meeting_svc.create_meeting(
                    title=input_data["title"],
                    start_time=start_time,
                    description=input_data.get("agenda"),
                    location=input_data.get("location"),
                    participant_ids=participant_ids
                )

                result = {"status": "success", "meeting_id": meeting.id, "title": meeting.title}

                # 如果腾讯会议已配置，自动创建线上会议
                from app.services.tencent_meeting_service import tencent_meeting
                if tencent_meeting.is_configured:
                    try:
                        start_ts = start_time.strftime("%Y-%m-%d %H:%M:%S")
                        tm_result = await tencent_meeting.create_meeting(
                            subject=input_data["title"],
                            start_time=start_ts
                        )
                        meeting_info = tm_result.get("meeting_info", {})
                        join_url = meeting_info.get("join_url", "")
                        tm_meeting_id = meeting_info.get("meeting_id", "")
                        if join_url:
                            await meeting_svc.update_meeting(
                                meeting.id,
                                meeting_url=join_url,
                                meeting_id=tm_meeting_id
                            )
                            result["join_url"] = join_url
                            result["tencent_meeting_id"] = tm_meeting_id
                    except Exception as e:
                        logger.warning(f"创建腾讯会议失败（本地会议已创建）: {e}")

                return result

            elif name == "query_projects":
                proj_svc = ProjectService(db)
                projects = await proj_svc.get_projects(status=input_data.get("status"))
                return {
                    "status": "success",
                    "count": len(projects),
                    "projects": [
                        {
                            "id": p.id,
                            "name": p.name,
                            "status": p.status,
                            "research_area": p.research_area,
                            "start_date": str(p.start_date) if p.start_date else None,
                            "end_date": str(p.end_date) if p.end_date else None
                        }
                        for p in projects
                    ]
                }

            elif name == "generate_project_plan":
                proj_svc = ProjectService(db)
                plan_prompt = f"请为课题「{input_data['project_name']}」生成一份详细的项目计划。"
                if input_data.get("duration_months"):
                    plan_prompt += f" 预计时长：{input_data['duration_months']}个月。"
                if input_data.get("team_size"):
                    plan_prompt += f" 团队人数：{input_data['team_size']}人。"
                if input_data.get("research_area"):
                    plan_prompt += f" 研究方向：{input_data['research_area']}。"
                plan_prompt += "\n\n请分阶段列出：文献调研、方案设计、预实验、正式实验、数据分析、论文撰写，每阶段包含具体任务和时间安排。"
                plan_response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=get_system_prompt(),
                    messages=[{"role": "user", "content": plan_prompt}]
                )
                plan_text = ""
                for block in plan_response.content:
                    if block.type == "text":
                        plan_text += block.text
                project = await proj_svc.create_project(
                    name=input_data["project_name"],
                    description=plan_text,
                    research_area=input_data.get("research_area")
                )
                return {"status": "success", "project_id": project.id, "plan": plan_text}

            elif name == "search_knowledge":
                kb_svc = KnowledgeService(db)
                results = await kb_svc.search_semantic(
                    query=input_data["query"],
                    top_k=5
                )
                return {"status": "success", "results": results}

            # 长期记忆工具
            elif name == "save_memory":
                if not user_id:
                    return {"status": "error", "message": "无法识别用户身份"}
                from app.services.memory_service import MemoryService
                mem_svc = MemoryService(db)
                memory = await mem_svc.save_memory(
                    user_id=user_id,
                    memory_type=input_data["memory_type"],
                    content=input_data["content"],
                    key=input_data.get("key"),
                    importance=input_data.get("importance", 0.7),
                )
                return {"status": "success", "memory_id": memory.id, "type": memory.memory_type}

            elif name == "search_memory":
                if not user_id:
                    return {"status": "error", "message": "无法识别用户身份"}
                from app.services.memory_service import MemoryService
                mem_svc = MemoryService(db)
                results = await mem_svc.search_memories(
                    user_id=user_id,
                    query=input_data["query"],
                    top_k=5,
                    memory_type=input_data.get("memory_type")
                )
                return {"status": "success", "memories": results}

            elif name == "forget_memory":
                if not user_id:
                    return {"status": "error", "message": "无法识别用户身份"}
                from app.services.memory_service import MemoryService
                mem_svc = MemoryService(db)
                success = await mem_svc.forget_memory(
                    user_id=user_id,
                    memory_id=input_data["memory_id"]
                )
                if success:
                    return {"status": "success", "message": "记忆已遗忘"}
                return {"status": "error", "message": "记忆不存在或无权操作"}

            elif name == "save_conversation_knowledge":
                kb_svc = KnowledgeService(db)
                knowledge = await kb_svc.create_from_conversation(
                    title=input_data["title"],
                    content=input_data["content"],
                    category=input_data.get("category"),
                    tags=input_data.get("tags", []),
                    created_by=user_id,
                )
                return {"status": "success", "knowledge_id": knowledge.id, "title": knowledge.title}

            elif name == "set_custom_instructions":
                if not user_id:
                    return {"status": "error", "message": "需要登录才能设置自定义指令"}
                from app.models.member import Member
                member = await db.get(Member, user_id)
                if not member:
                    return {"status": "error", "message": "用户不存在"}
                instructions = input_data["instructions"][:2000]
                member.custom_instructions = instructions
                await db.commit()
                return {"status": "success", "message": f"已保存你的自定义指令：{instructions[:100]}..."}

            elif name == "submit_feedback":
                from app.models.feedback import Feedback
                fb = Feedback(
                    user_id=user_id or 0,
                    session_id=input_data.get("session_id"),
                    rating=input_data["rating"],
                    comment=input_data.get("comment"),
                    agent_reply=input_data.get("agent_reply", "")[:500],
                )
                db.add(fb)
                await db.commit()
                return {"status": "success", "message": "感谢你的反馈！"}

            else:
                return {"status": "error", "message": f"未知工具: {name}"}

        except Exception as e:
            return {"status": "error", "message": f"工具 {name} 执行失败: {str(e)}"}

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        db=None,
        image_data: Optional[bytes] = None,
        image_media_type: str = "image/png",
        user_id: Optional[int] = None
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
                result = await self._execute_tool(call["name"], input_data, db, user_id=user_id)
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
