from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member
from app.schemas.meeting import (
    MeetingCreate, MeetingUpdate, MeetingResponse, MeetingList, MeetingMinutes,
    SpeakerDetectRequest, SpeakerDetectResponse,
    TranscriptAnalyzeRequest, TranscriptAnalyzeResponse,
    SpeakerMapRequest, MeetingAnalyticsResponse,
)
from app.services.meeting_service import MeetingService
from app.services.meeting_analysis_service import meeting_analysis
from app.agent.core import agent

router = APIRouter()


@router.post("/meetings", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    meeting_data: MeetingCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建会议"""
    meeting = Meeting(
        title=meeting_data.title,
        description=meeting_data.description,
        start_time=meeting_data.start_time,
        end_time=meeting_data.end_time,
        location=meeting_data.location,
        meeting_url=meeting_data.meeting_url,
        meeting_id=meeting_data.meeting_id,
        status="scheduled"
    )

    db.add(meeting)
    await db.flush()

    # 添加参与者
    if meeting_data.participants:
        for member_id in meeting_data.participants:
            participant = MeetingParticipant(
                meeting_id=meeting.id,
                member_id=member_id
            )
            db.add(participant)

    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("/meetings", response_model=MeetingList)
async def list_meetings(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询会议列表"""
    query = select(Meeting)

    if date_from:
        query = query.where(Meeting.start_time >= date_from)
    if date_to:
        query = query.where(Meeting.start_time <= date_to)
    if keyword:
        query = query.where(Meeting.title.contains(keyword))

    query = query.order_by(Meeting.start_time.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    meetings = result.scalars().all()

    return MeetingList(items=meetings, total=len(meetings))


# === 粘贴转录 + AI 分析（固定路径必须在参数化路由之前） ===

@router.post("/meetings/detect-speakers", response_model=SpeakerDetectResponse)
async def detect_speakers(
    request: SpeakerDetectRequest,
    current_user: Member = Depends(get_current_user),
):
    """检测转录文本中的发言者（阶段1：不创建会议）"""
    try:
        result = await meeting_analysis.detect_speakers(request.transcript_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发言者检测失败: {str(e)}")


@router.post("/meetings/analyze-text")
async def analyze_transcript_text(
    request: TranscriptAnalyzeRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """粘贴转录文本并全量分析（阶段2：创建会议 + AI 分析 + 创建任务）

    支持两种模式：
    - 不带 speaker_mapping：先返回发言者检测结果让用户确认
    - 带 speaker_mapping：直接执行完整分析
    """
    meeting_service = MeetingService(db)

    if not request.speaker_mapping:
        # 阶段1：只检测发言者，不创建会议
        detection = await meeting_analysis.detect_speakers(request.transcript_text)
        return {
            "phase": "speaker_detection",
            "detection": detection,
            "message": "请确认发言者映射后再次提交",
        }

    # 阶段2：完整分析
    try:
        title = request.title or await meeting_analysis.generate_title(request.transcript_text)
        result = await meeting_service.process_pasted_transcript(
            title=title,
            start_time=request.start_time,
            transcript_text=request.transcript_text,
            speaker_mapping=request.speaker_mapping,
            participant_ids=request.participants,
            created_by=current_user.id,
        )
        result["phase"] = "complete"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转录分析失败: {str(e)}")


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取会议详情"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    return meeting


@router.get("/meetings/{meeting_id}/minutes", response_model=MeetingMinutes)
async def get_meeting_minutes(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取会议纪要"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    if not meeting.summary:
        # 返回空内容而非 404，让前端能正常展示空状态
        return MeetingMinutes(
            summary="",
            key_points=meeting.key_points or [],
            decisions=meeting.decisions or [],
            action_items=[],
            next_meeting=None
        )

    return MeetingMinutes(
        summary=meeting.summary,
        key_points=meeting.key_points or [],
        decisions=meeting.decisions or [],
        action_items=[],
        next_meeting=None
    )


@router.post("/meetings/{meeting_id}/generate-minutes")
async def generate_meeting_minutes(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成会议纪要"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="会议转写内容为空")

    transcript_text = json.dumps(meeting.transcript, ensure_ascii=False)

    # 直接调用 AI 分析服务，不走 agent.chat()（避免污染会话状态）
    analysis = await meeting_analysis.analyze_transcript(transcript_text)

    meeting.summary = analysis.get("summary", "")
    meeting.key_points = analysis.get("key_points") or None
    meeting.decisions = analysis.get("decisions") or None
    meeting.status = "completed"
    await db.commit()

    return {
        "message": "会议纪要生成成功",
        "summary": meeting.summary,
        "key_points": meeting.key_points or [],
        "decisions": meeting.decisions or [],
    }


@router.post("/meetings/{meeting_id}/analyze")
async def analyze_meeting_transcript(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """分析会议转写内容，自动提取摘要、要点、决定和任务"""
    meeting_service = MeetingService(db)
    meeting = await meeting_service.get_meeting(meeting_id)

    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="会议转写内容为空，无法分析")

    try:
        result = await meeting_service.process_meeting_transcript(meeting_id)
        return {
            "message": "分析完成",
            "summary": result["summary"],
            "key_points": result["key_points"],
            "decisions": result["decisions"],
            "tasks_created": result["tasks_created"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.put("/meetings/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: int,
    meeting_data: MeetingUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新会议"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    update_data = meeting_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(meeting, field, value)

    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除会议"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    await db.delete(meeting)
    await db.commit()


@router.post("/meetings/{meeting_id}/speaker-map")
async def apply_speaker_mapping(
    meeting_id: int,
    request: SpeakerMapRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为已有会议设置发言者映射并重新分析"""
    meeting_service = MeetingService(db)

    meeting = await meeting_service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    try:
        result = await meeting_service.reanalyze_with_speakers(
            meeting_id, request.speaker_mapping
        )
        return {"message": "发言者映射已应用并重新分析", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新分析失败: {str(e)}")


@router.get("/meetings/{meeting_id}/analytics", response_model=MeetingAnalyticsResponse)
async def get_meeting_analytics(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会议发言者维度统计"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    if not meeting.speaker_stats:
        # 如果还没有统计但有转录内容，实时计算
        if meeting.transcript and isinstance(meeting.transcript, list):
            stats = meeting_analysis.compute_speaker_stats(meeting.transcript)
            meeting.speaker_stats = stats
            await db.commit()
        else:
            return MeetingAnalyticsResponse(
                speaker_stats=[],
                meeting_stats={"total_turns": 0, "total_words": 0},
            )

    total_turns = sum(s.get("turn_count", 0) for s in (meeting.speaker_stats or []))
    total_words = sum(s.get("word_count", 0) for s in (meeting.speaker_stats or []))

    return MeetingAnalyticsResponse(
        speaker_stats=meeting.speaker_stats or [],
        meeting_stats={
            "total_turns": total_turns,
            "total_words": total_words,
            "speaker_count": len(meeting.speaker_stats or []),
        },
    )
