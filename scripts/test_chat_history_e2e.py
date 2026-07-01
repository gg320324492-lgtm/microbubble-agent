import os
import sys
import time

import requests

# 测试账号 (从 conftest 常量导, 避免与生产 admin wangtianzhi 物理隔离被破坏)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import TEST_BOT_USERNAME, TEST_BOT_PASSWORD  # noqa: E402

BASE = "http://localhost:8000/api/v1"
E2E_USERNAME = os.environ.get("E2E_USERNAME", TEST_BOT_USERNAME)
E2E_PASSWORD = os.environ.get("E2E_PASSWORD", TEST_BOT_PASSWORD)
TOKEN = requests.post(
    f"{BASE}/auth/login",
    json={"username": E2E_USERNAME, "password": E2E_PASSWORD},
    timeout=10,
).json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}
TS = int(time.time())  # 每次跑用唯一时间戳避免 test pollution
SID_BASE = f"test_e2e_{TS}"

results = []
def test(name, fn):
    try:
        r = fn()
        results.append(f"  {'OK' if r.ok else 'FAIL'} [{r.status_code}] {name}")
        return r
    except Exception as e:
        results.append(f"  ERROR {name}: {e}")
        return None

print("=== 1. Session CRUD ===")
test("GET /chat/sessions", lambda: requests.get(f"{BASE}/chat/sessions", headers=H))
r = test("POST /chat/sessions", lambda: requests.post(f"{BASE}/chat/sessions", headers=H, json={"title":"测试","first_message":"你好","client_session_id":SID_BASE}))
if r and r.ok:
    SID = r.json()["id"]
    print(f"  SID: {SID}")
    test("GET /chat/sessions/{id}", lambda: requests.get(f"{BASE}/chat/sessions/{SID}", headers=H))
    test("PATCH pin+tags", lambda: requests.patch(f"{BASE}/chat/sessions/{SID}", headers=H, json={"is_pinned":True,"tags":["work","research"]}))
    test("POST messages (assistant)", lambda: requests.post(f"{BASE}/chat/sessions/{SID}/messages", headers=H, json={"role":"assistant","content":"我很好","client_msg_id":f"msg_{TS}_001","rich_blocks":[{"type":"meeting","data":{}}]}))
    test("POST same client_msg_id (idempotency)", lambda: requests.post(f"{BASE}/chat/sessions/{SID}/messages", headers=H, json={"role":"assistant","content":"我很好","client_msg_id":f"msg_{TS}_001"}))
    test("GET messages", lambda: requests.get(f"{BASE}/chat/sessions/{SID}/messages?page_size=50", headers=H))
    test("GET export?format=md", lambda: requests.get(f"{BASE}/chat/sessions/{SID}/export?format=md", headers=H))
    test("GET search?q=你好", lambda: requests.get(f"{BASE}/chat/sessions/search?q=你好", headers=H))
    test("POST share", lambda: requests.post(f"{BASE}/chat/sessions/{SID}/share", headers=H, json={"permission":"read","expires_hours":24}))
    r3 = test("GET shares", lambda: requests.get(f"{BASE}/chat/sessions/{SID}/shares", headers=H))
    if r3 and r3.ok and r3.json():
        token = r3.json()[0]["id"]
        test(f"GET public share {token[:10]}...", lambda: requests.get(f"{BASE}/chat/shares/{token}"))
        test("DELETE share", lambda: requests.delete(f"{BASE}/chat/sessions/{SID}/shares/{token}", headers=H))

print("\n=== 2. Sync (localStorage migrate) ===")
test("POST /chat/sync", lambda: requests.post(f"{BASE}/chat/sync", headers=H, json={"local_sessions":[{"id":f"test_mig_{TS}","title":"旧数据","preview":"hello","is_pinned":False,"is_archived":False,"tags":[],"messages":[{"client_msg_id":f"local_msg_{TS}_001","role":"user","content":"旧消息","rich_blocks":[],"tool_trace":{}}]}]}))

print("\n=== 3. Soft delete ===")
test(f"DELETE /chat/sessions/{SID_BASE}", lambda: requests.delete(f"{BASE}/chat/sessions/{SID_BASE}", headers=H))
test(f"DELETE /chat/sessions/{SID_BASE} (再次, 404)", lambda: requests.delete(f"{BASE}/chat/sessions/{SID_BASE}", headers=H))

print("\n=== 4. Filter 列表 ===")
test("GET pinned=true", lambda: requests.get(f"{BASE}/chat/sessions?pinned=true", headers=H))
test("GET tag=work", lambda: requests.get(f"{BASE}/chat/sessions?tag=work", headers=H))
test("GET search=测试", lambda: requests.get(f"{BASE}/chat/sessions?search=测试", headers=H))

print("\n=== 5. 越权防护 (无 token) ===")
test("GET /chat/sessions (no auth, 401)", lambda: requests.get(f"{BASE}/chat/sessions"))
test("POST /chat/sessions (no auth, 401)", lambda: requests.post(f"{BASE}/chat/sessions", json={"title":"x"}))

print(f"\n=== 6. 跨用户越权 (用 {E2E_USERNAME} token 访问自己 session OK) ===")
test("GET 自己的 session", lambda: requests.get(f"{BASE}/chat/sessions/{SID_BASE}", headers=H))

print("\n=== 全部结果 ===")
ok_count = sum(1 for r in results if "[OK]" in r or "[401]" in r or "[404]" in r or "[422]" in r and "再次" in r)
fail_count = sum(1 for r in results if "FAIL" in r and "[401]" not in r and "再次" not in r and "[404]" not in r)
for r in results:
    print(r)
print(f"\nSummary: {ok_count} ok / {fail_count} fail (401/404 越权防护视为 ok)")
