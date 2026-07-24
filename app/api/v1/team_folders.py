"""Drive v2 PR18 — Team Folder REST API (2026-07-24, W68 第 14 批 B-2)

4 个端点:
  POST   /api/v1/team-folders                    → 创建团队共享盘
  POST   /api/v1/team-folders/{id}/members       → 邀请成员 (写 audit share action)
  DELETE /api/v1/team-folders/{id}/members/{user_id} → 移除成员 (写 audit delete action)
  GET    /api/v1/team-folders/{id}/audit         → 查审计日志 (4 维过滤 + 分页)

权限模型:
- 仅 owner 可邀请 / 移除成员 (本期简化, 后续 PR 加 admin 角色)
- 任何登录用户可见自己的 team folder (本期不实现跨用户共享, 仅 owner 视角)

CLAUDE.md 2026-07-24 v78 audit_log 模式:
- 所有写操作必写 audit (4 维: actor_id + action + target_type + target_id)
- GET /audit 必须支持 4 维过滤
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.security import get_current_user
from app.models.member import Member
from app.schemas.team_folder import (
    TeamFolderAddMember,
    TeamFolderAuditLogListResponse,
    TeamFolderCreate,
    TeamFolderResponse,
)
from app.services.team_folder_service import (
    AuditAction,
    AuditTarget,
    TeamFolderService,
    TeamFolderServiceError,
)

router = APIRouter(prefix="/team-folders", tags=["团队共享盘"])


def _reraise_service_error(e: TeamFolderServiceError) -> None:
    """TeamFolderServiceError → 统一 AppException 格式 (CLAUDE.md 752 行)"""
    msg = str(e)
    if e.status_code == 404:
        raise NotFoundException(resource="TeamFolder") from e
    if e.status_code == 403:
        raise ForbiddenException(message=msg) from e
    raise ValidationException(message=msg) from e


# ============================================================
# 端点 1: POST /team-folders — 创建团队共享盘
# ============================================================


@router.post(
    "",
    response_model=TeamFolderResponse,
    status_code=201,
    summary="创建团队共享盘",
)
async def create_team_folder_endpoint(
    payload: TeamFolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """创建团队共享盘 (自动 write + share audit)"""
    try:
        team_folder = await TeamFolderService.create_team_folder(
            db,
            name=payload.name,
            owner_id=current_user.id,
            initial_member_ids=payload.initial_member_ids,
            visibility=payload.visibility,
        )
        return team_folder
    except TeamFolderServiceError as e:
        _reraise_service_error(e)


# ============================================================
# 端点 2: POST /team-folders/{id}/members — 邀请成员
# ============================================================


@router.post(
    "/{team_folder_id}/members",
    response_model=TeamFolderResponse,
    summary="添加成员到团队共享盘",
)
async def add_member_endpoint(
    team_folder_id: int,
    payload: TeamFolderAddMember,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """邀请成员 (仅 owner 可操作, 自动 write + share audit)"""
    try:
        team_folder = await TeamFolderService.add_member(
            db,
            team_folder_id=team_folder_id,
            actor_id=current_user.id,
            target_user_id=payload.target_user_id,
            permission=payload.permission,
        )
        return team_folder
    except TeamFolderServiceError as e:
        _reraise_service_error(e)


# ============================================================
# 端点 3: DELETE /team-folders/{id}/members/{user_id} — 移除成员
# ============================================================


@router.delete(
    "/{team_folder_id}/members/{user_id}",
    summary="移除团队共享盘成员",
)
async def remove_member_endpoint(
    team_folder_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """移除成员 (仅 owner 可操作, 自动 delete audit)"""
    try:
        await TeamFolderService.remove_member(
            db,
            team_folder_id=team_folder_id,
            actor_id=current_user.id,
            target_user_id=user_id,
        )
        return {"ok": True, "team_folder_id": team_folder_id, "removed_user_id": user_id}
    except TeamFolderServiceError as e:
        _reraise_service_error(e)


# ============================================================
# 端点 4: GET /team-folders/{id}/audit — 查审计日志 (4 维过滤)
# ============================================================


@router.get(
    "/{team_folder_id}/audit",
    response_model=TeamFolderAuditLogListResponse,
    summary="查询团队共享盘审计日志 (4 维过滤)",
)
async def list_audit_endpoint(
    team_folder_id: int,
    actor_id: Optional[int] = Query(None, description="按 actor 过滤 (who)"),
    action: Optional[str] = Query(
        None,
        description="过滤 action: read / write / delete / share / restore",
    ),
    target_type: Optional[str] = Query(
        None,
        description="过滤 target_type: folder / file / member / permission",
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """4 维度审计查询: actor_id (who) + action (what) + target_type (on_what) + 分页 (when)"""
    try:
        items, total = await TeamFolderService.list_audit(
            db,
            team_folder_id=team_folder_id,
            page=page,
            page_size=page_size,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
        )
        return TeamFolderAuditLogListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except TeamFolderServiceError as e:
        _reraise_service_error(e)
