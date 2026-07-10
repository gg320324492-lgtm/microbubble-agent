#!/usr/bin/env python3
"""
upload_team_ppts.py — 把桌面的 组会ppt/ 上传到团队共享网盘 (resumable + retry)

v2 (2026-07-11):
- 跳过已上传: 启动时查 DB alive (folder_id, file_name) 集合, 已存在 skip
- 复用 connection: requests.Session + HTTPAdapter (ConnectionResetError 容错)
- 重试机制: 单 file 失败 retry 3 次 (指数退避)
- 进度持久: 每上传 5 个打印一次状态

## 层级
- /组会ppt/2025.6.09.pptx → 团队盘/组会PPT/
- /组会ppt/2025.9.22.pptx (110MB, chunked) → 团队盘/组会PPT/
- /组会ppt/<姓名>/<PPT> → 团队盘/组会PPT/<姓名>/<PPT>

## 全部 is_team_shared=true
"""

import os
import sys
import io
import time
import requests
from requests.adapters import HTTPAdapter
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set

# Fix Windows console encoding (避免 GBK 编码错误)
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
ROOT_FOLDER_NAME = "组会PPT"
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB
RETRY_MAX = 3
RETRY_BACKOFF = 2  # seconds

# === Logging (UTF-8 safe) ===
def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# === HTTP session with retry ===
def make_session() -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

# === Step 1: Login ===
def login(session: requests.Session) -> str:
    r = session.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

# === Step 2: Create folder (idempotent) ===
def create_folder(session: requests.Session, headers: dict, name: str, parent_id: Optional[int]) -> int:
    payload = {"name": name, "visibility": "team"}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    r = session.post(f"{BASE_URL}/api/v1/folders", json=payload, headers=headers, timeout=30)
    if r.status_code == 201:
        return r.json()["id"]
    # 409 Conflict = 同名已存在, 查列表找 id
    if r.status_code in (400, 409, 422):
        r2 = session.get(f"{BASE_URL}/api/v1/folders", headers=headers, timeout=30)
        r2.raise_for_status()
        for f in r2.json()["items"]:
            if f["name"] == name and f["parent_id"] == parent_id and f["deleted_at"] is None:
                return f["id"]
    r.raise_for_status()

# === Step 3: Get existing files (for skip) ===
def get_existing_files(session: requests.Session, headers: dict, folder_ids: List[int]) -> Dict[int, Set[str]]:
    """返回 {folder_id: {file_name, ...}}, 用于跳过已上传"""
    existing = {fid: set() for fid in folder_ids}
    for fid in folder_ids:
        try:
            # list files in folder via search by folder_id
            r = session.get(f"{BASE_URL}/api/v1/drive/files", params={"page": 1, "page_size": 100, "view": "team"}, headers=headers, timeout=30)
            r.raise_for_status()
            for f in r.json().get("items", []):
                if f.get("folder_id") == fid:
                    existing[fid].add(f["file_name"])
        except Exception as e:
            log(f"  WARN: get_existing_files folder {fid}: {e}")
    return existing

# === Step 4: Small file upload (single endpoint) ===
def upload_small(session: requests.Session, headers: dict, filepath: Path, folder_id: int) -> Tuple[bool, str]:
    with open(filepath, "rb") as f:
        r = session.post(
            f"{BASE_URL}/api/v1/drive/files/upload",
            files={"file": (filepath.name, f)},
            data={
                "folder_id": str(folder_id),
                "visibility": "team",
                "is_team_shared": "true",
            },
            headers=headers,
            timeout=300,
        )
    if r.status_code in (200, 201):
        data = r.json()
        return True, f"id={data['id']} is_team_shared={data['is_team_shared']}"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"

# === Step 5: Large file chunked upload ===
def upload_chunked(session: requests.Session, headers: dict, filepath: Path, folder_id: int) -> Tuple[bool, str]:
    file_size = filepath.stat().st_size
    r = session.post(
        f"{BASE_URL}/api/v1/drive/files/upload/init",
        json={
            "filename": filepath.name,
            "file_size": file_size,
            "total_chunks": 1,
            "file_hash": None,
            "folder_id": folder_id,
            "visibility": "team",
        },
        headers=headers,
        timeout=60,
    )
    if r.status_code != 200:
        return False, f"init failed: {r.status_code} {r.text[:200]}"
    upload_id = r.json()["upload_id"]
    with open(filepath, "rb") as f:
        r = session.post(
            f"{BASE_URL}/api/v1/drive/files/upload/{upload_id}/complete",
            data={
                "folder_id": str(folder_id),
                "visibility": "team",
                "is_team_shared": "true",
            },
            files={"data": (filepath.name, f)},
            headers=headers,
            timeout=900,
        )
    if r.status_code in (200, 201):
        data = r.json()
        return True, f"id={data['id']} is_team_shared={data['is_team_shared']}"
    return False, f"complete failed: {r.status_code} {r.text[:200]}"

