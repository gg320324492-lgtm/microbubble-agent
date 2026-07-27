"""Drive v2 PR5 分片上传会话模型（Alembic 080）。"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    func,
)

from app.core.database import Base


class DriveChunkedUpload(Base):
    """一个可断点续传的 Drive 文件上传。

    ``uploaded_chunks`` 使用 JSON list[int]，以兼容 PostgreSQL 与测试数据库；每次
    更新都整体赋新 list，避免 SQLAlchemy 原地 JSON mutate 不落库的问题。
    """

    __tablename__ = "drive_chunked_uploads"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    upload_id = Column(String(64), nullable=False, unique=True)
    user_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
    uploaded_chunks = Column(JSON, nullable=False, default=list, server_default="[]")
    checksum = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_drive_chunked_uploads_upload_id", "upload_id", unique=True),
        Index("ix_drive_chunked_uploads_user_id", "user_id"),
        Index("ix_drive_chunked_uploads_status", "status"),
        Index("ix_drive_chunked_uploads_expires_at", "expires_at"),
        CheckConstraint("file_size > 0", name="ck_drive_chunked_uploads_file_size"),
        CheckConstraint("chunk_size > 0", name="ck_drive_chunked_uploads_chunk_size"),
        CheckConstraint("total_chunks > 0", name="ck_drive_chunked_uploads_total_chunks"),
        CheckConstraint(
            "status IN ('pending', 'uploading', 'completed', 'aborted')",
            name="ck_drive_chunked_uploads_status",
        ),
    )

    def __repr__(self) -> str:
        uploaded = len(self.uploaded_chunks or [])
        return (
            f"<DriveChunkedUpload(upload_id='{self.upload_id}', user_id={self.user_id}, "
            f"status='{self.status}', chunks={uploaded}/{self.total_chunks})>"
        )
