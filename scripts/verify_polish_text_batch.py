"""验证 polish-text-batch 端点

模拟会议 #137 真实场景：83 条转录条目, 旧实现会触发 83 个 polish-text POST
→ write tier 30/min 限流后 53 个 429。新批量端点应该只发 1 个请求就处理完。
"""
import json
import sys
import time
import urllib.request
import urllib.error


def login(username: str = "wangtianzhi", password: str = "admin123") -> str:
    data = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        "https://agent.mnb-lab.cn/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


def post_batch(token: str, texts: list, label: str = "") -> dict:
    data = json.dumps({"texts": texts}).encode()
    req = urllib.request.Request(
        "https://agent.mnb-lab.cn/api/v1/meetings/137/polish-text-batch",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read())
            elapsed = time.time() - start
            return {
                "ok": True,
                "status": r.status,
                "elapsed": elapsed,
                "body": body,
                "headers": dict(r.headers),
            }
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return {
            "ok": False,
            "status": e.code,
            "elapsed": elapsed,
            "body": e.read().decode()[:500],
            "headers": dict(e.headers) if e.headers else {},
        }


def main():
    token = login()
    print(f"TOKEN: {token[:30]}...")

    # Test 1: 5 普通文本
    print("\n=== Test 1: 5 普通文本 ===")
    r = post_batch(token, [
        "今天我们讨论一下微纳米气泡的基本原理",
        "这是第二条测试文本",
        "This is the third test text",
        "这是第四条",
        "和第五条",
    ])
    print(f"status: {r['status']}, elapsed: {r['elapsed']:.3f}s")
    if r["ok"]:
        print(f"polished count: {len(r['body'].get('polished', []))}")
        for i, t in enumerate(r["body"].get("polished", [])):
            print(f"  [{i}] {t[:60]}")
    else:
        print(f"ERROR: {r['body']}")

    # Test 2: 空数组
    print("\n=== Test 2: 空数组 (edge case) ===")
    r = post_batch(token, [])
    print(f"status: {r['status']}, body: {r['body']}")

    # Test 3: 超过 200 上限
    print("\n=== Test 3: 201 条 (over 200 limit) ===")
    texts_201 = [f"测试文本{i}" for i in range(201)]
    r = post_batch(token, texts_201)
    print(f"status: {r['status']}, body: {r['body']}")

    # Test 4: 真实场景 - 会议 137 的 83 条转录
    print("\n=== Test 4: 真实场景 - 会议 137 的 83 条转录 ===")
    req = urllib.request.Request(
        "https://agent.mnb-lab.cn/api/v1/meetings/137",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        meeting = json.loads(r.read())

    transcript = meeting.get("transcript") or meeting.get("transcript_polished") or []
    texts_real = [
        t.get("text", "")
        for t in transcript
        if t.get("text", "").strip() and len(t.get("text", "").strip()) >= 3
    ]
    print(f"真实转录条目数: {len(texts_real)}")

    r = post_batch(token, texts_real, "real-83")
    if r["ok"]:
        print(f"✅ status: {r['status']}, elapsed: {r['elapsed']:.3f}s")
        print(f"   polished 返回条数: {len(r['body'].get('polished', []))}")
        remaining = r["headers"].get("x-ratelimit-remaining")
        policy = r["headers"].get("x-ratelimit-policy")
        print(f"   X-RateLimit-Remaining: {remaining}, Policy: {policy}")
        print(f"   前 3 条 polished:")
        for i in range(min(3, len(r["body"].get("polished", [])))):
            print(f"     [{i}] {r['body']['polished'][i][:60]}")
        # 对比：相同文本二次请求应该全部 Redis 缓存命中
        print("\n=== Test 4b: 二次调用（应该全部 Redis 缓存命中）===")
        r2 = post_batch(token, texts_real, "real-83-second")
        if r2["ok"]:
            print(f"✅ status: {r2['status']}, elapsed: {r2['elapsed']:.3f}s (缓存命中应该 < 0.5s)")
            print(f"   X-RateLimit-Remaining: {r2['headers'].get('x-ratelimit-remaining')}")
        else:
            print(f"❌ {r2['status']}: {r2['body']}")
    else:
        print(f"❌ status: {r['status']}, body: {r['body']}")

    # Test 5: 确认单文本 polish-text 仍能正常工作（向后兼容）
    print("\n=== Test 5: 单文本 polish-text 向后兼容 ===")
    data = json.dumps({"text": "单文本测试"}).encode()
    req = urllib.request.Request(
        "https://agent.mnb-lab.cn/api/v1/meetings/137/polish-text",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read())
        print(f"✅ status: {r.status}, polished: {body}")


if __name__ == "__main__":
    main()