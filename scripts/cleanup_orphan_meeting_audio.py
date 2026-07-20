"""清理会议表孤儿 audio_url 字段 (MinIO wipe 后果修复)

背景 (2026-07-11 事故): MinIO bucket wipe 当时只回填了 avatars, 14 个会议的
recordings/{uuid}.{ext} 文件被永久擦除, 但 DB audio_url 字段还在 → MeetingDetailView
AudioPlayer 永远 404, 会议 detail 页红框报警告。

2026-07-20 (P0): polish 修复时发现 #135 仍报 MinIO 404, 写本 CLI 3 段式处理:
  ① --scan   扫所有 audio_url IS NOT NULL 的会议, 调 file_service.object_exists()
             检测 MinIO 实际文件状态, 打印孤儿列表 (无副作用, 必跑)
  ② --apply --confirm  单事务包裹, 防御性 UPDATE WHERE audio_url IS NOT NULL
             清空 audio_url / last_chunk_index / total_chunks / upload_status
             + backup JSON 写 /tmp/meeting_audio_orphan_<ts>.json (PR6-P10+ 一致 UX)
  ③ --apply 不带 --confirm 走 DRY RUN 强制

与 PR6-P18 fill_wechat_id_placeholders.py 3 段式范式一致。

usage:
  docker exec microbubble-agent-app-1 python -m scripts.cleanup_orphan_meeting_audio --scan
  docker exec microbubble-agent-app-1 python -m scripts.cleanup_orphan_meeting_audio --apply --confirm
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update

# 把项目根目录加进 path (容器内 /app 是 cwd, 相对导入可能失败)
sys.path.insert(0, "/app")

from app.core.database import async_session as async_session_maker  # noqa
from app.models.meeting import Meeting
from app.services.file_service import file_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cleanup_orphan_meeting_audio")


async def scan_orphans() -> list[dict]:
    """扫所有 audio_url IS NOT NULL 的会议, 调 MinIO object_exists 判定孤儿"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(
                Meeting.id,
                Meeting.title,
                Meeting.audio_url,
                Meeting.last_chunk_index,
                Meeting.total_chunks,
                Meeting.upload_status,
                Meeting.status,
            ).where(Meeting.audio_url.is_not(None)).order_by(Meeting.id)
        )
        rows = result.all()

    orphans: list[dict] = []
    for row in rows:
        object_exists = await file_service.object_exists(row.audio_url)
        record = {
            "id": row.id,
            "title": row.title,
            "audio_url": row.audio_url,
            "last_chunk_index": row.last_chunk_index,
            "total_chunks": row.total_chunks,
            "upload_status": row.upload_status,
            "status": row.status,
            "minio_exists": object_exists,
        }
        if not object_exists:
            orphans.append(record)
        logger.info(
            f"  meeting {row.id:>4} | minio={object_exists!s:5} | "
            f"{row.status:10} | upload={row.upload_status:10} | {row.audio_url}"
        )
    return orphans


async def apply_cleanup(orphans: list[dict], backup_path: str) -> int:
    """单事务包裹, 防御性 UPDATE WHERE, 写 backup JSON"""
    if not orphans:
        logger.info("无孤儿, 无操作")
        return 0

    # 1. 写 backup JSON (PR6-P10+ 一致 UX, 永远备份)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ts": datetime.now().isoformat(),
                "kind": "meeting_audio_orphan_cleanup",
                "orphan_count": len(orphans),
                "items": orphans,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"backup 写入: {backup_path} ({len(orphans)} 条)")

    # 2. 单事务 UPDATE
    async with async_session_maker() as session:
        async with session.begin():
            orphan_ids = [o["id"] for o in orphans]
            result = await session.execute(
                update(Meeting)
                .where(Meeting.id.in_(orphan_ids))
                .where(Meeting.audio_url.is_not(None))  # 防御性 WHERE
                .values(
                    audio_url=None,
                    last_chunk_index=-1,
                    total_chunks=None,
                    upload_status="orphan_cleaned",
                )
            )
            updated_count = result.rowcount
    logger.info(
        f"UPDATE 完成: 期望清 {len(orphans)} 条, 实际清 {updated_count} 条"
    )
    return updated_count


async def main():
    parser = argparse.ArgumentParser(
        description="清理会议表孤儿 audio_url 字段 (MinIO wipe 后果修复)",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="扫所有会议 audio_url, 标 MinIO 孤儿 (无副作用, 推荐先跑)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际 UPDATE 清字段 (默认 DRY RUN, 必须加 --confirm)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="二次确认门, 防止误操作 (与 --apply 配合使用)",
    )
    args = parser.parse_args()

    if not args.scan and not args.apply:
        parser.print_help()
        print("\n至少指定 --scan 或 --apply", file=sys.stderr)
        sys.exit(1)

    if args.apply and not args.confirm:
        print(
            "[DRY RUN] 实际清理需要 --apply --confirm 双重确认 (与 PR6-P10+ 一致 UX)",
            file=sys.stderr,
        )

    if args.scan or args.apply:
        print("=" * 80)
        print("扫描 meeting audio_url 状态...")
        print("=" * 80)
        orphans = await scan_orphans()
        print(f"\n扫描完成: 总会议 {len(orphans) if orphans else 0} 个孤儿 (MinIO 文件不存在)")
        if orphans:
            print("\n孤儿清单:")
            for o in orphans:
                print(
                    f"  meeting {o['id']:>4} | {o['status']:10} | "
                    f"upload={o['upload_status']:10} | {o['audio_url']}"
                )
            print(
                f"\n  total {len(orphans)} orphans — "
                f"前端 MeetingDetailView AudioPlayer 永远 404"
            )

    if args.apply:
        if not args.confirm:
            print(
                f"\n[DRY RUN] 将清 {len(orphans) if orphans else 0} 条会议 audio_url 字段 "
                "(未传 --confirm, 跳过 apply)"
            )
            return
        if not orphans:
            print("\n无孤儿, 无需 apply")
            return
        backup_path = (
            f"/tmp/meeting_audio_orphan_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        print(f"\n开始 apply: backup → {backup_path}")
        updated = await apply_cleanup(orphans, backup_path)
        print(f"\n[OK] {updated} 条 meeting audio_url 字段已清空")
        print(
            f"  frontend: MeetingDetailView AudioPlayer 不再尝试加载 404 录音\n"
            f"  backup:   {backup_path}\n"
            f"  提示:     重跑 --scan 验证 0 孤儿"
        )


if __name__ == "__main__":
    asyncio.run(main())
