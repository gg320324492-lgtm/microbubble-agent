"""
v2 PR3 端到端测试脚本

测试覆盖 (10+ assertions, 4 groups):
1. KnowledgeUploadDialog 后端等效 — drive 模式调 POST /drive/files/upload (folder_id+visibility)
2. createFolder 后 drive 上传到指定 folder → verify 文件 folder_id 正确
3. drive 文件 storage_mode='drive' 隔离 — KB 列表 /drive list 都按 storage_mode 过滤
4. 不同 visibility (private/team/public) drive 文件 visibility 写入 + 可读
5. PR2 regression — /starred /trash 仍工作 (PR3 zero touch)

测试账号: xiaoqi_testbot / testbot_pass_2026 (v0.1.0 隔离, 不碰 wangtianzhi)
"""
import os
import sys
import asyncio
import time
from typing import Optional

import httpx

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000/api/v1")
USERNAME = os.environ.get("E2E_USERNAME", "xiaoqi_testbot")
PASSWORD = os.environ.get("E2E_PASSWORD", "testbot_pass_2026")


async def login(client: httpx.AsyncClient) -> str:
    resp = await client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    resp.raise_for_status()
    return resp.json()["access_token"]


async def upload_drive_file(
    client: httpx.AsyncClient,
    headers: dict,
    file_name: str,
    content: bytes,
    visibility: str = "team",
    folder_id: Optional[int] = None,
    content_type: str = "text/plain",
) -> dict:
    """模拟 KnowledgeUploadDialog drive 模式 → POST /drive/files/upload"""
    files = {"file": (file_name, content, content_type)}
    data = {"visibility": visibility}
    if folder_id is not None:
        data["folder_id"] = str(folder_id)
    resp = await client.post(
        "/drive/files/upload",
        headers=headers,
        files=files,
        data=data,
    )
    resp.raise_for_status()
    return resp.json()


def h(headers):
    return {**headers}


PASSED = []
FAILED = []


def assert_eq(name, got, expected):
    if got == expected:
        PASSED.append(f"  ✅ {name}")
    else:
        FAILED.append(f"  ❌ {name}: expected {expected!r}, got {got!r}")


def assert_in(name, value, container):
    if value in container:
        PASSED.append(f"  ✅ {name}")
    else:
        FAILED.append(f"  ❌ {name}: '{value}' not in {container}")


def assert_true(name, cond, hint=""):
    if cond:
        PASSED.append(f"  ✅ {name}")
    else:
        FAILED.append(f"  ❌ {name} {hint}")


# ============== Group 1: drive 上传基础 (KnowledgeUploadDialog 后端等效) ==============
async def test_group_1_drive_upload_basic(client, headers):
    """1. 模拟 dialog drive 模式 — 默认顶级 + team 可见性"""
    print("\n=== Test Group 1: drive upload basic ===")
    file_name = f"pr3_basic_{int(time.time())}.txt"
    resp_data = await upload_drive_file(
        client, headers, file_name, b"pr3 basic upload", "team"
    )
    assert_true(f"upload 201 ok", resp_data.get("id") is not None, hint=str(resp_data))
    assert_eq("upload visibility=team", resp_data.get("visibility"), "team")
    assert_eq("storage_mode=drive (implied)", resp_data.get("storage_mode"), "drive")
    return [resp_data["id"]]


# ============== Group 2: 上传到指定 folder ==============
async def test_group_2_drive_upload_to_folder(client, headers):
    """2. 创建 folder + drive 上传到指定 folder_id"""
    print("\n=== Test Group 2: drive upload to folder ===")
    # 创建 test folder (REST POST 应 201 Created)
    folder_name = f"pr3_folder_{int(time.time())}"
    resp = await client.post("/folders", headers=headers, json={
        "name": folder_name,
        "parent_id": None,
        "visibility": "team",
    })
    assert_eq("folder create 201", resp.status_code, 201)
    folder = resp.json()
    folder_id = folder.get("id")
    assert_true(f"folder id={folder_id} > 0", isinstance(folder_id, int) and folder_id > 0, hint=str(folder))

    # drive 上传到该 folder
    file_name = f"pr3_into_folder_{int(time.time())}.txt"
    file_resp = await upload_drive_file(
        client, headers, file_name, b"pr3 into folder", "team", folder_id=folder_id
    )
    assert_true("upload to folder returned data", file_resp.get("id") is not None, hint=str(file_resp))
    assert_eq(f"file folder_id={folder_id}", file_resp.get("folder_id"), folder_id)

    # verify list_files 走顶级时不返回该文件
    resp = await client.get("/drive/files?page_size=50", headers=headers)
    items_top = resp.json().get("items", [])
    file_in_top = any(f["id"] == file_resp["id"] for f in items_top)
    assert_eq(f"file NOT in 顶级 list (folder_id={folder_id})", file_in_top, False)

    # verify list 走 folder_id 时能看到
    resp = await client.get(f"/drive/files?folder_id={folder_id}&page_size=50", headers=headers)
    items_in = resp.json().get("items", [])
    file_in_folder = any(f["id"] == file_resp["id"] for f in items_in)
    assert_eq(f"file IS in folder list", file_in_folder, True)

    return folder_id, file_resp["id"]


