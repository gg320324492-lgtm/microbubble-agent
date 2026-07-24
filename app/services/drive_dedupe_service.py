"""Drive v2 PR17 — 文件秒传 (hash dedupe) 服务 (2026-07-24, W68 第 14 批 B-1)

背景 (ppt-word-replicated-swing.md PR4 招牌功能):
- 百度网盘招牌"秒传": 上传前算文件 hash, 若服务器已存在相同内容 → 秒返已存在 file_id,
  跳过 MinIO 实际上传 (零带宽, < 200ms)
- W68 第 6 批调研发现 knowledge.file_hash 列已有 (alembic 044) + ix_knowledge_file_hash 部分索引
  但**上传时未走查重**, 每次都实打实写 MinIO. PR17 补齐查重能力.

核心边界 (铁律):
- user_id 隔离: 跨用户同 hash **不秒传** (created_by 隔离) — 防越权 / 泄漏他人私有文件
- deleted_at IS NULL: 已软删 file 不参与秒传 (避免恢复冲突 / 引用已删数据)
- storage_mode='drive': 只在 drive 文件之间秒传 (KB 卡片走别的入库管线)
- is_latest=True: 只命中当前活跃版本 (历史版本不秒传, 语义上"该文件已存在")

审计字段 (alembic 078):
- drive_dedupe_count: 命中累计次数 (mark_dedupe_hit 每次 +1)
- drive_dedupe_first_hit_at: 首次命中时间戳

API 契约:
- check_dedupe(db, user_id, file_hash) → Optional[Knowledge]
  命中返回已存在 Knowledge (调用方 mark_dedupe_hit + 复用 file_path); miss 返回 None
- mark_dedupe_hit(db, knowledge_id) → int (返回命中后的 count)
- find_files_by_hash(db, file_hash, exclude_user_id) → List[Knowledge] (审计: 跨用户同 hash)
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Knowledge

logger = logging.getLogger(__name__)

# sha256 十六进制长度 (64 chars) — 与 knowledge.file_hash String(64) 对齐
SHA256_HEX_LEN = 64

# 流式读文件 chunk 大小 (8MB) — 大文件不一次性读进内存
_HASH_CHUNK_SIZE = 8 * 1024 * 1024


class DriveDedupeServiceError(Exception):
    """秒传服务异常 (status_code 语义与 DriveServiceError 一致)"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def compute_file_hash(file_path: str) -> str:
    """流式计算文件 sha256 hex (大文件不一次性入内存)

    Args:
        file_path: 本地文件系统路径 (不是 MinIO object_name)

    Returns:
        64 字符十六进制 sha256

    Raises:
        DriveDedupeServiceError(404): 文件不存在 / 不可读
    """
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(_HASH_CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
    except (FileNotFoundError, IsADirectoryError) as e:
        raise DriveDedupeServiceError(f"文件不可读: {file_path}", status_code=404) from e
    return hasher.hexdigest()


def compute_bytes_hash(data: bytes) -> str:
    """内存字节 sha256 hex (小文件 / UploadFile.read() 已读进内存时用)"""
    return hashlib.sha256(data).hexdigest()


def _normalize_hash(file_hash: str) -> str:
    """规范化 hash 字符串 (去空白 + 小写), 并校验长度

    Raises:
        DriveDedupeServiceError(400): 空 / 长度非法
    """
    if not file_hash or not file_hash.strip():
        raise DriveDedupeServiceError("file_hash 不能为空", status_code=400)
    normalized = file_hash.strip().lower()
    if len(normalized) != SHA256_HEX_LEN:
        raise DriveDedupeServiceError(
            f"file_hash 长度非法 (期望 {SHA256_HEX_LEN} 字符 sha256, 实际 {len(normalized)})",
            status_code=400,
        )
    return normalized


async def check_dedupe(
    db: AsyncSession,
    user_id: int,
    file_hash: str,
) -> Optional[Knowledge]:
    """秒传查重: 同 user + 同 hash + 活跃 drive 文件 → 命中

    铁律:
    - user_id 隔离: WHERE created_by = user_id (跨用户不秒传)
    - deleted_at IS NULL: 已软删不秒传
    - storage_mode='drive' + is_latest=True: 只命中当前活跃 drive 版本

    Args:
        db: AsyncSession
        user_id: 当前上传用户 (= knowledge.created_by)
        file_hash: sha256 hex (自动规范化 + 校验)

    Returns:
        命中的 Knowledge (最早创建的一条, 稳定命中); miss 返回 None
    """
    normalized = _normalize_hash(file_hash)
    stmt = (
        select(Knowledge)
        .where(
            and_(
                Knowledge.file_hash == normalized,
                Knowledge.created_by == user_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
                Knowledge.is_latest.is_(True),
            )
        )
        .order_by(Knowledge.id.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    hit = result.scalar_one_or_none()
    if hit is not None:
        logger.info(
            "[dedupe.check] HIT user_id=%s file_hash=%s… → file_id=%s",
            user_id,
            normalized[:12],
            hit.id,
        )
    else:
        logger.debug(
            "[dedupe.check] MISS user_id=%s file_hash=%s…",
            user_id,
            normalized[:12],
        )
    return hit


async def mark_dedupe_hit(db: AsyncSession, knowledge_id: int) -> int:
    """记录一次秒传命中: count+1 + 首次命中时间戳

    Args:
        db: AsyncSession
        knowledge_id: 被命中的活跃 file

    Returns:
        命中累计次数 (count+1 之后)

    Raises:
        DriveDedupeServiceError(404): file 不存在
    """
    result = await db.execute(
        select(Knowledge).where(Knowledge.id == knowledge_id)
    )
    knowledge = result.scalar_one_or_none()
    if knowledge is None:
        raise DriveDedupeServiceError(
            f"file id={knowledge_id} 不存在", status_code=404
        )

    current = knowledge.drive_dedupe_count or 0
    knowledge.drive_dedupe_count = current + 1
    if knowledge.drive_dedupe_first_hit_at is None:
        # 存 naive datetime (与项目 DateTime 列约定一致, 避免 tz-aware/naive 混用)
        knowledge.drive_dedupe_first_hit_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )
    await db.commit()
    await db.refresh(knowledge)
    logger.info(
        "[dedupe.mark] file_id=%s dedupe_count=%s first_hit_at=%s",
        knowledge_id,
        knowledge.drive_dedupe_count,
        knowledge.drive_dedupe_first_hit_at,
    )
    return knowledge.drive_dedupe_count


async def find_files_by_hash(
    db: AsyncSession,
    file_hash: str,
    exclude_user_id: int,
) -> List[Knowledge]:
    """审计: 找出**其他用户**持有同 hash 的活跃 drive 文件

    用途: 分析跨用户重复上传 (存储浪费), 供管理侧决策全局去重.
    注意: 这只是审计工具, 不用于秒传 (秒传严格 user_id 隔离).

    Args:
        db: AsyncSession
        file_hash: sha256 hex (自动规范化)
        exclude_user_id: 排除的 user (通常是当前用户)

    Returns:
        其他用户持有同 hash 的活跃 drive 文件列表 (按 id 升序)
    """
    normalized = _normalize_hash(file_hash)
    stmt = (
        select(Knowledge)
        .where(
            and_(
                Knowledge.file_hash == normalized,
                Knowledge.created_by != exclude_user_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
                Knowledge.is_latest.is_(True),
            )
        )
        .order_by(Knowledge.id.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
