from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional

from app.core.exceptions import ConflictException
from app.models.member import Member


class MemberService:
    """成员服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # v2 PR6-P13/P14: case-insensitive uniqueness helpers
    # ============================================================
    # 通用 helper: 同时支持 username 和 wechat_id (mention 3 路匹配都用 lower())
    # 反射 Member.__table__.columns 取列引用, 避免硬编码
    _IDENTIFIER_COLUMNS = frozenset({"username", "wechat_id"})

    @staticmethod
    async def _assert_identifier_unique(
        db: AsyncSession,
        column_name: str,
        value: Optional[str],
        exclude_member_id: Optional[int] = None,
    ) -> None:
        """case-insensitive 唯一检查 (PR6-P13 username + PR6-P14 wechat_id 通用)

        反射 Member 表的列名, 支持 username / wechat_id (未来可扩 personal_wechat_id 等).
        空值/None 跳过检查 (与 PG UNIQUE 索引 NULL 不参与行为一致).

        Args:
            db: AsyncSession
            column_name: 'username' 或 'wechat_id' (白名单限定, 防止任意列)
            value: 待检查值 (None / 空字符串跳过)
            exclude_member_id: 更新自己时排除自己 (Member.id != current)

        Raises:
            ValueError: column_name 不在白名单
            ConflictException: 值已存在 (case-insensitive), message 含 column_name
        """
        if column_name not in MemberService._IDENTIFIER_COLUMNS:
            raise ValueError(
                f"_assert_identifier_unique 只支持 {MemberService._IDENTIFIER_COLUMNS}, "
                f"实参 column_name={column_name!r}"
            )

        if not value:
            # 空 / None 跳过检查 (与 alembic 053/054 函数索引 NULL 不参与行为一致)
            return

        normalized = value.lower().strip()
        if not normalized:
            return

        # 反射获取列对象 (避免硬编码 Member.username / Member.wechat_id)
        column = getattr(Member, column_name)

        stmt = select(Member.id).where(func.lower(column) == normalized)
        if exclude_member_id is not None:
            stmt = stmt.where(Member.id != exclude_member_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            column_label = "用户名" if column_name == "username" else "微信号"
            raise ConflictException(
                f"{column_label}已存在 (大小写不敏感): {value} (existing_member_id={existing})",
                resource=f"members.{column_name}={value}",
            )

    @staticmethod
    async def _assert_username_unique(
        db: AsyncSession,
        username: str,
        exclude_member_id: Optional[int] = None,
    ) -> None:
        """v2 PR6-P13: 包装 _assert_identifier_unique(username=...) 向后兼容

        保留旧 API 给已有调用方 (test_member_username_ci_unique.py 等),
        新代码优先用 _assert_identifier_unique.
        """
        await MemberService._assert_identifier_unique(
            db, "username", username, exclude_member_id=exclude_member_id
        )

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
        wechat_id: Optional[str] = None,
        grade: Optional[str] = None,
        research_area: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "member"
    ) -> Member:
        """创建成员

        v2 PR6-P13/P14: 创建前检查 username + wechat_id 是否被占用 (case-insensitive),
        与 alembic 053 (username) + 054 (wechat_id) 兜底配合.
        """
        # PR6-P13 username 唯一检查
        await self._assert_identifier_unique(self.db, "username", username)
        # PR6-P14 wechat_id 唯一检查 (comment_service mention 3 路匹配也走 lower)
        await self._assert_identifier_unique(self.db, "wechat_id", wechat_id)
        member = Member(
            name=name,
            username=username,
            password_hash=password_hash,
            wechat_id=wechat_id,
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
        """更新成员信息

        v2 PR6-P13/P14: 如果 kwargs 含 username 或 wechat_id, 走 case-insensitive 唯一检查 (排除自己)
        """
        member = await self.get_member(member_id)
        if not member:
            return None

        # PR6-P13 username
        if "username" in kwargs and kwargs["username"] is not None:
            await self._assert_identifier_unique(
                self.db, "username", kwargs["username"], exclude_member_id=member_id
            )
        # PR6-P14 wechat_id
        if "wechat_id" in kwargs and kwargs["wechat_id"] is not None:
            await self._assert_identifier_unique(
                self.db, "wechat_id", kwargs["wechat_id"], exclude_member_id=member_id
            )

        for key, value in kwargs.items():
            if hasattr(member, key) and value is not None:
                setattr(member, key, value)

        await self.db.commit()
        await self.db.refresh(member)
        return member
