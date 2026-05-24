from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, ARRAY
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base
from app.models.base import TimestampMixin


class TaskStatus(str, enum.Enum):
    """任务状态"""
    TODO = "todo"               # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    BLOCKED = "blocked"         # 阻塞
    REVIEW = "review"           # 待审核
    DONE = "done"               # 已完成
    CANCELLED = "cancelled"     # 已取消


class TaskPriority(str, enum.Enum):
    """任务优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Task(Base, TimestampMixin):
    """任务模型"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)

    # 关联信息
    assignee_id = Column(Integer, ForeignKey("members.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    created_by = Column(Integer, ForeignKey("members.id"))

    # 状态信息
    status = Column(String(20), default=TaskStatus.TODO.value)
    priority = Column(String(10), default=TaskPriority.MEDIUM.value)
    progress = Column(Integer, default=0)  # 0-100

    # 时间信息
    due_date = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # 来源信息
    source = Column(String(50))  # manual/meeting/ai
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)

    # 标签
    tags = Column(ARRAY(String))

    # 软删除
    deleted_at = Column(DateTime, nullable=True)

    # 关系
    assignee = relationship("Member", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    creator = relationship("Member", back_populates="created_tasks", foreign_keys=[created_by])
    project = relationship("Project", back_populates="tasks")
    reminders = relationship("Reminder", back_populates="task", cascade="all, delete-orphan")

    # 依赖关系
    dependencies = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.task_id",
        back_populates="task"
    )
    dependents = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.depends_on_id",
        back_populates="depends_on"
    )

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}')>"


class TaskDependency(Base):
    """任务依赖关系"""
    __tablename__ = "task_dependencies"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    depends_on_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)

    task = relationship("Task", foreign_keys=[task_id], back_populates="dependencies")
    depends_on = relationship("Task", foreign_keys=[depends_on_id], back_populates="dependents")
