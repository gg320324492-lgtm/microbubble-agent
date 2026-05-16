"""会议服务模块"""

import json
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member
from app.voice.asr import asr_service
from app.voice.tts import tts_service
from app.voice.recorder import recorder_manager
from app.agent.core import agent


class MeetingService:
    """会议服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_meeting(
        self,
        title: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        meeting_url: Optional[str] = None,
        participants: Optional[List[int]] = None,
        created_by: Optional[int] = None
    ) -> Meeting:
        """创建会议"""
        meeting = Meeting(
            title=title,
            start_time=start_time,
            end_time=end_time,
            location=location,
            meeting_url=meeting_url,
            created_by=created_by,
            status="scheduled"
        )

        self.db.add(meeting)
        await self.db.flush()

        # 添加参与者
        if participants:
            for member_id in participants:
                participant = MeetingParticipant(
                    meeting_id=meeting.id,
                    member_id=member_id
                )
                self.db.add(participant)

        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        """获取会议"""
        result = await self.db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def get_meetings(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        keyword: Optional[str] = None
    ) -> List[Meeting]:
        """获取会议列表"""
        query = select(Meeting)

        if date_from:
            query = query.where(Meeting.start_time >= date_from)
        if date_to:
            query = query.where(Meeting.start_time <= date_to)
        if keyword:
            query = query.where(Meeting.title.contains(keyword))

        query = query.order_by(Meeting.start_time.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def start_meeting(self, meeting_id: int) -> dict:
        """开始会议"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError("会议不存在")

        # 更新状态
        meeting.status = "recording"
        await self.db.commit()

        # 开始录制
        recorder = await recorder_manager.start_meeting_recording(meeting_id)

        return {
            "meeting_id": meeting_id,
            "status": "recording",
            "message": "会议录制已开始"
        }

    async def stop_meeting(self, meeting_id: int) -> dict:
        """停止会议"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError("会议不存在")

        # 停止录制
        result = await recorder_manager.stop_meeting_recording()

        # 更新状态
        meeting.status = "completed"
        meeting.end_time = datetime.utcnow()

        if result:
            meeting.transcript = result.get("transcript", [])

        await self.db.commit()

        return {
            "meeting_id": meeting_id,
            "status": "completed",
            "duration": result.get("duration", 0) if result else 0,
            "message": "会议录制已结束"
        }

    async def generate_minutes(self, meeting_id: int) -> dict:
        """生成会议纪要"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError("会议不存在")

        if not meeting.transcript:
            raise ValueError("会议转写内容为空")

        # 格式化转写内容
        transcript_text = self._format_transcript(meeting.transcript)

        # 使用Agent生成纪要
        prompt = f"""
请分析以下会议转写内容，生成结构化的会议纪要。

要求输出：
1. 会议摘要（3-5句话概括）
2. 讨论要点（分点列出）
3. 决议事项
4. 待办任务（JSON格式，包含task、assignee、deadline）

会议转写内容：
{transcript_text}
"""

        result = await agent.chat(prompt)

        # 解析结果（简化处理）
        meeting.summary = result["content"]
        meeting.status = "completed"
        await self.db.commit()

        return {
            "meeting_id": meeting_id,
            "summary": meeting.summary,
            "message": "会议纪要生成成功"
        }

    async def extract_tasks_from_meeting(self, meeting_id: int) -> List[dict]:
        """从会议纪要中提取任务"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError("会议不存在")

        if not meeting.summary:
            raise ValueError("会议纪要尚未生成")

        # 使用Agent提取任务
        prompt = f"""
请从以下会议纪要中提取所有待办任务。

输出JSON数组格式：
[
    {{
        "task": "任务描述",
        "assignee": "负责人姓名",
        "deadline": "截止日期(YYYY-MM-DD)",
        "priority": "high/medium/low"
    }}
]

会议纪要：
{meeting.summary}
"""

        result = await agent.chat(prompt)

        # 尝试解析JSON
        try:
            # 提取JSON部分
            content = result["content"]
            # 查找JSON数组
            start = content.find("[")
            end = content.find("]") + 1
            if start != -1 and end != -1:
                tasks = json.loads(content[start:end])
            else:
                tasks = []
        except:
            tasks = []

        return tasks

    def _format_transcript(self, transcript: list) -> str:
        """格式化转写内容"""
        lines = []
        for entry in transcript:
            if isinstance(entry, dict):
                time_str = entry.get("timestamp", "")
                speaker = entry.get("speaker", "未知")
                text = entry.get("text", "")
                lines.append(f"[{time_str}] {speaker}: {text}")
        return "\n".join(lines)

    async def add_participant(self, meeting_id: int, member_id: int):
        """添加参与者"""
        participant = MeetingParticipant(
            meeting_id=meeting_id,
            member_id=member_id
        )
        self.db.add(participant)
        await self.db.commit()

    async def remove_participant(self, meeting_id: int, member_id: int):
        """移除参与者"""
        result = await self.db.execute(
            select(MeetingParticipant).where(
                MeetingParticipant.meeting_id == meeting_id,
                MeetingParticipant.member_id == member_id
            )
        )
        participant = result.scalar_one_or_none()

        if participant:
            await self.db.delete(participant)
            await self.db.commit()

    async def get_participants(self, meeting_id: int) -> List[Member]:
        """获取参与者列表"""
        result = await self.db.execute(
            select(Member)
            .join(MeetingParticipant)
            .where(MeetingParticipant.meeting_id == meeting_id)
        )
        return result.scalars().all()
