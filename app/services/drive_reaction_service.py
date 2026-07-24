"""Drive v2 PR12 — 表情反应 (Emoji Reactions) Service (2026-07-24)

职责:
- drive_reactions 表 CRUD (add / remove / list 聚合 / list_my)
- 校验 emoji 在内置白名单
- 校验 polymorphic target 存在 + 用户有 read 权限 (复用 drive_permission_service)
- WS 推送 reaction_added (W68 PR10 集成)

设计要点:
- 4 个方法 + 1 个聚合函数
- add_reaction 幂等 (UNIQUE 约束防重复 — 已存在返 None 不报错)
- remove_reaction 仅本人 (member_id == current_user.id)
- list_reactions 聚合 emoji → {count, members: [{id, name, avatar_url}]}
- list_my_reactions 返 emoji 列表 (前端 toggle 状态)

权限模型:
- add_reaction: 任何能访问 target (read 权限) 都能 add (类似 GitHub)
- remove_reaction: 仅本人 (admin 不 override, 与 comment author 主权一致)
- list: 复用 target 的 read 权限 (无 read → 返空 + 403)

调用方 (API 层):
- POST   /api/v1/drive/reactions                     → add (body: target_type/target_id/emoji)
- DELETE /api/v1/drive/reactions/{id}                → remove (按 id — DB 主键, 仅本人)
- GET    /api/v1/drive/reactions?target_type=&target_id=  → list 聚合

WS 推送:
- add_reaction 成功 → publish_reaction_added (HIGH priority, 通知 file/folder owner)
- remove 暂不推送 (低优先级, 用户量小; 后续 PR 按需加)

约束:
- emoji 列必须 ∈ ALLOWED_EMOJIS (12 个内置白名单, Pydantic schema 校验)
- target 必须存在 + 未删除 (service validate)
- polymorphic FK 故意不在 DB 层强制 (DB CHECK 约束 target_type 字符串, FK 关系 service validate)

锚点范式第 94 守恒 (W68 第 8 批 B-2).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_comment import DriveComment
from app.models.drive_reaction import ALLOWED_EMOJIS, DriveReaction
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member

logger = logging.getLogger("microbubble.drive_reaction")


class DriveReactionServiceError(Exception):
    """业务级错误, 调用方映射到 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ==========================================================================
# 目标验证辅助
# ==========================================================================


