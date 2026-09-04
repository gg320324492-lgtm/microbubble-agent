"""批次① B6 收藏个人化 — drive_file_stars 模型 (2026-09-05)

设计背景:
- 旧实现 is_starred 是 Knowledge 上的**全局限列**: 任何成员 star 对全员生效
  (单一团队空间改造后 owner 门禁删除, 矛盾激化 — A 收藏了 B 就看到"A 的收藏"挂全员)。
- 本表把收藏改为 per-(file, member) 关系: 每人一份自己的收藏夹,
  Knowledge.is_starred / starred_at 两列退役为 legacy (不再被 toggle 写入, 列保留)。
- 配套 alembic 134 把存量 is_starred=true 行回填给其 created_by (迁移后用户无感)。

字段设计:
- file_id FK knowledge.id ON DELETE CASCADE: 永久删文件自动清所有成员的 star 行
  (注意: drive_cleanup/permanent_delete 若走 bulk SQL DELETE 后版本表靠 CASCADE,
   本表同理; collect_object_keys 只涉及 MinIO key, 与本表无交叉)
- member_id FK members.id ON DELETE CASCADE: 删成员不残留幽灵收藏
  (删号链路 reassign_member_rows 不需要登记本表 — CASCADE 自动清)
- UNIQUE(file_id, member_id): 幂等 INSERT...ON CONFLICT DO NOTHING 的冲突目标
- starred_at: 个人收藏时间 (per-user /starred 列表默认倒序键)

调用方:
- DriveService.toggle_star_file — 单文件 360° 翻转 (本人视角)
- DriveService.batch_star_files — POST /drive/files/batch-star 幂等批量
- DriveService.get_starred_ids — 列表端点批量 attach per-user is_starred
- _build_list_files_query(starred_only=True) — 子查询 EXISTS 语义过滤本人收藏
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


class DriveFileStar(Base):
    """网盘文件个人收藏关系表 (一行 = 某成员收藏了某 drive 文件)"""
    __tablename__ = "drive_file_stars"

    id = Column(Integer, primary_key=True, index=True)

    file_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        comment="Knowledge.id — 被收藏的 drive 文件行",
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
        comment="收藏时间 (naive UTC, 与 Knowledge 时间列口径一致; 批量/单个收藏显式写入)",
    )

    # 关系
    file = relationship("Knowledge", foreign_keys=[file_id])
    member = relationship("Member", foreign_keys=[member_id])

    # 约束与索引 — 名称与 alembic 134 逐字一致 (create_all / 迁移双路径防漂移)
    __table_args__ = (
        UniqueConstraint("file_id", "member_id", name="uq_drive_file_stars"),
        # 本人收藏夹分页 (member_id 等值 + starred_at desc 翻页) 主路径
        Index("ix_dfs_member_starred", "member_id", text("starred_at DESC")),
        # 文件详情/列表批量反查该文件被谁收藏
        Index("ix_dfs_file", "file_id"),
    )

    def __repr__(self):
        return (
            f"<DriveFileStar(id={self.id}, file_id={self.file_id}, "
            f"member_id={self.member_id}, starred_at={self.starred_at})>"
        )
