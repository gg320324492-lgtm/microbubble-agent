#!/usr/bin/env python3
"""
upload_team_ppts_v3.py — 补传 12 missing files 到 336 hierarchy

v3 (2026-07-11): 上传 12 个 desktop 有但 336 缺的文件
- 用 DB 直接查 existing (绕过 broken /files endpoint)
- 含 1 个 110MB root PPT (走 chunked upload)
- 11 个 sub-folder PPT (single endpoint)

12 missing 详情:
- (root) 2025.9.22.pptx (110MB, chunked)
- 吴孟铨/2025.4.21 研一 吴孟铨.pptx
- 李胜景/2026.2.8 研二 李胜景.pptx
- 杨慈/2023.06.24 研一 杨慈.pptx
- 杨慈/2025.4.7 研二 杨慈.pptx
- 胡小琪/2024.10.21 研一 胡小琪.pptx
- 胡小琪/2025.6.16 研一 胡小琪.pptx
- 胡小琪/2026.2.8 研二 胡小琪.pptx
- 胡小琪/2026.3.23 研二胡小琪.pptx
- 赵航佳/2026.4.20 博一 赵航佳.pptx
- 陈金薪/2026.4.20 研二 陈金薪.pptx
- 韩重阳/2024.12.14 研二 韩重阳.pptx
"""

import os
import sys
import io
import time
import requests
from requests.adapters import HTTPAdapter
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

BASE_URL = "https://agent.mnb-lab.cn"
USERNAME = "xiaoqi_testbot"
PASSWORD = "testbot_pass_2026"
SOURCE_DIR = Path("C:/Users/pc/Desktop/组会ppt")
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024
RETRY_MAX = 3
RETRY_BACKOFF = 2

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def make_session() -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def login(session: requests.Session) -> str:
    r = session.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def get_db_folder_id(session: requests.Session, headers: dict, name: str, parent_id: Optional[int]) -> Optional[int]:
    """通过 DB 直接查 folder_id (避免 broken /files endpoint 干扰)"""
    import subprocess
    if parent_id is None:
        sql = f"SELECT id FROM folders WHERE name = '{name}' AND parent_id IS NULL AND deleted_at IS NULL LIMIT 1"
    else:
        sql = f"SELECT id FROM folders WHERE name = '{name}' AND parent_id = {parent_id} AND deleted_at IS NULL LIMIT 1"
    r = subprocess.run(
        ['docker', 'exec', 'microbubble-agent-db-1', 'psql', '-U', 'postgres', '-d', 'microbubble', '-tAc', sql],
        capture_output=True
    )
    out = r.stdout.decode('utf-8').strip()
    return int(out) if out else None

def file_already_in_folder(name: str, folder_id: int) -> bool:
    """通过 DB 直接查 file_name 是否已存在 (避免 broken /files endpoint)"""
    import subprocess
    r = subprocess.run(
        ['docker', 'exec', 'microbubble-agent-db-1', 'psql', '-U', 'postgres', '-d', 'microbubble', '-tAc',
         f"SELECT COUNT(*) FROM knowledge WHERE file_name = '{name.replace(chr(39), chr(39)+chr(39))}' AND folder_id = {folder_id} AND deleted_at IS NULL"],
        capture_output=True
    )
    return r.stdout.decode('utf-8').strip() != '0'

def upload_small(session, headers, filepath, folder_id):
    with open(filepath, "rb") as f:
        r = session.post(
            f"{BASE_URL}/api/v1/drive/files/upload",
            files={"file": (filepath.name, f)},
            data={"folder_id": str(folder_id), "visibility": "team", "is_team_shared": "true"},
            headers=headers, timeout=900,  # 大文件需要更长 timeout
        )
    if r.status_code in (200, 201):
        return True, f"id={r.json()['id']} is_team_shared={r.json()['is_team_shared']}"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"

