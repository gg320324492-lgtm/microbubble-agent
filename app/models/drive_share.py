"""Drive v2 PR7 — Folder Share 与 Folder Member 模型 (2026-07-23)

设计背景:
- 课题组场景: 老师想看学生的实验数据 / 学生之间共享论文 / 全组共用模板
- 现有 v2 PR1 文件分享 (Knowledge.share_token) 仅支持"对外公开链接 + 提取码",
  不能限定"具体成员 + 权限", 也不支持文件夹级别共享
- 本 PR 引入 2 张新表:
  * drive_folder_shares: 公开分享链接 (folder_id + token + expires_at + permission)
  * drive_folder_members: 邀请成员 (folder_id + member_id + permission + invited_by)

权限模型 (3 级):
- read:    只读 (拉文件 + 下载)
- write:   读写 (read + 上传 + 删除自己上传的文件)
- admin:   管理 (write + 分享给其他人 + 移除成员)

调用方 (API 层):
- POST /api/v1/drive/folders/{id}/share                → 创建公开链接
- GET  /api/v1/drive/folders/share/{token}             → 通过 token 访问 (无登录)
- POST /api/v1/drive/folders/{id}/members              → 邀请成员
- DELETE /api/v1/drive/folders/{id}/members/{member_id} → 移除成员

注意:
- folder.member 关系**不**级联删除 folder (on_delete RESTRICT, 与 Folder.member 关系一致)
- share_token 32 字节 url-safe base64 (43 字符, 实际 32 字符即可见 unique)
- expires_at NOT NULL: 安全性 (不允许永久分享, 7 天默认过期)
- (folder_id, member_id) UNIQUE: 同一成员不会被重复邀请
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# 合法 permission 枚举
VALID_FOLDER_PERMISSIONS: tuple = ("read", "write", "admin")
# 权限等级排序: read(0) < write(1) < admin(2)
FOLDER_PERMISSION_ORDER: dict = {
    "read": 0,
    "write": 1,
    "admin": 2,
}


class DriveFolderShare(Base, TimestampMixin):
    """Folder 公开分享链接表 (v2 PR7)

    与 DriveService 文件分享 (Knowledge.share_token) 的差异:
    - 文件分享 = 单文件 + 公开链接 (任何人可访问, 可选密码)
    - folder 分享 = 整个 folder + 公开链接 (无密码, 仅时间窗内有效)
    """
    __tablename__ = "drive_folder_shares"

    id = Column(Integer, primary_key=True, index=True)

    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    share_token = Column(
        String(64),  # 32 字节 url-safe base64 = 43 字符, 留 buffer
        nullable=False,
        unique=True,
        index=True,
    )
    permission = Column(
        String(16),
        nullable=False,
        server_default="read",
    )  # read | write | admin (admin 可分享给其他人)

    expires_at = Column(DateTime, nullable=False)  # 必须有过期, 不允许永久

    created_by = Column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revoked_at = Column(DateTime, nullable=True)  # 主动撤销的时间 (软撤销)

    # 关系
    folder = relationship("Folder", foreign_keys=[folder_id])

    # 索引
    __table_args__ = (
        Index("ix_drive_folder_shares_folder_active", "folder_id", "revoked_at"),
    )

    def __repr__(self):
        return (
            f"<DriveFolderShare(id={self.id}, folder_id={self.folder_id}, "
            f"token={self.share_token[:8]}..., permission={self.permission})>"
        )

    @property
    def is_active(self) -> bool:
        """是否有效 (未撤销 + 未过期)"""
        from datetime import datetime, timezone
        if self.revoked_at is not None:
            return False
        if self.expires_at is None:
            return False
        # 比较时统一为 naive UTC
        expires_naive = self.expires_at
        if expires_naive.tzinfo is not None:
            expires_naive = expires_naive.replace(tzinfo=None)
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        return expires_naive > now_naive


class DriveFolderMember(Base, TimestampMixin):
    """Folder 邀请成员表 (v2 PR7)

    与 folder 共享链接的区别:
    - share = 公开 token, 任何拿到 token 的人可访问
    - member = 实名 (绑 member_id), 只对特定成员开放 + 可设不同权限

    权限继承规则:
    - member 的 permission 限定他能干啥 (read/write/admin)
    - folder owner 始终是 admin (隐含, 无需在本表)
    - admin permission 可分享给其他人 (本表 / share 链接)
    """
    __tablename__ = "drive_folder_members"

    id = Column(Integer, primary_key=True, index=True)

    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission = Column(
        String(16),
        nullable=False,
        server_default="read",
    )  # read | write | admin

    invited_by = Column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 索引 + 唯一约束
    __table_args__ = (
        # 同一 folder 同一 member 只能有一条 (重复邀请幂等)
        UniqueConstraint(
            "folder_id", "member_id",
            name="uq_drive_folder_members_folder_member",
        ),
        Index("ix_drive_folder_members_folder", "folder_id"),
        Index("ix_drive_folder_members_member", "member_id"),
    )

    def __repr__(self):
        return (
            f"<DriveFolderMember(id={self.id}, folder_id={self.folder_id}, "
            f"member_id={self.member_id}, permission={self.permission})>"
        )