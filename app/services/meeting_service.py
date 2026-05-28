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
from app.services.meeting_analysis_service import meeting_analysis

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

    async def process_pasted_transcript(
        self,
        title: str,
        start_time: datetime,
        transcript_text: str,
        speaker_mapping: Optional[Dict[str, str]] = None,
        participant_ids: Optional[List[int]] = None,
        created_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """粘贴转录的完整处理流程。

        1. 创建会议记录
        2. 解析转录文本为结构化 JSON
        3. AI 分析（摘要 + 要点 + 决策 + 行动项）
        4. 计算发言者统计
        5. 更新会议记录
        6. 自动创建任务
        7. 自动链接发言者与成员
        """
        # 1. 创建会议
        meeting = await self.create_meeting(
            title=title,
            start_time=start_time,
            participant_ids=participant_ids,
            created_by=created_by,
        )

        # 2. 解析转录文本
        if speaker_mapping:
            transcript_entries = meeting_analysis.parse_with_mapping(
                transcript_text, speaker_mapping
            )
        else:
            # 无映射时，先检测发言者再解析
            detection = await meeting_analysis.detect_speakers(transcript_text)
            auto_mapping = {}
            for sp in detection.get("detected_speakers", []):
                label = sp["original_label"]
                auto_mapping[label] = sp.get("suggested_name") or label
            transcript_entries = meeting_analysis.parse_with_mapping(
                transcript_text, auto_mapping
            )

        if transcript_entries:
            meeting.transcript = transcript_entries

        # 3. AI 分析
        analysis = await meeting_analysis.analyze_transcript(
            transcript_text, speaker_mapping
        )

        # 4. 计算发言者统计
        if transcript_entries:
            stats = meeting_analysis.compute_speaker_stats(transcript_entries)
            meeting.speaker_stats = stats

        if speaker_mapping:
            meeting.speaker_mapping = speaker_mapping

        # 5. 更新会议记录
        meeting.summary = analysis.get("summary", "")
        meeting.key_points = analysis.get("key_points") or None
        meeting.decisions = analysis.get("decisions") or None
        meeting.status = "completed"
        await self.db.commit()

        # 6. 自动创建任务
        tasks_created = []
        for task_info in analysis.get("action_items", []):
            result = await self._auto_create_task_from_meeting(meeting, task_info)
            if result:
                tasks_created.append(result)

        # 7. 发言者-成员自动链接
        if speaker_mapping:
            await self._link_speakers_to_participants(meeting.id, speaker_mapping)

        await self.db.refresh(meeting)

        return {
            "meeting_id": meeting.id,
            "summary": meeting.summary,
            "key_points": meeting.key_points or [],
            "decisions": meeting.decisions or [],
            "tasks_created": tasks_created,
            "speaker_stats": meeting.speaker_stats,
            "speaker_mapping": meeting.speaker_mapping,
        }

    async def reanalyze_with_speakers(
        self,
        meeting_id: int,
        speaker_mapping: Dict[str, str],
    ) -> Dict[str, Any]:
        """用新的发言者映射重新分析已有会议。

        1. 用映射重写 transcript 条目中的 speaker 字段
        2. 重新生成摘要/要点/决策
        3. 重新计算发言者统计
        """
        meeting = await self.get_meeting(meeting_id)
        if not meeting or not meeting.transcript:
            return {"error": "会议或转录内容不存在"}

        # 重写 transcript 中的 speaker
        if isinstance(meeting.transcript, list):
            rewritten = []
            for entry in meeting.transcript:
                label = entry.get("speaker", "参会者")
                real_name = speaker_mapping.get(label, label)
                rewritten.append({"speaker": real_name, "text": entry.get("text", "")})
            meeting.transcript = rewritten

        # 重新生成全文
        transcript_text = self._transcript_to_text(meeting.transcript)

        # 重新分析
        analysis = await meeting_analysis.analyze_transcript(
            transcript_text, speaker_mapping
        )

        # 重新计算统计
        if isinstance(meeting.transcript, list):
            meeting.speaker_stats = meeting_analysis.compute_speaker_stats(
                meeting.transcript
            )

        meeting.speaker_mapping = speaker_mapping
        meeting.summary = analysis.get("summary", meeting.summary)
        meeting.key_points = analysis.get("key_points") or meeting.key_points
        meeting.decisions = analysis.get("decisions") or meeting.decisions

        await self.db.commit()
        await self.db.refresh(meeting)

        return {
            "meeting_id": meeting.id,
            "summary": meeting.summary,
            "key_points": meeting.key_points or [],
            "decisions": meeting.decisions or [],
            "speaker_stats": meeting.speaker_stats,
            "speaker_mapping": meeting.speaker_mapping,
        }

    async def _link_speakers_to_participants(
        self, meeting_id: int, speaker_mapping: Dict[str, str]
    ) -> None:
        """将发言者自动匹配到课题组成员并添加为会议参与者。"""
        from sqlalchemy import select as sa_select

        for real_name in speaker_mapping.values():
            result = await self.db.execute(
                sa_select(Member).where(Member.name == real_name)
            )
            member = result.scalar_one_or_none()
            if member:
                # 检查是否已是参与者
                existing = await self.db.execute(
                    sa_select(MeetingParticipant).where(
                        MeetingParticipant.meeting_id == meeting_id,
                        MeetingParticipant.member_id == member.id,
                    )
                )
                if not existing.scalar_one_or_none():
                    self.db.add(MeetingParticipant(
                        meeting_id=meeting_id,
                        member_id=member.id,
                        role="participant",
                    ))
        await self.db.commit()

    @classmethod
    async def _generate_summary(cls, transcript_text: str) -> str:
        """用 Claude 生成会议摘要"""
        try:
            client = get_anthropic_client()
            model = get_default_model()
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                system="你是课题组AI助手，请用简洁的中文总结以下会议内容，包含讨论主题、主要观点和结论。200字以内。",
                messages=[{
                    "role": "user",
                    "content": (
                        "请总结以下会议转写内容，注意区分不同发言人的观点：\n\n"
                        f"{transcript_text[:8000]}"
                    ),
                }],
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
            status=TaskStatus.IN_PROGRESS.value,
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