# ============== Group 3: storage_mode 隔离 (drive 文件不进 KB 列表) ==============
async def test_group_3_storage_mode_isolation(client, headers, drive_file_ids):
    """3. drive 文件 storage_mode='drive' — KB 列表过滤, /drive list 显示

    v2 PR3 默认 drive list = 顶级 (folder_id IS NULL). 文件如在 folder 里则不出现
    """
    print("\n=== Test Group 3: storage_mode isolation ===")
    # KB 列表 (默认 storage_mode='kb') 应不含 drive 文件
    resp = await client.get("/knowledge?page_size=20", headers=headers)
    assert_eq("KB list 200", resp.status_code, 200)
    kb_items = resp.json().get("items", [])
    kb_ids = {k["id"] for k in kb_items}
    drive_leaked = [fid for fid in drive_file_ids if fid in kb_ids]
    assert_eq("drive files NOT in KB list", len(drive_leaked), 0)

    # /drive/files?page_size=50 (默认 = 顶级 folder_id IS NULL)
    resp = await client.get("/drive/files?page_size=50", headers=headers)
    assert_eq("drive list 200", resp.status_code, 200)
    drive_items = resp.json().get("items", [])
    drive_ids_top = {f["id"] for f in drive_items}
    # /drive/files?include_all=true 不存在 (PR3 没这字段), 直接验证顶级 list 有 top-level 文件
    # 单独测 folder 内文件 — group 2 已验证 (file_in_folder not in top list)
    # 这里只确认 top-level drive files 都在顶级 list
    # drive_file_ids 包含 group1 文件 (顶级) + group2 文件 (folder 内)
    # 顶级 list 应至少 1 个 group1 文件
    assert_true(
        "group1 basic drive file in 顶级 list",
        drive_file_ids[0] in drive_ids_top,
        hint=f"want {drive_file_ids[0]} in top",
    )


# ============== Group 4: visibility 3 档验证 ==============
async def test_group_4_visibility_three_tiers(client, headers):
    """4. drive 文件 private/team/public 3 档可见性写入 + KB 跨账户隔离"""
    print("\n=== Test Group 4: visibility three tiers ===")
    results = {}
    for vis in ("private", "team", "public"):
        file_name = f"pr3_vis_{vis}_{int(time.time())}.txt"
        file_data = await upload_drive_file(
            client, headers, file_name, f"pr3 {vis}".encode(), vis
        )
        assert_true(f"upload ok ({vis})", file_data.get("id") is not None, hint=str(file_data))
        assert_eq(f"upload visibility={vis}", file_data.get("visibility"), vis)
        # detail 校验
        fid = file_data["id"]
        resp = await client.get(f"/drive/files/{fid}", headers=headers)
        assert_eq(f"file.visibility={vis} via GET", resp.json().get("visibility"), vis)
        results[vis] = fid
    return results


# ============== Group 5: PR2 regression — /starred /trash 仍工作 ==============
async def test_group_5_pr2_regression(client, headers, file_ids):
    """5. PR3 不破坏 PR2 — starred / trash / batch 端点仍 200"""
    print("\n=== Test Group 5: PR2 regression ===")
    # /starred 应 200
    resp = await client.get("/drive/starred?page_size=10", headers=headers)
    assert_eq("starred list 200", resp.status_code, 200)
    assert_true("starred returns {items, total}", "items" in resp.json() and "total" in resp.json())

    # /trash 应 200
    resp = await client.get("/drive/trash?page_size=10", headers=headers)
    assert_eq("trash list 200", resp.status_code, 200)
    assert_true("trash returns {items, total}", "items" in resp.json() and "total" in resp.json())

    # toggle-star 应工作
    if file_ids:
        fid = file_ids[0]
        resp = await client.post(f"/drive/files/{fid}/toggle-star", headers=headers)
        assert_eq("toggle-star 200", resp.status_code, 200)
        assert_eq("starred flag set", resp.json().get("is_starred"), True)


# ============== Group 6: 端点列表 + 副作用 cleanup ==============
async def cleanup(client, headers, file_ids, folder_id):
    """cleanup: 软删测试文件 + 软删测试文件夹"""
    print("\n=== Cleanup: soft-delete test files ===")
    if file_ids:
        await client.post(
            "/drive/files/batch-soft-delete",
            headers=headers,
            json={"file_ids": file_ids},
        )
    if folder_id:
        await client.delete(f"/folders/{folder_id}", headers=headers)
    print(f"  Cleanup done")


async def main():
    print(f"=== v2 PR3 E2E (KnowledgeUploadDialog 双模 + chip) ===")
    print(f"BASE={BASE}")
    print(f"USERNAME={USERNAME}")
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        basic_ids = await test_group_1_drive_upload_basic(client, headers)
        folder_id, file_in_folder_id = await test_group_2_drive_upload_to_folder(client, headers)
        await test_group_3_storage_mode_isolation(
            client, headers, basic_ids + [file_in_folder_id]
        )
        visibility_results = await test_group_4_visibility_three_tiers(client, headers)
        all_drive_ids = (
            basic_ids + [file_in_folder_id]
            + list(visibility_results.values())
        )
        await test_group_5_pr2_regression(client, headers, basic_ids)

        # cleanup
        await cleanup(client, headers, all_drive_ids, folder_id)

    print(f"\n=== RESULT ===")
    print(f"PASSED: {len(PASSED)}")
    print(f"FAILED: {len(FAILED)}")
    for f in FAILED:
        print(f)
    print(f"\n=== END ===")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
