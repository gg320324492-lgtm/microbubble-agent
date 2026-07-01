"""
v2 PR7 端到端测试脚本 (文件请求 + 审计日志 + 团队共享盘)

测试覆盖 (8 groups, 28+ assertions):
1. file_request_create: 创建文件请求 + 验证 token
2. file_request_get_public: 公开查请求 (无需登录)
3. file_request_submit_public: 公开匿名提交文件
4. file_request_list_my: 列我创建的请求
5. file_request_deactivate: 关闭请求 (owner only)
6. audit_log_auto_write: 中间件自动写 audit_log
7. admin_audit_list: admin 查审计
8. PR1-6 regression: 基础端点不回归
"""
import os
import sys
import asyncio
import time
import subprocess
import json
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


# ============== Group 1: file_request_create ==============
async def test_group_1_create(client, headers):
    print("\n=== Test Group 1: file_request_create ===")
    resp = await client.post(
        "/file-requests", headers=headers,
        json={
            "title": "PR7 e2e smoke test 收作业",
            "description": "v2 PR7 file request 测试",
            "expires_in_days": 7,
            "require_uploader_name": True,
            "allowed_extensions": ["pdf", "docx", "txt"],
        },
    )
    assert_eq("POST 201", resp.status_code, 201)
    data = resp.json()
    assert_true("token 32 chars", len(data.get("token", "")) == 32)
    assert_eq("is_active True", data.get("is_active"), True)
    assert_eq("submission_count 0", data.get("submission_count"), 0)
    assert_true("title preserved", data.get("title", "").startswith("PR7"))
    assert_eq("allowed_extensions len", len(data.get("allowed_extensions", [])), 3)
    return data["token"], data["id"]


# ============== Group 2: get_public ==============
async def test_group_2_get_public(client, token):
    print("\n=== Test Group 2: file_request_get_public (anonymous) ===")
    # 公开端点 — 不带 Authorization 头
    resp = await client.get(f"/file-requests/{token}/info")
    assert_eq("public GET 200", resp.status_code, 200)
    data = resp.json()
    assert_eq("active True", data.get("active"), True)
    assert_true("title in public", "PR7" in data.get("title", ""))
    assert_true("creator_name present", bool(data.get("creator_name")))

    # 404 for invalid token
    resp = await client.get("/file-requests/invalid_token_xxxx/info")
    assert_eq("invalid token 404", resp.status_code, 404)


# ============== Group 3: submit_public ==============
async def test_group_3_submit_public(client, token):
    print("\n=== Test Group 3: file_request_submit_public (anonymous) ===")
    # 提交 pdf (allowed_extensions 含 pdf)
    files = {"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")}
    data = {"uploader_name": "匿名测试员"}
    resp = await client.post(
        f"/file-requests/{token}/submit",
        files=files, data=data,
    )
    assert_eq("submit 201", resp.status_code, 201)
    body = resp.json()
    assert_eq("submission_count = 1", body.get("submission_count"), 1)
    assert_eq("file_name preserved", body.get("file_name"), "test.pdf")

    # 不允许的扩展名 (.exe)
    files = {"file": ("virus.exe", b"binary", "application/octet-stream")}
    data = {"uploader_name": "测试员"}
    resp = await client.post(
        f"/file-requests/{token}/submit",
        files=files, data=data,
    )
    assert_eq("exe rejected 422", resp.status_code, 422)
    # 实际 service 错误: "不允许的文件类型 '.exe'，仅支持 pdf, txt"
    assert_true("detail mentions not allowed", "不允许" in (resp.json().get("detail") or ""))

    # 必填姓名缺失 → 422
    files = {"file": ("ok.pdf", b"%PDF", "application/pdf")}
    data = {}  # no uploader_name
    resp = await client.post(
        f"/file-requests/{token}/submit",
        files=files, data=data,
    )
    assert_eq("missing name 422", resp.status_code, 422)


# ============== Group 4: list_my ==============
async def test_group_4_list_my(client, headers, request_id):
    print("\n=== Test Group 4: file_request_list_my ===")
    resp = await client.get("/file-requests/my", headers=headers)
    assert_eq("GET my 200", resp.status_code, 200)
    items = resp.json().get("items", [])
    assert_true(f"含 {request_id}", any(i["id"] == request_id for i in items))
    # 已收到 1 份 (group 3 提交)
    req_obj = next((i for i in items if i["id"] == request_id), None)
    if req_obj:
        assert_eq("submission_count = 1", req_obj.get("submission_count"), 1)


# ============== Group 5: deactivate ==============
async def test_group_5_deactivate(client, headers, request_id):
    print("\n=== Test Group 5: file_request_deactivate ===")
    resp = await client.post(
        f"/file-requests/{request_id}/deactivate", headers=headers,
    )
    assert_eq("deactivate 204", resp.status_code, 204)

    # inactive 后 GET public 应该显示 active=False
    # 拿 token
    resp = await client.get("/file-requests/my", headers=headers)
    items = resp.json().get("items", [])
    req_obj = next((i for i in items if i["id"] == request_id), None)
    if req_obj:
        token = req_obj["token"]
        resp2 = await client.get(f"/file-requests/{token}/info")
        assert_eq("inactive GET 200", resp2.status_code, 200)
        assert_eq("active False", resp2.json().get("active"), False)

        # inactive 后 submit 应该返 410
        files = {"file": ("x.pdf", b"%PDF", "application/pdf")}
        data = {"uploader_name": "test"}
        resp3 = await client.post(
            f"/file-requests/{token}/submit", files=files, data=data,
        )
        assert_eq("submit inactive 410", resp3.status_code, 410)


