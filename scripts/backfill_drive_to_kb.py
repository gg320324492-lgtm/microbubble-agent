"""网盘存量文件批量入库脚本 — 把历史 drive 文件一次性补进知识库 RAG (2026-09-05)

背景:
  "网盘文件默认入库" 上线后, 新上传文件自动进 RAG; 但上线前已存在的 drive 文件
  (storage_mode='drive') 没有对应 kb 条目, 需要本脚本一次性回填。
  复用 DriveToKBService (全格式分级提取 + 元数据兜底 + analyze_knowledge_task)。

用法 (容器内跑, 与 reassign_member_rows.py 同范式):
  # 1) dry-run 清点 (默认, 不动库)
  $ docker cp scripts/backfill_drive_to_kb.py microbubble-agent-app-1:/tmp/
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/backfill_drive_to_kb.py

  # 2) 真入库
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/backfill_drive_to_kb.py --confirm

  # 可选: --folder 7 只回填某文件夹; --limit 50 分批; --include-ingested 连已入库的也重刷
防御:
  - 默认 dry-run, 无 --confirm 不写库
  - 逐文件 best-effort, 单个失败记录 error 继续 (与 ingest_team_files 口径一致)
  - 已入库 (meta.drive_source_file_id 命中) 默认跳过, 幂等可重跑
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.models.knowledge import Knowledge  # noqa: E402


async def _iter_target_rows(folder_id: int | None):
    from app.core.database import async_session

    async with async_session() as db:
        stmt = (
            select(Knowledge)
            .where(
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
                Knowledge.is_latest.is_(True),
            )
            .order_by(Knowledge.id)
        )
        if folder_id is not None:
            stmt = stmt.where(Knowledge.folder_id == folder_id)
        result = await db.execute(stmt)
        rows = list(result.scalars().all())

        converted = set()
        if rows:
            res = await db.execute(
                select(Knowledge.meta["drive_source_file_id"].astext).where(
                    Knowledge.storage_mode == "kb",
                    Knowledge.deleted_at.is_(None),
                    Knowledge.meta["drive_source_file_id"].astext.in_(
                        [str(r.id) for r in rows]
                    ),
                )
            )
            converted = {int(v) for v in res.scalars().all() if v}
        return rows, converted


async def main(args: argparse.Namespace) -> int:
    rows, converted = await _iter_target_rows(args.folder)

    targets = [
        r for r in rows
        if args.include_ingested or r.id not in converted
    ]
    if args.limit and args.limit > 0:
        targets = targets[: args.limit]

    skipped = len(rows) - len(targets)
    print(f"[backfill] drive 文件总数={len(rows)} 已入库={len(converted)} "
          f"待回填={len(targets)} (skip={skipped}, limit={args.limit or 'none'})")

    if not targets:
        print("[backfill] 没有待回填文件, 完成")
        return 0

    if not args.confirm:
        for r in targets[:20]:
            print(f"  - id={r.id} {r.file_name!r} ({r.file_size or 0}B) folder={r.folder_id}")
        if len(targets) > 20:
            print(f"  ... 等共 {len(targets)} 个")
        print("[backfill] dry-run 结束 (加 --confirm 真正入库)")
        return 0

    from app.core.database import async_session
    from app.services.drive_to_kb_service import DriveToKBService, DriveToKBError

    ingested = failed = 0
    errors = []
    async with async_session() as db:
        svc = DriveToKBService(db)
        for i, row in enumerate(targets, 1):
            try:
                res = await svc.ingest_drive_file(row.id)
                ingested += 1
                print(f"  [{i}/{len(targets)}] id={row.id} → knowledge_id="
                      f"{res['knowledge_id']} mode={res.get('ingest_mode')} "
                      f"chars={res.get('content_length')}")
            except (DriveToKBError, Exception) as e:  # noqa: BLE001 — best-effort
                failed += 1
                errors.append({"file_id": row.id, "error": str(e)[:160]})
                print(f"  [{i}/{len(targets)}] id={row.id} 失败: {str(e)[:120]}")

    print(f"[backfill] 完成: 入库 {ingested} / 失败 {failed}")
    if errors:
        print("[backfill] 失败明细 (前 20):")
        for e in errors[:20]:
            print(f"  - file_id={e['file_id']}: {e['error']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="网盘存量文件批量入库知识库 RAG")
    parser.add_argument("--confirm", action="store_true", help="真正入库 (默认 dry-run)")
    parser.add_argument("--folder", type=int, default=None, help="只回填该 folder id 下的文件")
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 个 (分批用)")
    parser.add_argument(
        "--include-ingested", action="store_true",
        help="已入库的也重刷 (reingest, 版本内容刷新用)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args)))
