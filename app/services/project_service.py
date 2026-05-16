from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.models.project import Project, Milestone


class ProjectService:
    """项目服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_project(self, project_id: int) -> Optional[Project]:
        """获取单个项目"""
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.milestones))
            .where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_projects(self, status: Optional[str] = None) -> List[Project]:
        """查询项目列表"""
        query = select(Project)
        if status:
            query = query.where(Project.status == status)
        query = query.order_by(Project.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        research_area: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        member_ids: Optional[List[int]] = None,
        created_by: Optional[int] = None
    ) -> Project:
        """创建项目"""
        project = Project(
            name=name,
            description=description,
            research_area=research_area,
            start_date=start_date,
            end_date=end_date,
            members=member_ids,
            created_by=created_by,
            status="active"
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def update_project(self, project_id: int, **kwargs) -> Optional[Project]:
        """更新项目"""
        project = await self.get_project(project_id)
        if not project:
            return None

        for key, value in kwargs.items():
            if hasattr(project, key) and value is not None:
                setattr(project, key, value)

        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete_project(self, project_id: int) -> bool:
        """删除项目"""
        project = await self.get_project(project_id)
        if not project:
            return False

        await self.db.delete(project)
        await self.db.commit()
        return True

    async def get_milestones(self, project_id: int) -> List[Milestone]:
        """获取项目里程碑"""
        result = await self.db.execute(
            select(Milestone)
            .where(Milestone.project_id == project_id)
            .order_by(Milestone.due_date)
        )
        return result.scalars().all()

    async def create_milestone(
        self,
        project_id: int,
        name: str,
        description: Optional[str] = None,
        due_date: Optional[date] = None
    ) -> Milestone:
        """创建里程碑"""
        milestone = Milestone(
            project_id=project_id,
            name=name,
            description=description,
            due_date=due_date,
            status="pending"
        )
        self.db.add(milestone)
        await self.db.commit()
        await self.db.refresh(milestone)
        return milestone
