"""批次① B2+N1 — Drive 文件物理删除时的 MinIO 对象统一回收 (2026-09-05)

背景 (两个真 bug):
- B2: drive_service.permanent_delete / permanent_delete_batch 只删
  Knowledge.file_path 的**当前**对象, PR9 版本历史 (drive_file_versions.
  minio_object_key) 的旧对象全部泄漏在 MinIO 里, 永不可见也永不清理。
- N1: drive_cleanup_service.clean_old_drive_files 先 `DELETE FROM knowledge`
  后用**同一个 where** 再 SELECT 拿 file_path → 恒空 → MinIO 清理从未执行过
  (过期文件对象全量泄漏)。修复 = 重排为 先 SELECT → 后 DELETE, 本模块把
  "收集 key + 逐 key 删除" 收敛成两个函数供两处调用。

调用顺序铁律:
1. collect_object_keys **必须**在任何 db.delete/DELETE 之前调用 —
   drive_file_versions 对 knowledge 是 ON DELETE CASCADE, 主表行一删版本行即消失,
   之后再查 minio_object_key 永远查不到 (这正是 N1 的同型陷阱)。
2. purge_minio_keys 放在 DB commit **之后** — MinIO 不可达时不应回滚已成功的
   DB 硬删 (宁可留孤儿对象可事后清, 不可留无主 DB 行)。
3. purge 永不抛异常: 逐 key try/except + logger.warning, 返回失败计数,
   与 cleanup_service 原有 "失败不阻塞 DB 硬删" 铁律一致。

类 20.181 教训 (patch 目标 = 本地绑定): purge_minio_keys 内 file_service 走
**调用时 inline import**, 保持与旧 drive_cleanup_service 相同打点,
测试继续 patch("app.services.file_service.file_service") 即可生效。
"""
import logging
from typing import List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_file_version import DriveFileVersion

logger = logging.getLogger("microbubble.drive_object_gc")


async def collect_object_keys(db: AsyncSession, files: Sequence) -> List[str]:
    """收集一批 Knowledge 行关联的全部 MinIO object key (当前对象 + 全部历史版本).

    Args:
        db: AsyncSession (只读查询)
        files: Knowledge ORM 行序列 (需 .id / .file_path), 通常来自永久删前的 SELECT

    Returns:
        去重后的 key 列表 (保持发现顺序: 先当前对象后版本对象); 空输入返 []

    ⚠️ 必须在任何针对这些行的 DELETE 之前调用 (FK CASCADE 会先消版本行, 见模块 docstring)。
    """
    keys: List[str] = []
    seen: set = set()
    file_ids: List[int] = []

    for f in files:
        file_ids.append(f.id)
        if f.file_path and f.file_path not in seen:
            seen.add(f.file_path)
            keys.append(f.file_path)

    if file_ids:
        # PR9 版本仓库: 每个历史版本一份独立 object, 主表删了它们就是纯孤儿
        stmt = select(DriveFileVersion.minio_object_key).where(
            DriveFileVersion.file_id.in_(file_ids)
        )
        rows = (await db.execute(stmt)).scalars().all()
        for key in rows:
            if key and key not in seen:
                seen.add(key)
                keys.append(key)

    return keys


def purge_minio_keys(keys: Sequence[str]) -> int:
    """逐 key 物理删 MinIO 对象; 单 key 失败只记 warning 不抛 (防御性).

    Args:
        keys: collect_object_keys 的产出 (调用方保证已在 DB commit 之后)

    Returns:
        失败数 (0 = 全部删净); 失败对象留在 MinIO 可事后孤儿巡检再清
    """
    failures = 0
    # 类 20.181: 调用时 import, 与旧 drive_cleanup_service 打点兼容
    # (patch("app.services.file_service.file_service") 在调用时才解析)
    from app.services.file_service import file_service

    for key in keys:
        try:
            file_service.delete_file(key)
        except Exception as e:
            failures += 1
            logger.warning(f"⚠️ [drive_object_gc] MinIO 对象删除失败 key={key}: {e}")
    return failures
