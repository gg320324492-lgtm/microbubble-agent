"""会议模板 REST API"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting_template import MeetingTemplate
from app.services import meeting_template_service as svc

router = APIRouter(prefix="/meeting-templates", tags=["会议模板"])


class TemplateCreate(BaseModel):
    name: str
    title_template: Optional[str] = None
    description: Optional[str] = None
    agenda: Optional[List[str]] = None
    default_duration_minutes: Optional[int] = 60
    default_participant_ids: Optional[List[int]] = None
    default_location: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    title_template: Optional[str] = None
    description: Optional[str] = None
    agenda: Optional[List[str]] = None
    default_duration_minutes: Optional[int] = None
    default_participant_ids: Optional[List[int]] = None
    default_location: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    title_template: Optional[str]
    description: Optional[str]
    agenda: Optional[List[str]]
    default_duration_minutes: Optional[int]
    default_participant_ids: Optional[List[int]]
    default_location: Optional[str]
    is_builtin: bool
    is_active: bool
    created_by: Optional[int] = None
    cloned_from_id: Optional[int] = None  # v77 P2.6-F.5: 复制追溯 (NULL=原始 builtin)


@router.get("", response_model=List[TemplateResponse])
async def list_meeting_templates(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    templates = await svc.list_templates(db, include_inactive=include_inactive)
    return [_to_response(t) for t in templates]


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
    )
