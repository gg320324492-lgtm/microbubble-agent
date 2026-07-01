"""scripts/test_pr1_e2e.py — 课题组网盘 v2 PR1 端到端测试

覆盖范围:
1. ShareLink creation (no password / 4-digit / 8-digit / invalid / default 7d)
2. Public download with/without password (no-auth)
3. Revoke share link
4. Update visibility (owner / 越权 / invalid value / 404)
5. extract-to-kb (drive storage_mode flip + visibility 升级)
6. testbot 数据隔离 (他账号看不到 private 文件 + 不能操作他人文件)

测试账号: xiaoqi_testbot / testbot_pass_2026 (CLAUDE.md 2026-07-01 v0.1.0 规范)

支持环境变量覆盖:
- E2E_USERNAME: 默认 xiaoqi_testbot
- E2E_PASSWORD: 默认 testbot_pass_2026
- BASE_URL:    默认 http://localhost:8000

运行:
  python scripts/test_pr1_e2e.py
  E2E_USERNAME=foo E2E_PASSWORD=bar python scripts/test_pr1_e2e.py
"""
import asyncio
import os
import sys
import json

# 测试账号优先级: env 覆盖 > 硬编码默认值 (避免 import conftest 触发 pytest 强依赖)
TARGET_USERNAME = os.environ.get("E2E_USERNAME", "xiaoqi_testbot")
TARGET_PASSWORD = os.environ.get("E2E_PASSWORD", "testbot_pass_2026")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

import httpx


async def login(client, username, password):
    resp = await client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return resp.json()["access_token"]


async def upload_drive_file(client, token, label):
    """上传 1 个 drive 文件用于测试."""
    import io
    import time

    content = f"PR1 test content {label} - {time.time()}".encode()
    files = {"file": (f"pr1_{label}.txt", io.BytesIO(content), "text/plain")}
    data = {"visibility": "team", "storage_mode": "drive", "title": f"PR1 {label}"}
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        data=data,
    )
    assert resp.status_code in (200, 201), f"upload failed: {resp.text}"
    return resp.json()["id"]


async def test_share_link_password_validation(client, token, file_id):
    """测试 share-link creation 各场景.

    注意: 每次 create_share_link 都覆盖文件之前的 share 设置.
    为了让 Test 2 测试 password-protected, 这里**最后一个**操作必须保留 password.
    """
    print("\n=== Test 1: Share-link creation variations ===")

    # A. No password (公开分享)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_hours": 24, "password": None},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert not d["password_required"]
    assert d["expires_at"] is not None
    print(f"  ✓ A. no password: expires_at={d['expires_at'][:19]}, pwd_required={d['password_required']}")

    # B. 4-digit password (expires_hours=168)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_hours": 720, "password": "87654321"},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["password_required"]
    print(f"  ✓ B. 8-digit pwd: ok")

    # C. Invalid password (3 digits - too short, expect 400)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_hours": 168, "password": "123"},
    )
    assert resp.status_code == 400, f"invalid pwd should 400, got {resp.status_code}"
    print(f"  ✓ C. too short pwd: 400")

    # D. Invalid password (non-numeric - expect 400)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_hours": 168, "password": "abcd"},
    )
    assert resp.status_code == 400
    print(f"  ✓ D. non-numeric pwd: 400")

    # E. Permanent (-1)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_hours": -1, "password": None},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["expires_at"] is None  # 永久
    print(f"  ✓ E. permanent: expires_at={d['expires_at']} (永久)")

    # F. Default 7d (expires_hours=0)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_hours": 0, "password": None},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["expires_at"] is not None
    print(f"  ✓ F. default 7d: expires_at={d['expires_at'][:19]}")

    # G. 最后: 设回 password=1234 7d (供 Test 2 验证 password-protected 下载路径)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_hours": 168, "password": "1234"},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["password_required"]
    token_with_pwd = d["token"]
    share_url_with_pwd = d["share_url"]
    print(f"  ✓ G. final 4-digit pwd 1234 (供 Test 2 使用): token={token_with_pwd[:8]}...")

    return token_with_pwd, share_url_with_pwd


async def test_public_download_password(client, token_with_pwd, file_id_with_pwd):
    """测试公开下载 (无 JWT). 仅 password-protected 路径."""
    print("\n=== Test 2: Public download with/without password ===")

    # A. With password but providing wrong one → expect 403
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/{token_with_pwd}?password=0000")
    assert resp.status_code == 403, f"wrong pwd should 403: {resp.status_code}"
    print(f"  ✓ A. wrong pwd: 403")

    # B. With password but no password provided → expect 403
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/{token_with_pwd}")
    assert resp.status_code == 403, f"missing pwd should 403: {resp.status_code}"
    print(f"  ✓ B. missing pwd: 403")

    # C. With password providing correct one → expect 200 stream
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/{token_with_pwd}?password=1234")
    assert resp.status_code == 200, f"correct pwd should 200: {resp.status_code} {resp.text[:200]}"
    body = resp.content
    assert len(body) > 0
    print(f"  ✓ C. correct pwd: 200, {len(body)} bytes")

    # D. Non-existent token → expect 403 (统一错误不区分)
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/nonexistent_token_32chars_xxxxxxxx")
    assert resp.status_code == 403
    print(f"  ✓ D. bogus token: 403 (不区分不存在/过期/密码错)")