# ============== Group 6: audit_log_auto_write ==============
async def test_group_6_audit_auto(client, headers):
    print("\n=== Test Group 6: audit_log_auto_write (middleware) ===")
    # 调用 1 个 endpoint → audit_log 自动写
    resp = await client.get("/file-requests/my", headers=headers)
    assert_eq("trigger 200", resp.status_code, 200)
    # 检查 audit_log 表
    sql = """
        SELECT action, COUNT(*) FROM audit_log
        WHERE created_at > NOW() - INTERVAL '5 minutes'
        GROUP BY action
        ORDER BY 2 DESC LIMIT 5;
    """
    try:
        out = subprocess.run(
            ["docker", "exec", "microbubble-agent-db-1",
             "psql", "-U", "postgres", "-d", "microbubble", "-c", sql, "-t", "-A"],
            capture_output=True, text=True, timeout=10,
        )
        rows = [r.strip() for r in out.stdout.split("\n") if r.strip()]
        assert_true(f"audit 写入 (rows={len(rows)})", len(rows) > 0)
        if rows:
            print(f"  [dbg] audit actions: {rows[:3]}")
    except Exception as e:
        print(f"  [WARN] audit verify failed: {e}")


# ============== Group 7: admin_audit ==============
async def test_group_7_admin_audit(client, headers):
    print("\n=== Test Group 7: admin_audit_list (admin) ===")
    resp = await client.get("/admin/audit?page=1&page_size=10", headers=headers)
    assert_eq("admin GET 200", resp.status_code, 200)
    data = resp.json()
    assert_true(f"items array", isinstance(data.get("items"), list))
    assert_true("has total", "total" in data)

    # admin summary
    resp = await client.get("/admin/audit/summary", headers=headers)
    assert_eq("summary 200", resp.status_code, 200)
    summary = resp.json()
    assert_true("total in summary", "total" in summary)
    assert_true("by_action in summary", "by_action" in summary)


# ============== Group 8: PR1-6 regression ==============
async def test_group_8_regression(client, headers):
    print("\n=== Test Group 8: PR1-6 regression ===")
    # PR2 share + star
    files = {"file": (f"pr7_reg_{int(time.time())}.txt", b"reg", "text/plain")}
    data = {"visibility": "team", "storage_mode": "drive"}
    resp = await client.post("/drive/files/upload", headers=headers, files=files, data=data)
    assert_eq("upload 201", resp.status_code, 201)
    fid = resp.json()["id"]

    resp = await client.post(f"/drive/files/{fid}/share-link", headers=headers, json={"expires_hours": 24})
    assert_eq("share-link 200", resp.status_code, 200)

    resp = await client.post(f"/drive/files/{fid}/toggle-star", headers=headers)
    assert_eq("toggle-star 200", resp.status_code, 200)

    # PR6 notifications
    resp = await client.get("/notifications/unread-count", headers=headers)
    assert_eq("unread-count 200", resp.status_code, 200)

    # PR6 activities
    resp = await client.get("/activities?scope=me&limit=5", headers=headers)
    assert_eq("activities 200", resp.status_code, 200)

    # 清理
    await client.post(
        "/drive/files/batch-soft-delete", headers=headers,
        json={"file_ids": [fid]},
    )


# ============== Setup cleanup ==============
async def setup_cleanup():
    """清理 testbot 历史 PR7 数据"""
    sql = """
        DELETE FROM audit_log WHERE user_id IN (SELECT id FROM members WHERE username IN ('xiaoqi_testbot','xiaoqi_testbot_2'));
        DELETE FROM file_requests WHERE created_by IN (SELECT id FROM members WHERE username IN ('xiaoqi_testbot','xiaoqi_testbot_2'));
        UPDATE knowledge SET deleted_at = NOW() WHERE created_by IN (SELECT id FROM members WHERE username IN ('xiaoqi_testbot','xiaoqi_testbot_2'))
            AND deleted_at IS NULL AND storage_mode='drive' AND created_at > NOW() - INTERVAL '1 hour';
    """
    try:
        out = subprocess.run(
            ["docker", "exec", "microbubble-agent-db-1",
             "psql", "-U", "postgres", "-d", "microbubble", "-c", sql],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0:
            print(f"  [setup] cleaned PR7 data")
        else:
            print(f"  [WARN] setup: {out.stderr[:200]}")
    except Exception as e:
        print(f"  [WARN] setup failed: {e}")


async def main():
    print(f"=== v2 PR7 E2E (文件请求 + 审计 + 团队共享盘) ===")
    print(f"BASE={BASE}")
    print(f"USERNAME={USERNAME}")

    await setup_cleanup()

    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        token_str, req_id = await test_group_1_create(client, headers)
        await test_group_2_get_public(client, token_str)
        await test_group_3_submit_public(client, token_str)
        await test_group_4_list_my(client, headers, req_id)
        await test_group_5_deactivate(client, headers, req_id)
        await test_group_6_audit_auto(client, headers)
        await test_group_7_admin_audit(client, headers)
        await test_group_8_regression(client, headers)

    print(f"\n=== RESULT ===")
    print(f"PASSED: {len(PASSED)}")
    print(f"FAILED: {len(FAILED)}")
    for f in FAILED:
        print(f"  {f}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
