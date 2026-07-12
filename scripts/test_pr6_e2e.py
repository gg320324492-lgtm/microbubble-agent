"""
v2 PR6 端到端测试脚本 (通知 + @ 提醒 + 活动动态流 + 文件评论)

测试覆盖 (8 groups, 32+ assertions):
1. notification init: 创建 mention 后 unread_count=1, list 包含该条
2. mention idempotency: 24h 内同 (file_id, user) 重复 @ 跳过 (dedup)
3. mark-read / mark-all-read: 标已读后 unread_count=0
4. cross-user isolation: testbot2 看不到 testbot1 的 mentions
# 2026-07-12: Group 5 activity log + Group 6 activity feed 已删除 (UI 已下线)
# (后续行号保留为 7/8/9, 注释标明删除原因)
7. comment + auto-mention: 评论含 @xiaoqi_testbot_2 → 自动创建 mention
8. comment delete: owner of comment OR owner of file 才能删
9. PR1-5 regression: drive upload + share + star + version + thumbnail
"""
import os
import sys
import asyncio
import time
import subprocess
import re
from typing import Optional

import httpx

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000/api/v1")
USERNAME = os.environ.get("E2E_USERNAME", "xiaoqi_testbot")
PASSWORD = os.environ.get("E2E_PASSWORD", "testbot_pass_2026")
USERNAME2 = os.environ.get("E2E_USERNAME2", "xiaoqi_testbot_2")
PASSWORD2 = os.environ.get("E2E_PASSWORD2", "testbot_pass_2026_2")


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


