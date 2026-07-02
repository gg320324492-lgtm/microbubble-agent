"""Single question cloud SSE smoke test"""
import asyncio
import httpx
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from collections import Counter


async def main():
    token_path = Path("/tmp/round9_token.txt")
    if not token_path.exists():
        print("ERROR: token file not found")
        return
    TOKEN = token_path.read_text().strip()
    print(f"token: {TOKEN[:20]}...{TOKEN[-10:]}", flush=True)

    q = {
        "id": "A-L1-0001",
        "category": "A",
        "question": "王天志是干什么的？",
        "expect": {
            "intent": "search_info",
            "tools_any": ["query_members"],
            "must_contain_any": [["王天志"], ["博士生"]],
            "forbidden_names": ["杜同贺", "赵航佳", "杨慈", "宋洋", "测试", "test_json"],
        },
    }
    payload = {"message": q["question"], "session_id": f"qa-test-{int(time.time())}"}

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://agent.mnb-lab.cn/api/v1/chat/stream",
                json=payload,
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            elapsed = time.monotonic() - t0
            print(f"http status: {r.status_code} (elapsed: {elapsed:.1f}s)", flush=True)
            print(f"response length: {len(r.text)} chars", flush=True)

            events = []
            for line in r.text.split("\n"):
                if line.startswith("data: "):
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        pass
            print(f"events: {len(events)}", flush=True)

            types = Counter(e.get("type") for e in events)
            print(f"event types: {dict(types)}", flush=True)

            content = "".join(e.get("delta", "") for e in events if e.get("type") == "text_delta")
            print(f"content ({len(content)} chars): {content[:300]}", flush=True)

            tools = [e.get("tool_name") for e in events if e.get("type") == "tool_use"]
            print(f"tools called: {tools}", flush=True)

            for e in events:
                if e.get("type") == "done":
                    print(f"done text_without_json (200 chars): {(e.get('text_without_json') or '')[:200]}", flush=True)
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"Exception after {elapsed:.1f}s: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())