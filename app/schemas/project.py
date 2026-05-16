from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class ProjectBase(BaseModel):
    """项目基础信息"""
    name: str
    description: Optional[str] = None
    research_area: Optional[str] = None


class ProjectCreate(ProjectBase):
    """创建项目"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    members: Optional[List[int]] = None


class ProjectUpdate(BaseModel):
    """更新项目"""
    name: Optional[str] = None
    description: Optional[str] = None
    research_area: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    members: Optional[List[int]] = None


class ProjectResponse(ProjectBase):
    """项目响应"""
    id: int
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_by: Optional[int] = None
    members: Optional[List[int]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectList(BaseModel):
    """项目列表"""
    items: List[ProjectResponse]
    total: int


class MilestoneBase(BaseModel):
    """里程碑基础信息"""
    name: str
    description: Optional[str] = None
    due_date: Optional[date] = None


class MilestoneCreate(MilestoneBase):
    """创建里程碑"""
    project_id: int


class MilestoneResponse(MilestoneBase):
    """里程碑响应"""
    id: int
    project_id: int
    status: str
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
