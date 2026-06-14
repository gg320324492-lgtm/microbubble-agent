from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.security import get_password_hash, get_current_user, get_current_admin_user
from app.core.exceptions import NotFoundException, ValidationException, ForbiddenException
from app.models.member import Member
from app.schemas.member import MemberCreate, MemberUpdate, MemberResponse, MemberList
from app.api.v1.auth import _resolve_avatar_url

router = APIRouter()


@router.post("/members", response_model=MemberResponse, status_code=201)
async def create_member(
    member_data: MemberCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建成员"""
    existing = await db.execute(select(Member).where(Member.username == member_data.username))
    if existing.scalar_one_or_none():
        raise ValidationException("用户名已存在")

    member = Member(
        name=member_data.name,
        username=member_data.username,
        password_hash=get_password_hash(member_data.password) if member_data.password else None,
        grade=member_data.grade,
        research_area=member_data.research_area,
        skills=member_data.skills,
        email=member_data.email,
        phone=member_data.phone,
        bio=member_data.bio,
        wechat_id=member_data.wechat_id,
        wechat_nickname=member_data.wechat_nickname,
        wechat_remark=member_data.wechat_remark,
        personal_wechat_id=member_data.personal_wechat_id,
        wechat_mobile=member_data.wechat_mobile,
        role=member_data.role
    )

    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.get("/members", response_model=MemberList)
async def list_members(
    name: Optional[str] = None,
    research_area: Optional[str] = None,
    grade: Optional[str] = None,
    is_active: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询成员列表"""
    query = select(Member).where(Member.is_active == is_active)

    if name:
        query = query.where(Member.name.contains(name))
    if research_area:
        query = query.where(Member.research_area.contains(research_area))
    if grade:
        query = query.where(Member.grade == grade)

    query = query.order_by(Member.id)
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    members = result.scalars().all()

    # Build response with resolved avatar URLs — do NOT mutate ORM objects
    # (get_db auto-commits after every request, even GET)
    items = []
    for m in members:
        resp = MemberResponse.model_validate(m)
        resp.avatar = _resolve_avatar_url(m)
        items.append(resp)

    return MemberList(items=items, total=len(members))


@router.get("/members/{member_id}", response_model=MemberResponse)
async def get_member(
    member_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取成员详情"""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()

    if not member:
        raise NotFoundException("成员")

    resp = MemberResponse.model_validate(member)
    resp.avatar = _resolve_avatar_url(member)
    return resp


@router.put("/members/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: int,
    member_data: MemberUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新成员"""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()

    if not member:
        raise NotFoundException("成员")

    update_data = member_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(member, field, value)

    await db.commit()
    await db.refresh(member)
    return member


@router.delete("/members/{member_id}", status_code=204)
async def delete_member(
    member_id: int,
    current_user: Member = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除成员（软删除）"""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()

    if not member:
        raise NotFoundException("成员")

    member.is_active = False
    await db.commit()

    from app.core.redis import invalidate_verified_cache_for_member
    await invalidate_verified_cache_for_member(member_id)


# === v2 通知偏好 API（2026-06-15 提醒体系优化） ===

@router.get("/members/me/notification-preferences")
async def get_my_notification_preferences(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的通知偏好（v2 11AM 单一窗口）"""
    from app.services.reminder_policy import (
        is_in_digest_window,
        next_digest_slot,
    )
    from app.models.base import utcnow
    pref = current_user.notification_preferences or {}
    return {
        "enabled": pref.get("enabled", True),
        "digest_time": pref.get("digest_time", "11:00"),
        "channels": pref.get("channels", ["wechat"]),
        "snoozed_until": pref.get("snoozed_until"),
        "in_digest_window": is_in_digest_window(),
        "next_digest_at": next_digest_slot(utcnow()),
    }


@router.put("/members/me/notification-preferences")
async def update_my_notification_preferences(
    payload: dict,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户的通知偏好

    副作用：digest_time 改了后，已有 pending reminder 按新时间重排
    """
    from datetime import time as dtime
    from app.services.reminder_policy import next_digest_slot, batch_date_for
    from app.services.reminder_scheduler import reminder_scheduler
    from app.models.reminder import Reminder

    pref = dict(current_user.notification_preferences or {})

    # 只更新传入的字段
    for k in ("enabled", "digest_time", "channels", "snoozed_until"):
        if k in payload and payload[k] is not None:
            v = payload[k]
            if k == "snoozed_until" and hasattr(v, "isoformat"):
                v = v.isoformat()
            pref[k] = v

    # 允许把 snoozed_until 显式设为 null 解锁
    if "snoozed_until" in payload and payload["snoozed_until"] is None:
        pref["snoozed_until"] = None

    current_user.notification_preferences = pref
    await db.commit()
    await db.refresh(current_user)

    # digest_time 改了 → 已有 reminder 重排
    if "digest_time" in payload and payload["digest_time"]:
        try:
            hh, mm = payload["digest_time"].split(":")
            new_digest_time = dtime(int(hh), int(mm))
        except (ValueError, AttributeError):
            raise ValidationException("digest_time 格式错误，应为 HH:MM")

        result = await db.execute(
            select(Reminder).where(Reminder.status == "pending")
        )
        for r in result.scalars().all():
            new_at = next_digest_slot(r.remind_at, digest_time=new_digest_time)
            r.remind_at = new_at
            r.reminder_batch_date = batch_date_for(new_at)
            try:
                await reminder_scheduler.add_reminder(r.id, new_at.timestamp())
            except Exception as e:
                import logging
                logging.getLogger("microbubble.member_api").warning(
                    f"重排 reminder 失败 reminder_id={r.id}: {e}"
                )
        await db.commit()

    return await get_my_notification_preferences(
        current_user=current_user, db=db
    )
