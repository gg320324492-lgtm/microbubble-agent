from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TaskBase(BaseModel):
    """任务基础信息"""
    title: str
    description: Optional[str] = None
    priority: str = "medium"


class TaskCreate(TaskBase):
    """创建任务"""
    assignee_id: Optional[int] = None
    project_id: Optional[int] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    dependencies: Optional[List[int]] = None


class TaskUpdate(BaseModel):
    """更新任务"""
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    project_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    progress: Optional[int] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None


class TaskResponse(TaskBase):
    """任务响应"""
    id: int
    assignee_id: Optional[int] = None
    project_id: Optional[int] = None
    created_by: Optional[int] = None
    status: str
    priority: str
    progress: int
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    source: Optional[str] = None
    meeting_id: Optional[int] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskList(BaseModel):
    """任务列表"""
    items: List[TaskResponse]
    total: int


class TaskStats(BaseModel):
    """任务统计"""
    total: int
    todo: int
    in_progress: int
    blocked: int
    review: int
    done: int
    cancelled: int
    overdue: int