# 注: 项目 init/complete endpoint 不支持实际文件传输, 大文件 (≥50MB) 也走单端点 /files/upload
# (nginx client_max_body_size 需 ≥ 200m, 已调过)
def upload_with_retry(session, headers, filepath, folder_id):
    for attempt in range(1, RETRY_MAX + 1):
        try:
            return upload_small(session, headers, filepath, folder_id)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < RETRY_MAX:
                wait = RETRY_BACKOFF ** attempt
                log(f"  WARN: {e.__class__.__name__}, retry {attempt}/{RETRY_MAX} in {wait}s...")
                time.sleep(wait)
                continue
            return False, f"connection error after {RETRY_MAX} retries: {e}"
        except Exception as e:
            return False, f"unexpected: {e}"

# 12 missing files (relative to SOURCE_DIR)
MISSING_FILES = [
    ("", "2025.9.22.pptx"),  # root
    ("吴孟铨", "2025.4.21 研一 吴孟铨.pptx"),
    ("李胜景", "2026.2.8 研二 李胜景.pptx"),
    ("杨慈", "2023.06.24 研一 杨慈.pptx"),
    ("杨慈", "2025.4.7 研二 杨慈.pptx"),
    ("胡小琪", "2024.10.21 研一 胡小琪.pptx"),
    ("胡小琪", "2025.6.16 研一 胡小琪.pptx"),
    ("胡小琪", "2026.2.8 研二 胡小琪.pptx"),
    ("胡小琪", "2026.3.23 研二胡小琪.pptx"),
    ("赵航佳", "2026.4.20 博一 赵航佳.pptx"),
    ("陈金薪", "2026.4.20 研二 陈金薪.pptx"),
    ("韩重阳", "2024.12.14 研二 韩重阳.pptx"),
]

def main():
    log("=== Upload 12 missing files (v3) ===")
    log(f"  source: {SOURCE_DIR}")
    log(f"  target folder (id=336=组会PPT, parent=NULL)")

    session = make_session()
    token = login(session)
    headers = {"Authorization": f"Bearer {token}"}
    log(f"  login OK")

    # 1. Get 336 + 22 sub-folder IDs (DB direct, since API endpoint broken)
    root_id = get_db_folder_id(session, headers, "组会PPT", None)
    log(f"  root folder '组会PPT' id = {root_id}")
    if root_id is None:
        log(f"  ERROR: root folder not found, aborting")
        return 1

    subdir_ids = {}
    for sd in sorted([d for d in SOURCE_DIR.iterdir() if d.is_dir()]):
        subdir_ids[sd.name] = get_db_folder_id(session, headers, sd.name, root_id)
    log(f"  sub-folders: {subdir_ids}")

    # 2. Upload each missing file
    success = 0
    fail = 0
    skip = 0
    for parent_name, fname in MISSING_FILES:
        # Find folder
        if parent_name == "":
            folder_id = root_id
        else:
            folder_id = subdir_ids.get(parent_name)
        if folder_id is None:
            log(f"  SKIP [{parent_name}/{fname}]: folder not found")
            skip += 1
            continue

        # Check if already uploaded (DB direct)
        if file_already_in_folder(fname, folder_id):
            log(f"  SKIP [{parent_name or '(root)'}/{fname}]: already in DB")
            skip += 1
            continue

        # Build local path
        local_path = SOURCE_DIR / parent_name / fname if parent_name else SOURCE_DIR / fname
        if not local_path.exists():
            log(f"  SKIP [{parent_name or '(root)'}/{fname}]: file not found locally")
            skip += 1
            continue

        # Upload
        size_mb = local_path.stat().st_size / 1024 / 1024
        log(f"  [{parent_name or '(root)'}/{fname}] ({size_mb:.1f} MB)...")
        ok, msg = upload_with_retry(session, headers, local_path, folder_id)
        if ok:
            success += 1
            log(f"    -> {msg}")
        else:
            fail += 1
            log(f"    -> FAIL: {msg}")

    log(f"\n=== Done ===")
    log(f"  success: {success}, skip: {skip}, fail: {fail}, total: {len(MISSING_FILES)}")
    return 0 if fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
