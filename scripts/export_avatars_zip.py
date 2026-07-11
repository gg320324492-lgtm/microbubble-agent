#!/usr/bin/env python3
"""
export_avatars_zip.py — 一键打包所有成员头像为 zip (admin 自恢复工具)

v1 (2026-07-11) Defense #4:
根因: avatar 文件丢失后, 没有快速途径恢复
防御: admin 一键导出 全部 avatar + name 映射 → zip
      → 解压后跑 scripts/upload_avatars_v2.py 即可批量回填

输出:
    backups/avatars-export-<timestamp>.zip
    ├── 王天志.jpg
    ├── 赵航佳.jpg
    └── manifest.json (name → 源 URL 映射)

用法:
    python export_avatars_zip.py              # 打包当前所有 avatar
    python export_avatars_zip.py --output X   # 自定义输出路径
"""

import os
import sys
import io
import json
import argparse
import zipfile
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass


def query_members_with_avatars() -> list[dict]:
    sql = (
        "SELECT id, name, avatar FROM members "
        "WHERE avatar IS NOT NULL AND avatar != '' "
        "ORDER BY id;"
    )
    cmd = [
        "docker", "exec", "microbubble-agent-db-1",
        "psql", "-U", "postgres", "-d", "microbubble",
        "-tAF", "|", "-c", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"psql 失败: {result.stderr.decode('utf-8', errors='replace')}")

    members = []
    for line in result.stdout.decode("utf-8", errors="replace").strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            members.append({
                "id": int(parts[0]),
                "name": parts[1],
                "avatar": parts[2],
            })
    return members


def download_avatar(url: str, timeout: int = 30) -> bytes | None:
    """下载头像 bytes"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "export_avatars_zip/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"  ⚠️  下载失败 {url}: {e}", file=sys.stderr)
        return None


def ext_from_url(url: str) -> str:
    """从 URL 推断扩展名 (默认 .jpg)"""
    path = urllib.parse.urlparse(url).path
    suffix = Path(path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".gif"} else ".jpg"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="输出 zip 路径 (默认 backups/avatars-export-<ts>.zip)")
    parser.add_argument("--include-inactive", action="store_true", help="包含 is_active=false 成员")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = Path(rf"E:\microbubble-agent\backups\avatars-export-{ts}.zip")
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"=== Avatar ZIP 导出 ===")
    print(f"  输出: {output_path}")

    members = query_members_with_avatars()
    print(f"  找到 {len(members)} 个有头像的成员")

    manifest = {
        "exported_at": datetime.now().isoformat(),
        "total": len(members),
        "members": [],
    }

    success = 0
    failed = []
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for m in members:
            print(f"  >> {m['name']} (id={m['id']})")
            data = download_avatar(m["avatar"])
            if not data:
                failed.append(m["name"])
                continue

            ext = ext_from_url(m["avatar"])
            zip_name = f"{m['name']}{ext}"
            zf.writestr(zip_name, data)
            manifest["members"].append({
                "id": m["id"],
                "name": m["name"],
                "filename": zip_name,
                "source_url": m["avatar"],
            })
            success += 1

        # 写 manifest
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    print(f"\n=== 完成 ===")
    print(f"  成功: {success}/{len(members)}")
    print(f"  输出: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
    if failed:
        print(f"  失败: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main() or 0)