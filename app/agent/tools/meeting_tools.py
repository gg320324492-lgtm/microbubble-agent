"""会议域工具（v2 架构）

迁移工具（从 core.py._execute_tool 提取）：
- query_meetings: 字段大幅补全（key_points_count/decisions_count/agenda_summary/participants/location/audio_url/task_count）

新增工具：
- get_meeting_detail: 深挖单次会议（key_points/decisions/agenda/participants/speaker_stats/audio）
- get_recent_meeting_conclusions: 按时间范围批量查所有会议决议/要点

未迁移（仍走 dispatch_legacy 回退到 core.py._execute_tool）：
- create_meeting / analyze_meeting_transcript / summarize_meeting_transcript
"""

import logging
from datetime import datetime, timedelta
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.meeting")


# ============================================================================
# 1. query_meetings（迁移 + 字段补全）
# ============================================================================


class QueryMeetingsInput(BaseModel):
    date_from: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    keyword: Optional[str] = Field(None, description="标题关键词")


class MeetingListItem(BaseModel):
    id: int
    title: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    # === 字段补全（2026-06-12 优化）===
    key_points_count: int = 0
    decisions_count: int = 0
    agenda_summary: Optional[str] = None
    participants: list[dict] = Field(default_factory=list)  # [{id, name, role}]
    location: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration: Optional[int] = None
    speaker_stats_summary: Optional[dict] = None  # {total_speakers, top_speaker}
    task_count: int = 0
    rich_block_type: str = "meeting"


class QueryMeetingsOutput(BaseModel):
    status: str
    count: int
    meetings: list[MeetingListItem]


@tool(
    name="query_meetings",
    description="""【必调工具】查询课题组会议记录并返回会议列表。
当用户问题涉及任何会议相关内容时**必须调用此工具**：包括但不限于「最近的会议」「近期组会」「有哪些会议」「查会议」「会议纪要」「有什么会议」「哪些会议可以学习」「上次会议讲了什么」「今天/昨天/上周/本月开过什么会」「UV相关会议」「远紫外会议」「开过哪些学术报告」等。
**禁止编造「系统故障/技术问题/无法访问/需要联系管理员」等借口**——这些借口都是错的，系统正常，数据可查。""",
    input_model=QueryMeetingsInput,
    output_model=QueryMeetingsOutput,
)
async def query_meetings(input: QueryMeetingsInput, ctx: ToolContext) -> dict:
    """查询会议列表（含字段补全）"""
    from app.services.meeting_service import MeetingService

    date_from = None
    date_to = None
    if input.date_from:
        try:
            date_from = datetime.strptime(input.date_from, "%Y-%m-%d")
        except ValueError:
            pass
    if input.date_to:
        try:
            date_to = datetime.strptime(input.date_to, "%Y-%m-%d")
        except ValueError:
            pass

    svc = MeetingService(ctx.db)
    meetings = await svc.get_meetings(date_from=date_from, date_to=date_to, keyword=input.keyword)

    # 构建返回 items（含字段补全）
    items = []
    for m in meetings:
        # 议程摘要
        agenda_summary = None
        if isinstance(m.agenda, list) and m.agenda:
            agenda_titles = [
                a.get("title") if isinstance(a, dict) else str(a)
                for a in m.agenda[:3]
            ]
            agenda_summary = "、".join(filter(None, agenda_titles))
        elif isinstance(m.agenda, str):
            agenda_summary = m.agenda[:60]

        # 参与者
        participants = []
        for p in (m.participants or []):
            participants.append({
                "id": p.member_id,
                "name": getattr(p, "name", "") or "",
                "role": p.role or "participant",
            })

        # 发言人统计摘要
        speaker_stats_summary = None
        if isinstance(m.speaker_stats, list) and m.speaker_stats:
            total = len(m.speaker_stats)
            top = max(m.speaker_stats, key=lambda s: s.get("word_count", 0) if isinstance(s, dict) else 0)
            top_name = top.get("name", "?") if isinstance(top, dict) else "?"
            speaker_stats_summary = {"total_speakers": total, "top_speaker": top_name}

        # 任务数
        task_count = len(m.tasks or [])

        items.append({
            "id": m.id,
            "title": m.title,
            "start_time": m.start_time.strftime("%Y-%m-%d %H:%M") if m.start_time else None,
            "end_time": m.end_time.strftime("%Y-%m-%d %H:%M") if m.end_time else None,
            "status": m.status,
            "summary": (m.summary or "")[:300],
            "key_points_count": len(m.key_points or []),
            "decisions_count": len(m.decisions or []),
            "agenda_summary": agenda_summary,
            "participants": participants,
            "location": m.location,
            "audio_url": m.audio_url,
            "audio_duration": m.audio_duration,
            "speaker_stats_summary": speaker_stats_summary,
            "task_count": task_count,
            "rich_block_type": "meeting",
        })

    return {"status": "success", "count": len(items), "meetings": items}


