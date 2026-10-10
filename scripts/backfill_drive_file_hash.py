"""2026-10-10: drive 文件秒传 hash 存量回填 (knowledge.file_hash)

背景 (主指挥侦察):
- `knowledge` 表 storage_mode='drive' 336 行, 只有 3 行有 file_hash
  → 秒传 (instant upload / dedup) 永远 miss, 链路形同虚设。
- 根因: 小文件 multipart 上传端点从不接 file_hash (已于 2026-10-10 修复);
  历史存量文件的 hash 从未落库。本脚本从 MinIO 重读对象算 **SHA-256** hex 写回。

算法口径 (铁律, 与前端一致):
- 前端 hash.worker.js (小文件) 与 sha256.worker.js (分片) 2026-10-10 起
  **都统一为整文件 SHA-256 hex (64 chars)**, 分片路径服务端
  (DriveChunkedUploadService.complete_upload) 本就落的是服务端算的 SHA-256。
- 因此本回填必须算 SHA-256 (不是旧版的 MD5), 否则与前端查询侧不一致 → 仍 miss。

安全默认: dry-run (只统计/抽样, 不写库)。加 --apply 才真写。
大文件流式读 (minio response.stream), 不整体载入内存。

用法 (容器内, 见 CLAUDE.md MSYS 路径坑):
    docker exec -e PYTHONPATH=/app microbubble-agent-app-1 python /app/scripts/backfill_drive_file_hash.py
    ... python /app/scripts/backfill_drive_file_hash.py --apply
    ... python /app/scripts/backfill_drive_file_hash.py --apply --limit 50 --max-size-mb 200
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_drive_file_hash")

READ_CHUNK = 4 * 1024 * 1024  # 4MB 流式读


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="drive 文件秒传 hash (SHA-256) 存量回填")
    p.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    p.add_argument("--limit", type=int, default=0, help="最多处理 N 个 (0 = 全部)")
    p.add_argument("--max-size-mb", type=int, default=0,
                   help="跳过大于 N MB 的文件 (0 = 不限制; 大文件重算慢, 建议先设阈值)")
    p.add_argument("--probe", type=int, default=5,
                   help="dry-run 时抽样实算 hash 的数量 (验证可读性 + 估耗时), 0 = 只统计")
    p.add_argument("--overwrite", action="store_true",
                   help="同时重算已有 file_hash 的行 (默认只补 NULL/空)")
    return p.parse_args()


def _sha256_object(object_name: str) -> tuple[str, int]:
    """流式读 MinIO 对象算 SHA-256 hex。返回 (hash_hex, n_bytes)。

    复刻 sha256.worker.js / hash.worker.js 的整文件 SHA-256 口径。
    """
    from app.services.file_service import file_service

    hasher = hashlib.sha256()
    total = 0
    response = file_service.client.get_object(file_service.bucket, object_name)
    try:
        for chunk in response.stream(amt=READ_CHUNK):
            if not chunk:
                continue
            hasher.update(chunk)
            total += len(chunk)
    finally:
        response.close()
        response.release_conn()
    return hasher.hexdigest(), total


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.knowledge import Knowledge
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {
        "drive_total": 0, "with_hash": 0, "todo": 0,
        "over_size": 0, "no_path": 0,
        "processed": 0, "hashed_ok": 0, "size_mismatch": 0, "missing_object": 0, "failed": 0,
        "dry_run": not args.apply,
    }
    total_bytes = 0

    try:
        async with Session() as db:
            # 全量 drive 行统计
            all_rows = (await db.execute(
                select(Knowledge.id, Knowledge.file_hash).where(
                    Knowledge.storage_mode == "drive",
                    Knowledge.deleted_at.is_(None),
                )
            )).all()
            stats["drive_total"] = len(all_rows)
            stats["with_hash"] = sum(1 for _id, h in all_rows if h)

            # 待处理行: file_hash 为空 (除非 --overwrite)
            q = select(Knowledge.id, Knowledge.file_path, Knowledge.file_size).where(
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
            )
            if not args.overwrite:
                q = q.where(Knowledge.file_hash.is_(None))
            if args.limit > 0:
                q = q.limit(args.limit)
            rows = (await db.execute(q)).all()
            stats["todo"] = len(rows)

            max_bytes = args.max_size_mb * 1024 * 1024 if args.max_size_mb > 0 else None

            # 过滤掉超阈值的 (太大, 重算慢)
            candidates = []
            for kid, fpath, fsize in rows:
                if not fpath:
                    stats["no_path"] += 1
                    continue
                if max_bytes is not None and (fsize or 0) > max_bytes:
                    stats["over_size"] += 1
                    continue
                candidates.append((kid, fpath, fsize))
                total_bytes += fsize or 0

            logger.info(
                "[survey] drive_total=%d with_hash=%d todo=%d "
                "over_size=%d no_path=%d candidates=%d total_bytes=%.1fMB",
                stats["drive_total"], stats["with_hash"], stats["todo"],
                stats["over_size"], stats["no_path"], len(candidates), total_bytes / 1e6,
            )

            if not args.apply:
                # dry-run: 只抽样实算, 验证可读性 + 估单文件耗时
                probe_n = min(args.probe, len(candidates))
                logger.info("[dry-run] 抽样实算 %d/%d 个 (验证可读性 + 估耗时)", probe_n, len(candidates))
                probe_bytes = 0
                t0 = time.time()
                for kid, fpath, fsize in candidates[:probe_n]:
                    try:
                        s = time.time()
                        h, n = await asyncio.to_thread(_sha256_object, fpath)
                        dt = time.time() - s
                        probe_bytes += n
                        logger.info(
                            "  probe id=%s size=%.1fMB sha256=%s… took=%.2fs (%.1f MB/s)",
                            kid, n / 1e6, h[:12], dt, (n / 1e6) / dt if dt > 0 else 0,
                        )
                    except Exception as e:
                        stats["missing_object"] += 1
                        logger.warning("  probe id=%s FAILED: %s", kid, e)
                elapsed = max(time.time() - t0, 1e-9)
                logger.info(
                    "[dry-run] probe 汇总: ok=%d missing=%d bytes=%.1fMB elapsed=%.1fs",
                    probe_n - stats["missing_object"], stats["missing_object"],
                    probe_bytes / 1e6, elapsed,
                )
                if probe_n:
                    mbps = (probe_bytes / 1e6) / elapsed
                    est_total = total_bytes / 1e6 / max(mbps, 1e-9)
                    logger.info(
                        "[dry-run] 预估全量回填耗时: ~%.0fs (%.1f MB/s × %.1fMB)",
                        est_total, mbps, total_bytes / 1e6,
                    )
                logger.info("[dry-run] 未写库。加 --apply 执行真写。")
                return 0

            # --apply: 逐个回填 (流式算 hash + 写回), 单条 commit 避免长事务
            logger.info("[apply] 开始回填 %d 个 (SHA-256)", len(candidates))
            for i, (kid, fpath, fsize) in enumerate(candidates, 1):
                stats["processed"] += 1
                try:
                    h, n = await asyncio.to_thread(_sha256_object, fpath)
                    stats["hashed_ok"] += 1
                    if fsize is not None and n != fsize:
                        stats["size_mismatch"] += 1
                        logger.warning(
                            "  id=%s size 不一致: db=%d minio=%d (仍写 hash)", kid, fsize, n,
                        )
                    row = (await db.execute(
                        select(Knowledge).where(Knowledge.id == kid)
                    )).scalar_one()
                    row.file_hash = h
                    await db.commit()
                except Exception as e:
                    stats["failed"] += 1
                    await db.rollback()
                    logger.warning("  id=%s FAILED: %s", kid, e)
                if i % 10 == 0 or i == len(candidates):
                    logger.info(
                        "[apply] 进度 %d/%d ok=%d missing=%d failed=%d",
                        i, len(candidates), stats["hashed_ok"],
                        stats["missing_object"], stats["failed"],
                    )
    finally:
        await engine.dispose()

    logger.info("[final] %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))