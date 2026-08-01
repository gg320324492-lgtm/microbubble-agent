#!/usr/bin/env python3
"""
全库扫描失效 /minio/ 图片引用 (W99 +20 派工 v10 段 2.1)
- 遍历所有 knowledge.id
- 对每条 content 正则提取 /minio/<url>.(png|jpg|jpeg|gif|webp)
- 并发 HEAD/stat 请求 minio 验证 (限速 10 QPS)
- 输出 JSON 报告 + 标记 candidates: knowledge.meta["broken_images"]

用法:
  docker cp scripts/audit_broken_image_refs.py microbubble-agent-app-1:/tmp/
  docker exec -e PYTHONPATH=/app microbubble-agent-app-1 python /tmp/audit_broken_image_refs.py \
      --report /tmp/audit_report.json --mark-broken

如果 --mark-broken 开启, 会把每条 entry 的 broken_images 列表写到
knowledge.meta 中 (不删 content, 仅 metadata 标记, 主拍决策后再删).
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core.database import get_db
from app.models.knowledge import Knowledge
from minio import Minio
from minio.error import S3Error

URL_RE = re.compile(
    r'/minio/[^\s"\'\\`)]+\.(?:png|jpg|jpeg|gif|webp)',
    re.IGNORECASE,
)

QPS_LIMIT = 10  # 段 2.1 限速


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit broken /minio/ image references in knowledge.content")
    p.add_argument("--report", default="/tmp/audit_broken_image_refs.json", help="output JSON path")
    p.add_argument("--mark-broken", action="store_true", help="write broken_images into knowledge.meta")
    p.add_argument("--only-ids", default="", help="comma-separated ids to scan (default = all)")
    return p.parse_args()


def extract_urls(content: str) -> list[str]:
    if not content:
        return []
    seen = set()
    out = []
    for m in URL_RE.finditer(content):
        u = m.group(0)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def collect_knowledge_rows(only_ids: list[int]):
    async for db in get_db():
        if only_ids:
            stmt = select(Knowledge.id, Knowledge.content, Knowledge.meta).where(Knowledge.id.in_(only_ids))
        else:
            stmt = select(Knowledge.id, Knowledge.content, Knowledge.meta)
        result = await db.execute(stmt)
        rows = result.fetchall()
        return db, rows
    return None, []


def check_one(client: Minio, url: str) -> str:
    """Return 'EXISTS', 'NoSuchKey', 'Forbidden', 'Error', or similar."""
    obj = url[len("/minio/"):] if url.startswith("/minio/") else url
    try:
        client.stat_object(settings.MINIO_BUCKET, obj)
        return "EXISTS"
    except S3Error as e:
        return e.code or "S3Error"
    except Exception as e:  # noqa
        return f"Error:{type(e).__name__}"


async def main_async():
    args = parse_args()
    only_ids = [int(s) for s in args.only_ids.split(",") if s.strip()]

    db, rows = await collect_knowledge_rows(only_ids)
    if db is None:
        print("ERROR: failed to acquire db session", file=sys.stderr)
        return 2

    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )

    sem = asyncio.Semaphore(QPS_LIMIT)
    started = time.time()

    async def check(kid, url):
        async with sem:
            st = await asyncio.to_thread(check_one, client, url)
            return kid, url, st

    tasks = []
    for kid, content, _meta in rows:
        for u in extract_urls(content or ""):
            tasks.append(check(kid, u))

    results = await asyncio.gather(*tasks)
    elapsed = time.time() - started

    per_entry: dict[int, dict] = {}
    status_count: dict[str, int] = {}
    for kid, url, st in results:
        status_count[st] = status_count.get(st, 0) + 1
        e = per_entry.setdefault(kid, {"knowledge_id": kid, "total_refs": 0, "broken_refs": [], "ok_refs": []})
        e["total_refs"] += 1
        if st == "EXISTS":
            e["ok_refs"].append(url)
        else:
            e["broken_refs"].append({"url": url, "status": st})

    broken_kids = sorted([k for k, v in per_entry.items() if v["broken_refs"]])

    report = {
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_knowledge_rows": len(rows),
        "entries_with_minio_refs": len(per_entry),
        "entries_with_broken_refs": len(broken_kids),
        "total_url_refs_scanned": len(results),
        "url_status_distribution": status_count,
        "elapsed_seconds": round(elapsed, 3),
        "qps_limit": QPS_LIMIT,
        "only_ids": only_ids,
        "broken_knowledge_ids": broken_kids,
        "per_entry": [per_entry[k] for k in sorted(per_entry)],
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Report written: {args.report}")
    print(f"Total knowledge rows: {len(rows)}")
    print(f"Entries with /minio/ refs: {len(per_entry)}")
    print(f"Entries with broken refs: {len(broken_kids)} → {broken_kids}")
    print(f"Total URL refs scanned: {len(results)}")
    print(f"Status distribution: {status_count}")
    print(f"Elapsed: {elapsed:.2f}s ({len(results)/max(elapsed,0.001):.1f} req/s)")

    if args.mark_broken:
        written = 0
        for kid in broken_kids:
            k = await db.get(Knowledge, kid)
            if k is None:
                continue
            meta = dict(k.meta or {})
            broken = list(meta.get("broken_images") or [])
            for r in per_entry[kid]["broken_refs"]:
                entry = {"url": r["url"], "status": r["status"], "audited_at": report["scanned_at"]}
                if entry not in broken:
                    broken.append(entry)
            meta["broken_images"] = broken
            meta["broken_images_audit"] = {
                "scanned_at": report["scanned_at"],
                "count": len(broken),
            }
            k.meta = meta
            flag_modified(k, "meta")
            written += 1
        await db.commit()
        print(f"Marked {written} entries with broken_images in meta")

    return 0


def main():
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
