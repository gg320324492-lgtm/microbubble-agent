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

    async def resolve_by_nickname(self, nickname: str, db: AsyncSession) -> Optional[Member]:
        """
        通过昵称/备注名匹配用户

        匹配顺序：wechat_remark → wechat_nickname → name
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
        return result.scalars().first()

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
            member = await self.resolve_by_nickname(nickname, db)
            if member:
                return member

        return None

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
        db: AsyncSession = None
    ) -> Member:
        """
        绑定用户身份信息（用于首次识别后自动绑定）

        Returns:
            更新后的 Member
        """
        if wechat_userid and not member.wechat_id:
            member.wechat_id = wechat_userid
        if external_userid and not member.external_userid:
            member.external_userid = external_userid
        if wechat_nickname and not member.wechat_nickname:
            member.wechat_nickname = wechat_nickname
        if wechat_remark and not member.wechat_remark:
            member.wechat_remark = wechat_remark
        if personal_wechat_id and not member.personal_wechat_id:
            member.personal_wechat_id = personal_wechat_id
        if mobile and not member.phone:
            member.phone = mobile

        await db.commit()
        await db.refresh(member)
        return member


# 全局实例
identity_resolver = IdentityResolver()
