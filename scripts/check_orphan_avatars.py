#!/usr/bin/env python3
"""
check_orphan_avatars.py — 检测所有成员 avatar URL 是否有 404 (orphan)

v1 (2026-07-11) Defense #3:
根因: 2026-07-11 bucket 被 wipe 后 25 个头像 URL 全部 404, 但没人发现
防御: 每天跑一次, HEAD-check 所有 members.avatar URL, 报告 404 列表
      → 一旦 bucket 内容丢失, 第二天就能发现并触发自动恢复 (from backup_minio_daily)

零依赖: Python 3.7+ stdlib only (urllib + psycopg2 if available, else psycopg via docker)

用法:
    python check_orphan_avatars.py             # 报告 orphan avatars
    python check_orphan_avatars.py --json     # JSON 格式输出 (供后端调用)
    python check_orphan_avatars.py --alert    # 发现 orphan 时 console 红字 + 非零 exit
"""

import os
import sys
import io
import json
import argparse
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass


def query_db_members_with_avatars() -> list[dict]:
    """通过 docker exec psql 拿所有有 avatar 的成员 (避免 psycopg2 依赖)"""
    sql = (
        "SELECT id, name, avatar FROM members "
        "WHERE avatar IS NOT NULL AND avatar != '' "
        "ORDER BY id;"
    )
    cmd = [
        "docker", "exec", "microbubble-agent-db-1",
        "psql", "-U", "postgres", "-d", "microbubble",
        "-tAF", "|",  # -t (tuples only) -A (unaligned) -F (separator) "|"
        "-c", sql,
    ]
    # 用 utf-8 解码 (Windows 默认 gbk 会把中文搞坏)
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"psql 失败: {result.stderr.decode('utf-8', errors='replace')}")

    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    members = []
    for line in stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        members.append({
            "id": int(parts[0]),
            "name": parts[1],
            "avatar": parts[2],
        })
    return members


def head_check_avatar(url: str, timeout: int = 10) -> tuple[bool, int, str]:
    """HEAD 检查 URL, 返回 (is_orphan, http_code, reason)"""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (False, resp.status, "OK")
    except urllib.error.HTTPError as e:
        return (e.code in (404, 403), e.code, str(e.reason))
    except urllib.error.URLError as e:
        return (False, 0, f"URL error: {e.reason}")
    except Exception as e:
        return (False, 0, f"Exception: {type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--alert", action="store_true", help="发现 orphan 时非零 exit")
    parser.add_argument("--timeout", type=int, default=10, help="HEAD 超时秒数")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        members = query_db_members_with_avatars()
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"[{ts}] ❌ DB 查询失败: {e}", file=sys.stderr)
        sys.exit(2)

    if not args.json:
        print(f"[{ts}] === Avatar URL 健康检查 ===")
        print(f"  待检查: {len(members)} 个成员")

    results = []
    orphans = []
    for m in members:
        is_orphan, code, reason = head_check_avatar(m["avatar"], timeout=args.timeout)
        results.append({
            **m,
            "http_code": code,
            "is_orphan": is_orphan,
            "reason": reason,
        })
        if is_orphan:
            orphans.append(m)

    if args.json:
        print(json.dumps({
            "checked_at": ts,
            "total": len(members),
            "orphan_count": len(orphans),
            "orphans": orphans,
            "details": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"  检查完成: {len(members)} 个")
        print(f"  Orphan (404): {len(orphans)} 个")
        if orphans:
            print()
            print(f"  ⚠️  以下成员头像 URL 已失效:")
            for m in orphans:
                print(f"    [id={m['id']}] {m['name']}: {m['avatar']}")
            print()
            print(f"  💡 恢复建议:")
            print(f"     1. 检查 MinIO bucket 是否有该文件")
            print(f"     2. 从 backups/minio-daily/<昨天>/ 恢复")
            print(f"     3. 或重新跑 scripts/upload_avatars_v2.py")
        else:
            print(f"  ✅ 所有头像 URL 健康")

    if args.alert and orphans:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main() or 0)