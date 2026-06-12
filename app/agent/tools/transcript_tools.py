"""会议转录分析域工具（v3 迁移）

迁移自 core.py._execute_tool：
- analyze_meeting_transcript (line 838) — 多步 LLM
- summarize_meeting_transcript (line 906) — LLM + Memory 写库
"""

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.transcript")


# ============================================================================
# 1. analyze_meeting_transcript（中等复杂度，多步 LLM）
# ============================================================================


class AnalyzeMeetingTranscriptInput(BaseModel):
    transcript_text: str = Field(..., min_length=10, description="会议转录文本")
    speaker_mapping: Optional[dict] = Field(None, description="发言者映射，如 {'原始标签': '真实姓名'}")
    create_meeting: bool = Field(True, description="是否同时创建会议记录并自动创建任务，默认 true")


class AnalyzeMeetingTranscriptOutput(BaseModel):
    status: str
    meeting_id: Optional[int] = None
    summary: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    tasks_created: list[dict] = Field(default_factory=list)
    speaker_stats: Optional[dict] = None
    detection: Optional[dict] = None
    action_items: Optional[list] = Field(default_factory=list)
    rich_block_type: Optional[str] = None


@tool(
    name="analyze_meeting_transcript",
    description="对粘贴的会议转录文本进行完整的 AI 分析——自动识别发言者、生成摘要、提取要点/决策/行动项、自动创建任务。当用户粘贴会议文本并需要智能分析时调用。",
    input_model=AnalyzeMeetingTranscriptInput,
    output_model=AnalyzeMeetingTranscriptOutput,
)
async def analyze_meeting_transcript(input: AnalyzeMeetingTranscriptInput, ctx: ToolContext) -> dict:
    """完整分析会议转录（多步 LLM）"""
    from app.services.meeting_service import MeetingService
    from app.services.meeting_analysis_service import meeting_analysis

    if input.create_meeting:
        svc = MeetingService(ctx.db)
        created = await svc.process_pasted_transcript(
            title=f"会议分析 - {datetime.now().strftime('%m-%d %H:%M')}",
            start_time=datetime.now(),
            transcript_text=input.transcript_text,
            speaker_mapping=input.speaker_mapping,
            created_by=ctx.user_id,
        )
        return {
            "status": "success",
            "meeting_id": created.get("meeting_id"),
            "summary": created.get("summary", ""),
            "key_points": created.get("key_points", []),
            "decisions": created.get("decisions", []),
            "tasks_created": created.get("tasks_created", []),
            "speaker_stats": created.get("speaker_stats"),
        }
    # 仅分析不创建会议
    detection = await meeting_analysis.detect_speakers(input.transcript_text)
    analysis = await meeting_analysis.analyze_transcript(
        input.transcript_text, input.speaker_mapping
    )
    return {
        "status": "success",
        "detection": detection,
        "summary": analysis.get("summary", ""),
        "key_points": analysis.get("key_points", []),
        "decisions": analysis.get("decisions", []),
        "action_items": analysis.get("action_items", []),
    }


# ============================================================================
# 2. summarize_meeting_transcript（中等复杂度，LLM + 写库副作用）
# ============================================================================


class SummarizeMeetingTranscriptInput(BaseModel):
    transcript_text: str = Field(..., min_length=10, description="会议转录文本")


class SummarizeMeetingTranscriptOutput(BaseModel):
    status: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    tasks: list[dict] = Field(default_factory=list)
    rich_block_type: Optional[str] = None


@tool(
    name="summarize_meeting_transcript",
    description="对会议转录文字进行自动归纳总结，同时将总结存入 Agent 长期记忆。当用户提供会议转录文本、要求总结会议内容时使用。",
    input_model=SummarizeMeetingTranscriptInput,
    output_model=SummarizeMeetingTranscriptOutput,
)
async def summarize_meeting_transcript(input: SummarizeMeetingTranscriptInput, ctx: ToolContext) -> dict:
    """总结转录 + 写长期记忆（DB 副作用）"""
    if not ctx.user_id:
        return {
            "status": "error", "message": "无法识别用户身份",
            "summary": "", "key_points": [], "decisions": [], "tasks": [],
        }

    from app.services.meeting_service import MeetingService
    from app.services.memory_service import MemoryService
    from app.wechat.analyzer import ConversationAnalyzer

    # 1. 摘要
    summary = await MeetingService._generate_summary(input.transcript_text)
    # 2. 行动项
    analyzer = ConversationAnalyzer()
    analysis = await analyzer.extract_action_items(input.transcript_text)
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
    # 3. 写长期记忆
    mem_svc = MemoryService(ctx.db)
    await mem_svc.save_memory(
        user_id=ctx.user_id,
        memory_type="summary",
        content=f"【会议总结】\n\n摘要：{summary}\n\n要点：{'；'.join(key_points)}\n\n原始转录：{input.transcript_text[:3000]}",
        importance=0.8,
    )
    return {
        "status": "success",
        "summary": summary,
        "key_points": key_points,
        "decisions": analysis.get("decisions", []),
        "tasks": analysis.get("tasks", []),
    }
