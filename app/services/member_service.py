from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional

from app.models.member import Member


class MemberService:
    """成员服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_member(self, member_id: int) -> Optional[Member]:
        """获取单个成员"""
        result = await self.db.execute(select(Member).where(Member.id == member_id))
        return result.scalar_one_or_none()

    async def get_member_by_name(self, name: str) -> Optional[Member]:
        """按姓名查询成员"""
        result = await self.db.execute(select(Member).where(Member.name == name))
        return result.scalar_one_or_none()

    async def get_members(
        self,
        name: Optional[str] = None,
        research_area: Optional[str] = None,
        grade: Optional[str] = None,
        is_active: bool = True
    ) -> List[Member]:
        """查询成员列表"""
        query = select(Member)
        filters = [Member.is_active == is_active]

        if name:
            filters.append(Member.name.ilike(f"%{name}%"))
        if research_area:
            filters.append(Member.research_area.ilike(f"%{research_area}%"))
        if grade:
            filters.append(Member.grade == grade)

        query = query.where(and_(*filters))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_member(
        self,
        name: str,
        username: Optional[str] = None,
        password_hash: Optional[str] = None,
        grade: Optional[str] = None,
        research_area: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "member"
    ) -> Member:
        """创建成员"""
        member = Member(
            name=name,
            username=username,
            password_hash=password_hash,
            grade=grade,
            research_area=research_area,
            email=email,
            phone=phone,
            role=role,
            is_active=True
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def update_member(self, member_id: int, **kwargs) -> Optional[Member]:
        """更新成员信息"""
        member = await self.get_member(member_id)
        if not member:
            return None

        for key, value in kwargs.items():
            if hasattr(member, key) and value is not None:
                setattr(member, key, value)

        await self.db.commit()
        await self.db.refresh(member)
        return member
