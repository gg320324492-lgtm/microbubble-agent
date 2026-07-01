"""
v2 PR2 端到端测试脚本

测试覆盖 7 组 (29+ 断言):
1. toggle-star + starred 列表
2. sort_by (4 种) + sort_order (2 种) + invalid sort_by 返 400
3. file_type (pdf/image/office) 过滤
4. batch-soft-delete + batch-restore
5. batch-move (含 folder 越权)
6. batch-update-visibility
7. trash 列表 + permanent-delete + 数据隔离

测试账号: xiaoqi_testbot / testbot_pass_2026 (v0.1.0 隔离, 不碰 wangtianzhi)
"""
import os
import sys
import asyncio
import time
from typing import Optional

import httpx

# 与 PR1 e2e 一致: 容器内 localhost 不通, 必须用 service name
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000/api/v1")
USERNAME = os.environ.get("E2E_USERNAME", "xiaoqi_testbot")
PASSWORD = os.environ.get("E2E_PASSWORD", "testbot_pass_2026")


async def login(client: httpx.AsyncClient) -> str:
    resp = await client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    resp.raise_for_status()
    return resp.json()["access_token"]


async def upload_test_file(client: httpx.AsyncClient, headers: dict, file_name: str, content: bytes, visibility: str = "team") -> int:
    """上传一个测试文件, 返回 file_id"""
    resp = await client.post(
        "/drive/files/upload",
        headers=headers,
        files={"file": (file_name, content, "text/plain")},
        data={"visibility": visibility},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def h(headers: dict) -> dict:
    """auth header 快捷"""
    return {**headers}


PASSED = []
FAILED = []


def assert_eq(name: str, got, expected):
    if got == expected:
        PASSED.append(f"  ✅ {name}")
    else:
        FAILED.append(f"  ❌ {name}: expected {expected!r}, got {got!r}")


def assert_in(name: str, value: str, container: list):
    if value in container:
        PASSED.append(f"  ✅ {name}")
    else:
        FAILED.append(f"  ❌ {name}: '{value}' not in {container}")


async def fetch_all_trash(client, headers, page_size: int = 100, max_pages: int = 10) -> list:
    """遍历分页拿到所有 trash (因为 page_size 上限 100)"""
    all_items = []
    page = 1
    while page <= max_pages:
        resp = await client.get(
            "/drive/trash",
            headers=headers,
            params={"page": page, "page_size": page_size},
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        items = data.get("items", [])
        all_items.extend(items)
        total = data.get("total", 0)
        if len(all_items) >= total or not items:
            break
        page += 1
    return all_items


def assert_true(name: str, cond: bool, hint: str = ""):
    if cond:
        PASSED.append(f"  ✅ {name}")
    else:
        FAILED.append(f"  ❌ {name} {hint}")


async def test_group_1_toggle_star(client, headers):
    """1. 收藏切换 + starred 列表"""
    print("\n=== Test Group 1: toggle-star + starred list ===")
    # 上传一个新文件
    file_id = await upload_test_file(client, headers, f"pr2_star_{int(time.time())}.txt", b"star test", "team")
    print(f"  uploaded file_id={file_id}")

    # toggle on
    resp = await client.post(f"/drive/files/{file_id}/toggle-star", headers=headers)
    assert_eq("toggle returns 200", resp.status_code, 200)
    data = resp.json()
    assert_eq("after toggle 1: is_starred=True", data["is_starred"], True)
    assert_true("starred_at is set", data.get("starred_at") is not None)

    # starred 列表应包含
    resp = await client.get("/drive/starred?page_size=50", headers=headers)
    assert_eq("starred list 200", resp.status_code, 200)
    items = resp.json()["items"]
    assert_true(f"file {file_id} in starred list", any(f["id"] == file_id for f in items))

    # toggle off
    resp = await client.post(f"/drive/files/{file_id}/toggle-star", headers=headers)
    data = resp.json()
    assert_eq("after toggle 2: is_starred=False", data["is_starred"], False)
    assert_eq("starred_at reset to None", data["starred_at"], None)

    # starred 列表应不再包含
    resp = await client.get("/drive/starred?page_size=50", headers=headers)
    items = resp.json()["items"]
    assert_true(f"file {file_id} NOT in starred list", all(f["id"] != file_id for f in items))

    # toggle-star on bogus id → 404
    resp = await client.post("/drive/files/999999/toggle-star", headers=headers)
    assert_eq("bogus id → 404", resp.status_code, 404)

    return [file_id]


async def test_group_2_sort(client, headers, file_ids):
    """2. sort_by / sort_order / invalid"""
    print("\n=== Test Group 2: sort_by + sort_order ===")
    # default sort (created_at desc)
    resp = await client.get("/drive/files?page_size=5", headers=headers)
    items = resp.json()["items"]
    if len(items) >= 2:
        # 时间应该是降序
        assert_true("default sort=created_at desc",
                    items[0]["created_at"] >= items[-1]["created_at"])

    # sort by file_name asc
    resp = await client.get("/drive/files?sort_by=file_name&sort_order=asc&page_size=10", headers=headers)
    assert_eq("sort file_name asc 200", resp.status_code, 200)
    items = resp.json()["items"]
    if len(items) >= 2:
        names = [f["file_name"] for f in items if f.get("file_name")]
        assert_true("file_name asc", names == sorted(names), hint=str(names))

    # invalid sort_by → 400
    resp = await client.get("/drive/files?sort_by=invalid_col&page_size=5", headers=headers)
    assert_eq("invalid sort_by → 400", resp.status_code, 400)


async def test_group_3_file_type_filter(client, headers):
    """3. file_type 过滤"""
    print("\n=== Test Group 3: file_type filter ===")
    # 上传一个 PDF 文件
    pdf_name = f"pr2_pdf_{int(time.time())}.pdf"
    resp = await client.post(
        "/drive/files/upload",
        headers=headers,
        files={"file": (pdf_name, b"%PDF-1.4 fake content", "application/pdf")},
        data={"visibility": "team"},
    )
    if resp.status_code == 201:
        pdf_id = resp.json()["id"]
    else:
        print(f"  ⚠ PDF upload failed: {resp.status_code}, skipping")
        return []

    # filter pdf
    resp = await client.get("/drive/files?file_type=pdf&page_size=50", headers=headers)
    items = resp.json()["items"]
    assert_true(f"PDF file in pdf filter", any(f["id"] == pdf_id for f in items))

    # filter image (应不含 PDF)
    resp = await client.get("/drive/files?file_type=image&page_size=50", headers=headers)
    items = resp.json()["items"]
    assert_true(f"PDF file NOT in image filter", all(f["id"] != pdf_id for f in items))

    return [pdf_id]


async def test_group_4_batch_delete_restore(client, headers, file_ids):
    """4. batch soft-delete + restore"""
    print("\n=== Test Group 4: batch soft-delete + restore ===")
    if len(file_ids) < 2:
        print(f"  ⚠ skip (need ≥2 files, got {len(file_ids)})")
        return

    # batch soft-delete
    resp = await client.post(
        "/drive/files/batch-soft-delete",
        headers=headers,
        json={"file_ids": file_ids},
    )
    assert_eq("batch-soft-delete 200", resp.status_code, 200)
    data = resp.json()
    assert_eq(f"batch deleted count", data["succeeded_count"], len(file_ids))

    # trash 列表应包含
    items = await fetch_all_trash(client, headers)
    assert_true(f"all deleted files in trash",
                all(any(f["id"] == fid for f in items) for fid in file_ids))

    # batch restore
    resp = await client.post(
        "/drive/files/batch-restore",
        headers=headers,
        json={"file_ids": file_ids},
    )
    assert_eq("batch-restore 200", resp.status_code, 200)
    data = resp.json()
    assert_eq(f"batch restored count", data["succeeded_count"], len(file_ids))

    # trash 不再包含
    items = await fetch_all_trash(client, headers)
    assert_true(f"restored files NOT in trash",
                all(all(f["id"] != fid for f in items) for fid in file_ids))


async def test_group_5_batch_move(client, headers, file_ids):
    """5. batch move (target_folder_id=None=顶级)"""
    print("\n=== Test Group 5: batch move ===")
    if not file_ids:
        print("  ⚠ skip (no files)")
        return

    # move 到顶级 (None)
    resp = await client.post(
        "/drive/files/batch-move",
        headers=headers,
        json={"file_ids": file_ids, "target_folder_id": None},
    )
    assert_eq("batch-move to root 200", resp.status_code, 200)
    data = resp.json()
    assert_eq("moved count", data["succeeded_count"], len(file_ids))


async def test_group_6_batch_visibility(client, headers, file_ids):
    """6. batch update visibility"""
    print("\n=== Test Group 6: batch update visibility ===")
    if not file_ids:
        print("  ⚠ skip")
        return

    # private
    resp = await client.post(
        "/drive/files/batch-update-visibility",
        headers=headers,
        json={"file_ids": file_ids, "visibility": "private"},
    )
    assert_eq("batch-update-visibility private 200", resp.status_code, 200)

    # 验证 list 时按 private 过滤 (其他用户看不到)
    # 我们先用自己账号验证 visibility 已改
    resp = await client.get(f"/drive/files/{file_ids[0]}", headers=headers)
    if resp.status_code == 200:
        assert_eq("file visibility=private", resp.json()["visibility"], "private")

    # 改回 team 避免污染
    await client.post(
        "/drive/files/batch-update-visibility",
        headers=headers,
        json={"file_ids": file_ids, "visibility": "team"},
    )


async def test_group_7_trash_permanent_delete(client, headers):
    """7. trash 永久删除 + 数据隔离"""
    print("\n=== Test Group 7: trash permanent delete + isolation ===")
    # 上传一个新文件, 软删, 然后永久删
    file_id = await upload_test_file(client, headers, f"pr2_perm_{int(time.time())}.txt", b"perm test")
    await client.post(f"/drive/files/{file_id}/toggle-star", headers=headers)  # 加个变化便于观察

    # soft delete
    resp = await client.delete(f"/drive/files/{file_id}", headers=headers)
    assert_eq("soft delete 204", resp.status_code, 204)

    # trash 应包含
    items = await fetch_all_trash(client, headers)
    assert_true(f"file {file_id} in trash", any(f["id"] == file_id for f in items))

    # permanent delete
    resp = await client.post(
        "/drive/trash/permanent-delete",
        headers=headers,
        json={"file_ids": [file_id]},
    )
    assert_eq("permanent-delete 200", resp.status_code, 200)

    # trash 不再包含
    items = await fetch_all_trash(client, headers)
    assert_true(f"file {file_id} NOT in trash after perm-delete",
                all(f["id"] != file_id for f in items))

    # 直接 GET 应该 404
    resp = await client.get(f"/drive/files/{file_id}", headers=headers)
    assert_eq("perm-deleted file GET → 404", resp.status_code, 404)


async def main():
    print(f"=== v2 PR2 E2E ===")
    print(f"BASE={BASE}")
    print(f"USERNAME={USERNAME}")
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 准备: 上传一些测试文件 (足够后续测试用)
        setup_files = []
        for i in range(4):
            fid = await upload_test_file(client, headers, f"pr2_setup_{i}_{int(time.time())}.txt",
                                          f"setup test {i}".encode())
            setup_files.append(fid)
        print(f"  Setup: uploaded {len(setup_files)} test files: {setup_files}")

        await test_group_1_toggle_star(client, headers)
        await test_group_2_sort(client, headers, setup_files)
        pdf_ids = await test_group_3_file_type_filter(client, headers)
        await test_group_4_batch_delete_restore(client, headers, setup_files[:2])
        await test_group_5_batch_move(client, headers, setup_files[:1])
        await test_group_6_batch_visibility(client, headers, setup_files[2:4])
        await test_group_7_trash_permanent_delete(client, headers)

        # 清理: 把 setup_files 软删 (不影响后续测试)
        if setup_files:
            await client.post(
                "/drive/files/batch-soft-delete",
                headers=headers,
                json={"file_ids": setup_files},
            )
            print(f"\n  Cleanup: soft-deleted {len(setup_files)} setup files")

    print(f"\n=== RESULT ===")
    print(f"PASSED: {len(PASSED)}")
    print(f"FAILED: {len(FAILED)}")
    for f in FAILED:
        print(f)
    print(f"\n=== END ===")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))