def upload_with_retry(session, headers, filepath, folder_id):
    for attempt in range(1, RETRY_MAX + 1):
        try:
            if filepath.stat().st_size >= LARGE_FILE_THRESHOLD:
                return upload_chunked(session, headers, filepath, folder_id)
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

# === Main ===
def main():
    log(f"=== Upload 组会PPT (resumable v2) ===")
    log(f"  source: {SOURCE_DIR}")
    log(f"  target: {BASE_URL} 团队盘 / {ROOT_FOLDER_NAME}/")
    log(f"")

    session = make_session()
    token = login(session)
    headers = {"Authorization": f"Bearer {token}"}
    log(f"  login OK")

    # 1. 创建最外层 folder
    log(f"\n[1] 创建 folder '{ROOT_FOLDER_NAME}'...")
    root_folder_id = create_folder(session, headers, ROOT_FOLDER_NAME, parent_id=None)
    log(f"  root_folder_id = {root_folder_id}")

    # 2. 创建 22 个 sub-folder
    log(f"\n[2] 创建 22 个 sub-folder...")
    subdirs = sorted([d for d in SOURCE_DIR.iterdir() if d.is_dir()])
    sub_folder_ids: Dict[str, int] = {}
    for sd in subdirs:
        sub_folder_ids[sd.name] = create_folder(session, headers, sd.name, parent_id=root_folder_id)
    log(f"  sub_folder_ids = {sub_folder_ids}")

    # 3. 拿已存在的文件 (for skip)
    log(f"\n[3] 拿已上传文件 (skip)...")
    all_folder_ids = [root_folder_id] + list(sub_folder_ids.values())
    existing = get_existing_files(session, headers, all_folder_ids)
    total_existing = sum(len(v) for v in existing.values())
    log(f"  existing: {total_existing} 文件 across {len(all_folder_ids)} folders")

    # 4. 收集所有 PPT
    log(f"\n[4] 收集 PPT + 开始上传...")
    ppt_root = [p for p in SOURCE_DIR.iterdir() if p.is_file() and p.suffix.lower() in (".pptx", ".ppt")]
    ppt_subdirs: Dict[str, List[Path]] = {}
    for sd in subdirs:
        ppt_subdirs[sd.name] = sorted([
            p for p in sd.iterdir() if p.is_file() and p.suffix.lower() in (".pptx", ".ppt")
        ])
    total = len(ppt_root) + sum(len(v) for v in ppt_subdirs.values())
    log(f"  total: {len(ppt_root)} root + {sum(len(v) for v in ppt_subdirs.values())} sub = {total}")

    # 5. 上传
    success_count = 0
    skip_count = 0
    fail_count = 0
    start_time = time.time()

    def upload_one_to_folder(p: Path, fid: int, label: str):
        nonlocal success_count, skip_count, fail_count
        if p.name in existing.get(fid, set()):
            skip_count += 1
            log(f"  [{label}] {p.name} (skip, already uploaded)")
            return
        log(f"  [{label}] {p.name} ({p.stat().st_size/1024/1024:.1f} MB)...")
        ok, msg = upload_with_retry(session, headers, p, fid)
        if ok:
            success_count += 1
            log(f"    -> {msg}")
            existing[fid].add(p.name)  # 标记为已上传
        else:
            fail_count += 1
            log(f"    -> FAIL: {msg}")

    # 4a. root PPT
    log(f"\n[4a] 上传 root PPT (2 个)...")
    for p in ppt_root:
        upload_one_to_folder(p, root_folder_id, "root")

    # 4b. sub-dir PPT
    log(f"\n[4b] 上传 sub-dir PPT...")
    for sd_name, files in ppt_subdirs.items():
        sf_id = sub_folder_ids[sd_name]
        for p in files:
            upload_one_to_folder(p, sf_id, sd_name)

    elapsed = time.time() - start_time
    log(f"\n=== Done ===")
    log(f"  success: {success_count}, skip: {skip_count}, fail: {fail_count}, total: {total}")
    log(f"  elapsed: {elapsed:.1f}s")
    if fail_count > 0:
        log(f"  WARNING: {fail_count} 文件上传失败, 需手动重试")
        sys.exit(1)

if __name__ == "__main__":
    main()
