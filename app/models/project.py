from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Project(Base, TimestampMixin):
    """项目模型"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    research_area = Column(String(100))  # 研究方向

    # 状态
    status = Column(String(20), default="active")  # active/paused/completed/archived

    # 时间
    start_date = Column(Date)
    end_date = Column(Date)

    # 成员
    created_by = Column(Integer, ForeignKey("members.id"))
    members = Column(ARRAY(Integer))  # 成员ID列表

    # 关系
    creator = relationship("Member", back_populates="created_projects")
    tasks = relationship("Task", back_populates="project")
    milestones = relationship("Milestone", back_populates="project")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}')>"


class Milestone(Base):
    """里程碑"""
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # 时间
    due_date = Column(Date)
    completed_at = Column(DateTime)

    # 状态
    status = Column(String(20), default="pending")  # pending/completed/overdue

    # 关系
    project = relationship("Project", back_populates="milestones")

    def __repr__(self):
        return f"<Milestone(id={self.id}, name='{self.name}')>"
