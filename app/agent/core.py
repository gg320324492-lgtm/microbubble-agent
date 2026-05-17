import anthropic
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.services.task_service import TaskService
from app.services.member_service import MemberService
from app.services.meeting_service import MeetingService
from app.services.project_service import ProjectService
from app.services.knowledge_service import KnowledgeService
from app.core.redis import session_store


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
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.CLAUDE_API_KEY,
            base_url=settings.CLAUDE_BASE_URL or None,
        )
        self.model = "claude-sonnet-4-20250514"
        self.system_prompt = SYSTEM_PROMPT
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

    async def chat(
        self,
        message: str,
        session_id: str = "default",
        history: Optional[List[Dict]] = None,
        db=None
    ) -> Dict[str, Any]:
        """与Agent对话"""
        messages = await self._load_session(session_id)

        if history:
            messages = history

        messages.append({"role": "user", "content": message})

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            tools=self.tools,
            messages=messages
        )

        result = await self._process_response(response, session_id, db, messages)

        messages.append({
            "role": "assistant",
            "content": _serialize_content(result["content_blocks"])
        })

        if len(messages) > 20:
            messages = messages[-20:]

        await self._save_session(session_id, messages)
        return result

    async def _process_response(self, response, session_id: str, db=None, messages: List[Dict] = None) -> Dict[str, Any]:
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
                result = await self._execute_tool(call["name"], call["input"], db)
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

            follow_up = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages
            )

            result = await self._process_response(follow_up, session_id, db, messages)
            return {
                "content": result["content"],
                "content_blocks": result["content_blocks"],
                "tool_calls": tool_calls,
                "tool_results": tool_results
            }

        return {
            "content": "\n".join(content) if content else "",
            "content_blocks": response.content,
            "tool_calls": tool_calls,
            "tool_results": tool_results
        }

    async def _execute_tool(self, name: str, input_data: Dict, db=None) -> Any:
        """执行工具调用，路由到对应 service 层"""
        if db is None:
            return {"status": "error", "message": "数据库连接不可用"}

        try:
            if name == "create_task":
                task_svc = TaskService(db)
                assignee_id = None
                if input_data.get("assignee_name"):
                    member_svc = MemberService(db)
                    member = await member_svc.get_member_by_name(input_data["assignee_name"])
                    if member:
                        assignee_id = member.id
                    else:
                        return {"status": "error", "message": f"未找到成员: {input_data['assignee_name']}"}
                project_id = None
                if input_data.get("project_name"):
                    proj_svc = ProjectService(db)
                    projects = await proj_svc.get_projects()
                    for p in projects:
                        if p.name == input_data["project_name"]:
                            project_id = p.id
                            break
                due_date = None
                if input_data.get("due_date"):
                    due_date = datetime.strptime(input_data["due_date"], "%Y-%m-%d")
                task = await task_svc.create_task(
                    title=input_data["title"],
                    assignee_id=assignee_id,
                    project_id=project_id,
                    priority=input_data.get("priority", "medium"),
                    due_date=due_date,
                    description=input_data.get("description"),
                    source="ai"
                )
                return {"status": "success", "task_id": task.id, "title": task.title}

            elif name == "query_tasks":
                task_svc = TaskService(db)
                assignee_id = None
                if input_data.get("assignee_name"):
                    member_svc = MemberService(db)
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
                tasks = await task_svc.get_tasks(
                    assignee_id=assignee_id,
                    status=input_data.get("status"),
                    project_id=project_id,
                    overdue=input_data.get("overdue", False)
                )
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
                            "due_date": str(t.due_date) if t.due_date else None,
                            "progress": t.progress
                        }
                        for t in tasks
                    ]
                }

            elif name == "update_task":
                task_svc = TaskService(db)
                task = await task_svc.update_task_status(
                    task_id=input_data["task_id"],
                    status=input_data.get("status", "todo"),
                    progress=input_data.get("progress")
                )
                if task:
                    return {"status": "success", "task_id": task.id, "new_status": task.status}
                return {"status": "error", "message": f"任务 {input_data['task_id']} 不存在"}

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
                    "overdue": sum(1 for t in tasks if t.due_date and t.due_date < datetime.utcnow() and t.status not in [TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
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
                            "start_time": str(m.start_time),
                            "status": m.status,
                            "summary": m.summary
                        }
                        for m in meetings
                    ]
                }

            elif name == "create_meeting":
                meeting_svc = MeetingService(db)
                start_time = datetime.strptime(input_data["start_time"], "%Y-%m-%d %H:%M")
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
                return {"status": "success", "meeting_id": meeting.id, "title": meeting.title}

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
                    system=self.system_prompt,
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

            else:
                return {"status": "error", "message": f"未知工具: {name}"}

        except Exception as e:
            return {"status": "error", "message": f"工具 {name} 执行失败: {str(e)}"}

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        db=None
    ):
        """流式对话"""
        messages = await self._load_session(session_id)
        messages.append({"role": "user", "content": message})

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
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
                            tool_calls[-1]["input_json"] = getattr(event.delta, "partial_json", "")

            response = await stream.get_final_response()

        if tool_calls:
            tool_results = []
            for call in tool_calls:
                input_data = call.get("input", {})
                if not input_data and "input_json" in call:
                    try:
                        input_data = json.loads(call["input_json"])
                    except (json.JSONDecodeError, TypeError):
                        input_data = {}
                result = await self._execute_tool(call["name"], input_data, db)
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
                max_tokens=4096,
                system=self.system_prompt,
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
        else:
            messages.append({
                "role": "assistant",
                "content": _serialize_content(response.content)
            })

        if len(messages) > 20:
            messages = messages[-20:]

        await self._save_session(session_id, messages)
        yield {"type": "done", "content": full_text}

    async def clear_session(self, session_id: str):
        """清除会话历史"""
        self._sessions.pop(session_id, None)
        await session_store.delete(session_id)


agent = MicroBubbleAgent()
