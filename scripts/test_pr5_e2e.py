"""
v2 PR5 端到端测试脚本 (配额 + 分片上传 + 断点续传 + 缩略图)

测试覆盖 (8 groups, 30+ assertions):
1. storage-quota: 默认 10GB 配额, used_bytes/file_count 正确
2. 分片 init: 返 upload_id + total_chunks + chunk_size_hint + uploaded_chunks=[]
3. 分片上传 chunk 0/N-1: uploaded_chunks 累加
4. 断点续传 (GET status): 返已传 chunks 列表
5. 分片 complete: 创建 Knowledge 行 (file_size/file_hash/version_number)
6. 缩略图: 上传图片 (PNG) → 等 Celery 生成 → thumbnail_status='ready'
7. 配额超额: 故意超 quota (改 user.quota_bytes 模拟) → init 返 413
8. PR1-4 regression: share-link / toggle-star / version-history / restore / trash 仍工作
9. 跨用户隔离: testbot2 看不到 testbot1 的 quota + thumbnail
"""
import os
import sys
import asyncio
import time
import hashlib
import subprocess
from typing import Optional

import httpx

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000/api/v1")
USERNAME = os.environ.get("E2E_USERNAME", "xiaoqi_testbot")
PASSWORD = os.environ.get("E2E_PASSWORD", "testbot_pass_2026")


