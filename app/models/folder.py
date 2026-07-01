"""课题组网盘 (Lab Group Drive) — Folder 模型
2026-07-01

设计要点:
- 自引用 parent_id (self-FK ON DELETE SET NULL) 支持任意嵌套
- path 字段 '/1/4/7/' 形式存储, 便于 O(子项数) 列出子节点
- depth 字段限制 max=5 (5 层嵌套, 防止 UI 渲染崩溃)
- visibility 字段 (private/team/public) 是文件夹内文件的硬上限
  - folder=private → 文件只能是 private
  - folder=team    → 文件可以是 private/team/public
  - folder=public  → 文件只能是 public
- owner_id FK members (ondelete='RESTRICT'), 不能 cascade (删成员不删文件夹)
- 软删除 deleted_at (Celery beat 定期物理清除, 与 Knowledge 同步)
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Folder(Base, TimestampMixin):
    """课题组网盘文件夹"""
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    owner_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parent_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visibility = Column(
        String(16),
        nullable=False,
        server_default="team",
        index=True,
    )  # private | team | public

    # 物化路径: '/1/4/7/' 形式, 便于 O(子项数) 列出子节点
    # 创建时由 service 层自动维护 (parent.path + str(self.id) + '/')
    path = Column(String(1000), nullable=False, server_default="/")

    # 嵌套深度: 0=顶级, max=5 (用户决策: 限 5 层, 防 UI 渲染崩溃)
    depth = Column(Integer, nullable=False, server_default="0")

    deleted_at = Column(DateTime, nullable=True, index=True)

    # 关系 (backref 让 Knowledge 反查 folder)
    parent = relationship("Folder", remote_side=[id], backref="children")

    def __repr__(self):
        return f"<Folder(id={self.id}, name='{self.name}', depth={self.depth})>"

    # 索引: 常用查询组合
    __table_args__ = (
        Index("ix_folders_parent_active", "parent_id", "deleted_at"),
        Index("ix_folders_owner_active", "owner_id", "deleted_at"),
    )