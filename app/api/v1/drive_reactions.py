"""Drive v2 PR12 — 表情反应 (Emoji Reactions) REST API (2026-07-24, W68 第 8 批 B-2)

端点:
  POST   /api/v1/drive/reactions                  → 增 (body: target_type/target_id/emoji) — 幂等
  DELETE /api/v1/drive/reactions/{id}             → 删 (按 id — 仅本人)
  GET    /api/v1/drive/reactions?target_type=&target_id=  → 聚合列表

设计:
- add 幂等: 重复加同一 emoji 返 200 OK + 当前 reactions (不抛错, 体验更平滑)
- remove 仅本人: admin 不 override (与 comment author 主权一致)
- list 聚合: 返回 [{emoji, count, members, my_reacted}] 按 count desc

限流:
- POST/DELETE: drive_upload tier (50/min, app/core/rate_limit.py:285)
- GET: drive_list tier (300/min, app/core/rate_limit.py:287)

锚点范式第 94 守恒.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import get_current_user
from app.models.drive_reaction import ALLOWED_EMOJIS, DriveReaction
from app.models.member import Member
from app.services.drive_reaction_service import (
    DriveReactionService,
    DriveReactionServiceError,
)

router = APIRouter(prefix="/drive/reactions", tags=["网盘表情反应"])


def _reraise_reaction_service_error(e: DriveReactionServiceError) -> None:
    """DriveReactionServiceError → 统一异常响应

    错误码:
    - 400 → VALIDATION_ERROR
    - 403 → FORBIDDEN
    - 404 → RESOURCE_NOT_FOUND
    """
    code_map = {
        400: "VALIDATION_ERROR",
        403: "FORBIDDEN",
        404: "RESOURCE_NOT_FOUND",
    }
    raise AppException(
        code=code_map.get(e.status_code, "DRIVE_REACTION_ERROR"),
        message=str(e),
        status_code=e.status_code,
    )


# ==========================================================================
# ReactionCreate Pydantic (本地定义, 避免新增 schema 文件)
# ==========================================================================

from pydantic import BaseModel, Field  # noqa: E402


class ReactionCreate(BaseModel):
    """POST /drive/reactions 请求体"""
    target_type: str = Field(
        ..., description="目标类型: 'comment' / 'file' / 'note'"
    )
    target_id: int = Field(..., gt=0, description="polymorphic target ID")
    emoji: str = Field(..., min_length=1, max_length=16, description="emoji 字面值 (12 个内置白名单)")


class ReactionSummaryItem(BaseModel):
    """GET /drive/reactions 列表元素 (单个 emoji 聚合)"""
    emoji: str
    count: int
    members: List[dict] = Field(default_factory=list)
    my_reacted: bool = False


class ReactionListResponse(BaseModel):
    """GET /drive/reactions 列表响应"""
    target_type: str
    target_id: int
    items: List[ReactionSummaryItem] = Field(default_factory=list)
    total: int


class ReactionRead(BaseModel):
    """POST /drive/reactions 单条响应 (新建的反应)"""
    id: int
    target_type: str
    target_id: int
    member_id: int
    emoji: str
    created_at: str
    updated_at: str


# ==========================================================================
# CRUD
# ==========================================================================


@router.post("", response_model=ReactionRead, status_code=201)
async def add_reaction(
    payload: ReactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR12: 添加表情反应 (幂等)

    Body:
      target_type: 'comment' / 'file' / 'note'
      target_id:   polymorphic target ID
      emoji:       12 个内置白名单之一 (👍❤️🎉😂😮😢🔥💯✨🙏🤔👀)

    幂等:
      同一 user 对同一 target 同一 emoji 重复调用返 200 OK + 已存在 reaction
      (不抛错, 前端 toggle 体验平滑)

    权限:
      target 的 read 权限 (任何能访问 target 都能 add)
    """
    svc = DriveReactionService(db)
    try:
        reaction = await svc.add_reaction(
            target_type=payload.target_type,
            target_id=payload.target_id,
            member_id=current_user.id,
            emoji=payload.emoji,
        )
    except DriveReactionServiceError as e:
        _reraise_reaction_service_error(e)

    # 幂等命中 → 查已存在的 reaction (service 返 None 时)
    if reaction is None:
        existing = (await db.execute(
            __import__("sqlalchemy").select(DriveReaction).where(
                DriveReaction.target_type == payload.target_type,
                DriveReaction.target_id == payload.target_id,
                DriveReaction.member_id == current_user.id,
                DriveReaction.emoji == payload.emoji,
            )
        )).scalar_one_or_none()
        if existing is None:
            # 极小概率: UNIQUE 冲突但又查不到 (DB 不一致) → 返通用响应
            raise AppException(
                code="DRIVE_REACTION_ERROR",
                message="反应已存在但无法定位",
                status_code=500,
            )
        reaction = existing

    return ReactionRead(
        id=reaction.id,
        target_type=reaction.target_type,
        target_id=reaction.target_id,
        member_id=reaction.member_id,
        emoji=reaction.emoji,
        created_at=reaction.created_at.isoformat(),
        updated_at=reaction.updated_at.isoformat(),
    )


