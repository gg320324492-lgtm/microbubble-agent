from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.security import get_password_hash, get_current_user, get_current_admin_user
from app.models.member import Member
from app.schemas.member import MemberCreate, MemberUpdate, MemberResponse, MemberList

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
        raise HTTPException(status_code=400, detail="用户名已存在")

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

    return MemberList(items=members, total=len(members))


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
        raise HTTPException(status_code=404, detail="成员不存在")

    return member


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
        raise HTTPException(status_code=404, detail="成员不存在")

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
        raise HTTPException(status_code=404, detail="成员不存在")

    member.is_active = False
    await db.commit()