# ============================================================================
# 2. get_meeting_detail（新增）
# ============================================================================


class GetMeetingDetailInput(BaseModel):
    meeting_id: Optional[int] = Field(None, description="会议ID；不传则用最近一次")
    title_keyword: Optional[str] = Field(None, description="标题关键词（与 meeting_id 二选一）")


class MeetingParticipantInfo(BaseModel):
    id: int
    name: str
    role: str


class GetMeetingDetailOutput(BaseModel):
    status: str
    id: Optional[int] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    agenda: Optional[list] = None
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    participants: list[MeetingParticipantInfo] = Field(default_factory=list)
    speaker_stats: Optional[dict] = None
    task_count: int = 0
    transcript_meta: Optional[dict] = None  # {has_raw, has_polished, entries_count}
    rich_block_type: str = "meeting"


@tool(
    name="get_meeting_detail",
    description="获取一次会议的完整信息（key_points/decisions/agenda/transcript_meta/participants/speaker_stats/audio_url）。用户问「上次例会讲了什么」/「具体决议」/「会议详情」时调用。比 query_meetings 字段更全。",
    input_model=GetMeetingDetailInput,
    output_model=GetMeetingDetailOutput,
)
async def get_meeting_detail(input: GetMeetingDetailInput, ctx: ToolContext) -> dict:
    """获取单次会议详情（深挖）"""
    from app.services.meeting_service import MeetingService

    if not input.meeting_id and not input.title_keyword:
        return {
            "status": "error",
            "code": "MISSING_PARAM",
            "message": "必须提供 meeting_id 或 title_keyword 之一",
        }

    svc = MeetingService(ctx.db)
    m = None
    if input.meeting_id:
        m = await svc.get_meeting(input.meeting_id)
    elif input.title_keyword:
        # 通过 keyword 模糊匹配
        candidates = await svc.get_meetings(keyword=input.title_keyword)
        m = candidates[0] if candidates else None

    if not m:
        return {
            "status": "error",
            "code": "NOT_FOUND",
            "message": f"未找到会议（meeting_id={input.meeting_id}, keyword={input.title_keyword}）",
        }

    # 参与者
    participants = [
        {"id": p.member_id, "name": getattr(p, "name", "") or "", "role": p.role or "participant"}
        for p in (m.participants or [])
    ]

    # 转录元信息
    transcript_meta = {
        "has_raw": bool(m.transcript),
        "has_polished": bool(m.transcript_polished),
        "entries_count": len(m.transcript) if isinstance(m.transcript, list) else 0,
    }

    return {
        "status": "success",
        "id": m.id,
        "title": m.title,
        "summary": m.summary,
        "key_points": list(m.key_points or []),
        "decisions": list(m.decisions or []),
        "agenda": m.agenda,
        "location": m.location,
        "meeting_url": m.meeting_url,
        "audio_url": m.audio_url,
        "audio_duration": m.audio_duration,
        "start_time": m.start_time.isoformat() if m.start_time else None,
        "end_time": m.end_time.isoformat() if m.end_time else None,
        "participants": participants,
        "speaker_stats": m.speaker_stats,
        "task_count": len(m.tasks or []),
        "transcript_meta": transcript_meta,
        "rich_block_type": "meeting",
    }


# ============================================================================
# 3. get_recent_meeting_conclusions（新增）
# ============================================================================


class GetRecentConclusionsInput(BaseModel):
    days_back: int = Field(7, ge=1, le=90, description="查询多少天内的会议")
    min_decisions: int = Field(1, ge=0, description="最少决议数（过滤空会议）")
    status_filter: Optional[str] = Field("completed", description="会议状态过滤（completed/all）")


class RecentConclusionGroup(BaseModel):
    date: str
    meeting_id: int
    title: str
    status: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    start_time: Optional[str] = None


class GetRecentConclusionsOutput(BaseModel):
    status: str
    days_back: int
    total_meetings: int
    groups: list[RecentConclusionGroup]
    rich_block_type: str = "meeting"


