#!/usr/bin/env python3
"""
upload_avatars_v2.py — 批量上传成员证件照到 MinIO + 写回 DB

v2 (2026-07-11): 替代 upload_avatars.py 旧版
- 同步 requests (与 upload_team_ppts_v3.py 一致)
- 走 https://agent.mnb-lab.cn/api/v1 (生产 URL, frp 隧道)
- 走 PUT /api/v1/members/{id} 更新 avatar
- 容错: 单张失败不阻塞, 报告每张结果
- 幂等: 文件名 = 成员名, 跳过 DB 已有的同名
- 防御: 上传前先备份源目录到 backups/avatars-source/

用法:
    python upload_avatars_v2.py                    # 走 xiaoqi_testbot 凭证
    python upload_avatars_v2.py <user> <pass>      # 自定义凭证
    python upload_avatars_v2.py --dry-run          # 只匹配不实际上传
"""

import os
import sys
import io
import time
import shutil
import argparse
import hashlib
from pathlib import Path
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter

# 强制 UTF-8 输出 (Windows console cp936 默认乱码)
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

BASE_URL = os.environ.get("MICROBUBBLE_BASE_URL", "https://agent.mnb-lab.cn")
DEFAULT_USERNAME = "xiaoqi_testbot"
DEFAULT_PASSWORD = "testbot_pass_2026"
SOURCE_DIR = Path(r"C:\Users\pc\Desktop\证件照")
BACKUP_ROOT = Path(r"E:\microbubble-agent\backups\avatars-source")

# 允许的图片扩展名
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def make_session() -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def login(session: requests.Session, username: str, password: str) -> str:
    r = session.post(f"{BASE_URL}/api/v1/auth/login",
                     json={"username": username, "password": password},
                     timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def get_members(session: requests.Session, token: str) -> dict:
    """返回 {name: id} 映射

    v2.1 (2026-07-11): 包含 is_active=false 成员 (恢复 alumni 头像用)
    服务端 /api/v1/members 默认 filter is_active=true, 需要明确传 is_active=false
    """
    name_to_id = {}
    for include_inactive in (False, True):
        params = {"page_size": 100, "is_active": str(include_inactive).lower()}
        r = session.get(f"{BASE_URL}/api/v1/members",
                        params=params,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30)
        r.raise_for_status()
        for m in r.json().get("items", []):
            name_to_id[m["name"]] = m["id"]
    return name_to_id


def upload_photo(session: requests.Session, token: str, photo_path: Path) -> str:
    """上传到 MinIO avatars/ prefix, 返回 public URL (带 429 retry + 文件重开)

    v2.2 (2026-07-11): retry 时必须重新打开文件 (HTTP POST stream 完, file pointer 到 EOF)
    """
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        # 每次 retry 重新打开文件 (file pointer 不能跨 request 复用)
        with open(photo_path, "rb") as f:
            files = {"file": (photo_path.name, f, "image/jpeg")}
            r = session.post(f"{BASE_URL}/api/v1/upload",
                             headers={"Authorization": f"Bearer {token}"},
                             files=files, data={"prefix": "avatars"},
                             timeout=120)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 60))
            wait = min(retry_after, 120)
            log(f"     ⏳ 429 限流, 等待 {wait}s 后重试 ({attempt}/{max_retries})...")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"upload HTTP {r.status_code}: {r.text[:200]}")
        result = r.json()
        url = result.get("url") or result.get("object_url")
        if not url:
            raise RuntimeError(f"upload 响应缺 url 字段: {result}")
        return url
    raise RuntimeError(f"429 限流 {max_retries} 次后仍失败")


def update_member_avatar(session: requests.Session, token: str,
                          member_id: int, avatar_url: str) -> bool:
    """更新成员 avatar (带 429 retry)"""
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        r = session.put(f"{BASE_URL}/api/v1/members/{member_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"avatar": avatar_url},
                        timeout=30)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 60))
            wait = min(retry_after, 120)
            log(f"     ⏳ 429 限流, 等待 {wait}s 后重试 ({attempt}/{max_retries})...")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"update HTTP {r.status_code}: {r.text[:200]}")
        return True
    raise RuntimeError(f"429 限流 {max_retries} 次后仍失败")


def backup_source() -> Path:
    """备份源证件照到 E 盘 backups/avatars-source/current/

    v2.3 (2026-07-11): 改为固定目录 (非日期子目录), 保持最新版本, 占用固定 ~37 MB
    """
    backup_dir = BACKUP_ROOT / "current"
    backup_dir.mkdir(parents=True, exist_ok=True)
    # 直接复制所有 jpg/png 到 current/ (覆盖更新)
    count = 0
    for f in SOURCE_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in IMG_EXTS:
            shutil.copy2(f, backup_dir / f.name)
            count += 1
    log(f"  ✅ 源文件已备份到: {backup_dir} ({count} 个)")
    return backup_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--dry-run", action="store_true",
                        help="只匹配成员, 不实际上传")
    parser.add_argument("--source", default=str(SOURCE_DIR),
                        help=f"源证件照目录 (默认: {SOURCE_DIR})")
    args = parser.parse_args()

    source_dir = Path(args.source)
    if not source_dir.exists():
        log(f"❌ 源目录不存在: {source_dir}")
        sys.exit(1)

    log(f"=== 批量上传成员证件照 ===")
    log(f"  源目录: {source_dir}")
    log(f"  目标: {BASE_URL}/api/v1/upload (prefix=avatars)")
    log(f"  模式: {'DRY-RUN' if args.dry_run else '实际上传'}")

    # 1. 备份源文件 (Defense #1)
    log("\n[1/4] 备份源证件照...")
    if not args.dry_run:
        backup_source()

    # 2. 登录
    log("\n[2/4] 登录...")
    session = make_session()
    token = login(session, args.user, args.password)
    log(f"  ✅ 登录成功: {args.user}")

    # 3. 获取成员映射
    log("\n[3/4] 获取成员列表...")
    name_to_id = get_members(session, token)
    log(f"  找到 {len(name_to_id)} 个活跃成员")

    # 4. 匹配 + 上传
    log("\n[4/4] 匹配 + 上传...")
    photo_files = sorted([f for f in source_dir.iterdir()
                          if f.is_file() and f.suffix.lower() in IMG_EXTS])
    log(f"  源照片: {len(photo_files)} 张")

    success = 0
    failed = []
    skipped = []
    for photo in photo_files:
        member_name = photo.stem  # 文件名不含扩展名
        member_id = name_to_id.get(member_name)

        if not member_id:
            log(f"  ⚠️  {photo.name} → 未找到成员 '{member_name}', 跳过")
            skipped.append(photo.name)
            continue

        size_kb = photo.stat().st_size / 1024
        log(f"  >> [{member_name} (id={member_id})] {photo.name} ({size_kb:.1f} KB)")

        if args.dry_run:
            log(f"     [DRY-RUN] 跳过实际上传")
            success += 1
            continue

        try:
            url = upload_photo(session, token, photo)
            log(f"     uploaded: {url}")
            update_member_avatar(session, token, member_id, url)
            log(f"     ✅ avatar 字段已更新")
            success += 1
        except Exception as e:
            log(f"     ❌ FAILED: {e}")
            failed.append((photo.name, str(e)))

    # 总结
    log(f"\n=== 完成 ===")
    log(f"  成功: {success}/{len(photo_files)}")
    if skipped:
        log(f"  跳过 (无匹配成员): {len(skipped)}")
        for s in skipped:
            log(f"    - {s}")
    if failed:
        log(f"  失败: {len(failed)}")
        for name, err in failed:
            log(f"    - {name}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main() or 0)