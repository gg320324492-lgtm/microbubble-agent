"""批次⑩ 文件夹个人收藏 — drive_folder_stars 模型 (2026-09-05)

与 drive_file_stars (alembic 134) 同构: 收藏是 per-(folder, member) 关系,
每个成员一份自己的文件夹收藏夹, 不在 folders 表上加全局 is_starred 限列
(单一团队空间下 A 收藏 B 的文件夹不该对 C 生效, 同 134 的设计动因)。

字段设计:
- folder_id FK folders.id ON DELETE CASCADE: 删文件夹自动清所有成员的 star 行
- member_id FK members.id ON DELETE CASCADE: 删成员不残留幽灵收藏
- UNIQUE(folder_id, member_id): 幂等 toggle / ON CONFLICT 防重
- starred_at: 个人收藏时间 (per-user /starred 列表倒序键)

调用方:
- POST /api/v1/folders/{id}/toggle-star — 360° 翻转 (本人视角)
- GET /api/v1/drive/starred — 收藏列表合并带出收藏的文件夹
- GET /api/v1/folders/tree — 树节点 is_starred 批量反查
"""
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DriveFolderStar(Base):
    """网盘文件夹个人收藏关系表 (一行 = 某成员收藏了某文件夹)"""
    __tablename__ = "drive_folder_stars"

    id = Column(Integer, primary_key=True, index=True)

    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=False,
        comment="folders.id — 被收藏的文件夹行",
    )
    member_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        comment="收藏人 members.id (per-user 视角主体)",
    )
    starred_at = Column(
        DateTime,
        nullable=False,
        server_default=text("now()"),
        comment="收藏时间 (naive UTC, 与 folders 时间列口径一致)",
    )

    # 关系
    folder = relationship("Folder", foreign_keys=[folder_id])
    member = relationship("Member", foreign_keys=[member_id])

    # 约束与索引 — 名称与 alembic 135 逐字一致 (create_all / 迁移双路径防漂移)
    __table_args__ = (
        UniqueConstraint("folder_id", "member_id", name="uq_drive_folder_stars"),
        Index("ix_dfos_member_starred", "member_id", text("starred_at DESC")),
        Index("ix_dfos_folder", "folder_id"),
    )

    def __repr__(self):
        return (
            f"<DriveFolderStar(id={self.id}, folder_id={self.folder_id}, "
            f"member_id={self.member_id}, starred_at={self.starred_at})>"
        )
