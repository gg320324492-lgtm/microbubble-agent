"""Drive v2 PR9 — File Version 模型 (2026-07-24)

设计背景:
- 课题组场景: 老师改论文 v1→v2→v3 / 学生更新实验数据需要保留旧版可回滚 / 多人协作需要变更审计
- 现有 Knowledge 表 (is_latest + version_number) 把"版本"概念糅进主表行, 主表膨胀
  (一个文件 N 版 = N 行 Knowledge), 列宽度复用, 查询需要过滤 is_latest
- 本 PR 引入独立的 drive_file_versions 表 + 与 Knowledge.file_id (1:N) 关系,
  Knowledge 主表保留**当前**版本 (1 行), 历史版本在 drive_file_versions 表

字段设计 (与 KnowledgeVersion (PR4) 的差异):
- minio_object_key: 独立存储字段 (KnowledgeVersion 用 file_path 间接拿)
- size: 独立存储 (KnowledgeVersion 用 file_size)
- uploader_id + comment (KnowledgeVersion: uploaded_by + change_note)
- 不冗余 file_hash (与 Knowledge 表 1:1 关联, 通过 file_id JOIN 拿)
- 不冗余 version_number (同一 file_id 下的 max(version_number)+1 即下个版本号)

调用方 (API 层):
- POST /api/v1/drive/versions/files/{file_id}/versions             → 上传新版本
- GET  /api/v1/drive/versions/files/{file_id}/versions             → 列所有版本
- GET  /api/v1/drive/versions/versions/{version_id}/download        → 下载指定版本
- POST /api/v1/drive/versions/files/{file_id}/versions/{version_id}/rollback → 回滚
- DELETE /api/v1/drive/versions/versions/{version_id}              → 删除某版

权限模型:
- list / download: 走 DriveService._can_see_file (private 仅 owner)
- upload_new_version / rollback / delete: 创建人 OR folder 管理员 OR 平台管理员
- 删除中间版本: 不允许 (会被回滚功能悬空), 只能删最新非当前版本

注意:
- Knowledge.file_id 是 Knowledge.id (PR4 起每个文件 1 行, 历史版在 knowledge_versions)
- DriveFileVersion.file_id = Knowledge.id (即同一个 file_id)
- ON DELETE CASCADE: 删 Knowledge 主表行 → 自动清 drive_file_versions 全部明细
"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DriveFileVersion(Base, TimestampMixin):
    """Drive v2 PR9 — 文件版本历史明细表

    与 KnowledgeVersion (PR4) 的关系:
    - PR4 的 knowledge_versions 表: 写"每次版本变更事件" (一行 = 一次 create_version/restore 调用)
    - PR9 的 drive_file_versions 表: 存"每个版本的完整数据" (一行 = 一份历史 bytes)
    - 两者并行存在, 职责分离:
      * KnowledgeVersion = 变更审计日志 (immutable, append-only, 包含 change_note)
      * DriveFileVersion = 历史版本仓库 (含 minio_object_key, 用于回滚时 copy_object)

    使用方式:
    - Drive v2 PR9 upload_new_version(): 创建新行 + 把旧行 is_current=False
    - Drive v2 PR9 rollback(): 拿 DriveFileVersion.minio_object_key → copy_object → 创建新行
    - Drive v2 PR9 list_versions(): 按 file_id 查, 按 version_number desc 排

    注意:
    - Knowledge.file_id 即 DriveFileVersion.file_id (FK 到 knowledge.id)
    - version_number 是同一 file_id 下的单调递增整数
    - is_current 标识哪个版本是当前用户看到的最新版 (与 Knowledge.is_latest 同步)
    """
    __tablename__ = "drive_file_versions"

    id = Column(Integer, primary_key=True, index=True)

    file_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Knowledge.id — 主文件行 (current version 的 Knowledge 行)",
    )
    version_number = Column(
        Integer,
        nullable=False,
        comment="同一 file_id 下的版本号 (1, 2, 3... 单调递增)",
    )
    minio_object_key = Column(
        String(500),
        nullable=False,
        comment="MinIO object_name (uploads/drive/{owner_id}/v{n}_{hash12}_{ts}{ext})",
    )
    size = Column(
        BigInteger,
        nullable=False,
        comment="文件字节大小",
    )
    uploader_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="上传者 member.id",
    )
    comment = Column(
        Text,
        nullable=True,
        comment="版本备注 (用户输入, 可选, 比如 '修订实验结论' 或 '回滚到 v2')",
    )
    is_current = Column(
        Integer,
        nullable=False,
        server_default="0",
        comment="是否当前版本 (1=是, 0=否, 同一 file_id 只有 1 行 =1)",
    )

    # 关系
    file = relationship("Knowledge", foreign_keys=[file_id])
    uploader = relationship("Member", foreign_keys=[uploader_id])

    # 索引: (file_id, version_number) 复合 — list_versions 高频
    __table_args__ = (
        Index(
            "ix_drive_file_versions_file_version",
            "file_id", "version_number",
            unique=False,
        ),
        # (file_id, is_current) 复合 — 找当前版本 (每个 file_id 只 1 行 is_current=1)
        Index(
            "ix_drive_file_versions_file_current",
            "file_id", "is_current",
            unique=False,
        ),
    )

    def __repr__(self):
        return (
            f"<DriveFileVersion(id={self.id}, file_id={self.file_id}, "
            f"v{self.version_number}, size={self.size}, current={bool(self.is_current)})>"
        )