from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Text, ARRAY, DateTime, JSON
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base
from app.models.base import TimestampMixin


class Member(Base, TimestampMixin):
    """成员模型"""
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-07-02 v2 PR6-P13: 大小写不敏感 UNIQUE INDEX (alembic 053_member_username_ci_unique)
    # comment_service 解析 @ 时用 username.lower() → 防 "Alice" vs "alice" 歧义
    username = Column(String(50), index=False)  # 登录用户名
    password_hash = Column(String(200))  # 密码哈希
    name = Column(String(50), nullable=False)
    grade = Column(String(20))  # 研一/研二/博一等
    research_area = Column(String(100))  # 研究方向
    skills = Column(ARRAY(String))  # 技能列表
    # 2026-07-02 v2 PR6-P14: 大小写不敏感 UNIQUE INDEX (alembic 054_member_wechat_id_ci_unique)
    # comment_service mention 解析用 wechat_id.lower() (3 路匹配优先) → 防 "WangTianZhi" vs "wangtianzhi" 歧义
    wechat_id = Column(String(100))  # 企业微信 userid
    wechat_nickname = Column(String(100))  # 企业微信昵称
    wechat_remark = Column(String(100))  # 企业微信备注名
    # 2026-07-02 v2 PR6-P15: 大小写不敏感 UNIQUE INDEX (alembic 055_member_personal_wechat_id_ci_unique)
    # app/wechat/identity.py:79 resolve_by_wechat_id() 当前精确匹配, 但为防未来 lower() 匹配出现撞车
    # 与 PR6-P13/014 同模式, _IDENTIFIER_COLUMNS 白名单已加 personal_wechat_id
    personal_wechat_id = Column(String(100))  # 个人微信号
    wechat_mobile = Column(String(20))  # 绑定手机号
    external_userid = Column(String(100))  # 微信互通外部用户ID（普通微信用户，wm开头）
    email = Column(String(100))
    phone = Column(String(20))
    avatar = Column(String(500))
    bio = Column(Text)  # 个人简介
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="member")  # admin/leader/member
    custom_instructions = Column(Text)  # 用户自定义指令
    notification_preferences = Column(JSON, nullable=True)  # 通知偏好（2026-06-15 v2）：
    # {"enabled": True, "digest_time": "11:00", "channels": ["wechat"],
    #  "snoozed_until": "2026-06-16T03:00:00Z"}

    # 声纹识别
    voice_embedding = Column(Vector(192))  # 3D-Speaker ERes2Net 192 维说话人嵌入
    voice_enrolled_at = Column(DateTime)  # 声纹录入时间
    voice_sample_count = Column(Integer, default=0)  # 采样次数

    # 声纹确认 (2026-06-28 增量 Cross-Anchor 策略):
    # voice_confirmed_at IS NOT NULL = anchor (永不再修改 embedding)
    voice_confirmed_at = Column(DateTime(timezone=True), nullable=True)  # 用户确认时间
    voice_confirmed_by = Column(String(50), nullable=True)  # 确认者 (username 或 "user")
    voice_confirmed_meeting_id = Column(Integer, nullable=True)  # 触发的会议 ID (audit)

    # ==================== v2 PR5 网盘配额 2026-07-01 ====================
    # drive_quota_bytes: 总配额 (默认 10GB); admin 可单独调
    # drive_used_bytes: 已用字节数 (sum of file_size WHERE storage_mode='drive' AND deleted_at IS NULL)
    # drive_quota_updated_at: drive_used_bytes 重算时间 (Celery hourly 重算)
    drive_quota_bytes = Column(BigInteger, nullable=False, server_default="10737418240")  # 10 GB
    drive_used_bytes = Column(BigInteger, nullable=False, server_default="0")
    drive_quota_updated_at = Column(DateTime, nullable=True)
    # ==================== /v2 PR5 ====================

    # 关系
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    created_tasks = relationship("Task", back_populates="creator", foreign_keys="Task.created_by")
    created_meetings = relationship("Meeting", back_populates="creator")
    created_projects = relationship("Project", back_populates="creator")

    def __repr__(self):
        return f"<Member(id={self.id}, name='{self.name}')>"