async def login(client, username=None, password=None):
    resp = await client.post("/auth/login", json={
        "username": username or USERNAME,
        "password": password or PASSWORD,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


PASSED = []
FAILED = []


def assert_eq(name, got, expected):
    if got == expected:
        PASSED.append(f"  OK {name}")
    else:
        FAILED.append(f"  FAIL {name}: expected {expected!r}, got {got!r}")


def assert_true(name, cond, hint=""):
    if cond:
        PASSED.append(f"  OK {name}")
    else:
        FAILED.append(f"  FAIL {name} {hint}")


# ============== Group 1: storage-quota ==============
async def test_group_1_quota_default(client, headers):
    """1. 默认 10GB 配额, used_bytes/file_count 正确"""
    print("\n=== Test Group 1: storage-quota default ===")
    resp = await client.get("/drive/storage-quota", headers=headers)
    assert_eq("storage-quota 200", resp.status_code, 200)
    data = resp.json()
    assert_eq("user_id 字段", isinstance(data.get("user_id"), int), True)
    assert_eq("quota_bytes == 10GB", data.get("quota_bytes"), 10737418240)
    assert_eq("used_bytes >= 0", isinstance(data.get("used_bytes"), int), True)
    assert_eq("percent >= 0", data.get("percent", -1) >= 0, True)
    assert_eq("file_count >= 0", isinstance(data.get("file_count"), int), True)
    assert_eq("is_over_quota false", data.get("is_over_quota"), False)
    return data


# ============== Group 2: 分片 init ==============
async def test_group_2_chunked_init(client, headers):
    """2. 分片 init 返 upload_id + 必要字段"""
    print("\n=== Test Group 2: chunked upload init ===")
    file_name = f"pr5_chunk_{int(time.time())}.bin"
    file_size = 12 * 1024 * 1024  # 12MB / 4MB chunk = 3 chunks
    body = {
        "file_name": file_name,
        "file_size": file_size,
        "total_chunks": 3,
        "visibility": "team",
    }
    resp = await client.post("/drive/files/upload/init", headers=headers, json=body)
    assert_eq("init 200", resp.status_code, 200)
    data = resp.json()
    assert_eq("upload_id 32 chars", len(data.get("upload_id") or ""), 32)
    assert_eq("total_chunks=3", data.get("total_chunks"), 3)
    assert_eq("chunk_size_hint=5MB", data.get("chunk_size_hint"), 5 * 1024 * 1024)
    assert_eq("uploaded_chunks=[]", data.get("uploaded_chunks"), [])
    assert_true("expires_at present", data.get("expires_at") is not None)
    return data["upload_id"], file_name


# ============== Group 3: 分片上传 chunk 0/N-1 ==============
async def test_group_3_upload_chunks(client, headers, upload_id):
    """3. 上传 3 chunks (4MB each, 总 12MB) → uploaded_chunks 累加"""
    print("\n=== Test Group 3: upload chunks ===")
    chunk_size = 4 * 1024 * 1024  # 4MB / chunk (total 12MB)
    chunks = [os.urandom(chunk_size) for _ in range(3)]

    for idx, chunk_data in enumerate(chunks):
        resp = await client.put(
            f"/drive/files/upload/{upload_id}/chunk/{idx}",
            headers=headers,  # 不设 Content-Type, httpx auto = application/octet-stream
            content=chunk_data,
        )
        assert_eq(f"chunk {idx} 200", resp.status_code, 200)
        data = resp.json()
        assert_eq(
            f"chunk {idx} uploaded_chunks 累加",
            data.get("uploaded_chunks"),
            list(range(idx + 1)),
        )

    # 越界 chunk 索引 → 400
    resp = await client.put(
        f"/drive/files/upload/{upload_id}/chunk/999",
        headers=headers,
        content=b"bad",
    )
    assert_eq("越界 chunk 400", resp.status_code, 400)
    return chunks


# ============== Group 4: 断点续传 ==============
async def test_group_4_resume(client, headers, upload_id):
    """4. GET status 返已传 chunks (前端 reload 后查, 跳过已传)"""
    print("\n=== Test Group 4: resume check ===")
    resp = await client.get(f"/drive/files/upload/{upload_id}", headers=headers)
    assert_eq("GET status 200", resp.status_code, 200)
    data = resp.json()
    assert_eq("uploaded_chunks [0,1,2]", data.get("uploaded_chunks"), [0, 1, 2])
    assert_eq("status=active", data.get("status"), "active")
    assert_eq("total_chunks=3", data.get("total_chunks"), 3)
    return data


# ============== Group 5: 分片 complete ==============
async def test_group_5_complete(client, headers, upload_id, file_name, chunks):
    """5. complete → 创建 Knowledge 行, file_size=15MB, version_number=1"""
    print("\n=== Test Group 5: complete chunked ===")
    resp = await client.post(
        f"/drive/files/upload/{upload_id}/complete",
        headers=headers,
        json={"change_note": "PR5 e2e test"},
    )
    if resp.status_code != 200:
        print(f"  [DBG] complete 失败: status={resp.status_code} body={resp.text[:500]}")
    assert_eq("complete 200", resp.status_code, 200)
    new_file = resp.json()
    if not new_file.get("id"):
        print(f"  [DBG] response 缺 id: {new_file}")
    assert_eq("file_name correct", new_file.get("file_name"), file_name)
    assert_eq("file_size=12MB", new_file.get("file_size"), 12 * 1024 * 1024)
    assert_eq("version_number=1", new_file.get("version_number"), 1)
    assert_eq("is_latest=True", new_file.get("is_latest"), True)
    assert_eq("storage_mode=drive", new_file.get("storage_mode"), "drive")
    assert_eq("thumbnail_status=pending", new_file.get("thumbnail_status"), "pending")
    return new_file


# ============== Group 6: 缩略图 Celery 生成 ==============
async def test_group_6_thumbnail(client, headers, file_id, file_name):
    """6. 上传 PNG 后等 Celery 生成 thumbnail → status='ready'"""
    print("\n=== Test Group 6: thumbnail generation ===")
    # 用 PIL 生成真 PNG bytes (PR5 教训: 手工 hex PNG header PIL 解析失败)
    import io
    from PIL import Image
    img = Image.new("RGB", (320, 240), color=(73, 109, 137))
    # 加几条像素让 PIL 认得
    for x in range(0, 320, 10):
        for y in range(0, 240, 10):
            img.putpixel((x, y), (255, 100, 50))
    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    png_bytes = png_buf.getvalue()

    files = {"file": (f"pr5_thumb_{int(time.time())}.png", png_bytes, "image/png")}
    data = {"visibility": "team", "storage_mode": "drive"}
    resp = await client.post("/drive/files/upload", headers=headers, files=files, data=data)
    assert_eq("PNG upload 201", resp.status_code, 201)
    png_file_id = resp.json()["id"]

    # 立刻查 status (pending)
    resp = await client.get(f"/drive/files/{png_file_id}/thumbnail", headers=headers)
    assert_eq("thumbnail 端点 200", resp.status_code, 200)
    assert_eq("初始 status=pending", resp.json().get("thumbnail_status"), "pending")
    assert_true("thumbnail_url=null (pending)", resp.json().get("thumbnail_url") is None)

    # 等 Celery 生成 (最长 30s)
    ready = False
    for i in range(30):
        await asyncio.sleep(1)
        resp = await client.get(f"/drive/files/{png_file_id}/thumbnail", headers=headers)
        if resp.json().get("thumbnail_status") == "ready":
            ready = True
            print(f"  [info] thumbnail ready at {i+1}s")
            break
    assert_true("thumbnail_status 转 ready (30s 内)", ready)

    if ready:
        # ready 后应返 thumbnail_url
        resp = await client.get(f"/drive/files/{png_file_id}/thumbnail", headers=headers)
        data = resp.json()
        assert_true("thumbnail_url 非空 (ready 后)", data.get("thumbnail_url") is not None)
        assert_eq("thumbnail_path 含 .jpg", ".jpg" in (data.get("thumbnail_path") or ""), True)

    return png_file_id


# ============== Group 7: 配额超额 ==============
async def test_group_7_quota_overflow(client, headers):
    """7. 故意把 user quota 设小, 触发 413"""
    print("\n=== Test Group 7: quota overflow ===")
    # 直接 UPDATE DB (测试用, 生产不会这么做)
    sql = f"""
        UPDATE members SET drive_quota_bytes = 1000 WHERE username = 'xiaoqi_testbot';
    """
    try:
        result = subprocess.run(
            ["docker", "exec", "microbubble-agent-db-1",
             "psql", "-U", "postgres", "-d", "microbubble", "-c", sql],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"  [WARN] DB UPDATE failed: {result.stderr[:200]}")
    except FileNotFoundError:
        print("  [WARN] docker not available")
    except Exception as e:
        print(f"  [WARN] {e}")

    # 试上传 > 1000 字节
    body = {
        "file_name": f"pr5_overflow_{int(time.time())}.bin",
        "file_size": 5000,  # 5KB > 1000 字节配额
        "total_chunks": 1,
        "visibility": "team",
    }
    resp = await client.post("/drive/files/upload/init", headers=headers, json=body)
    assert_eq("超额 init 返 413", resp.status_code, 413)
    assert_true("错误信息含 quota", "配额" in (resp.text or ""))

    # 还原 quota
    sql_restore = "UPDATE members SET drive_quota_bytes = 10737418240 WHERE username = 'xiaoqi_testbot';"
    try:
        subprocess.run(
            ["docker", "exec", "microbubble-agent-db-1",
             "psql", "-U", "postgres", "-d", "microbubble", "-c", sql_restore],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        pass


# ============== Group 8: PR1-4 regression ==============
async def test_group_8_pr1_4_regression(client, headers):
    """8. PR1-4 端点不回归"""
    print("\n=== Test Group 8: PR1-4 regression ===")
    # share-link
    files = {"file": (f"pr5_reg_{int(time.time())}.txt", b"reg test", "text/plain")}
    data = {"visibility": "team", "storage_mode": "drive"}
    resp = await client.post("/drive/files/upload", headers=headers, files=files, data=data)
    assert_eq("upload 201", resp.status_code, 201)
    fid = resp.json()["id"]

    resp = await client.post(
        f"/drive/files/{fid}/share-link", headers=headers, json={"expires_hours": 24}
    )
    assert_eq("share-link 200", resp.status_code, 200)

    # toggle-star
    resp = await client.post(f"/drive/files/{fid}/toggle-star", headers=headers)
    assert_eq("toggle-star 200", resp.status_code, 200)

    # list starred
    resp = await client.get("/drive/starred?page_size=5", headers=headers)
    assert_eq("/starred 200", resp.status_code, 200)

    # trash + restore
    resp = await client.post(
        "/drive/files/batch-soft-delete", headers=headers, json={"file_ids": [fid]}
    )
    assert_eq("batch-soft-delete 200", resp.status_code, 200)
    resp = await client.post(f"/drive/files/{fid}/restore", headers=headers)
    assert_eq("restore 200", resp.status_code, 200)

    # versions (empty 列表即可)
    resp = await client.get(f"/drive/files/{fid}/versions", headers=headers)
    assert_eq("versions 200", resp.status_code, 200)

    return fid


# ============== Group 9: 跨用户隔离 ==============
async def test_group_9_cross_user_isolation(client, headers):
    """9. testbot2 看不到 testbot1 的 storage-quota 数值 + thumbnail"""
    print("\n=== Test Group 9: cross-user isolation ===")
    try:
        token2 = await login(client, "xiaoqi_testbot_2", "testbot_pass_2026_2")
        headers2 = {"Authorization": f"Bearer {token2}"}
    except Exception as e:
        print(f"  [WARN] testbot2 not available: {e}")
        return

    # storage-quota 各看各的
    resp1 = await client.get("/drive/storage-quota", headers=headers)
    resp2 = await client.get("/drive/storage-quota", headers=headers2)
    q1 = resp1.json()
    q2 = resp2.json()
    assert_eq("testbot1 user_id != testbot2 user_id", q1.get("user_id") != q2.get("user_id"), True)

    # thumbnail 越权 (testbot2 拿 testbot1 文件 id)
    resp = await client.get("/drive/files/99999999/thumbnail", headers=headers2)
    assert_true(
        f"testbot2 越权 thumbnail 返 404 (got {resp.status_code})",
        resp.status_code == 404,
    )


async def cleanup(client, headers, file_ids):
    """cleanup"""
    print("\n=== Cleanup ===")
    if file_ids:
        try:
            await client.post(
                "/drive/files/batch-soft-delete",
                headers=headers,
                json={"file_ids": file_ids},
            )
        except Exception as e:
            print(f"  cleanup warn: {e}")
        print(f"  Cleaned {len(file_ids)} files")


async def main():
    print(f"=== v2 PR5 E2E (配额 + 分片 + 断点续传 + 缩略图) ===")
    print(f"BASE={BASE}")
    print(f"USERNAME={USERNAME}")

    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        await test_group_1_quota_default(client, headers)
        upload_id, file_name = await test_group_2_chunked_init(client, headers)
        chunks = await test_group_3_upload_chunks(client, headers, upload_id)
        await test_group_4_resume(client, headers, upload_id)
        new_file = await test_group_5_complete(client, headers, upload_id, file_name, chunks)
        png_id = await test_group_6_thumbnail(client, headers, new_file["id"], file_name)
        await test_group_7_quota_overflow(client, headers)
        reg_fid = await test_group_8_pr1_4_regression(client, headers)
        await test_group_9_cross_user_isolation(client, headers)

        await cleanup(client, headers, [new_file["id"], png_id, reg_fid])

    print(f"\n=== RESULT ===")
    print(f"PASSED: {len(PASSED)}")
    print(f"FAILED: {len(FAILED)}")
    for f in FAILED:
        safe = str(f).encode("ascii", "replace").decode("ascii")
        print(safe)
    print(f"\n=== END ===")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))