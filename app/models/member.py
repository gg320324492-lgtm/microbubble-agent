from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Text, ARRAY, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.types import HalfVector  # W-N-B 阶段 B.5: halfvec 量化


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
    # 2026-07-03 v2 PR6-P17: nullable=False (alembic 057_wechat_id_not_null 防 NULL 渗透)
    # 14/35 行原 NULL 已 backfill 为 '__NULL_BACKFILL_<id>__' 占位, 留给后续真实值填充
    wechat_id = Column(String(100), nullable=False)  # 企业微信 userid (NOT NULL)
    wechat_nickname = Column(String(100))  # 企业微信昵称
    wechat_remark = Column(String(100))  # 企业微信备注名
    # 2026-07-02 v2 PR6-P15: 大小写不敏感 UNIQUE INDEX (alembic 055_member_personal_wechat_id_ci_unique)
    # app/wechat/identity.py:79 resolve_by_wechat_id() 当前精确匹配, 但为防未来 lower() 匹配出现撞车
    # 与 PR6-P13/014 同模式, _IDENTIFIER_COLUMNS 白名单已加 personal_wechat_id
    personal_wechat_id = Column(String(100))  # 个人微信号
    wechat_mobile = Column(String(20))  # 绑定手机号
    # 2026-07-03 v2 PR6-P16: 大小写不敏感 UNIQUE INDEX (alembic 056_external_userid_ci)
    # app/wechat/identity.py:41 resolve_by_external_userid() 当前精确匹配, 但为防未来 lower() 匹配出现撞车
    # 与 PR6-P13/014/015 同模式, _IDENTIFIER_COLUMNS 白名单已加 external_userid (wm 开头通常大写)
    external_userid = Column(String(100))  # 微信互通外部用户ID（普通微信用户，wm开头）
    email = Column(String(100))
    phone = Column(String(20))
    avatar = Column(String(500))
    bio = Column(Text)  # 个人简介
    is_active = Column(Boolean, default=True)
    # 2026-09-05 角色扁平化 (alembic 132): 不再区分 admin/leader/member,
    # 全员等权, 本列仅作历史保留 (恒为 'member'), 不得用于任何权限判断。
    # 成员对外展示统一身份称谓, 由 grade 派生: app/core/member_identity.member_status
    role = Column(String(20), default="member")
    custom_instructions = Column(Text)  # 用户自定义指令
    notification_preferences = Column(JSON, nullable=True)  # 通知偏好（2026-06-15 v2）：
    # {"enabled": True, "digest_time": "11:00", "channels": ["wechat"],
    #  "snoozed_until": "2026-06-16T03:00:00Z"}

    # 声纹识别
    voice_embedding = Column(HalfVector(192))  # W-N-B 阶段 B.5: float32 -> float16. 3D-Speaker ERes2Net 192 维说话人嵌入
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

    # 自助重置密码恢复码 (2026-09-02, alembic 131):
    # 只存 SHA-256 哈希, 明文仅在生成响应里出现一次; 单次使用后置 NULL (需重新生成)
    recovery_code_hash = Column(String(255), nullable=True)
    recovery_code_generated_at = Column(DateTime, nullable=True)

    # 关系
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    created_tasks = relationship("Task", back_populates="creator", foreign_keys="Task.created_by")
    created_meetings = relationship("Meeting", back_populates="creator")
    created_projects = relationship("Project", back_populates="creator")

    def __repr__(self):
        return f"<Member(id={self.id}, name='{self.name}')>"
