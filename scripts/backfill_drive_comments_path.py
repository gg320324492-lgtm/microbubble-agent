"""scripts/backfill_drive_comments_path.py — Drive v2 PR14 path 回填 CLI

用法 (容器内推荐, 避免 import 失败):
  # 1. 单文件 dry-run (只看不写)
  docker exec microbubble-agent-app-1 python /app/scripts/backfill_drive_comments_path.py --file-id 42

  # 2. 单文件真回填
  docker exec microbubble-agent-app-1 python /app/scripts/backfill_drive_comments_path.py --file-id 42 --apply

  # 3. 单 folder dry-run
  docker exec microbubble-agent-app-1 python /app/scripts/backfill_drive_comments_path.py --folder-id 3

  # 4. 全部 dry-run (会扫全表, 给个总数)
  docker exec microbubble-agent-app-1 python /app/scripts/backfill_drive_comments_path.py --all

  # 5. 全部真回填 (生产慎用! 锁整表)
  docker exec microbubble-agent-app-1 python /app/scripts/backfill_drive_comments_path.py --all --apply

  # 6. 本地 (需 PYTHONPATH=. 或 pip install -e .)
  PYTHONPATH=. python scripts/backfill_drive_comments_path.py --all

纪律 (W68 第 12 批 B-1):
- 默认 dry_run=True, 显式 --apply 才写库 (防误操作)
- 跨 PR 部署时, 必须先跑 alembic 070 后再跑此 CLI (否则 070 会重算, 重复劳动)
- 走 raw service 入口 (不调 Celery task, 因为 Celery 是异步, CLI 同步看结果)
- 输出 JSON 格式 + 人类可读 summary 方便 audit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Optional

# 让 Python 找到 app 模块 (本地跑)
sys.path.insert(0, ".")


async def run_backfill(
    *,
    file_id: Optional[int],
    folder_id: Optional[int],
    do_all: bool,
    apply: bool,
    fix_orphans: bool,
) -> dict:
    """调 service 跑 backfill

    Returns:
        dict 形式 BackfillResult
    """
    # 延迟 import 避免 CLI 启动时 sqlalchemy 失败
    from app.core.database import AsyncSessionLocal
    from app.services.drive_comments_path_backfill_service import (
        DriveCommentsPathBackfillService,
    )

    async with AsyncSessionLocal() as db:
        svc = DriveCommentsPathBackfillService(db)

        if file_id is not None:
            updated = await svc.backfill_for_file(
                file_id,
                dry_run=not apply,
                fix_orphans=fix_orphans,
            )
            return {
                "target": f"file:{file_id}",
                "updated": updated,
                "orphans_fixed": 0,
                "dry_run": not apply,
            }
        elif folder_id is not None:
            updated = await svc.backfill_for_folder(
                folder_id,
                dry_run=not apply,
                fix_orphans=fix_orphans,
            )
            return {
                "target": f"folder:{folder_id}",
                "updated": updated,
                "orphans_fixed": 0,
                "dry_run": not apply,
            }
        elif do_all:
            result = await svc.backfill_all_paths(
                dry_run=not apply,
                fix_orphans=fix_orphans,
            )
            return result.to_dict()
        else:
            # 不传 target, 给个 help
            print("ERROR: 必须指定 --file-id / --folder-id / --all 之一", file=sys.stderr)
            sys.exit(2)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Drive v2 PR14 path 回填 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--file-id", type=int, help="单文件 mode (e.g. --file-id 42)")
    target.add_argument("--folder-id", type=int, help="单 folder mode (e.g. --folder-id 3)")
    target.add_argument("--all", action="store_true", help="全部 mode (扫全表)")

    p.add_argument(
        "--apply",
        action="store_true",
        help="真写库 (默认 dry-run, 只统计不写)",
    )
    p.add_argument(
        "--no-fix-orphans",
        action="store_true",
        help="不修孤儿引用 (默认修, parent_id 指向不存在 ID → 置 NULL + path='/'",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="仅输出 JSON 格式 (默认人类可读 summary)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # 参数互斥检查
    if args.apply and args.file_id is None and args.folder_id is None and not args.all:
        # 不会到这里 (mutually_exclusive_group required), 但保险
        print("ERROR: --apply 必须配合 --file-id / --folder-id / --all", file=sys.stderr)
        return 2

    fix_orphans = not args.no_fix_orphans
    apply = args.apply

    # 提示
    if not apply:
        print(
            "🔍 DRY-RUN 模式 (不写库). 加 --apply 才真更新.",
            file=sys.stderr,
        )
    else:
        print(
            "⚠️  APPLY 模式 (真写库). 5 秒内 Ctrl+C 取消...",
            file=sys.stderr,
        )
        import time
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n❌ 用户取消", file=sys.stderr)
            return 1

    # 跑
    try:
        result = asyncio.run(run_backfill(
            file_id=args.file_id,
            folder_id=args.folder_id,
            do_all=args.all,
            apply=apply,
            fix_orphans=fix_orphans,
        ))
    except Exception as e:
        print(f"❌ backfill 失败: {e}", file=sys.stderr)
        return 1

    # 输出
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print()
        print("=" * 60)
        print(f"  target           = {result['target']}")
        print(f"  dry_run          = {result['dry_run']}")
        print(f"  updated          = {result.get('updated', 0)}")
        print(f"  orphans_fixed    = {result.get('orphans_fixed', 0)}")
        if "total_examined" in result:
            print(f"  total_examined   = {result['total_examined']}")
        print("=" * 60)
        if not apply:
            print("  (DRY-RUN: 未写库. 跑 --apply 真更新)")
        else:
            print("  ✅ 真写库完成")

    return 0


if __name__ == "__main__":
    sys.exit(main())
