"""外部收件的分片上传会话模型 (Alembic 150)。

为什么单开一张表, 不复用 `drive_chunked_uploads`:

1. **归属主体不同**。`drive_chunked_uploads.user_id` 是 `members.id` 的 NOT NULL 外键,
   而外部收件人**没有账号**。把 `request.created_by` 塞进 user_id 会让"谁在传"这个事实
   被抹掉, 还会让 drive 会话列表/清理任务把它们当成内部会话处理。
2. **生命周期与配额语义不同**。本表随 FileRequest 一起 CASCADE 删除, 且完成后的
   Knowledge 行**不计入成员配额** (由 settings.FILE_REQUEST_COUNTS_TOWARD_QUOTA 决定)。
3. **安全闸不同**。本表受请求级三重闸约束 (单文件 / 累计总量 / 提交次数),
   那三样是 FileRequest 的属性, 不是 drive 会话的属性。

⚠️ 本表**只**存会话元数据与已传片号; 片的字节躺在 MinIO 的 staging 前缀下
   (见 `file_request_upload_service.STAGING_PREFIX`)。合并由 MinIO 服务端
   `compose_object` 完成, 全程不把文件读进 Python 内存 —— 这是 10GB 能成立的根因,
   app 容器 `mem_limit: 8g` 不用动。
"""

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)

from app.core.database import Base


class FileRequestUpload(Base):
    """一个匿名的、可断点续传的大文件上传会话。

    ``uploaded_chunks`` 用 JSON list[int] (与 DriveChunkedUpload 同理由: 兼容测试库,
    且每次整体赋新 list, 避免 SQLAlchemy 原地 mutate 不落库)。
    """

    __tablename__ = "file_request_uploads"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 对外暴露的会话标识 (secrets.token_urlsafe), 不用自增 id —— 匿名侧不可枚举
    upload_id = Column(String(64), nullable=False, unique=True)
    request_id = Column(
        Integer,
        ForeignKey("file_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 匿名者自报姓名 (仅当 FileRequest.require_uploader_name=false 时可为空)
    uploader_name = Column(String(200), nullable=True)
    filename = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
    uploaded_chunks = Column(JSON, nullable=False, default=list, server_default="[]")
    # 客户端声明的整文件 SHA256 (hex, 64)。可选: 传了就与服务端合并后实算的值比对,
    # 不一致 ⇒ 判定传输不完整并拒绝落库 (不是只记录了事)。
    checksum = Column(String(64), nullable=True)
    # 服务端合并后**实算**的内容 SHA256, 完成后写入 Knowledge.file_hash。
    verified_sha256 = Column(String(64), nullable=True)
    status = Column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    # 完成后回填: 便于从会话追溯到落地的 drive 行
    knowledge_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_file_request_uploads_upload_id", "upload_id", unique=True),
        Index("ix_file_request_uploads_request_id", "request_id"),
        Index("ix_file_request_uploads_status", "status"),
        Index("ix_file_request_uploads_expires_at", "expires_at"),
        CheckConstraint("file_size > 0", name="ck_file_request_uploads_file_size"),
        CheckConstraint(
            "chunk_size > 0", name="ck_file_request_uploads_chunk_size"
        ),
        CheckConstraint(
            "total_chunks >= 1 AND total_chunks <= 10000",
            name="ck_file_request_uploads_total_chunks",
        ),
        CheckConstraint(
            "status IN ('pending','uploading','completed','aborted','expired')",
            name="ck_file_request_uploads_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FileRequestUpload(upload_id={self.upload_id!r}, "
            f"request_id={self.request_id}, filename={self.filename!r}, "
            f"status={self.status!r}, chunks={len(self.uploaded_chunks or [])}"
            f"/{self.total_chunks})>"
        )
