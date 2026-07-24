"""Drive v2 PR10 — Y.Doc 协同编辑文档表 (2026-07-24, W68 第 5 批骨架)

设计背景:
- Drive v2 PR10 启动 CRDT 协同编辑 (W19 PR8g 落地第一步)
- 每个文件 1:1 关联 1 个 Y.Doc 状态 (ydoc_state 二进制)
- 增量 op 走 drive_doc_op_logs (N:1)

字段设计 (与 drive_file_versions 的差异):
- ydoc_state: LargeBinary, Yjs/pycrdt 字节 (PR9 version 用 minio_object_key 存老版)
- ops_count: 累计 op 计数 (PR9 用 is_current 0/1 标识当前版)
- version_number: 本表独立 (PR9 version_number 是顺序快照号, 本表是协同编辑版本)
- active_users: 实时房间人数 (PR9 无此字段)

调用方 (W69 PR10 骨架 实施):
- DriveCollabService.get_or_create_ydoc_state(file_id): 读 ydoc_state, 不存在创建空行
- DriveCollabService.apply_remote_op(file_id, op_bytes, client_id, user_id): 写 op_logs
- DriveCollabService.flush_ydoc_state(file_id, state, version): Celery beat 30s 周期刷盘
- DriveCollabService.export_text(file_id): 提取纯文本 → MinIO (供 PR9 手动 check-in 复用)

权限模型 (W69 实施):
- 读 / apply_op: 走 DriveService._can_see_file + _can_edit_file
- flush / export: 创建人 OR folder 管理员 OR 平台管理员

注意:
- file_id 是 Knowledge.id, ON DELETE CASCADE (删 Knowledge 主表行 → 自动清 Y.Doc)
- UNIQUE 约束保证 1 文件最多 1 个 Y.Doc (不能用 1:N 拆分)
- 本表暂不部署到生产 (W68 第 5 批 0 production code 改动铁律)
"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DriveDocument(Base, TimestampMixin):
    """Drive v2 PR10 — Y.Doc 协同编辑状态表 (1:1 with Knowledge)

    使用方式 (W69 PR10 实施):
    - 客户端连接 WS /api/v1/drive/collab/{file_id} → 服务端 get_or_create_ydoc_state()
    - 客户端发 op → apply_remote_op() → 写 drive_doc_op_logs
    - 30s 周期 / 显式 save → flush_ydoc_state() → 更新本行 ydoc_state
    - 客户端断开 → 不立即删行 (Celery beat 5min 清无活跃 room)

    关系:
    - 1:1 with Knowledge (file_id UNIQUE)
    - 1:N with DriveDocOpLog (file_id FK)
    - 1:N with Member (last_edited_by FK)
    """
    __tablename__ = "drive_documents"

    id = Column(Integer, primary_key=True, index=True)

    file_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Knowledge.id — 1:1 关系, UNIQUE 约束保证 1 文件最多 1 个 Y.Doc",
    )
    ydoc_state = Column(
        LargeBinary,
        nullable=False,
        server_default=text("''::bytea"),
        comment="Y.Doc 二进制 state vector (pycrdt.Doc.get_state() 输出, 0 字节 = 空 doc)",
    )
    ops_count = Column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="累计应用 op 数 (用于 UI 展示 '已编辑 N 次')",
    )
    version_number = Column(
        Integer,
        nullable=False,
        server_default="0",
        comment="save_version 计数器 (与 drive_file_versions.version_number 解耦)",
    )
    active_users = Column(
        Integer,
        nullable=False,
        server_default="0",
        comment="实时房间人数 (best-effort, collab-gateway 30s 周期刷盘)",
    )
    last_edited_by = Column(
        Integer,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="最近编辑者 member.id",
    )
    last_edited_at = Column(
        DateTime,
        nullable=True,
        comment="最近编辑时间",
    )

    # 关系
    file = relationship("Knowledge", foreign_keys=[file_id])
    last_editor = relationship("Member", foreign_keys=[last_edited_by])
    op_logs = relationship(
        "DriveDocOpLog",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DriveDocOpLog.file_id",
    )

    def __repr__(self):
        return (
            f"<DriveDocument(id={self.id}, file_id={self.file_id}, "
            f"v{self.version_number}, ops={self.ops_count}, "
            f"active={self.active_users})>"
        )


class DriveDocOpLog(Base):
    """Drive v2 PR10 — Yjs 增量 op 日志 (N:1 with Knowledge)

    用途:
    - 审计 (谁在什么时候改了什么)
    - 撤销 (按 user_id + 时间窗口反推)
    - 崩溃恢复 (启动时 ydoc_state + 30 天内 ops 重建 Y.Doc)
    - 时间机器 (UI 滑块回放)

    生命周期:
    - Celery compress_op_logs_task 每天凌晨 3:00 合并 op → 写 ydoc_state → 删 7 天前 op
    - 7 天内 op 全部保留 (审计要求)

    注意:
    - client_id 是 Yjs 客户端标识 (uint32, 存 BIGINT 兼容)
    - user_id 可空 (匿名 / system flush)
    """
    __tablename__ = "drive_doc_op_logs"

    id = Column(BigInteger, primary_key=True, index=True)

    file_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        comment="Knowledge.id — N:1 关系",
    )
    op = Column(
        LargeBinary,
        nullable=False,
        comment="单次 Yjs update 字节 (典型 5-200 字节)",
    )
    client_id = Column(
        BigInteger,
        nullable=False,
        comment="发起 op 的 Yjs client_id (uint32, 存 BIGINT 兼容)",
    )
    user_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作者 member.id (nullable: 匿名 / system flush)",
    )
    applied_at = Column(
        DateTime,
        nullable=False,
        server_default="CURRENT_TIMESTAMP",
        comment="op 应用时间",
    )

    # 关系
    document = relationship("DriveDocument", back_populates="op_logs", foreign_keys=[file_id])
    user = relationship("Member", foreign_keys=[user_id])

    __table_args__ = (
        Index(
            "ix_drive_doc_op_logs_file_time",
            "file_id", "applied_at",
            unique=False,
        ),
        Index(
            "ix_drive_doc_op_logs_user",
            "user_id",
            unique=False,
        ),
    )

    def __repr__(self):
        return (
            f"<DriveDocOpLog(id={self.id}, file_id={self.file_id}, "
            f"client={self.client_id}, user={self.user_id})>"
        )
