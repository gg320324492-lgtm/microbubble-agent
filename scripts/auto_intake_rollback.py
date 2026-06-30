#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W5 T5.3 - Celery 7 天 rollback task (每天 3:30 跑)

逻辑:
  1. 查询 knowledge 表 source_type='auto_expansion' AND created_at < NOW() - 7 days
  2. 同时查 backups/auto_intake/ 最新备份, 验证 KB ID 映射
  3. 删除 7 天前入库的 auto_expansion 条目
  4. 输出 rollback 报告
"""
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

ROLLBACK_DAYS = 7
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "microbubble2026")
DB_NAME = os.environ.get("DB_NAME", "microbubble")

BACKUP_DIR = Path("backups/auto_intake")


def connect():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
                            password=DB_PASS, dbname=DB_NAME)


def find_rollback_candidates(cur) -> list[dict]:
    """查询 7 天前入库的 auto_expansion 条目"""
    cur.execute("""
        SELECT id, title, source_type, created_at
        FROM knowledge
        WHERE source_type = 'auto_expansion'
          AND created_at < NOW() - INTERVAL '%s days'
        ORDER BY created_at
    """, (ROLLBACK_DAYS,))
    return cur.fetchall()


def rollback_entries(cur, ids: list[int]) -> int:
    """物理删除 (production 实际可改为 UPDATE is_active=False)"""
    if not ids:
        return 0
    cur.execute("DELETE FROM knowledge WHERE id = ANY(%s)", (ids,))
    return cur.rowcount


def match_backups(entries: list[dict]) -> dict:
    """在 backups/auto_intake/ 找匹配 kb_id 的备份"""
    matches = {}
    if not BACKUP_DIR.exists():
        return matches
    for backup_path in BACKUP_DIR.glob("candidates_*.json"):
        try:
            data = json.loads(backup_path.read_text(encoding="utf-8"))
            backup_ids = {c.get("qa_id") for c in data if c.get("qa_id")}
            for entry in entries:
                if f"qa:{entry['id']}" in backup_ids or str(entry["id"]) in backup_ids:
                    matches[entry["id"]] = str(backup_path)
        except Exception:
            pass
    return matches


def main():
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print(f"[auto_intake_rollback] 开始 ({datetime.now().isoformat()})")
    print(f"  ROLLBACK_DAYS = {ROLLBACK_DAYS}")

    candidates = find_rollback_candidates(cur)
    print(f"  候选 rollback 条目: {len(candidates)} 条")

    if not candidates:
        print("  无候选, 跳过")
        cur.close()
        conn.close()
        return 0

    backup_matches = match_backups(candidates)
    print(f"  匹配备份: {len(backup_matches)}/{len(candidates)}")

    ids = [e["id"] for e in candidates]
    deleted = rollback_entries(cur, ids)
    conn.commit()
    print(f"  ✓ 删除 {deleted} 条")

    # 输出报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "rollback_days": ROLLBACK_DAYS,
        "candidates_count": len(candidates),
        "deleted_count": deleted,
        "backup_match_count": len(backup_matches),
        "entries": [
            {**dict(e), "created_at": str(e["created_at"])}
            for e in candidates
        ],
    }
    report_path = Path(f"data/auto_intake_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  报告 → {report_path}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
