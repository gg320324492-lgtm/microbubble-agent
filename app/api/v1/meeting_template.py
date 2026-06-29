"""会议模板 REST API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting_template import MeetingTemplate
from app.schemas.meeting_template import (
    TemplateCreate, TemplateUpdate, TemplateResponse, TemplateListResponse,
    BatchToggleActiveRequest, BatchDeleteRequest,
)
from app.services import meeting_template_service as svc

router = APIRouter(prefix="/meeting-templates", tags=["会议模板"])


@router.get("", response_model=TemplateListResponse)
async def list_meeting_templates(
    include_inactive: bool = False,
    search: Optional[str] = None,         # 按 name ILIKE 模糊匹配
    type: Optional[str] = None,           # 'builtin' | 'custom' | None(全部)
    status: Optional[str] = None,         # 'active' | 'inactive' | None(全部)
    page: int = 1,                        # 1-based 页码
    page_size: int = 20,                  # 每页条数
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v77 P2.6-G.2: 列模板支持 search/filter/pagination

    响应: TemplateListResponse {items, total, page, page_size}
    """
    items, total = await svc.list_templates(
        db,
        include_inactive=include_inactive,
        search=search,
        type_filter=type,
        status_filter=status,
        page=page,
        page_size=page_size,
    )
    return TemplateListResponse(
        items=[_to_response(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_meeting_template(
    payload: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    template = await svc.create_template(
        db, created_by=current_user.id, is_builtin=False, is_active=True,
        **payload.model_dump(),
    )
    return _to_response(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_meeting_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    template = await svc.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _to_response(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_meeting_template(
    template_id: int,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    template = await svc.update_template(db, template_id, **payload.model_dump(exclude_unset=True))
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在或不可修改")
    return _to_response(template)


@router.delete("/{template_id}", status_code=200)
async def delete_meeting_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    success = await svc.delete_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在或不可删除")
    return {"status": "deleted", "id": template_id}


@router.post("/{template_id}/clone", response_model=TemplateResponse, status_code=201)
async def clone_meeting_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v77 P2.6-F.5: 一键复制 builtin 为 custom 副本

    - 复制 source 全部非元字段 + 强制 is_builtin=False + name "(副本)" 后缀
    - cloned_from_id 记录复制追溯
    - 必须登录（已 require auth）
    - 404: source_id 不存在
    """
    clone = await svc.clone_template(
        db, source_id=template_id, current_user_id=current_user.id,
    )
    if not clone:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return _to_response(clone)


# v77 P2.6-G.2: 批量操作端点 (模板管理页 /admin/templates 桌面端批量管理用)


@router.post("/batch-toggle-active", response_model=dict)
async def batch_toggle_active_endpoint(
    payload: BatchToggleActiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v77 P2.6-G.2: 批量启用/禁用模板

    - builtin 模板允许 toggle (与单条 update_template 一致)
    - 响应: {updated: N, is_active: bool}
    """
    count = await svc.batch_toggle_active(db, payload.ids, payload.is_active)
    return {"updated": count, "is_active": payload.is_active}


@router.post("/batch-delete", response_model=dict)
async def batch_delete_endpoint(
    payload: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v77 P2.6-G.2: 批量删除模板 (内置 builtin 自动跳过)

    - builtin 模板不可删 (业务规则) - service 层自动跳过
    - 响应: {deleted: N, skipped_builtin: [id1, id2, ...]}
    - 前端 toast 提示"已删除 N 个, M 个内置模板已跳过"
    """
    deleted, skipped_builtin = await svc.batch_delete_templates(db, payload.ids)
    return {"deleted": deleted, "skipped_builtin": skipped_builtin}


def _to_response(t: MeetingTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=t.id,
        name=t.name,
        title_template=t.title_template,
        description=t.description,
        agenda=t.agenda,
        default_duration_minutes=t.default_duration_minutes,
        default_participant_ids=t.default_participant_ids,
        default_location=t.default_location,
        is_builtin=t.is_builtin,
        is_active=t.is_active,
        created_by=t.created_by,
        cloned_from_id=t.cloned_from_id,
        # v77 P2.6-G.2: 暴露时间戳 (TimestampMixin 提供)
        created_at=t.created_at,
        updated_at=t.updated_at,
    )
