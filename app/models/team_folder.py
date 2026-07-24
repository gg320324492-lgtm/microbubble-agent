"""Drive v2 PR18 — 团队共享盘 (Team Folder) 模型 (2026-07-24, W68 第 14 批 B-2)

设计:
- TeamFolder 与 Folder (drive v2 PR2) 是不同域的对象:
    * Folder=个人/私有的文件夹树, owner 可分享给成员 (PR7 用 drive_share/drive_folder_members)
    * TeamFolder=明确标记为 "团队" 的文件夹, 公开可见 (默认 visibility=team)
- TeamFolder 的成员列表用 PostgreSQL ARRAY 字段简化存储
  (vs Folder 用 drive_share 三表嵌套, 本 PR 不复用那套机制, 避免圈子混乱)
- 软删除: deleted_at 字段, Celery 定时清理或人工 restore

4 维审计 (CLAUDE.md 2026-07-24 v78 audit_log 模式):
- TeamFolderAuditLog: 记录所有 read / write / delete / share / restore 操作
- 4 维度过滤: actor_id (谁) + action (什么操作) + target_type (对象类型) + time (什么时候)

调用方 (API 层):
- POST   /api/v1/team-folders              → create_team_folder
- POST   /api/v1/team-folders/{id}/members → add_member (写 share audit)
- DELETE /api/v1/team-folders/{id}/members/{user_id} → remove_member (写 delete audit)
- GET    /api/v1/team-folders/{id}/audit   → list_audit (4 维度过滤 + 分页)

注意:
- 与 drive_folder_shares / drive_folder_members 不冲突 (本 PR 不复用)
- member_ids 字段冗余: add_member 时同时持久化到 TeamFolderAuditLog (audit trail)
"""
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# 合法 action 枚举 (4 维审计)
VALID_TEAM_FOLDER_AUDIT_ACTIONS: tuple = ("read", "write", "delete", "share", "restore")

# 合法 target_type 枚举
VALID_TEAM_FOLDER_AUDIT_TARGETS: tuple = ("folder", "file", "member", "permission")

# visibility 复用 Folder 的 3 级 (与 PR2/PR7 保持一致)
VALID_TEAM_FOLDER_VISIBILITIES: tuple = ("private", "team", "public")


class TeamFolder(Base, TimestampMixin):
    """团队共享盘 (Team Folder) 主表

    vs Folder:
    - Folder (PR2): 个人文件夹, owner 私有, 通过 PR7 share 机制邀请成员
    - TeamFolder (PR18): 明确标记为 "团队" 的文件夹, 默认 visibility=team,
                         受邀成员直接列在 member_ids 数组里 (无 share token)

    注意:
    - member_ids 是冗余字段: 仍是 source of truth, 与 audit log 配合展示
    - 删除成员时 audit_log 自动写 delete action, member_ids 同步更新
    """

    __tablename__ = "team_folders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    owner_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # 受邀成员 ID 列表 (PG ARRAY, service 层 add_member 同步更新)
    member_ids = Column(
        ARRAY(Integer),
        nullable=False,
        server_default=text("'{}'::int[]"),
    )
    # visibility (private/team/public, 默认 team)
    visibility = Column(
        String(16),
        nullable=False,
        server_default="team",
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # === relationships ===
    # owner 关联 (用于 join 查询 owner 姓名)
    owner = relationship(
        "Member",
        foreign_keys=[owner_id],
        lazy="select",
    )
    # audit log 关联 (cascade delete)
    audit_logs = relationship(
        "TeamFolderAuditLog",
        back_populates="team_folder",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(TeamFolderAuditLog.created_at)",
    )


class TeamFolderAuditLog(Base):
    """团队共享盘 4 维审计日志 (CLAUDE.md 2026-07-24 v78 audit_log 模式)

    4 维度审计:
    1. who (actor_id)         — 谁做的
    2. what (action)          — 5 个合法动作: read / write / delete / share / restore
    3. on_what (target_type + target_id) — 操作对象类型 + ID
    4. when (created_at)      — 何时做
    + extra JSONB             — 5+ 结构化字段 (页面 URL / request id / diff 等)

    设计:
    - BigInteger id (审计可能很大, BIGSERIAL 防溢出)
    - action 用 VARCHAR(16) + CHECK 约束 (5 合法枚举, 写入即校验)
    - target_id 允许 NULL (read 类操作可能无明确 target)
    - extra JSONB NULL 是合法的 (最小审计只 4 列够用)
    """

    __tablename__ = "team_folder_audit_log"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    team_folder_id = Column(
        Integer,
        ForeignKey("team_folders.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # 5 个合法 action (read/write/delete/share/restore)
    action = Column(String(16), nullable=False)
    # 操作对象类型 (folder/file/member/permission)
    target_type = Column(String(32), nullable=False)
    # 对象 ID (字符串, 兼容 path/复合 key)
    target_id = Column(String(64), nullable=True)
    # 额外结构化字段 (页面 URL / diff / request id 等)
    extra = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # === CHECK 约束 ===
    __table_args__ = (
        CheckConstraint(
            "action IN ('read', 'write', 'delete', 'share', 'restore')",
            name="ck_team_folder_audit_action",
        ),
        # 索引定义在 alembic 迁移中显式创建 (含 DESC 排序)
        # model 这边仅声明字段, 索引交由 Alembic 管理
    )

    # === relationships ===
    team_folder = relationship(
        "TeamFolder",
        back_populates="audit_logs",
        lazy="select",
    )
    actor = relationship(
        "Member",
        foreign_keys=[actor_id],
        lazy="select",
    )
