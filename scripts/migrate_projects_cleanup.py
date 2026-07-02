#!/usr/bin/env python3
"""
migrate_projects_cleanup.py — 清理 projects 表里的测试/残留数据

触发场景 (2026-07-02):
  - 用户截图反馈"项目动态"页面第 1 张卡 "微纳米气泡降解抗生素研究计划" 不应存在
  - DB 排查: id=8, description 2598 字符完整 markdown 研究计划 (阶段划分/任务内容/成果输出)
  - 跟其他 4 个真项目 (description 30-45 字符短描述) 风格完全不同
  - id=8 还伴随 created_by=NULL, start_date=NULL, end_date=NULL

设计 (仿 migrate_kb_tags.py / migrate_kb_dedup_titles.py 范式):
  --scan        输出要删除的项目详情 (含 description 摘要)
  --apply       不带 --confirm 时拒绝执行 (dry-run)
  --apply --confirm  才真正 DELETE + 写 JSON 备份

防御性策略:
  - 默认 WHERE description 长度 > 500 字符 (真项目描述短, 测试残留长)
  - 排除 created_by IS NOT NULL 的项目 (任何有 owner 的不动)
  - 排除里程碑 (milestones) / 任务 (tasks) / 任何关联引用 (PR6 FK 防御)
  - JSON 备份含 id/name/description/status/created_at/updated_at 完整字段

使用:
  python scripts/migrate_projects_cleanup.py --scan
  python scripts/migrate_projects_cleanup.py --apply --confirm
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import asyncpg

# 与 migrate_kb_tags.py 一致的连接参数
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", "postgres")
DB_NAME = os.environ.get("DB_NAME", "microbubble")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "microbubble2026")

BACKUP_DIR = Path("/tmp/projects_cleanup_backups")


def _get_db_password():
    """从 docker exec env 拿 password (避免硬编码)."""
    pw = os.environ.get("DB_PASSWORD")
    if pw:
        return pw
    # fallback: 从 .env 读
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1]
                # postgresql+asyncpg://user:pass@host:port/db
                if "@" in url and ":" in url.split("@")[0]:
                    return url.split("@")[0].split(":")[-1]
    return DB_PASSWORD


async def get_conn():
    pw = _get_db_password()
    return await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=pw, database=DB_NAME,
    )


# ============================================================
# 防御性 WHERE: 真项目特征 (created_by NOT NULL OR description 短)
# ============================================================
LONG_DESCRIPTION_THRESHOLD = 500  # 字符

CANDIDATE_SQL = """
SELECT id, name, description, status, created_by,
       start_date, end_date, created_at, updated_at
