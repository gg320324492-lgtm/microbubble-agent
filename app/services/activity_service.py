"""activity_service — v2 PR6 活动动态流服务

职责:
1. log(): 记录活动 (drive 增删改事件)
2. feed(): 拉取动态流 (cursor 分页, 按 created_at desc)
3. parse_metadata(): 序列化/反序列化 JSONB metadata

Action 枚举:
- upload / rename / move / delete / restore / share / version_restore
- comment / mention / star / unstar

Target 类型:
- file / folder / comment

设计:
- target_name 冗余存: 目标被删后仍能显示
- metadata JSONB 存 action 特定信息:
  - rename: {old_name, new_name}
  - move: {from_folder_id, to_folder_id}
  - share: {token, expires_at}
  - comment: {comment_id, content_preview}
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import ActivityEvent
from app.models.member import Member

logger = logging.getLogger(__name__)

# 合法 action 白名单 (防止脏数据)
VALID_ACTIONS = frozenset({
    "upload", "rename", "move", "delete", "restore", "share",
    "version_restore", "comment", "mention", "star", "unstar",
})

VALID_TARGET_TYPES = frozenset({"file", "folder", "comment"})


class ActivityService:
    """v2 PR6: activity_events CRUD + feed 查询"""

    @staticmethod
    async def log(
        db: AsyncSession,
        *,
        actor_id: Optional[int],
        action: str,
        target_type: str,
        target_id: Optional[int] = None,
        target_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        """记录一条活动

        Args:
            actor_id: 触发者 user_id (None = 系统)
            action: upload|rename|move|delete|restore|share|...
            target_type: file|folder|comment
            target_id: 目标 id (None = 创建前无法预知, OK)
            target_name: 目标显示名 (冗余)
            metadata: action 特定的额外信息 dict

        Returns:
            ActivityEvent 实例 (含 id + created_at)

        Note:
            - 不抛错 (best-effort, 失败只 log warn)
            - 不 commit (调用方已有自己的事务, 这里只是 add)
        """
        if action not in VALID_ACTIONS:
            logger.warning(f"[Activity] 非法 action: {action}, 跳过")
            return None
        if target_type not in VALID_TARGET_TYPES:
            logger.warning(f"[Activity] 非法 target_type: {target_type}, 跳过")
            return None

        try:
            evt = ActivityEvent(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
                meta_data=metadata or {},
            )
            db.add(evt)
            # 不 commit: 留给调用方 (drive_service.create_file 等)
            logger.debug(
                f"[Activity] log actor={actor_id} action={action} "
                f"target={target_type}:{target_id}"
            )
            return evt
        except Exception as e:
            logger.error(f"[Activity] log 失败: {e}", exc_info=True)
            return None

    @staticmethod
    async def feed(
        db: AsyncSession,
        *,
        actor_ids: Optional[List[int]] = None,
        target_types: Optional[List[str]] = None,
        actions: Optional[List[str]] = None,
        limit: int = 50,
        before_id: Optional[int] = None,
    ) -> List[ActivityEvent]:
        """拉取动态流 (cursor 分页: before_id 之前更早的 N 条)

        Args:
            actor_ids: 限定 actor (例如 "我关注的人", 默认 None = 全部)
            target_types: 限定 target 类型 (None = 全部)
            actions: 限定 action (None = 全部)
            limit: 上限 (默认 50)
            before_id: cursor (id < before_id 之前更早的事件)
        """
        stmt = select(ActivityEvent)

        conditions = []
        if actor_ids is not None:
            conditions.append(ActivityEvent.actor_id.in_(actor_ids))
        if target_types is not None:
            conditions.append(ActivityEvent.target_type.in_(target_types))
        if actions is not None:
            conditions.append(ActivityEvent.action.in_(actions))
        if before_id is not None:
            conditions.append(ActivityEvent.id < before_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(ActivityEvent.created_at), desc(ActivityEvent.id)).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def feed_for_target(
        db: AsyncSession,
        *,
        target_type: str,
        target_id: int,
        limit: int = 30,
    ) -> List[ActivityEvent]:
        """某 target 的活动历史 (例如某文件的所有 rename 记录)"""
        stmt = (
            select(ActivityEvent)
            .where(and_(
                ActivityEvent.target_type == target_type,
                ActivityEvent.target_id == target_id,
            ))
            .order_by(desc(ActivityEvent.created_at))
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    def to_dict(evt: ActivityEvent, actor_name: Optional[str] = None) -> Dict[str, Any]:
        """活动 → 前端 dict (含 actor_name 冗余)

        Args:
            evt: ActivityEvent ORM 实例
            actor_name: actor 显示名 (避免 N+1, caller 批量查)
        """
        meta = evt.meta_data or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        return {
            "id": evt.id,
            "actor_id": evt.actor_id,
            "actor_name": actor_name,
            "action": evt.action,
            "target_type": evt.target_type,
            "target_id": evt.target_id,
            "target_name": evt.target_name,
            "metadata": meta,
            "created_at": evt.created_at.isoformat() if evt.created_at else None,
        }


# 全局单例
activity_service = ActivityService()