@tool(
    name="get_recent_meeting_conclusions",
    description="按时间范围批量查所有会议决议/要点（按日期分组）。用户问「上周的会议结论是什么」/「近期所有会议决议」/「最近开过什么会讨论了什么」时调用。",
    input_model=GetRecentConclusionsInput,
    output_model=GetRecentConclusionsOutput,
)
async def get_recent_meeting_conclusions(input: GetRecentConclusionsInput, ctx: ToolContext) -> dict:
    """批量查近期会议结论（按日期分组）"""
    from app.services.meeting_service import MeetingService

    date_from = datetime.now() - timedelta(days=input.days_back)
    svc = MeetingService(ctx.db)
    meetings = await svc.get_meetings(date_from=date_from)

    # 状态过滤
    if input.status_filter and input.status_filter != "all":
        meetings = [m for m in meetings if m.status == input.status_filter]

    # 决议数过滤
    meetings = [m for m in meetings if len(m.decisions or []) >= input.min_decisions]

    # 按日期分组
    groups_by_date: dict[str, list[dict]] = {}
    for m in meetings:
        date_key = m.start_time.strftime("%Y-%m-%d") if m.start_time else "unknown"
        groups_by_date.setdefault(date_key, []).append({
            "date": date_key,
            "meeting_id": m.id,
            "title": m.title,
            "status": m.status,
            "key_points": list(m.key_points or []),
            "decisions": list(m.decisions or []),
            "start_time": m.start_time.strftime("%H:%M") if m.start_time else None,
        })

    # 平铺成 groups（按日期倒序）
    groups = []
    for date_key in sorted(groups_by_date.keys(), reverse=True):
        groups.extend(groups_by_date[date_key])

    return {
        "status": "success",
        "days_back": input.days_back,
        "total_meetings": len(groups),
        "groups": groups,
        "rich_block_type": "meeting",
    }


# ============================================================================
# 4. get_meeting_transcript（新增）
# ============================================================================


class GetMeetingTranscriptInput(BaseModel):
    meeting_id: int = Field(..., description="会议ID")
    format: str = Field("text", description="输出格式：raw / polished / text（默认 text）")
    max_chars: int = Field(10000, ge=100, le=50000, description="最大字符数（默认 10000，防止 token 溢出）")


class GetMeetingTranscriptOutput(BaseModel):
    status: str
    meeting_id: int
    title: Optional[str] = None
    transcript_text: str = ""
    format: str = "text"
    entries_count: int = 0
    truncated: bool = False
    rich_block_type: str = "transcript"


@tool(
    name="get_meeting_transcript",
    description="获取一次会议的完整转录文本（默认优先 polished 精润色版）。返回文本可能很长（>10k 字会自动截断）。当用户要看会议转录原文、想复盘某段对话、查具体发言内容时调用。",
    input_model=GetMeetingTranscriptInput,
    output_model=GetMeetingTranscriptOutput,
)
async def get_meeting_transcript(input: GetMeetingTranscriptInput, ctx: ToolContext) -> dict:
    """获取单次会议转录（按需截断）"""
    from app.services.meeting_service import MeetingService

    svc = MeetingService(ctx.db)
    m = await svc.get_meeting(input.meeting_id)
    if not m:
        return {
            "status": "error", "code": "NOT_FOUND",
            "message": f"未找到会议（meeting_id={input.meeting_id}）",
            "meeting_id": input.meeting_id, "transcript_text": "",
            "entries_count": 0, "truncated": False,
        }

    # 按 format 选择源
    source_data = None
    if input.format == "polished":
        source_data = m.transcript_polished
    elif input.format == "raw":
        source_data = m.transcript
    else:  # text 默认优先 polished
        source_data = m.transcript_polished or m.transcript

    # 转纯文本
    if isinstance(source_data, list):
        # JSON 格式 [{speaker, text}] → 拼成纯文本
        lines = []
        for entry in source_data:
            if isinstance(entry, dict):
                speaker = entry.get("speaker", "未知")
                text = entry.get("text", "")
                lines.append(f"【{speaker}】{text}")
            elif isinstance(entry, str):
                lines.append(entry)
        text = "\n".join(lines)
    elif isinstance(source_data, str):
        text = source_data
    else:
        text = str(source_data) if source_data else ""

    entries_count = len(source_data) if isinstance(source_data, list) else 0

    # 截断
    truncated = False
    if len(text) > input.max_chars:
        text = text[: input.max_chars] + f"\n\n... (已截断到 {input.max_chars} 字符)"
        truncated = True

    return {
        "status": "success",
        "meeting_id": m.id,
        "title": m.title,
        "transcript_text": text,
        "format": input.format,
        "entries_count": entries_count,
        "truncated": truncated,
        "rich_block_type": "transcript",
    }
