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

    async def get_member_by_name(self, name: str, is_active: Optional[bool] = None) -> Optional[Member]:
        """按姓名查询成员

        2026-06-14 收官：is_active=None 时不过滤（兼容历史成员/alumni 查找）。
        显式传 True/False 则按值过滤。
        """
        query = select(Member).where(Member.name == name)
        if is_active is not None:
            query = query.where(Member.is_active == is_active)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_members(
        self,
        name: Optional[str] = None,
        research_area: Optional[str] = None,
        grade: Optional[str] = None,
        is_active: bool = True
    ) -> List[Member]:
        """查询成员列表

        2026-06-14 收官：
        - 按姓名查（name 显式传）时不强制 is_active=True — 用户明确指名应能查到 alumni/已离开成员
        - 按 research_area/grade 查（列表筛选）时仍走 is_active=True — 列表展示只给当前成员
        - 显式传 is_active=False 可看历史成员

        2026-06-15 增强：
        - grade 简写自动模糊匹配（防「博一」查不到「博士」类 bug）：
          * 博一/博二/博三/博四 → ilike "博%"（匹配博士、博一、博二 等所有博士相关记录）
          * 研一/研二/研三 → exact match（保留精确）
          * 大三/大四/副教授/已毕业 → exact match
          * 博士 → ilike "博%"
          * 其他 → exact match
        """
        query = select(Member)
        filters = []
        if name:
            # 显式指名查询：不过滤 is_active
            filters.append(Member.name.ilike(f"%{name}%"))
        else:
            # 列表筛选：默认 is_active=True（仅当前成员）
            filters.append(Member.is_active == is_active)

        if research_area:
            filters.append(Member.research_area.ilike(f"%{research_area}%"))
        if grade:
            # grade 简写模糊匹配：博一/博二/博三/博四/博士 一律匹配博%
            grade_normalized = grade.strip()
            if grade_normalized in ("博一", "博二", "博三", "博四", "博士"):
                filters.append(Member.grade.ilike("博%"))
            else:
                filters.append(Member.grade == grade_normalized)

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