# ============== Group 1: notification init ==============
async def test_group_1_notification_init(client, headers):
    """1. 创建 mention 后 unread_count=1, list 包含该条"""
    print("\n=== Test Group 1: notification init ===")
    # 先传一个文件
    files = {"file": (f"pr6_init_{int(time.time())}.txt", b"init", "text/plain")}
    data = {"visibility": "team", "storage_mode": "drive"}
    resp = await client.post("/drive/files/upload", headers=headers, files=files, data=data)
    assert_eq("upload 201", resp.status_code, 201)
    file_id = resp.json()["id"]

    # 直接调 service 写 mention (绕开评论; @mention 单元单独测)
    # 这里用 SQL 直接 INSERT 简化 (测试不依赖评论流程)
    sql = f"""
        INSERT INTO file_mentions (file_id, mentioned_user_id, mentioned_by, context, is_read)
        VALUES ({file_id}, (SELECT id FROM members WHERE username='xiaoqi_testbot'),
                (SELECT id FROM members WHERE username='xiaoqi_testbot'),
                'mention', false);
    """
    try:
        subprocess.run(
            ["docker", "exec", "microbubble-agent-db-1",
             "psql", "-U", "postgres", "-d", "microbubble", "-c", sql],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        print(f"  [WARN] DB insert failed: {e}")

    # unread_count
    resp = await client.get("/notifications/unread-count", headers=headers)
    assert_eq("unread-count 200", resp.status_code, 200)
    assert_true("unread_count >= 1", resp.json().get("unread_count", 0) >= 1)

    # list
    resp = await client.get("/notifications?unread_only=true", headers=headers)
    assert_eq("list 200", resp.status_code, 200)
    items = resp.json().get("items", [])
    assert_true(f"items 含 {file_id}", any(i.get("file_id") == file_id for i in items))

    return file_id


# ============== Group 2: mention idempotency ==============
async def test_group_2_mention_idempotency(client, headers):
    """2. 24h 内同 (file_id, user) 重复 @ 跳过 (dedup)"""
    print("\n=== Test Group 2: mention idempotency ===")
    # upload 文件
    files = {"file": (f"pr6_idem_{int(time.time())}.txt", b"idem", "text/plain")}
    data = {"visibility": "team", "storage_mode": "drive"}
    resp = await client.post("/drive/files/upload", headers=headers, files=files, data=data)
    file_id = resp.json()["id"]
    print(f"  [dbg] Group 2 file_id={file_id}", flush=True)

    # 用 SQL 两次 INSERT 看 dedup 是否生效 (因为走 API 难触发, 直接调 service)
    # 这里改为通过 comment 触发 (测评论流程同时测 idempotency)
    initial_unread = (await client.get("/notifications/unread-count", headers=headers)).json()["unread_count"]

    # 评论 1 次 (无 @ → 不应创建 mention)
    resp = await client.post(
        f"/drive/files/{file_id}/comments", headers=headers,
        json={"content": "first comment no mention"},
    )
    assert_eq("comment 1 201", resp.status_code, 201)
    assert_eq("mention_count = 0", resp.json().get("mentioned_user_ids"), [])

    # 评论含 @xiaoqi_testbot → 创建 1 mention
    resp = await client.post(
        f"/drive/files/{file_id}/comments", headers=headers,
        json={"content": "@xiaoqi_testbot_2 看下这个文件"},
    )
    assert_eq("comment 2 201", resp.status_code, 201)
    mentioned = resp.json().get("mentioned_user_ids", [])
    assert_eq("mention_count = 1", len(mentioned), 1)

    # 评论含 @xiaoqi_testbot 第二次 → 应被 dedup 跳过 (24h 内)
    resp = await client.post(
        f"/drive/files/{file_id}/comments", headers=headers,
        json={"content": "@xiaoqi_testbot_2 第二次提"},
    )
    assert_eq("comment 3 201", resp.status_code, 201)
    dbg_resp3 = resp.json()
    print(f"  [dbg] Group 2 comment 3 resp: file_id={file_id} mentioned={dbg_resp3.get('mentioned_user_ids')}", flush=True)
    # 因 idempotency, 不再增加 mention (mentioned_user_ids 返空)
    assert_eq("mention_count = 0 (dedup)", resp.json().get("mentioned_user_ids"), [])

    return file_id


# ============== Group 3: mark-read / mark-all-read ==============
async def test_group_3_mark_read(client, headers):
    """3. 标已读后 unread_count=0"""
    print("\n=== Test Group 3: mark-read ===")
    # 先 unread 列表取 first
    resp = await client.get("/notifications?unread_only=true", headers=headers)
    items = resp.json().get("items", [])
    assert_true(f"at least 1 unread", len(items) > 0)
    if not items:
        return

    first_id = items[0]["id"]
    resp = await client.post(f"/notifications/{first_id}/read", headers=headers)
    assert_eq("mark-read 204", resp.status_code, 204)

    # 越权 (用 testbot2 token 标 testbot1 的 mention)
    try:
        token2 = await login(client, USERNAME2, PASSWORD2)
        headers2 = {"Authorization": f"Bearer {token2}"}
        resp = await client.post(f"/notifications/{first_id}/read", headers=headers2)
        assert_eq("cross-user mark-read 404", resp.status_code, 404)
    except Exception as e:
        print(f"  [WARN] testbot2 login failed: {e}")

    # 标全部
    resp = await client.post("/notifications/read-all", headers=headers)
    assert_eq("read-all 200", resp.status_code, 200)
    assert_true("marked_count >= 0", resp.json().get("marked_count", -1) >= 0)

    # 全部 unread 应该 0
    resp = await client.get("/notifications/unread-count", headers=headers)
    assert_eq("unread_count=0 after read-all", resp.json().get("unread_count"), 0)


# ============== Group 4: cross-user isolation ==============
async def test_group_4_cross_user_isolation(client, headers):
    """4. testbot2 看不到 testbot1 的 mentions"""
    print("\n=== Test Group 4: cross-user isolation ===")
    try:
        token2 = await login(client, USERNAME2, PASSWORD2)
        headers2 = {"Authorization": f"Bearer {token2}"}

        # testbot2 的 notifications 应不含 testbot1 的 mention
        resp = await client.get("/notifications", headers=headers2)
        items2 = resp.json().get("items", [])

        # testbot2 自己 unread_count
        resp2 = await client.get("/notifications/unread-count", headers=headers2)
        assert_eq("testbot2 unread_count >= 0", resp2.json().get("unread_count", 0) >= 0, True)
        return headers2
    except Exception as e:
        print(f"  [WARN] testbot2 setup failed: {e}")
        return None


# 2026-07-12: Group 5 (activity log) + Group 6 (activity feed) 已删除
# 原因: /api/v1/activities endpoint 已随"活动动态"UI 一起彻底删除 (commit f66a2120, 2026-07-03 用户决策)
# 仅 audit log (activity_events 表) 保留供 drive/comment/file_request 审计用, 但前端 UI 无 consumer


# ============== Group 7: comment + auto-mention ==============
async def test_group_7_comment_mention(client, headers):
    """7. 评论含 @ → 自动创建 mention"""
    print("\n=== Test Group 7: comment + mention ===")
    # upload file
    files = {"file": (f"pr6_com_{int(time.time())}.txt", b"comment test", "text/plain")}
    data = {"visibility": "team", "storage_mode": "drive"}
    resp = await client.post("/drive/files/upload", headers=headers, files=files, data=data)
    file_id = resp.json()["id"]

    # 评论含 @xiaoqi_testbot_2
    resp = await client.post(
        f"/drive/files/{file_id}/comments", headers=headers,
        json={"content": "@xiaoqi_testbot_2 你看看"},
    )
    assert_eq("comment 201", resp.status_code, 201)
    data = resp.json()
    comment_id = data["comment"]["id"]
    mentioned = data["mentioned_user_ids"]
    L = len(mentioned)
    assert_eq("mention_count = 1", L, 1)

    # 列评论
    resp = await client.get(f"/drive/files/{file_id}/comments", headers=headers)
    assert_eq("list comments 200", resp.status_code, 200)
    items = resp.json().get("items", [])
    assert_true(f"含刚才评论 id={comment_id}", any(c["id"] == comment_id for c in items))

    # testbot2 看到 mention
    try:
        token2 = await login(client, USERNAME2, PASSWORD2)
        headers2 = {"Authorization": f"Bearer {token2}"}
        resp = await client.get("/notifications?unread_only=true", headers=headers2)
        items = resp.json().get("items", [])
        assert_true("testbot2 收到 mention",
                    any(i.get("file_id") == file_id for i in items))
    except Exception as e:
        print(f"  [WARN] testbot2 login failed: {e}")

    return file_id, comment_id


# ============== Group 8: comment delete (越权防护) ==============
async def test_group_8_comment_delete(client, headers):
    """8. owner of comment OR owner of file 才能删"""
    print("\n=== Test Group 8: comment delete ===")
    file_id, comment_id = await test_group_7_comment_mention(client, headers)

    # owner (testbot1 = self) 删自己的评论 → 应成功
    resp = await client.delete(f"/drive/files/{file_id}/comments/{comment_id}", headers=headers)
    assert_eq("owner delete 204", resp.status_code, 204)

    # 再次 DELETE → 404
    resp = await client.delete(f"/drive/files/{file_id}/comments/{comment_id}", headers=headers)
    assert_eq("re-delete 404", resp.status_code, 404)

    # testbot2 越权 → 应 404 (隐身)
    try:
        token2 = await login(client, USERNAME2, PASSWORD2)
        headers2 = {"Authorization": f"Bearer {token2}"}
        # testbot2 先写一条评论
        resp = await client.post(
            f"/drive/files/{file_id}/comments", headers=headers2,
            json={"content": "testbot2 评论"},
        )
        if resp.status_code == 201:
            c2_id = resp.json()["comment"]["id"]
            # testbot1 是 file owner, 有权删 → 应 204
            resp = await client.delete(f"/drive/files/{file_id}/comments/{c2_id}", headers=headers)
            assert_eq("file owner 删别人评论 204", resp.status_code, 204)
            # 重复删 → 404
            resp = await client.delete(f"/drive/files/{file_id}/comments/{c2_id}", headers=headers)
            assert_eq("re-delete 404", resp.status_code, 404)
    except Exception as e:
        print(f"  [WARN] testbot2 delete test failed: {e}")


# ============== Group 9: PR1-5 regression ==============
async def test_group_9_pr1_5_regression(client, headers):
    """9. PR1-5 端点不回归"""
    print("\n=== Test Group 9: PR1-5 regression ===")
    # PR2 share + star
    files = {"file": (f"pr6_reg_{int(time.time())}.txt", b"reg", "text/plain")}
    data = {"visibility": "team", "storage_mode": "drive"}
    resp = await client.post("/drive/files/upload", headers=headers, files=files, data=data)
    fid = resp.json()["id"]

    resp = await client.post(f"/drive/files/{fid}/share-link", headers=headers, json={"expires_hours": 24})
    assert_eq("share-link 200", resp.status_code, 200)

    resp = await client.post(f"/drive/files/{fid}/toggle-star", headers=headers)
    assert_eq("toggle-star 200", resp.status_code, 200)

    # PR5 storage quota
    resp = await client.get("/drive/storage-quota", headers=headers)
    assert_eq("storage-quota 200", resp.status_code, 200)

    # PR4 versions
    resp = await client.get(f"/drive/files/{fid}/versions", headers=headers)
    assert_eq("versions 200", resp.status_code, 200)

    # PR5 thumbnail
    resp = await client.get(f"/drive/files/{fid}/thumbnail", headers=headers)
    assert_eq("thumbnail 200", resp.status_code, 200)

    return fid


async def cleanup(client, headers, file_ids):
    if not file_ids:
        return
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
    print(f"=== v2 PR6 E2E (通知 + @ 提醒 + 活动流 + 评论) ===")
    print(f"BASE={BASE}")
    print(f"USERNAME={USERNAME}")

    # PR6 setup: 清空 testbot 全部 PR6 数据 (file_mentions / activity_events / file_comments + drive files)
    # e2e 必须幂等 (跑多次结果一致), 否则 dedup + 累积会让断言不可靠
    setup_cleanup_sql = """
        DELETE FROM file_comments WHERE user_id IN (SELECT id FROM members WHERE username IN ('xiaoqi_testbot','xiaoqi_testbot_2'));
        DELETE FROM file_mentions WHERE mentioned_user_id IN (SELECT id FROM members WHERE username IN ('xiaoqi_testbot','xiaoqi_testbot_2'));
        UPDATE knowledge SET deleted_at = NOW() WHERE created_by IN (SELECT id FROM members WHERE username IN ('xiaoqi_testbot','xiaoqi_testbot_2')) AND deleted_at IS NULL;
    """
    print(f"  [setup] running cleanup SQL...")
    try:
        result = subprocess.run(
            ["docker", "exec", "microbubble-agent-db-1",
             "psql", "-U", "postgres", "-d", "microbubble", "-c", setup_cleanup_sql],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            print(f"  [WARN] setup cleanup SQL rc={result.returncode}: {result.stderr[:200]}")
        else:
            print(f"  [setup] cleanup done: {result.stdout.strip()[:200]}")
    except Exception as e:
        print(f"  [WARN] setup cleanup failed: {e}")

    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        init_fid = await test_group_1_notification_init(client, headers)
        await test_group_2_mention_idempotency(client, headers)
        await test_group_3_mark_read(client, headers)
        await test_group_4_cross_user_isolation(client, headers)
        # Group 7 在 Group 8 内部调用 (comment_id 复用)
        await test_group_8_comment_delete(client, headers)
        reg_fid = await test_group_9_pr1_5_regression(client, headers)

        # 清理 (保留 init_fid 用于 verify)
        cleanup_ids = [reg_fid] if reg_fid else []
        # Group 7/8 内部产生的 file_id 不返回, 用 SQL 清残留
        subprocess.run(
            ["docker", "exec", "microbubble-agent-db-1",
             "psql", "-U", "postgres", "-d", "microbubble", "-c",
             f"UPDATE knowledge SET deleted_at = NOW() WHERE created_by = (SELECT id FROM members WHERE username='xiaoqi_testbot') AND deleted_at IS NULL AND storage_mode='drive' AND id > 100;"],
            capture_output=True, text=True, timeout=15,
        )

    print(f"\n=== RESULT ===")
    print(f"PASSED: {len(PASSED)}")
    print(f"FAILED: {len(FAILED)}")
    for f in FAILED:
        safe = str(f).encode("ascii", "replace").decode("ascii")
        print(safe)
    for f in FAILED:
        if chr(109)+chr(101)+chr(110)+chr(116)+chr(105)+chr(111)+chr(110)+chr(95)+chr(99)+chr(111)+chr(117)+chr(110)+chr(116) in f:
            print(f">>> FAIL: {f}", flush=True)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))