"""
qa-bench/onebyone.py — 逐个问答循环

设计：
- 读 tests/qa-bench/seed_expand.jsonl 种子题（75 个拓展领域问题）
- 还可以动态追加（基于回答发现新问题）
- 一个一个 POST 到 /api/v1/chat/stream
- 每个回答后：
  - 记录 Q+A 到 results/onebyone_log.jsonl
  - 简单质量评分（是否有工具调用 / 是否有 grounded 名字 / 是否有 fake XML / duration）
  - 如果是 "external_knowledge" 类且回答好 → 触发"保存到知识库"模式（用户后续可手动 save）
- 支持 --from N --to M 范围运行（便于断点续跑）

用法：
  python tests/qa-bench/onebyone.py --token "<JWT>" --from 1 --to 10
  python tests/qa-bench/onebyone.py --from 11 --to 30
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx


API_BASE = "http://127.0.0.1:8000"
STREAM_TIMEOUT_S = 90


def parse_sse(response_text: str) -> List[Dict[str, Any]]:
    events = []
    for line in response_text.split("\n"):
        if not line.startswith("data: "):
            continue
        try:
            events.append(json.loads(line[6:]))
        except json.JSONDecodeError:
            continue
    return events


def assemble_content(events: List[Dict[str, Any]]) -> str:
    return "".join(
        evt.get("delta", "")
        for evt in events
        if evt.get("type") == "text_delta" and evt.get("delta")
    )


def detect_fake_xml(content: str) -> bool:
    import re
    patterns = [
        r"<tool_call>\s*<function",
        r"<tool_call>\s*\{",
        r"<function_calls?\s*>",
        r"<function\s*=[^>]+>.*?</function\s*>",
    ]
    return any(re.search(p, content, re.DOTALL) for p in patterns)


def assess_quality(events: List[Dict[str, Any]], content: str) -> Dict[str, Any]:
    """简单质量评估（不依赖期望字段）"""
    tools_called = [e.get("tool_name") for e in events if e.get("type") == "tool_use"]
    duration = next((e.get("duration_ms") for e in events if e.get("type") == "done"), None)
    critique = next((e.get("critique", {}).get("score") for e in events if e.get("type") == "critique"), None)
    intent = next((e.get("intent", {}).get("category") for e in events if e.get("type") == "intent_detected"), None)
    has_rich_block = any(e.get("type") == "rich_block" for e in events)
    has_fake_xml = detect_fake_xml(content)
    has_placeholder = any(p in content for p in ("暂无详细信息", "系统故障", "技术问题"))
    content_len = len(content)
    grounded_names = set()
    for e in events:
        if e.get("type") == "tool_result" and isinstance(e.get("tool_output"), dict):
            out = e["tool_output"]
            if isinstance(out.get("members"), list):
                for m in out["members"]:
                    if isinstance(m, dict) and isinstance(m.get("name"), str):
                        grounded_names.add(m["name"])
            if isinstance(out.get("name"), str):
                grounded_names.add(out["name"])

    quality = {
        "tools_called": tools_called,
        "intent": intent,
        "duration_ms": duration,
        "critique_score": critique,
        "content_len": content_len,
        "has_rich_block": has_rich_block,
        "has_fake_xml": has_fake_xml,
        "has_placeholder": has_placeholder,
        "grounded_names": sorted(grounded_names),
    }

    # 简单评分（1-5）
    score = 5
    if has_fake_xml:
        score -= 2
    if has_placeholder:
        score -= 2
    if duration and duration > 60_000:
        score -= 1
    if not tools_called and "expand" in (intent or ""):
        score -= 1  # 拓展问题应该调 web_search / search_knowledge
    quality["auto_score"] = max(1, score)
    return quality


async def ask_one(client: httpx.AsyncClient, question_data: Dict[str, Any], token: str) -> Dict[str, Any]:
    qid = question_data["id"]
    question = question_data["question"]
    session_id = f"onebyone-{qid}-{int(time.time())}"

    payload = {"message": question, "session_id": session_id}
    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{API_BASE}/api/v1/chat/stream",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=STREAM_TIMEOUT_S,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code != 200:
            return {
                "id": qid, "question": question, "category": question_data.get("category"),
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "elapsed_ms": elapsed_ms,
            }
        events = parse_sse(resp.text)
    except Exception as e:
        return {
            "id": qid, "question": question, "category": question_data.get("category"),
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        }

    content = assemble_content(events)
    quality = assess_quality(events, content)
    quality["elapsed_ms"] = elapsed_ms
    return {
        "id": qid,
        "question": question,
        "category": question_data.get("category"),
        "kind": question_data.get("kind"),
        "scope": question_data.get("scope"),
        "content": content,
        "quality": quality,
        "timestamp": datetime.now().isoformat(),
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--seed", default="tests/qa-bench/seed_expand.jsonl")
    parser.add_argument("--log", default="results/onebyone_log.jsonl")
    parser.add_argument("--from", dest="start", type=int, default=1)
    parser.add_argument("--to", dest="end", type=int, default=9999)
    parser.add_argument("--delay", type=float, default=1.0, help="每题间隔秒数")
    args = parser.parse_args()

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    questions = []
    with open(args.seed, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            questions.append(json.loads(line))

    # 解析 id 范围 (S01 -> 1)
    selected = []
    for q in questions:
        try:
            num = int(q["id"].lstrip("SABMCTPKXYZUE") or "0")
        except Exception:
            num = 0
        if args.start <= num <= args.end:
            selected.append((num, q))
    selected.sort(key=lambda x: x[0])

    print(f"📚 逐个问答: {len(selected)} 题 (S{args.start:02d} - S{args.end:02d})")
    print(f"   log: {log_path}")
    print()

    results = []
    total_score = 0
    async with httpx.AsyncClient() as client:
        for i, (num, q) in enumerate(selected):
            t0 = time.monotonic()
            result = await ask_one(client, q, args.token)
            dt = time.monotonic() - t0
            score = result.get("quality", {}).get("auto_score", 0)
            total_score += score
            avg = total_score / (i + 1)
            tools = result.get("quality", {}).get("tools_called", [])
            intent = result.get("quality", {}).get("intent", "")
            content_len = result.get("quality", {}).get("content_len", 0)
            print(
                f"  [{i+1:3d}/{len(selected)}] S{num:02d} score={score}/5 avg={avg:.1f} "
                f"({dt:.0f}s) tools={tools[:2]} intent={intent} len={content_len}",
                flush=True,
            )
            if "error" in result:
                print(f"      ❌ {result['error'][:100]}")

            # 写一行 log
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
            results.append(result)
            await asyncio.sleep(args.delay)

    print()
    print(f"📊 完成 {len(results)} 题，平均分 {total_score/len(results):.2f}/5")


if __name__ == "__main__":
    asyncio.run(main())
