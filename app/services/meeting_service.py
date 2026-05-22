import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any

from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member
from app.models.task import Task, TaskStatus, TaskPriority
from app.wechat.analyzer import analyzer
from app.wechat.identity import identity_resolver
from app.core.llm import get_anthropic_client, get_default_model, extract_text_from_response

logger = logging.getLogger("microbubble.meeting_service")


class MeetingService:
    """会议服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        """获取单个会议（含参与者）"""
        result = await self.db.execute(
            select(Meeting)
            .options(selectinload(Meeting.participants))
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def get_meetings(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        keyword: Optional[str] = None
    ) -> List[Meeting]:
        """查询会议列表"""
        query = select(Meeting).options(selectinload(Meeting.participants))
        filters = []

        if date_from:
            filters.append(Meeting.start_time >= date_from)
        if date_to:
            filters.append(Meeting.start_time <= date_to)
        if keyword:
            filters.append(Meeting.title.ilike(f"%{keyword}%"))

        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(Meeting.start_time.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_meeting(
        self,
        title: str,
        start_time: datetime,
        description: Optional[str] = None,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        participant_ids: Optional[List[int]] = None,
        created_by: Optional[int] = None
    ) -> Meeting:
        """创建会议"""
        meeting = Meeting(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location,
            created_by=created_by,
            status="scheduled"
        )
        self.db.add(meeting)
        await self.db.flush()

        if participant_ids:
            for member_id in participant_ids:
                participant = MeetingParticipant(
                    meeting_id=meeting.id,
                    member_id=member_id,
                    role="participant"
                )
                self.db.add(participant)

        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def update_meeting(self, meeting_id: int, **kwargs) -> Optional[Meeting]:
        """更新会议"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return None

        for key, value in kwargs.items():
            if hasattr(meeting, key) and value is not None:
                setattr(meeting, key, value)

        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def delete_meeting(self, meeting_id: int) -> bool:
        """删除会议"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return False

        await self.db.delete(meeting)
        await self.db.commit()
        return True

    def _transcript_to_text(self, transcript: Any) -> str:
        """将转写 JSON 转为可分析的纯文本"""
        if isinstance(transcript, list):
            lines = []
            for entry in transcript:
                speaker = entry.get("speaker", "参会者")
                text = entry.get("text", "")
                if text.strip():
                    lines.append(f"【{speaker}】: {text}")
            return "\n".join(lines)
        if isinstance(transcript, str):
            return transcript
        return str(transcript)

    async def process_meeting_transcript(self, meeting_id: int) -> Dict[str, Any]:
        """
        分析会议转写内容，提取摘要、要点、决定，并自动创建任务

        Returns:
            {
                "summary": str,
                "key_points": [str],
                "decisions": [str],
                "tasks_created": [{"title": str, "assignee": str}],
            }
        """
        meeting = await self.get_meeting(meeting_id)
        if not meeting or not meeting.transcript:
            return {"summary": "", "key_points": [], "decisions": [], "tasks_created": []}

        transcript_text = self._transcript_to_text(meeting.transcript)
        if not transcript_text.strip():
            return {"summary": "", "key_points": [], "decisions": [], "tasks_created": []}

        # 1. 调用 Claude 分析转写内容
        analysis = await analyzer.extract_action_items(transcript_text)

        decisions = analysis.get("decisions", [])
        tasks_info = analysis.get("tasks", [])

        # 2. 用 Claude 生成会议摘要
        summary = await self._generate_summary(transcript_text)

        # 3. 从分析结果中提取要点（任务标题 + 决定）
        key_points = []
        for t in tasks_info:
            if t.get("title"):
                assignee = t.get("assignee_name", "")
                point = f"[任务] {t['title']}"
                if assignee:
                    point += f" → {assignee}"
                key_points.append(point)
        for d in decisions:
            key_points.append(f"[决定] {d}")

        # 4. 更新会议记录
        meeting.summary = summary
        meeting.key_points = key_points or None
        meeting.decisions = decisions or None
        await self.db.commit()

        # 5. 自动创建任务
        tasks_created = []
        for task_info in tasks_info:
            result = await self._auto_create_task_from_meeting(meeting, task_info)
            if result:
                tasks_created.append(result)

        return {
            "summary": summary,
            "key_points": key_points,
            "decisions": decisions,
            "tasks_created": tasks_created,
        }

    @classmethod
    async def _generate_summary(cls, transcript_text: str) -> str:
        """用 Claude 生成会议摘要"""
        try:
            client = get_anthropic_client()
            model = get_default_model()
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                system="你是课题组AI助手，请用简洁的中文总结以下会议内容，200字以内。",
                messages=[{"role": "user", "content": f"请总结以下会议转写内容：\n\n{transcript_text[:8000]}"}]
            )
            return extract_text_from_response(response)
        except Exception as e:
            logger.error(f"生成会议摘要失败: {e}")
            return ""

    async def _auto_create_task_from_meeting(self, meeting: Meeting, task_info: Dict) -> Optional[Dict]:
        """从会议分析结果中自动创建单个任务"""
        assignee_name = task_info.get("assignee_name")
        title = task_info.get("title")
        if not title:
            return None

        # 匹配负责人
        assignee = None
        if assignee_name:
            matches = await identity_resolver.fuzzy_search(assignee_name, self.db)
            if matches:
                assignee = matches[0]

        # 解析截止日期
        due_date = None
        due_date_str = task_info.get("due_date")
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            except ValueError:
                pass

        # 映射优先级
        priority_map = {"high": TaskPriority.HIGH.value, "medium": TaskPriority.MEDIUM.value, "low": TaskPriority.LOW.value}
        priority = priority_map.get(task_info.get("priority", "medium"), TaskPriority.MEDIUM.value)

        task = Task(
            title=title,
            description=task_info.get("description", ""),
            assignee_id=assignee.id if assignee else None,
            priority=priority,
            due_date=due_date,
            status=TaskStatus.TODO.value,
            source="meeting",
            meeting_id=meeting.id,
            created_by=meeting.created_by,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"会议自动创建任务: {title} (会议ID={meeting.id}, 负责人={assignee_name})")

        result = {"title": title, "assignee": assignee_name or "未指定"}
        return result
