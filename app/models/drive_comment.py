"""Drive v2 PR9 — 文件/文件夹 评论 Thread 模型 (2026-07-24, W68 第 8 批 PR11 path 物化)

设计背景:
- Drive v2 PR6 已有 `FileComment` (file_comments 表, 仅绑 file_id, 单层评论 + 回复),
  不支持 folder 级别讨论, 也不支持跨 thread 多层嵌套回复 + resolved 状态.
- 课题组场景: 文件讨论 (例: "实验数据有疑问 @张三") / 文件夹讨论 (例: "本月论文归类")
  / 嵌套回复 (GitHub PR review comments 风格) / 已解决标记 (issue close).
- 本 PR 引入 1 张新表:
  * drive_comments: file/folder 评论 thread + 嵌套回复 + resolved 状态

W68 第 8 批 PR11 增量:
- 加 path VARCHAR(500) 列, 物化嵌套路径
  * 顶层 (parent_id IS NULL): path = '/'
  * 子评论: path = parent.path + str(parent.id) + '/'
  * 例: comment id=42 在嵌套祖先 /1/2/3/ 下 → path='/1/2/3/42/'
- GIN 索引 + file_id+path 复合索引 (migration 066 中加)
- 用途: path LIKE prefix 查询 + breadcrumb 一次 query 拿祖先链

表设计 vs FileComment (PR6) 区别:
- FileComment 仅绑 file_id; DriveComment 同时绑 file_id/folder_id (二者互斥)
- FileComment 只 2 层 (parent_comment_id + thread_depth MAX=3); DriveComment 嵌套深度不限
  (GitHub PR style — 用户深度对话, UI 缩进显示)
- FileComment 无 resolved 状态; DriveComment 加 resolved_at + resolved_by
- FileComment 落 user_id=NULL (用户注销保留); DriveComment 强约束 author_id 不为空
  (删除 author → 评论也跟着删, 因为有 resolved_by FK 关联)

权限模型:
- 任何能访问 file/folder 的用户都能写评论 (read 权限足够, 类似 GitHub issue 讨论)
- 仅作者本人能编辑/删除自己的评论 (admin 不 override, 保证作者主权)
- 作者本人 / 文件 owner / folder owner / admin member 可以标记 resolved
- author_id 删除时: 评论 CASCADE 删除 (resolved_by FK CASCADE 兜底)

调用方 (API 层):
- POST   /api/v1/drive/comments                     → 创建顶层评论 / 嵌套回复
- GET    /api/v1/drive/comments                     → 列表 (按 file_id / folder_id / author_id 过滤)
- GET    /api/v1/drive/comments/{id}                → 详情
- PATCH  /api/v1/drive/comments/{id}                → 编辑内容 (仅 author)
- DELETE /api/v1/drive/comments/{id}                → 删除 (仅 author, 级联子回复)
- POST   /api/v1/drive/comments/{id}/resolve        → 标记 resolved (author / 文件 owner / folder admin)
- POST   /api/v1/drive/comments/{id}/unresolve      → 取消 resolved (同权限)
- GET    /api/v1/drive/comments/{id}/breadcrumb     → 祖先链 (PR11 新增)

注意:
- file_id/folder_id 二选一 (CHECK 约束在 migration 加, ORM 层用 validators 校验)
- parent_id 自引用 FK, 嵌套深度不限 (前端 UI 控制缩进, DB 不限制)
- content TEXT, 不限长度 (前端建议 1-10000 字符, 由 schema 校验)
- mentions ARRAY(Integer) 冗余存 user_id 列表 (前端 O(1) 高亮 '提到你', 与 PR6 FileComment 一致)
- resolved_at NULL=未解决, NOT NULL=已解决 (含 resolved_by 必填)
- path 默认 '/', 由 service.create_comment 自动根据 parent.path 计算
"""
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DriveComment(Base, TimestampMixin):
    """Drive v2 PR9 — 文件/文件夹评论 thread (GitHub PR review comment 风格)

    与 PR6 FileComment 区别:
    - file_id / folder_id 二选一 (folder 级别讨论)
    - parent_id 嵌套不限深度 (FileComment 仅 2 层)
    - resolved_at / resolved_by 状态管理 (FileComment 无)
    - author_id NOT NULL CASCADE (FileComment SET NULL 保留)

    W68 第 8 批 PR11 增量:
    - path VARCHAR(500) 物化嵌套路径 (例: '/1/2/3/42/')
    """
    __tablename__ = "drive_comments"

    id = Column(Integer, primary_key=True, index=True)

    # === 主体 (二选一) ===
    file_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # === 作者 (NOT NULL, 删除作者时评论 CASCADE 跟删) ===
    author_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # === 嵌套回复 (parent_id 自引用, 深度不限) ===
    parent_id = Column(
        "parent_id",  # DB 列名 (与 Python 属性同名, 显式写)
        Integer,
        ForeignKey("drive_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # === 评论内容 ===
    content = Column(Text, nullable=False)

    # === @ 提醒 (冗余存 user_id 列表, 前端 O(1) 高亮) ===
    mentions = Column(ARRAY(Integer), nullable=True)

    # === resolved 状态 (NULL=未解决) ===
    resolved_at = Column(DateTime, nullable=True, index=True)
    resolved_by = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=True,
    )

    # === 嵌套路径物化 (W68 第 8 批 PR11 增量) ===
    # 顶层 (parent_id IS NULL): path = '/'
    # 子评论: path = parent.path + str(parent.id) + '/'
    # 例: comment id=42 在嵌套祖先 /1/2/3/ 下 → path='/1/2/3/42/'
    # 用途: path LIKE prefix 查询 (GIN trigram 索引) + breadcrumb 一次 query 拿祖先链
    path = Column(
        String(500),
        nullable=True,
        default="/",
        server_default="/",
    )

    # === 软删 (W68 第 12 批 C-2 增量) ===
    # PR9 老 delete 是 hard delete (CASCADE 子回复)
    # C-2 改软删: deleted_at + deleted_by 标记, 不物理删除
    # 用途:
    # - 保留 audit_log 链路 (谁在什么时候删的, 即使删人账号注销仍可追溯)
    # - 子回复保留 (parent 不被 CASCADE 连带)
    # - deleted_by SET NULL 而非 CASCADE (删人时不连带删评论, 与 resolved_by 一致)
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_by = Column(
        Integer,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )

    # === 关系 ===
    author = relationship("Member", foreign_keys=[author_id])
    resolver = relationship("Member", foreign_keys=[resolved_by])
    parent = relationship(
        "DriveComment", remote_side=[id], backref="replies"
    )

    # === 索引 + 约束 ===
    __table_args__ = (
        # file/folder 二选一 (CHECK 约束)
        CheckConstraint(
            "(file_id IS NOT NULL AND folder_id IS NULL) OR "
            "(file_id IS NULL AND folder_id IS NOT NULL)",
            name="ck_drive_comments_target_xor",
        ),
        # 常用查询: file_id + resolved_at + created_at
        Index("ix_drive_comments_file_resolved", "file_id", "resolved_at"),
        # 常用查询: folder_id + resolved_at + created_at
        Index("ix_drive_comments_folder_resolved", "folder_id", "resolved_at"),
        # 常用查询: parent_id (拉子回复)
        Index("ix_drive_comments_parent", "parent_id"),
        # W68 PR11: file_id + path 复合索引 (按 file 过滤 + path prefix 常用)
        Index("ix_drive_comments_file_path", "file_id", "path"),
    )

    def __repr__(self):
        target = f"file_id={self.file_id}" if self.file_id else f"folder_id={self.folder_id}"
        return (
            f"<DriveComment(id={self.id}, {target}, "
            f"author_id={self.author_id}, parent_id={self.parent_id}, "
            f"path='{self.path}', "
            f"resolved={'yes' if self.resolved_at else 'no'})>"
        )

    @property
    def is_resolved(self) -> bool:
        """是否已解决 (resolved_at NOT NULL)"""
        return self.resolved_at is not None

    @property
    def is_deleted(self) -> bool:
        """是否软删 (deleted_at NOT NULL) — W68 第 12 批 C-2"""
        return self.deleted_at is not None

    @property
    def is_top_level(self) -> bool:
        """是否顶层评论 (parent_id NULL)"""
        return self.parent_id is None

    @property
    def depth(self) -> int:
        """嵌套深度 (顶层=0, 子=parent.depth+1)

        从 path 推导:
        - '/' → 顶层 (depth=0)
        - '/5/' → id=5 的子评论 (depth=1)
        - '/5/12/' → depth=2
        - '/5/12/30/' → depth=3
        公式: depth = max(0, len(path.split('/') 非空 segments))
        """
        if not self.path or self.path == "/":
            return 0
        # path 形式: '/5/12/30/' → split('/') → ['', '5', '12', '30', '']
        # 非空 segments: ['5', '12', '30'] → length = depth
        segments = [s for s in self.path.split("/") if s]
        return len(segments)