async def _validate_target_exists(
    db: AsyncSession, target_type: str, target_id: int
) -> bool:
    """验证 polymorphic target 存在 + 未删除

    Returns:
        True: 存在 (调用方继续)
        False: 不存在 (调用方抛 404)

    Notes:
        - 'note' 暂未建表, 直接返 False (未来 PR 加 drive_notes 表后再放开)
        - 'comment' → drive_comments.id (无软删, hard delete)
        - 'file'    → knowledge.id (deleted_at IS NULL + storage_mode='drive')
    """
    if target_type == "comment":
        stmt = select(func.count()).select_from(DriveComment).where(
            DriveComment.id == target_id
        )
        return (await db.execute(stmt)).scalar_one() > 0
    if target_type == "file":
        stmt = select(func.count()).select_from(Knowledge).where(
            and_(
                Knowledge.id == target_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        return (await db.execute(stmt)).scalar_one() > 0
    if target_type == "note":
        # 未来 PR 引入 drive_notes 表后, 在此处加查询
        return False
    return False


async def _check_target_read_authority(
    db: AsyncSession, target_type: str, target_id: int, user_id: int
) -> bool:
    """校验 user 对 target 的 read 权限

    Returns:
        True: 有 read 权限 (或 admin)
        False: 无 read 权限 (调用方抛 403)

    Notes:
        - 'comment': 走 file/folder 权限 (与 drive_comment_service 一致)
        - 'file':    走 folder 权限 (owner / folder permission read+)
        - 'note':    暂无 (未来 PR 引入)
    """
    from app.services.drive_permission_service import DrivePermissionService
    perm_svc = DrivePermissionService(db)

    if target_type == "comment":
        # comment → 拿 file_id/folder_id → 走 folder 权限
        stmt = select(DriveComment.file_id, DriveComment.folder_id).where(
            DriveComment.id == target_id
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            return False
        file_id, folder_id = row[0], row[1]
        if file_id is not None:
            # file → 拿 folder_id → 走 folder permission
            f_stmt = select(Knowledge.folder_id, Knowledge.created_by).where(
                Knowledge.id == file_id
            )
            f_row = (await db.execute(f_stmt)).first()
            if f_row is None:
                return False
            folder_id, owner_id = f_row[0], f_row[1]
            if owner_id == user_id:
                return True
            if folder_id is None:
                return False
            perm = await perm_svc.get_user_folder_permission(folder_id, user_id)
            return perm is not None
        if folder_id is not None:
            perm = await perm_svc.get_user_folder_permission(folder_id, user_id)
            return perm is not None
        return False

    if target_type == "file":
        stmt = select(Knowledge.folder_id, Knowledge.created_by).where(
            and_(
                Knowledge.id == target_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            return False
        folder_id, owner_id = row[0], row[1]
        if owner_id == user_id:
            return True
        if folder_id is None:
            return False
        perm = await perm_svc.get_user_folder_permission(folder_id, user_id)
        return perm is not None

    if target_type == "note":
        return False  # 未来 PR 引入

    return False


# ==========================================================================
# Service 类
# ==========================================================================


class DriveReactionService:
    """表情反应 CRUD + 聚合 + 权限"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 增 (幂等)
    # ==========================================================================

    async def add_reaction(
        self,
        *,
        target_type: str,
        target_id: int,
        member_id: int,
        emoji: str,
    ) -> Optional[DriveReaction]:
        """添加表情反应 (幂等)

        Args:
            target_type: 'comment' / 'file' / 'note'
            target_id: polymorphic target ID
            member_id: 反应者 (从 JWT 取)
            emoji: emoji 字面值 (必须在 ALLOWED_EMOJIS 白名单)

        Returns:
            DriveReaction: 新创建的反应
            None: 已存在相同反应 (UNIQUE 约束, 幂等)

        Raises:
            DriveReactionServiceError(400): emoji 不在白名单 / target_type 不支持
            DriveReactionServiceError(404): target 不存在
            DriveReactionServiceError(403): 无 read 权限
        """
        # 1. emoji 白名单校验
        if emoji not in ALLOWED_EMOJIS:
            raise DriveReactionServiceError(
                f"emoji '{emoji}' 不在白名单 ({len(ALLOWED_EMOJIS)} 个内置: 👍❤️🎉😂😮😢🔥💯✨🙏🤔👀)",
                status_code=400,
            )

        # 2. target_type 校验
        if target_type not in ("comment", "file", "note"):
            raise DriveReactionServiceError(
                f"target_type '{target_type}' 不支持 (必须是 'comment' / 'file' / 'note')",
                status_code=400,
            )

        # 3. target 存在性校验
        if not await _validate_target_exists(self.db, target_type, target_id):
            raise DriveReactionServiceError(
                f"Target {target_type}:{target_id} 不存在或不支持",
                status_code=404,
            )

        # 4. read 权限校验
        if not await _check_target_read_authority(self.db, target_type, target_id, member_id):
            raise DriveReactionServiceError(
                f"无权对 {target_type}:{target_id} 添加 reaction",
                status_code=403,
            )

        # 5. INSERT (UNIQUE 约束保证幂等 — 已存在返 None)
        reaction = DriveReaction(
            target_type=target_type,
            target_id=target_id,
            member_id=member_id,
            emoji=emoji,
        )
        self.db.add(reaction)
        try:
            await self.db.commit()
        except IntegrityError:
            # UNIQUE 约束触发 — 同一 user 同一 target 同一 emoji 已存在
            await self.db.rollback()
            logger.debug(
                f"[DriveReactionService.add_reaction] 幂等命中: "
                f"target={target_type}:{target_id} member={member_id} emoji={emoji}"
            )
            return None

        await self.db.refresh(reaction)

        logger.info(
            f"[DriveReactionService.add_reaction] id={reaction.id} "
            f"target={target_type}:{target_id} member={member_id} emoji={emoji}"
        )

        # 6. WS 推送 (best-effort, 不阻塞主流程)
        try:
            from app.services.drive_event_publisher import publish_reaction_added
            await publish_reaction_added(
                self.db,
                reaction_id=reaction.id,
                target_type=target_type,
                target_id=target_id,
                actor_id=member_id,
                emoji=emoji,
            )
        except Exception as e:
            logger.debug(
                f"[DriveReactionService] publish_reaction_added 失败 (非阻塞): {e!r}"
            )

        return reaction

    # ==========================================================================
    # 删 (按 id — 仅本人)
    # ==========================================================================

    async def remove_reaction_by_id(
        self,
        *,
        reaction_id: int,
        user_id: int,
    ) -> bool:
        """按 ID 删除 reaction (仅反应者本人)

        Args:
            reaction_id: DriveReaction.id
            user_id: 当前操作者 (从 JWT 取)

        Returns:
            True: 成功删除
            False: 不存在 / 已被删除

        Raises:
            DriveReactionServiceError(403): 非本人 (admin 不 override)
        """
        reaction = (await self.db.execute(
            select(DriveReaction).where(DriveReaction.id == reaction_id)
        )).scalar_one_or_none()
        if reaction is None:
            return False

        if reaction.member_id != user_id:
            raise DriveReactionServiceError(
                "仅本人可删除自己的 reaction",
                status_code=403,
            )

        await self.db.delete(reaction)
        await self.db.commit()

        logger.info(
            f"[DriveReactionService.remove_reaction_by_id] id={reaction_id} by user={user_id}"
        )
        return True

    # ==========================================================================
    # 聚合列表
    # ==========================================================================

    async def list_reactions(
        self,
        *,
        target_type: str,
        target_id: int,
    ) -> List[Dict]:
        """列 target 的全部 reactions (聚合)

        Args:
            target_type: 'comment' / 'file' / 'note'
            target_id: polymorphic target ID

        Returns:
            List[dict] 格式: [{emoji, count, members: [{id, name, avatar_url}]}, ...]
            按 emoji count desc 排序 (最热门在前)

        权限:
        - 调用方应已校验 read 权限 (service 入口 / API 层都校验)
        - 本函数不做权限校验 (假设 caller 已 OK)
        """
        stmt = (
            select(DriveReaction)
            .where(
                DriveReaction.target_type == target_type,
                DriveReaction.target_id == target_id,
            )
            .order_by(DriveReaction.created_at.asc())
        )
        reactions = list((await self.db.execute(stmt)).scalars().all())

        # 聚合: emoji → {count, members, my_member_ids}
        agg: Dict[str, Dict] = {}
        member_ids = set()
        for r in reactions:
            entry = agg.setdefault(r.emoji, {
                "emoji": r.emoji,
                "count": 0,
                "members": [],
                "my_member_ids": [],
            })
            entry["count"] += 1
            entry["my_member_ids"].append(r.member_id)
            member_ids.add(r.member_id)

        # 一次查询拿 member 概要 (避免 N+1)
        member_map: Dict[int, Member] = {}
        if member_ids:
            m_stmt = select(Member).where(Member.id.in_(member_ids))
            members = list((await self.db.execute(m_stmt)).scalars().all())
            member_map = {m.id: m for m in members}

        # 拼装结果 + 按 count desc 排序
        result: List[Dict] = []
        for entry in agg.values():
            member_summaries = []
            for mid in entry["my_member_ids"]:
                m = member_map.get(mid)
                if m is None:
                    member_summaries.append({
                        "id": mid,
                        "name": "[已注销用户]",
                        "avatar_url": None,
                    })
                else:
                    member_summaries.append({
                        "id": m.id,
                        "name": m.name,
                        "avatar_url": getattr(m, "avatar_url", None),
                    })
            entry["members"] = member_summaries
            result.append({
                "emoji": entry["emoji"],
                "count": entry["count"],
                "members": entry["members"],
            })
        result.sort(key=lambda x: (-x["count"], x["emoji"]))
        return result

    # ==========================================================================
    # 当前用户的 reactions (前端 toggle 状态)
    # ==========================================================================

    async def list_my_reactions(
        self,
        *,
        target_type: str,
        target_id: int,
        member_id: int,
    ) -> List[str]:
        """列当前用户对 target 已添加的 emoji 列表 (前端 toggle 状态)

        Returns:
            List[str] emoji 字面值列表 (无序)
        """
        stmt = select(DriveReaction.emoji).where(
            DriveReaction.target_type == target_type,
            DriveReaction.target_id == target_id,
            DriveReaction.member_id == member_id,
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows)


__all__ = [
    "DriveReactionService",
    "DriveReactionServiceError",
]