"""多信号用户身份识别模块

支持通过多种信号识别用户身份：
- 企业微信 userid（精确匹配）
- 微信互通 external_userid（普通微信用户，精确匹配）
- 企业微信昵称 / 备注名
- 个人微信号
- 手机号
- 姓名（模糊匹配）
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.member import Member


class IdentityResolver:
    """用户身份解析器"""

    async def resolve(self, wechat_userid: str, db: AsyncSession) -> Optional[Member]:
        """
        通过企业微信 userid 解析用户身份

        Args:
            wechat_userid: 企业微信回调中的 FromUserName
            db: 数据库会话

        Returns:
            匹配到的 Member，未找到返回 None
        """
        result = await db.execute(
            select(Member).where(
                Member.wechat_id == wechat_userid,
                Member.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def resolve_by_external_userid(self, external_userid: str, db: AsyncSession) -> Optional[Member]:
        """
        通过微信互通外部用户ID解析用户身份

        Args:
            external_userid: 普通微信用户的 external_userid（wm 开头）
            db: 数据库会话

        Returns:
            匹配到的 Member，未找到返回 None
        """
        result = await db.execute(
            select(Member).where(
                Member.external_userid == external_userid,
                Member.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def resolve_by_nickname(self, nickname: str, db: AsyncSession) -> List[Member]:
        """
        通过昵称/备注名匹配用户

        匹配顺序：wechat_remark → wechat_nickname → name
        返回列表，调用方需处理重名消歧
        """
        result = await db.execute(
            select(Member).where(
                or_(
                    Member.wechat_remark == nickname,
                    Member.wechat_nickname == nickname,
                    Member.name == nickname
                ),
                Member.is_active == True
            )
        )
        return result.scalars().all()

    async def resolve_by_wechat_id(self, wechat_id: str, db: AsyncSession) -> Optional[Member]:
        """通过个人微信号匹配"""
        result = await db.execute(
            select(Member).where(
                Member.personal_wechat_id == wechat_id,
                Member.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def resolve_by_mobile(self, mobile: str, db: AsyncSession) -> Optional[Member]:
        """通过手机号匹配"""
        result = await db.execute(
            select(Member).where(
                or_(
                    Member.phone == mobile,
                    Member.wechat_mobile == mobile
                ),
                Member.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def resolve_multi_signal(
        self,
        wechat_userid: str = None,
        external_userid: str = None,
        nickname: str = None,
        wechat_id: str = None,
        mobile: str = None,
        db: AsyncSession = None
    ) -> Optional[Member]:
        """
        多信号综合匹配

        按优先级依次尝试：
        1. wechat_userid（企业微信ID，最可靠）
        2. external_userid（微信互通外部用户ID）
        3. wechat_id（个人微信号）
        4. mobile（手机号）
        5. nickname（昵称/备注/姓名，可能重名）
        """
        if wechat_userid:
            member = await self.resolve(wechat_userid, db)
            if member:
                return member

        if external_userid:
            member = await self.resolve_by_external_userid(external_userid, db)
            if member:
                return member

        if wechat_id:
            member = await self.resolve_by_wechat_id(wechat_id, db)
            if member:
                return member

        if mobile:
            member = await self.resolve_by_mobile(mobile, db)
            if member:
                return member

        if nickname:
            members = await self.resolve_by_nickname(nickname, db)
            if len(members) == 1:
                return members[0]
            # len > 1 表示有歧义，返回 None 让调用方处理消歧

        return None

    async def resolve_by_name_or_mobile(self, content: str, db: AsyncSession) -> Optional[Member]:
        """
        通过姓名或手机号匹配已绑定的成员

        用于已验证用户换设备/会话后的快速识别。
        只匹配已绑定过 external_userid 或 wechat_id 的成员（已验证用户）。
        """
        result = await db.execute(
            select(Member).where(
                Member.is_active == True,
                or_(
                    Member.external_userid.isnot(None),
                    Member.wechat_id.isnot(None)
                ),
                or_(
                    Member.name == content,
                    Member.phone == content,
                    Member.wechat_mobile == content
                )
            )
        )
        return result.scalars().first()

    async def fuzzy_search(self, keyword: str, db: AsyncSession) -> List[Member]:
        """
        模糊搜索成员（用于候选匹配）

        搜索范围：name, wechat_nickname, wechat_remark, research_area
        """
        result = await db.execute(
            select(Member).where(
                or_(
                    Member.name.ilike(f"%{keyword}%"),
                    Member.wechat_nickname.ilike(f"%{keyword}%"),
                    Member.wechat_remark.ilike(f"%{keyword}%"),
                    Member.research_area.ilike(f"%{keyword}%")
                ),
                Member.is_active == True
            )
        )
        return result.scalars().all()

    async def bind_identity(
        self,
        member: Member,
        wechat_userid: str = None,
        external_userid: str = None,
        wechat_nickname: str = None,
        wechat_remark: str = None,
        personal_wechat_id: str = None,
        mobile: str = None,
        db: AsyncSession = None,
        force: bool = False
    ) -> Member:
        """
        绑定用户身份信息

        Args:
            force: True 时覆盖已有值，False 时仅填充空字段
        """
        changed = False

        def _update(field_name: str, new_value: str):
            nonlocal changed
            if not new_value:
                return
            current = getattr(member, field_name)
            if force or not current:
                setattr(member, field_name, new_value)
                changed = True

        _update("wechat_id", wechat_userid)
        _update("external_userid", external_userid)
        _update("wechat_nickname", wechat_nickname)
        _update("wechat_remark", wechat_remark)
        _update("personal_wechat_id", personal_wechat_id)
        _update("phone", mobile)

        if changed:
            await db.commit()
            await db.refresh(member)
        return member


# 全局实例
identity_resolver = IdentityResolver()