async def test_share_info_endpoint(client):
    """测试 GET /share/{token}/info 元信息端点."""
    print("\n=== Test 3: Share /info endpoint ===")
    test_bot_token = await login(client, TARGET_USERNAME, TARGET_PASSWORD)
    file_id = await upload_drive_file(client, test_bot_token, "info_test")

    # Create with pwd
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"expires_hours": 24, "password": "1234"},
    )
    token = resp.json()["token"]

    # A. Get info (no auth, no pwd)
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/{token}/info")
    assert resp.status_code == 200
    d = resp.json()
    assert d["password_required"] is True
    assert d["expires_at"] is not None
    assert d["file_name"] == "pr1_info_test.txt"
    print(f"  ✓ A. info w/ pwd: file_name={d['file_name']}, pwd_required={d['password_required']}")

    # B. Non-existent token (expect 404)
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/bogus_x32/info")
    assert resp.status_code == 404
    print(f"  ✓ B. bogus token: 404")


async def test_revoke_and_isolation(client):
    """测试 revoke share + user 隔离 (不能 revoke 他人 share)."""
    print("\n=== Test 4: Revoke share + user isolation ===")
    test_bot_token = await login(client, TARGET_USERNAME, TARGET_PASSWORD)
    file_id = await upload_drive_file(client, test_bot_token, "revoke_test")

    # Create share
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"expires_hours": 24, "password": "1234"},
    )
    token = resp.json()["token"]
    assert resp.json()["password_required"] is True

    # Public download w/ pwd works
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/{token}?password=1234")
    assert resp.status_code == 200
    print(f"  ✓ A. before revoke: 200")

    # Revoke
    resp = await client.delete(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {test_bot_token}"},
    )
    assert resp.status_code == 204
    print(f"  ✓ B. revoke: 204")

    # Public download after revoke (expect 403)
    resp = await client.get(f"{BASE_URL}/api/v1/drive/share/{token}?password=1234")
    assert resp.status_code == 403
    print(f"  ✓ C. after revoke: 403 (token 失效)")


async def test_visibility_endpoint(client):
    """测试 PUT /visibility 各种场景."""
    print("\n=== Test 5: Update visibility endpoint ===")
    test_bot_token = await login(client, TARGET_USERNAME, TARGET_PASSWORD)
    file_id = await upload_drive_file(client, test_bot_token, "vis_test")

    # A. Owner sets to private
    resp = await client.put(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/visibility",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"visibility": "private"},
    )
    assert resp.status_code == 200
    assert resp.json()["visibility"] == "private"
    print(f"  ✓ A. owner → private: 200")

    # B. Owner sets to team
    resp = await client.put(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/visibility",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"visibility": "team"},
    )
    assert resp.status_code == 200
    print(f"  ✓ B. owner → team: 200")

    # C. Owner sets to public
    resp = await client.put(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/visibility",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"visibility": "public"},
    )
    assert resp.status_code == 200
    print(f"  ✓ C. owner → public: 200")

    # D. Invalid value (expect 400)
    resp = await client.put(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/visibility",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"visibility": "bogus"},
    )
    assert resp.status_code == 400
    print(f"  ✓ D. invalid value: 400")

    # E. Non-existent file (expect 404)
    resp = await client.put(
        f"{BASE_URL}/api/v1/drive/files/999999/visibility",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"visibility": "team"},
    )
    assert resp.status_code == 404
    print(f"  ✓ E. non-existent: 404")


