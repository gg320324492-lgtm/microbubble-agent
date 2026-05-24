"""腾讯会议 API"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.base import utcnow

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.tencent_meeting_service import tencent_meeting

logger = logging.getLogger("microbubble.tencent_meeting")

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
    if not tencent_meeting.is_configured:
        raise HTTPException(status_code=500, detail="腾讯会议未配置（缺少 TENCENT_MEETING_SDK_ID/SDK_KEY）")

    try:
        start_ts = request.start_time.strftime("%Y-%m-%d %H:%M:%S") if request.start_time else None
        end_ts = request.end_time.strftime("%Y-%m-%d %H:%M:%S") if request.end_time else None

        result = await tencent_meeting.create_meeting(
            subject=request.subject,
            start_time=start_ts,
            end_time=end_ts,
            meeting_type=request.meeting_type
        )

        meeting_info = result.get("meeting_info", {})
        meeting_id = meeting_info.get("meeting_id", "")
        join_url = meeting_info.get("join_url", "")

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
    if not tencent_meeting.is_configured:
        raise HTTPException(status_code=500, detail="腾讯会议未配置")

    try:
        start_ts = request.start_time.strftime("%Y-%m-%d %H:%M:%S") if request.start_time else None
        end_ts = request.end_time.strftime("%Y-%m-%d %H:%M:%S") if request.end_time else None

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
            start_time=request.start_time or utcnow(),
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


@router.get("/tencent-meeting/list")
async def list_tencent_meetings(
    current_user: Member = Depends(get_current_user)
):
    """查询腾讯会议列表"""
    if not tencent_meeting.is_configured:
        raise HTTPException(status_code=500, detail="腾讯会议未配置")

    try:
        result = await tencent_meeting.list_meetings()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询会议列表失败: {str(e)}")


@router.get("/tencent-meeting/{meeting_id}/info")
async def get_tencent_meeting_info(
    meeting_id: str,
    current_user: Member = Depends(get_current_user)
):
    """获取腾讯会议详情"""
    if not tencent_meeting.is_configured:
        raise HTTPException(status_code=500, detail="腾讯会议未配置")

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
    if not tencent_meeting.is_configured:
        raise HTTPException(status_code=500, detail="腾讯会议未配置")

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


@router.post("/tencent-meeting/{meeting_id}/end")
async def end_tencent_meeting(
    meeting_id: str,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """结束腾讯会议"""
    if not tencent_meeting.is_configured:
        raise HTTPException(status_code=500, detail="腾讯会议未配置")

    try:
        result = await tencent_meeting.end_meeting(meeting_id)

        # 同步更新本地会议状态
        db_result = await db.execute(
            select(Meeting).where(Meeting.meeting_id == meeting_id)
        )
        meeting = db_result.scalar_one_or_none()
        if meeting:
            meeting.status = "completed"
            await db.commit()

        return {"message": "会议已结束", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"结束会议失败: {str(e)}")


@router.post("/tencent-meeting/webhook")
async def meeting_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    腾讯会议 Webhook 回调

    接收会议生命周期事件，更新本地会议状态
    """
    try:
        body = await request.json()

        # 验证签名（如果有 Token）
        token = body.get("token", "")
        timestamp = request.headers.get("X-TC-Timestamp", "")
        nonce = request.headers.get("X-TC-Nonce", "")
        signature = request.headers.get("X-TC-Signature", "")

        if signature and not tencent_meeting.verify_webhook_signature(token, timestamp, nonce, signature):
            logger.warning(f"Webhook 签名验证失败")
            raise HTTPException(status_code=401, detail="签名验证失败")

        event_type = body.get("event_type", "")
        meeting_id = body.get("meeting_id", "")
        logger.info(f"收到腾讯会议 Webhook: event={event_type}, meeting_id={meeting_id}")

        if not meeting_id:
            return {"code": 0, "message": "ok"}

        # 根据事件类型更新本地会议状态
        status_map = {
            "meeting_started": "recording",
            "meeting_ended": "completed",
            "meeting_cancelled": "cancelled",
        }

        new_status = status_map.get(event_type)
        if new_status:
            db_result = await db.execute(
                select(Meeting).where(Meeting.meeting_id == meeting_id)
            )
            meeting = db_result.scalar_one_or_none()
            if meeting:
                meeting.status = new_status
                await db.commit()
                logger.info(f"本地会议 {meeting.id} 状态更新为 {new_status}")

                # 会议结束时，如果有转写内容则自动分析
                if event_type == "meeting_ended" and meeting.transcript:
                    try:
                        from app.services.meeting_service import MeetingService
                        meeting_service = MeetingService(db)
                        await meeting_service.process_meeting_transcript(meeting.id)
                        logger.info(f"会议 {meeting.id} 结束，自动分析完成")
                    except Exception as e:
                        logger.error(f"会议自动分析失败: {e}", exc_info=True)

        return {"code": 0, "message": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook 处理失败: {e}", exc_info=True)
        return {"code": 0, "message": "ok"}  # 返回成功避免重试