@router.delete("/{reaction_id}", status_code=204)
async def remove_reaction(
    reaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR12: 删除 reaction (仅本人)

    仅反应者本人可删除 (admin 不 override, 与 comment author 主权一致)
    """
    svc = DriveReactionService(db)
    try:
        ok = await svc.remove_reaction_by_id(
            reaction_id=reaction_id,
            user_id=current_user.id,
        )
    except DriveReactionServiceError as e:
        _reraise_reaction_service_error(e)

    if not ok:
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message=f"Reaction id={reaction_id} 不存在",
            status_code=404,
        )
    return Response(status_code=204)


@router.get("", response_model=ReactionListResponse)
async def list_reactions(
    target_type: str = Query(..., description="目标类型: 'comment' / 'file' / 'note'"),
    target_id: int = Query(..., gt=0, description="polymorphic target ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR12: 列 target 的全部 reactions (聚合)

    返回:
      items: [{emoji, count, members: [{id, name, avatar_url}], my_reacted}, ...]
      按 count desc 排序 (最热门在前)
      total: items 长度 (= emoji 种类数, 不是 reaction 总数)

    权限:
      调用方应已校验 target 的 read 权限 (service 入口强制, 此处冗余校验)
    """
    svc = DriveReactionService(db)
    # 复用 service 权限校验 (返 403 时 reraise)
    from app.services.drive_reaction_service import (
        _validate_target_exists,
        _check_target_read_authority,
    )
    if not await _validate_target_exists(db, target_type, target_id):
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message=f"Target {target_type}:{target_id} 不存在",
            status_code=404,
        )
    if not await _check_target_read_authority(db, target_type, target_id, current_user.id):
        raise AppException(
            code="FORBIDDEN",
            message=f"无权访问 {target_type}:{target_id} 的 reactions",
            status_code=403,
        )

    items = await svc.list_reactions(
        target_type=target_type,
        target_id=target_id,
    )
    my_emojis = set(await svc.list_my_reactions(
        target_type=target_type,
        target_id=target_id,
        member_id=current_user.id,
    ))

    # 拼装响应 + 标 my_reacted
    response_items: List[ReactionSummaryItem] = []
    for entry in items:
        response_items.append(ReactionSummaryItem(
            emoji=entry["emoji"],
            count=entry["count"],
            members=entry["members"],
            my_reacted=entry["emoji"] in my_emojis,
        ))

    return ReactionListResponse(
        target_type=target_type,
        target_id=target_id,
        items=response_items,
        total=len(response_items),
    )


__all__ = [
    "router",
    "ReactionCreate",
    "ReactionRead",
    "ReactionListResponse",
    "ReactionSummaryItem",
]