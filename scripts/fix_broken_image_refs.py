#!/usr/bin/env python3
"""
轻量 fix 脚本: 仅做 metadata 标记 + 可选 content 软删 (W99 +20 段 2.3)

执行顺序:
  1. 读 audit 报告
  2. 标记 meta["broken_images"]
  3. (可选, --apply-soft-delete) 移除 content 里的 broken /minio/ 引用
  4. (可选, --apply-hard-delete) DELETE 整个 entry (主拍决策用, 默认 OFF)

不动 schema, 不动 alembic.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.models.knowledge import Knowledge


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--audit-report", default="/tmp/audit_report.json")
    p.add_argument("--apply-soft-delete", action="store_true",
                   help="removes /minio/... .png/jpg/jpeg/gif/webp refs from content")
    p.add_argument("--apply-hard-delete", action="store_true",
                   help="DELETE the broken entries from DB (DANGEROUS)")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would change but don't commit")
    return p.parse_args()


async def main_async():
    args = parse_args()
    report_path = Path(args.audit_report)
    if not report_path.exists():
        print(f"ERROR: {report_path} not found, run audit_broken_image_refs.py first", file=sys.stderr)
        return 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    broken_ids = report.get("broken_knowledge_ids") or []
    if not broken_ids:
        print("No broken entries in report, exiting.")
        return 0

    print(f"Broken entry ids: {broken_ids}")
    print(f"apply_soft_delete={args.apply_soft_delete} apply_hard_delete={args.apply_hard_delete} dry_run={args.dry_run}")

    if args.apply_hard_delete:
        print("HARD DELETE mode — this is destructive, aborting unless --i-know-what-im-doing flag is set")
        return 1  # 不允许裸跑

    async for db in get_db():
        for kid in broken_ids:
            k = await db.get(Knowledge, kid)
            if k is None:
                continue
            before_content = k.content or ""
            meta = dict(k.meta or {})
            bi_count = 0
            if args.apply_soft_delete:
                import re
                URL_RE = re.compile(r'/minio/[^\s"\'\\`)]+\.(?:png|jpg|jpeg|gif|webp)', re.IGNORECASE)
                # Strip both the markdown img syntax wrapper AND standalone refs
                # Approach: only strip the path, leave surrounding md intact
                removed = []
                def _strip(m):
                    removed.append(m.group(0))
                    return ""
                new_content = URL_RE.sub(_strip, before_content)
                # Also clean up orphan markdown: ![alt]()  → ''
                new_content = re.sub(r'!\[[^\]]*\]\(\s*\)', '', new_content)
                # Tidy double-blanks
                new_content = re.sub(r'\n{3,}', '\n\n', new_content).strip()
                bi_count = len(removed)
                if not args.dry_run:
                    k.content = new_content
                print(f"  k={kid} soft-delete {bi_count} broken refs from content (len {len(before_content)} -> {len(new_content) if not args.dry_run else 'preview'})")
            # Always update meta with broken_images list
            meta["broken_images"] = [
                {"url": r["url"], "status": r["status"],
                 "fixed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                 "fix_action": "soft_delete" if args.apply_soft_delete else "marked_only"}
                for r in (next((e["broken_refs"] for e in report["per_entry"] if e["knowledge_id"] == kid), []))
            ]
            meta["broken_images_audit"] = {
                "scanned_at": report.get("scanned_at"),
                "count": bi_count if args.apply_soft_delete else len(meta["broken_images"]),
            }
            if not args.dry_run:
                k.meta = meta
                flag_modified(k, "meta")
        if not args.dry_run and not args.dry_run:
            if args.apply_soft_delete or True:  # always commit meta update
                await db.commit()
                print("Committed.")
            else:
                await db.rollback()
        else:
            print("Dry-run, no commit.")
        break

    return 0


def main():
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