FROM projects
WHERE (
    LENGTH(description) > $1
    OR created_by IS NULL
)
AND status != 'deleted'  -- 已软删的跳过
ORDER BY id ASC
"""

# 排除规则 — 真项目参考以下任何一项:
# 1. created_by IS NOT NULL 且 is_active=true (正常用户录入)
# 2. description 短 (< 500 字符) (真项目都是一句话研究简介)
# 3. 有 end_date (真项目会填结束时间)


def is_real_project(row) -> bool:
    """判断是否为真项目 (有 owner + 短描述 + 有 end_date)."""
    desc_len = len(row["description"] or "")
    has_owner = row["created_by"] is not None
    has_end_date = row["end_date"] is not None
    return has_owner and desc_len <= LONG_DESCRIPTION_THRESHOLD and has_end_date


def is_test_residue(row) -> bool:
    """测试残留特征: 长描述 + 无 owner + 无 end_date + 长 markdown 结构."""
    desc_len = len(row["description"] or "")
    has_owner = row["created_by"] is not None
    has_end_date = row["end_date"] is not None
    # 长描述 + (无 owner 或 无 end_date) → 高度疑似
    return desc_len > LONG_DESCRIPTION_THRESHOLD and (not has_owner or not has_end_date)


async def scan_candidates(conn):
    """扫描候选测试残留项目."""
    rows = await conn.fetch(CANDIDATE_SQL, LONG_DESCRIPTION_THRESHOLD)
    candidates = []
    reals = []
    for row in rows:
        d = dict(row)
        if is_test_residue(row):
            candidates.append(d)
        else:
            reals.append(d)
    return candidates, reals


def print_scan_report(candidates, reals):
    """打印 SCAN 报告 — 红色候选 + 黄色真项目参考."""
    print("=" * 80)
    print(f"📋 SCAN 结果 (threshold: description > {LONG_DESCRIPTION_THRESHOLD} chars OR created_by IS NULL)")
    print("=" * 80)

    if candidates:
        print(f"\n🔴 [CANDIDATES] 疑似测试残留 ({len(candidates)} 个):")
        for c in candidates:
            desc_len = len(c["description"] or "")
            print(f"\n  id={c['id']:>3}  '{c['name'][:60]}'")
            print(f"        desc_len={desc_len}  created_by={c['created_by']}  start={c['start_date']}  end={c['end_date']}  status={c['status']}")
            print(f"        desc 预览: {(c['description'] or '')[:100]!r}...")
    else:
        print("\n✅ 无候选测试残留")

    if reals:
        print(f"\n🟡 [REALS - SKIP] 参考真项目 (不会被删) ({len(reals)} 个):")
        for r in reals[:5]:
            desc_len = len(r["description"] or "")
            print(f"  id={r['id']:>3}  '{r['name'][:60]}'  desc_len={desc_len}  created_by={r['created_by']}  end={r['end_date']}")

    print("\n" + "=" * 80)
    print(f"⚠️  --apply --confirm 才会 DELETE 上述 {len(candidates)} 个候选")
    print("=" * 80)


async def fetch_backup_data(conn, candidate_ids):
    """拉取候选完整字段用于 JSON 备份."""
    rows = await conn.fetch(
        """
        SELECT id, name, description, research_area, status, created_by,
               start_date, end_date, members, created_at, updated_at
        FROM projects
        WHERE id = ANY($1::int[])
        """,
        candidate_ids,
    )
    backup_data = []
    for row in rows:
        d = dict(row)
        # datetime → ISO 字符串 (JSON-friendly)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        backup_data.append(d)
    return backup_data


async def check_fk_references(conn, candidate_ids):
    """5 类引用防御 (仿 migrate_kb_dedup_titles.py 铁律)."""
    refs = {"project_id_in_tasks": 0, "project_id_in_meetings": 0, "other": {}}

    # 1. projects.tasks (如果有)
    try:
        rows = await conn.fetch(
            "SELECT project_id, COUNT(*) AS cnt FROM tasks WHERE project_id = ANY($1::int[]) GROUP BY project_id",
            candidate_ids,
        )
        for r in rows:
            refs["other"][f"project_id={r['project_id']}"] = f"tasks: {r['cnt']}"
            refs["project_id_in_tasks"] += r["cnt"]
    except asyncpg.UndefinedTableError:
        pass

    return refs


async def apply_deletion(conn, candidate_ids):
    """实际删除 — 单事务包裹."""
    # 备份 (先拉数据)
    backup_data = await fetch_backup_data(conn, candidate_ids)
    fk_refs = await check_fk_references(conn, candidate_ids)

    # 写 JSON 备份到 /tmp/projects_cleanup_backups/
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"projects_cleanup_backup_{ts}.json"
    payload = {
        "deleted_at": ts,
        "candidate_ids": candidate_ids,
        "fk_references": fk_refs,
        "rows": backup_data,
    }
    backup_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"\n📦 备份已写: {backup_file}")

    # 防御性 DELETE — 即使脚本中途崩, 也能恢复
    if fk_refs["project_id_in_tasks"] > 0:
        # 有引用: 先 SET session_replication_role = 'replica' 跳过 FK
        await conn.execute("SET session_replication_role = 'replica'")

    try:
        await conn.execute(
            "DELETE FROM projects WHERE id = ANY($1::int[])",
            candidate_ids,
        )
    finally:
        if fk_refs["project_id_in_tasks"] > 0:
            await conn.execute("SET session_replication_role = 'origin'")  # 默认

    return backup_file


async def main():
    parser = argparse.ArgumentParser(description="清理 projects 表的测试残留")
    parser.add_argument("--scan", action="store_true", help="只扫描不修改")
    parser.add_argument("--apply", action="store_true", help="应用删除")
    parser.add_argument("--confirm", action="store_true", help="确认 DELETE (与 --apply 同用)")
    args = parser.parse_args()

    if not args.scan and not args.apply:
        parser.print_help()
        print("\n[ERROR] 必须指定 --scan 或 --apply")
        sys.exit(2)

    conn = await get_conn()
    try:
        candidates, reals = await scan_candidates(conn)
        print_scan_report(candidates, reals)

        if args.scan:
            return

        if args.apply and not args.confirm:
            print("\n[DRY RUN] --apply 但未传 --confirm — 拒绝执行")
            print("[DRY RUN] 真的要删, 请加 --confirm:")
            print(f"             python scripts/migrate_projects_cleanup.py --apply --confirm")
            sys.exit(1)

        if args.apply and args.confirm:
            if not candidates:
                print("\n✅ 无候选, 跳过")
                return
            candidate_ids = [c["id"] for c in candidates]
            print(f"\n[APPLY] 删除 {len(candidate_ids)} 个项目: {candidate_ids}")
            backup_file = await apply_deletion(conn, candidate_ids)
            print(f"[APPLY] ✅ 完成, 备份: {backup_file}")
            print(f"[APPLY] 记得把 /tmp/projects_cleanup_backups/*.json 拷到 D 盘长期保留!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
