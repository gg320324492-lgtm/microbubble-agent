"""腾讯会议 API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting import Meeting, MeetingParticipant
from app.services.tencent_meeting_service import tencent_meeting

router = APIRouter()


class CreateTencentMeetingRequest(BaseModel):
    """创建腾讯会议请求"""
    subject: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_type: int = 1  # 1=预约, 0=快速


class CreateTencentMeetingResponse(BaseModel):
    """创建腾讯会议响应"""
    meeting_id: str
    join_url: str
    subject: str
    meeting_info: dict


@router.post("/tencent-meeting/create", response_model=CreateTencentMeetingResponse)
async def create_tencent_meeting(
    request: CreateTencentMeetingRequest,
    current_user: Member = Depends(get_current_user)
):
    """创建腾讯会议（不自动创建本地会议记录）"""
    if not tencent_meeting.app_id:
        raise HTTPException(status_code=500, detail="腾讯会议未配置（缺少 TENCENT_MEETING_APP_ID）")

    try:
        start_ts = str(int(request.start_time.timestamp())) if request.start_time else None
        end_ts = str(int(request.end_time.timestamp())) if request.end_time else None

        result = await tencent_meeting.create_meeting(
            subject=request.subject,
            start_time=start_ts,
            end_time=end_ts,
            meeting_type=request.meeting_type
        )

        meeting_id = result.get("meeting_info", {}).get("meeting_id", "")
        join_url = result.get("meeting_info", {}).get("join_url", "")

        return CreateTencentMeetingResponse(
            meeting_id=meeting_id,
            join_url=join_url,
            subject=request.subject,
            meeting_info=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建腾讯会议失败: {str(e)}")


@router.post("/tencent-meeting/create-and-link")
async def create_and_link_meeting(
    request: CreateTencentMeetingRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建腾讯会议并自动创建本地会议记录"""
    if not tencent_meeting.app_id:
        raise HTTPException(status_code=500, detail="腾讯会议未配置")

    try:
        start_ts = str(int(request.start_time.timestamp())) if request.start_time else None
        end_ts = str(int(request.end_time.timestamp())) if request.end_time else None

        tm_result = await tencent_meeting.create_meeting(
            subject=request.subject,
            start_time=start_ts,
            end_time=end_ts,
            meeting_type=request.meeting_type
        )

        meeting_info = tm_result.get("meeting_info", {})
        meeting_id = meeting_info.get("meeting_id", "")
        join_url = meeting_info.get("join_url", "")

        # 创建本地会议记录
        meeting = Meeting(
            title=request.subject,
            start_time=request.start_time or datetime.utcnow(),
            end_time=request.end_time,
            meeting_url=join_url,
            meeting_id=meeting_id,
            status="scheduled",
            created_by=current_user.id
        )
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)

        return {
            "local_meeting_id": meeting.id,
            "tencent_meeting_id": meeting_id,
            "join_url": join_url,
            "subject": request.subject
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/tencent-meeting/{meeting_id}/info")
async def get_tencent_meeting_info(
    meeting_id: str,
    current_user: Member = Depends(get_current_user)
):
    """获取腾讯会议详情"""
    try:
        result = await tencent_meeting.get_meeting_info(meeting_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会议信息失败: {str(e)}")


@router.post("/tencent-meeting/{meeting_id}/cancel")
async def cancel_tencent_meeting(
    meeting_id: str,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消腾讯会议"""
    try:
        result = await tencent_meeting.cancel_meeting(meeting_id)

        # 同步更新本地会议状态
        db_result = await db.execute(
            select(Meeting).where(Meeting.meeting_id == meeting_id)
        )
        meeting = db_result.scalar_one_or_none()
        if meeting:
            meeting.status = "cancelled"
            await db.commit()

        return {"message": "会议已取消", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消会议失败: {str(e)}")
