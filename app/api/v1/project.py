from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.models.project import Project, Milestone
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectList,
    MilestoneCreate, MilestoneResponse
)

router = APIRouter()


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建项目"""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        research_area=project_data.research_area,
        start_date=project_data.start_date,
        end_date=project_data.end_date,
        members=project_data.members,
        status="active"
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects", response_model=ProjectList)
async def list_projects(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """查询项目列表"""
    query = select(Project)

    if status:
        query = query.where(Project.status == status)

    query = query.order_by(Project.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    projects = result.scalars().all()

    return ProjectList(items=projects, total=len(projects))


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取项目详情"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.post("/projects/{project_id}/milestones", response_model=MilestoneResponse, status_code=201)
async def create_milestone(
    project_id: int,
    milestone_data: MilestoneCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建里程碑"""
    milestone = Milestone(
        project_id=project_id,
        name=milestone_data.name,
        description=milestone_data.description,
        due_date=milestone_data.due_date,
        status="pending"
    )

    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return milestone


@router.get("/projects/{project_id}/milestones")
async def list_milestones(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取项目里程碑"""
    result = await db.execute(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .order_by(Milestone.due_date)
    )
    milestones = result.scalars().all()
    return milestones
