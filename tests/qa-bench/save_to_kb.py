"""
qa-bench/save_to_kb.py — 把 qa-bench 高分 (auto_score >= 4) 答案入库为"自动拓展"知识卡片 (#043)

设计:
- 读 results/onebyone_log.jsonl
- 筛 auto_score >= 4 + intent in [explain_concept, search_info] + content >= 200 字
- POST /api/v1/knowledge/from-auto-expansion (服务端做幂等 + 质量门 + RichBlock 写入)
- 自动 batch_size=50/批, 失败继续, 完成后报告 saved/skipped/errors

触发命令:
    python tests/qa-bench/save_to_kb.py --token <jwt>
    python tests/qa-bench/save_to_kb.py --token <jwt> --base-url https://agent.mnb-lab.cn
    python tests/qa-bench/save_to_kb.py --token <jwt> --batch-size 10
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# 质量门 (与 API 端 AutoExpansionIngestRequest 默认值对齐)
DEFAULT_MIN_SCORE = 4
DEFAULT_MIN_CONTENT_LENGTH = 200
DEFAULT_ALLOWED_INTENTS = ["explain_concept", "search_info"]


def collect_candidates(log_path: Path) -> list[dict]:
    """从 onebyone_log.jsonl 收集候选条目

    候选条件:
      - id startswith "S" (qa-bench 测试题前缀)
      - auto_score >= DEFAULT_MIN_SCORE
      - content 长度 >= DEFAULT_MIN_CONTENT_LENGTH
      - intent ∈ DEFAULT_ALLOWED_INTENTS

    每个 candidate 是完整 payload dict, 供 POST batch 用
    """
    candidates = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            qid = d.get("id", "")
            if not qid.startswith("S"):
                continue

            score = d.get("quality", {}).get("auto_score", 0)
            if score < DEFAULT_MIN_SCORE:
                continue

            content = d.get("content", "")
            if len(content) < DEFAULT_MIN_CONTENT_LENGTH:
                continue

            intent = d.get("intent", "")
            if DEFAULT_ALLOWED_INTENTS and intent not in DEFAULT_ALLOWED_INTENTS:
                continue

            # 提取 tool_calls + rich_blocks (qa-bench runner 已存)
            actual = d.get("actual", {})
            tool_calls = actual.get("tool_inputs", [])
            rich_blocks = actual.get("tool_results", [])

            candidates.append({
                "qa_id": qid,
                "question": d["question"],
                "content": content,
                "scope": d.get("scope"),
                "score": score,
                "intent": intent,
                "tool_calls": tool_calls,
                "rich_blocks": rich_blocks,
            })
    return candidates


def post_batch(
    items: list[dict], token: str, base_url: str,
    min_score: int, min_content_length: int, allowed_intents: list[str],
) -> dict:
    """POST 批量到 /api/v1/knowledge/from-auto-expansion"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    resp = httpx.post(
        f"{base_url}/api/v1/knowledge/from-auto-expansion",
        json={
            "items": items,
            "min_score": min_score,
            "min_content_length": min_content_length,
            "allowed_intents": allowed_intents,
        },
        headers=headers,
        timeout=60,
    )
    if resp.status_code != 201:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def main():
    p = argparse.ArgumentParser(
        description="qa-bench 高分问答 → 自动拓展知识卡片 (#043)",
    )
    p.add_argument("--token", required=True, help="JWT token (从 /api/v1/auth/login 拿)")
    p.add_argument("--base-url", default="http://127.0.0.1:8000",
                   help="API base URL (默认本地; 生产用 https://agent.mnb-lab.cn)")
    p.add_argument("--log", default="results/onebyone_log.jsonl",
                   help="qa-bench 日志路径")
    p.add_argument("--batch-size", type=int, default=50,
                   help="单次 POST batch 大小 (默认 50)")
    p.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE,
                   help=f"最低 auto_score 阈值 (默认 {DEFAULT_MIN_SCORE})")
    p.add_argument("--min-content-length", type=int, default=DEFAULT_MIN_CONTENT_LENGTH,
                   help=f"最低 content 长度 (默认 {DEFAULT_MIN_CONTENT_LENGTH})")
    p.add_argument("--allowed-intents", default=",".join(DEFAULT_ALLOWED_INTENTS),
                   help=f"白名单 intent (默认 {','.join(DEFAULT_ALLOWED_INTENTS)})")
    args = p.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"❌ 找不到日志: {log_path}")
        return 1

    candidates = collect_candidates(log_path)
    print(
        f"📊 候选 (auto_score>={args.min_score}, content>={args.min_content_length}, "
        f"intent∈{args.allowed_intents.split(',')}): {len(candidates)} 题"
    )

    if not candidates:
        print("没有候选条目可入库")
        return 0

    allowed_intents = [s.strip() for s in args.allowed_intents.split(",") if s.strip()]
    total_saved = 0
    total_skipped = 0
    total_errors: list[str] = []

    for i in range(0, len(candidates), args.batch_size):
        batch = candidates[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        try:
            result = post_batch(
                batch, args.token, args.base_url,
                min_score=args.min_score,
                min_content_length=args.min_content_length,
                allowed_intents=allowed_intents,
            )
            total_saved += result["saved"]
            total_skipped += result["skipped"]
            if result.get("errors"):
                total_errors.extend(result["errors"])
            print(
                f"  batch {batch_num}: "
                f"saved={result['saved']}, skipped={result['skipped']}"
            )
        except Exception as e:
            print(f"  batch {batch_num}: ❌ {e}")
            total_errors.append(f"batch {batch_num}: {e}")

    print(
        f"\n✅ 完成: saved={total_saved}, skipped={total_skipped}, "
        f"errors={len(total_errors)}"
    )
    return 0 if not total_errors else 1


if __name__ == "__main__":
    sys.exit(main())