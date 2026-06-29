"""会议模板 Pydantic Schemas (v77 P2.6-G.2 抽出)

原本内联在 app/api/v1/meeting_template.py，抽出便于:
1. 共享 list/detail 响应模型
2. 暴露 created_at/updated_at 时间戳给前端
3. 支持分页响应 (TemplateListResponse)
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TemplateBase(BaseModel):
    """基础字段 (Create/Update 共享)"""
    name: str
    title_template: Optional[str] = None
    description: Optional[str] = None
    agenda: Optional[List[str]] = None
    default_duration_minutes: Optional[int] = 60
    default_participant_ids: Optional[List[int]] = None
    default_location: Optional[str] = None


class TemplateCreate(TemplateBase):
    """新建 custom 模板"""
    pass


class TemplateUpdate(BaseModel):
    """更新模板 (所有字段 Optional)

    builtin 保护规则在 service 层 enforce (update_template 拒绝改 name/is_builtin)
    """
    name: Optional[str] = None
    title_template: Optional[str] = None
    description: Optional[str] = None
    agenda: Optional[List[str]] = None
    default_duration_minutes: Optional[int] = None
    default_participant_ids: Optional[List[int]] = None
    default_location: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(TemplateBase):
    """模板响应 (包含全部字段)"""
    id: int
    is_builtin: bool
    is_active: bool
    created_by: Optional[int] = None
    cloned_from_id: Optional[int] = None  # v77 P2.6-F.5 复制追溯 (NULL=原始 builtin)
    created_at: Optional[datetime] = None  # v77 P2.6-G.2 新增暴露时间戳
    updated_at: Optional[datetime] = None  # v77 P2.6-G.2 新增暴露时间戳


class TemplateListResponse(BaseModel):
    """分页响应 (v77 P2.6-G.2)"""
    items: List[TemplateResponse]
    total: int
    page: int
    page_size: int


# v77 P2.6-G.2: 批量操作请求模型


class BatchToggleActiveRequest(BaseModel):
    """批量启用/禁用模板请求体"""
    ids: List[int]
    is_active: bool


class BatchDeleteRequest(BaseModel):
    """批量删除模板请求体"""
    ids: List[int]
