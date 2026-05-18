from sqlalchemy import Column, Integer, String, Boolean, Text, ARRAY
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Member(Base, TimestampMixin):
    """成员模型"""
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)  # 登录用户名
    password_hash = Column(String(200))  # 密码哈希
    name = Column(String(50), nullable=False)
    grade = Column(String(20))  # 研一/研二/博一等
    research_area = Column(String(100))  # 研究方向
    skills = Column(ARRAY(String))  # 技能列表
    wechat_id = Column(String(100))  # 企业微信 userid
    wechat_nickname = Column(String(100))  # 企业微信昵称
    wechat_remark = Column(String(100))  # 企业微信备注名
    personal_wechat_id = Column(String(100))  # 个人微信号
    wechat_mobile = Column(String(20))  # 绑定手机号
    external_userid = Column(String(100))  # 微信互通外部用户ID（普通微信用户，wm开头）
    email = Column(String(100))
    phone = Column(String(20))
    avatar = Column(String(500))
    bio = Column(Text)  # 个人简介
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="member")  # admin/leader/member

    # 关系
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    created_tasks = relationship("Task", back_populates="creator", foreign_keys="Task.created_by")
    created_meetings = relationship("Meeting", back_populates="creator")
    created_projects = relationship("Project", back_populates="creator")

    def __repr__(self):
        return f"<Member(id={self.id}, name='{self.name}')>"
