#!/usr/bin/env python3
"""
clean_project_descriptions.py — 清洗 projects.description 字段的 LLM 原始输出

触发场景 (2026-07-15):
  - 用户反馈 /workspace?tab=projects 第 1/2 张卡 description 含 markdown 字符(#/**/##) + LLM 套路开场白
  - DB 排查: id=9/10 description 3338/4111 字符含完整 LLM 项目计划原始输出
  - 与 4 个真项目 (description 30-45 字符) 风格完全不同

范式 (仿 migrate_projects_cleanup.py 3 段式):
  --scan        列出所有 candidates (description > 280 字符 OR 含 markdown 标志)
  --apply       DRY RUN 报告 + BEFORE/AFTER 预览
  --apply --confirm  才真正 UPDATE (单事务 + JSON 备份)
  --by-id <id>  仅扫描指定项目 (默认所有)

清洗算法复用: app.utils.text_sanitize.sanitize_project_description
  (与 project_service.create_project 入库清洗前端 ProjectsPanel.vue 兜底共享一套逻辑)

使用:
  python scripts/clean_project_descriptions.py --scan
  python scripts/clean_project_descriptions.py --apply
  python scripts/clean_project_descriptions.py --apply --confirm
  python scripts/clean_project_descriptions.py --apply --confirm --by-id 9,10
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import asyncpg

# 引入共享清洗函数 (避免脚本 + 服务层两套实现不一致)
sys.path.insert(0, "/app")
from app.utils.text_sanitize import sanitize_project_description  # noqa: E402

# ============== DB connection (与 migrate_projects_cleanup.py 一致) ==============
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", "postgres")
DB_NAME = os.environ.get("DB_NAME", "microbubble")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "microbubble2026")

BACKUP_DIR = Path("/tmp/projects_desc_cleanup_backups")

# 长度阈值: 真项目描述都 ≤ 50 字, 超过 280 一律视为脏
LONG_DESCRIPTION_THRESHOLD = 280


def _get_db_password():
    pw = os.environ.get("DB_PASSWORD")
    if pw:
        return pw
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1]
                if "@" in url and ":" in url.split("@")[0]:
                    return url.split("@")[0].split(":")[-1]
    return DB_PASSWORD


async def get_conn():
    pw = _get_db_password()
    return await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=pw, database=DB_NAME,
    )


# ============== scan / apply ==============

CANDIDATE_SQL = """
SELECT id, name, description, created_at, updated_at
FROM projects
WHERE (
    LENGTH(description) > $1
    OR description ~ '(\n\\s*#+ |\\*\\*|---|好的[，,]\\s*非常荣幸|以下是.{0,20}计划)'
)
AND status != 'deleted'
ORDER BY id ASC
"""


async def scan_candidates(conn, ids_filter=None):
    """扫描候选脏 description 项目."""
    if ids_filter:
        rows = await conn.fetch(
            "SELECT id, name, description, created_at, updated_at "
            "FROM projects WHERE id = ANY($1::int[]) ORDER BY id ASC",
            ids_filter,
        )
    else:
        rows = await conn.fetch(CANDIDATE_SQL, LONG_DESCRIPTION_THRESHOLD)

    candidates = []
    for row in rows:
        d = dict(row)
        old_desc = d["description"] or ""
        new_desc = sanitize_project_description(old_desc)
        # datetime → ISO 字符串 (print + JSON friendly)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        d["_old_desc_len"] = len(old_desc)
        d["_new_desc_len"] = len(new_desc)
        d["_new_desc_preview"] = new_desc[:80] + ("..." if len(new_desc) > 80 else "")
        d["_changed"] = (old_desc != new_desc) and bool(new_desc)
        candidates.append(d)
    return candidates


def print_scan_report(candidates):
    print("=" * 80)
    print(f"📋 SCAN 结果 (threshold: description > {LONG_DESCRIPTION_THRESHOLD} chars OR 含 markdown)")
    print("=" * 80)

    if not candidates:
        print("\n✅ 无脏 description (无需清洗)")
        return

    print(f"\n🔴 [CANDIDATES] 待清洗 ({len(candidates)} 个):")
    for c in candidates:
        print(f"\n  id={c['id']:>3}  '{c['name'][:50]}'")
        print(f"        old_desc_len={c['_old_desc_len']:>5}  →  new_desc_len={c['_new_desc_len']:>3}")
        print(f"        new_preview: {c['_new_desc_preview']!r}")

    print("\n" + "=" * 80)
    changed_count = sum(1 for c in candidates if c["_changed"])
    print(f"⚠️  --apply --confirm 才会 UPDATE 这 {changed_count} 个项目的 description")
    print("=" * 80)


async def fetch_full_data(conn, ids):
    """拉取完整字段用于 JSON 备份."""
    rows = await conn.fetch(
        "SELECT id, name, description, research_area, status, created_by, "
        "start_date, end_date, members, created_at, updated_at "
        "FROM projects WHERE id = ANY($1::int[])",
        ids,
    )
    backup_data = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        backup_data.append(d)
    return backup_data


async def apply_clean(conn, candidates):
    """实际 UPDATE — 单事务包裹 + JSON 备份."""
    changed_ids = [c["id"] for c in candidates if c["_changed"]]
    if not changed_ids:
        print("\n✅ 无需 UPDATE")
        return None

    # 备份 (before)
    backup_data = await fetch_full_data(conn, changed_ids)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"project_desc_cleanup_{ts}.json"
    backup_file.write_text(
        json.dumps(
            {"cleaned_at": ts, "ids": changed_ids, "rows": backup_data},
            ensure_ascii=False, indent=2, default=str,
        )
    )

    # 逐行 UPDATE (不破坏其他字段)
    for c in candidates:
        if not c["_changed"]:
            continue
        new_desc = sanitize_project_description(c["description"] or "")
        await conn.execute(
            "UPDATE projects SET description = $1, updated_at = NOW() WHERE id = $2",
            new_desc, c["id"],
        )

    return backup_file


async def main():
    parser = argparse.ArgumentParser(description="清洗 projects.description 字段的 LLM 原始输出")
    parser.add_argument("--scan", action="store_true", help="只扫描不修改")
    parser.add_argument("--apply", action="store_true", help="应用清洗")
    parser.add_argument("--confirm", action="store_true", help="确认 UPDATE (与 --apply 同用)")
    parser.add_argument("--by-id", type=str, default=None,
                        help="逗号分隔的 id 列表 (默认所有 candidates)")
    args = parser.parse_args()

    if not args.scan and not args.apply:
        parser.print_help()
        print("\n[ERROR] 必须指定 --scan 或 --apply")
        sys.exit(2)

    ids_filter = None
    if args.by_id:
        try:
            ids_filter = [int(x) for x in args.by_id.split(",") if x.strip()]
        except ValueError:
            print(f"[ERROR] --by-id 格式错误: {args.by_id}", file=sys.stderr)
            sys.exit(2)

    conn = await get_conn()
    try:
        candidates = await scan_candidates(conn, ids_filter)
        print_scan_report(candidates)

        if args.scan:
            return

        if args.apply and not args.confirm:
            print("\n[DRY RUN] --apply 但未传 --confirm — 拒绝执行")
            print("[DRY RUN] 真要清, 请加 --confirm:")
            print("             python scripts/clean_project_descriptions.py --apply --confirm")
            sys.exit(1)

        if args.apply and args.confirm:
            backup_file = await apply_clean(conn, candidates)
            if backup_file:
                print(f"\n[APPLY] ✅ 清洗完成, 备份: {backup_file}")
                print(f"[APPLY] 记得把 /tmp/projects_desc_cleanup_backups/*.json 拷到 D 盘长期保留!")
            else:
                print("\n[APPLY] ✅ 无需清洗")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