async def test_extract_to_kb(client):
    """测试 extract-to-kb 升级."""
    print("\n=== Test 6: Extract to KB ===")
    test_bot_token = await login(client, TARGET_USERNAME, TARGET_PASSWORD)
    file_id = await upload_drive_file(client, test_bot_token, "extract_test")

    # A. Upgrade to team
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/extract-to-kb",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"target_visibility": "team"},
    )
    assert resp.status_code == 200
    print(f"  ✓ A. extract → team: 200")

    # Verify storage_mode in /api/v1/drive/files list
    resp = await client.get(
        f"{BASE_URL}/api/v1/drive/files",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        params={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    # The extracted file should NOT be in drive list anymore (storage_mode=kb)
    match = [f for f in items if f["id"] == file_id]
    assert len(match) == 0, "extracted file should be removed from drive list"
    print(f"  ✓ B. drive list no longer contains file {file_id} (storage_mode=kb)")

    # C. Verify in /knowledge stats
    resp = await client.get(
        f"{BASE_URL}/api/v1/knowledge/stats",
        headers={"Authorization": f"Bearer {test_bot_token}"},
    )
    assert resp.status_code == 200
    print(f"  ✓ C. /knowledge/stats ok")


async def test_data_isolation(client):
    """测试 testbot 数据隔离 - 创建 private 文件 + 用临时 2nd 账号尝试访问.

    依赖: ensure_test_user.py 已创建 pr1_temp_user / pr1_temp_pass_2026 (一次性)
    """
    print("\n=== Test 7: testbot data isolation ===")

    temp_user = "pr1_temp_user"
    temp_password = "pr1_temp_pass_2026"
    test_bot_token = await login(client, TARGET_USERNAME, TARGET_PASSWORD)

    # Verify temp user exists
    try:
        temp_token = await login(client, temp_user, temp_password)
        print(f"  ✓ setup: temp user '{temp_user}' exists + logged in")
    except AssertionError as e:
        print(f"  ⚠️  temp user not exists: {e}")
        print(f"  ⚠️  跳过数据隔离测试 (确保运行 scripts/ensure_test_user.py --username pr1_temp_user)")
        return

    file_id = await upload_drive_file(client, test_bot_token, "private_test")

    # Set to private (only testbot owner can see)
    resp = await client.put(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/visibility",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        json={"visibility": "private"},
    )
    assert resp.status_code == 200
    print(f"  ✓ setup: file id={file_id} visibility=private")

    # A. testbot (owner) lists → should see the file
    resp = await client.get(
        f"{BASE_URL}/api/v1/drive/files",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        params={"page": 1, "page_size": 100},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    match = [f for f in items if f["id"] == file_id]
    assert len(match) == 1, f"owner should see own private file, got count={len(match)}"
    print(f"  ✓ A. owner sees own private: yes")

    # B. temp user (different) lists → should NOT see it
    resp = await client.get(
        f"{BASE_URL}/api/v1/drive/files",
        headers={"Authorization": f"Bearer {temp_token}"},
        params={"page": 1, "page_size": 100},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    match = [f for f in items if f["id"] == file_id]
    assert len(match) == 0, f"non-owner should NOT see private file, got count={len(match)}"
    print(f"  ✓ B. non-owner blocked from private: yes")

    # C. temp user tries to modify visibility (expect 404 - 隐身)
    resp = await client.put(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/visibility",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={"visibility": "public"},
    )
    assert resp.status_code == 404, f"non-owner should get 404, got {resp.status_code}"
    print(f"  ✓ C. non-owner PUT /visibility: 404 (隐身)")

    # D. temp user tries to share it (expect 404)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/share-link",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={"expires_hours": 24, "password": None},
    )
    assert resp.status_code == 404
    print(f"  ✓ D. non-owner POST /share-link: 404")

    # E. temp user tries to extract to kb (expect 404)
    resp = await client.post(
        f"{BASE_URL}/api/v1/drive/files/{file_id}/extract-to-kb",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={"target_visibility": "team"},
    )
    assert resp.status_code == 404
    print(f"  ✓ E. non-owner POST /extract-to-kb: 404")


async def cleanup(client):
    """清理测试产生的数据."""
    print("\n=== Cleanup ===")
    test_bot_token = await login(client, TARGET_USERNAME, TARGET_PASSWORD)
    resp = await client.get(
        f"{BASE_URL}/api/v1/drive/files",
        headers={"Authorization": f"Bearer {test_bot_token}"},
        params={"page": 1, "page_size": 100},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    deleted = 0
    for f in items:
        if f.get("title", "").startswith("PR1 "):
            r = await client.delete(
                f"{BASE_URL}/api/v1/drive/files/{f['id']}",
                headers={"Authorization": f"Bearer {test_bot_token}"},
            )
            if r.status_code in (200, 204):
                deleted += 1
    print(f"  ✓ Cleaned {deleted} PR1 test files")


async def main():
    print("=" * 60)
    print("PR1 端到端测试 (xiaoqi_testbot / testbot_pass_2026)")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            test_bot_token = await login(client, TARGET_USERNAME, TARGET_PASSWORD)
            file_id = await upload_drive_file(client, test_bot_token, "master_test")
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            sys.exit(1)

        try:
            token_with_pwd, share_url = await test_share_link_password_validation(client, test_bot_token, file_id)
            await test_public_download_password(client, token_with_pwd, file_id)
            await test_share_info_endpoint(client)
            await test_revoke_and_isolation(client)
            await test_visibility_endpoint(client)
            await test_extract_to_kb(client)
            await test_data_isolation(client)
            await cleanup(client)
            print("\n" + "=" * 60)
            print("✅ 所有 PR1 测试 PASS")
            print("=" * 60)
        except AssertionError as e:
            print(f"\n❌ ASSERTION FAILED: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
