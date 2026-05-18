from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member
from app.schemas.meeting import (
    MeetingCreate, MeetingUpdate, MeetingResponse, MeetingList, MeetingMinutes
)
from app.services.meeting_service import MeetingService
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
        raise HTTPException(status_code=404, detail="会议纪要尚未生成")

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

    # 使用Agent生成纪要
    transcript_text = json.dumps(meeting.transcript, ensure_ascii=False)
    prompt = f"""
    请分析以下会议转写内容，生成结构化的会议纪要。

    要求输出：
    1. 会议摘要（3-5句话）
    2. 讨论要点
    3. 决议事项
    4. 待办任务（包含负责人和截止日期建议）

    会议转写内容：
    {transcript_text}
    """

    response = await agent.chat(prompt, db=db)

    # 解析并保存（简化处理）
    meeting.summary = response["content"]
    meeting.status = "completed"
    await db.commit()

    return {"message": "会议纪要生成成功", "minutes": response["content"]}


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
