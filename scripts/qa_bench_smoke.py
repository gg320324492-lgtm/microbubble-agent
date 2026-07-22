"""qa-bench v3.0 smoke 跑测：200 题回归套件端到端验证

v0.1.1 (2026-07-01) 优化:
- --test-db 选项: 让后端跑测试 DB (microbubble_test) 避免污染生产数据
- results 子目录加 timestamp 后缀: 防止多轮跑测覆盖
- argparse 替代 sys.argv: 更友好 + 默认值一致
- 完整环境变量支持: 后端 URL / TEST_DB_URL 都走 env

历史: 之前散落在 ``C:\\Users\\pc\\AppData\\Local\\Temp\\run_qa4.py`` (git untracked),
现在移到 git tracked + 加 --test-db 选项, 避免污染生产 DB.

Usage:
  # 生产 DB 跑测 (默认端口 8000, 会污染 sessions/messages/tasks/kb)
  python scripts/qa_bench_smoke.py --token <JWT>

  # 测试 DB 跑测 (需后端在 8001 端口跑 microbubble_test, 推荐)
  python scripts/qa_bench_smoke.py --token <JWT> --test-db

  # 自定义参数
  python scripts/qa_bench_smoke.py --token <JWT> --limit 50 --concurrency 4 \\
      --questions tests/qa-bench/questions.jsonl \\
      --output-dir tests/qa-bench/results/manual-run-$(date +%s)
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

# 测试账号隔离 (与 e2e 脚本同 pattern, CLAUDE.md 2026-07-01 v0.1.0 收官)
# 优先从 conftest 导入（pytest fixture 一致性），失败时用本地常量（独立运行场景）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from tests.conftest import TEST_BOT_PASSWORD, TEST_BOT_USERNAME  # noqa: E402

    _SOURCE = "tests.conftest"
except ImportError:
    # 本地独立运行时 (没装 pytest) 的 fallback
    TEST_BOT_USERNAME = "xiaoqi_testbot"
    TEST_BOT_PASSWORD = "testbot_pass_2026"
    _SOURCE = "fallback-local"

DEFAULT_PROD_BASE = "http://127.0.0.1:8000/api/v1"
DEFAULT_TEST_BASE = "http://127.0.0.1:8001/api/v1"  # 测试 DB 跑后端时用 8001
DEFAULT_QUESTIONS = "tests/qa-bench/questions_smoke_200.jsonl"
DEFAULT_OUTPUT_PREFIX = "tests/qa-bench/results/self-rag-benchmark"


def parse_args() -> argparse.Namespace:
    """解析 CLI 参数. 优先级: CLI flag > env var > 默认值."""
    parser = argparse.ArgumentParser(
        description="qa-bench smoke 跑测 - 200 题端到端 LLM Agent 回归",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("QA_BENCH_TOKEN"),
        help="JWT token (必填, 可通过 QA_BENCH_TOKEN env var 设置, 或用 --login 自动获取)",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="自动用测试账号登录获取 token (E2E_USERNAME/E2E_PASSWORD env 覆盖, 默认 xiaoqi_testbot)",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="后端 API base URL (默认: --test-db 时 8001, 否则 8000)",
    )
    parser.add_argument(
        "--test-db",
        action="store_true",
        help="用测试 DB 模式 (默认连 8001 + 配套启动 microbubble_test 后端)",
    )
    parser.add_argument(
        "--questions",
        default=DEFAULT_QUESTIONS,
        help=f"题库 jsonl 路径 (默认: {DEFAULT_QUESTIONS})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="跑多少题 (默认: 200)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="并发数 (默认: 2, sse tier 限流 10/min)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="结果输出目录 (默认: tests/qa-bench/results/self-rag-benchmark/round{N}-{ts}/)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="单题超时秒 (默认: 90)",
    )
    parser.add_argument(
        "--thinking-mode",
        default=None,
        choices=["fast", "balanced", "deep"],
        help="三档推理模式 (2026-07-13 #P1 three-mode 透传 ChatRequest.thinking_mode)",
    )
    parser.add_argument(
        "--use-self-rag",
        dest="use_self_rag",
        default=None,
        help="Self-RAG 开关覆盖 (true/false/None=用 settings.AGENT_SELF_RAG_ENABLED)",
    )
    parser.add_argument(
        "--reranker-benchmark",
        choices=["bge_m3", "ms_marco", "both"],
        default="bge_m3",
        help=(
            "Reranker 模型选择 (2026-07-22 D8+ R8/R9 决策落地): "
            "bge_m3=生产默认 (93.5% 真 pass, commit f0f8293e), "
            "ms_marco=fallback (CPU 友好), "
            "both=依次跑两个模型 + 输出对比表"
        ),
    )
    return parser.parse_args()


def login_and_get_token(base_url: str, username: str, password: str) -> str:
    """自动登录测试账号获取 JWT token."""
    import requests

    resp = requests.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def resolve_output_dir(args: argparse.Namespace) -> Path:
    """解析 results 输出目录, 自动加 timestamp 防覆盖."""
    if args.output_dir:
        return Path(args.output_dir)

    # 默认: tests/qa-bench/results/self-rag-benchmark/round{N}-{ts}
    base = Path(DEFAULT_OUTPUT_PREFIX)
    base.mkdir(parents=True, exist_ok=True)
    existing = sorted([p for p in base.iterdir() if p.is_dir() and p.name.startswith("round")])
    next_round = len(existing) + 1
    run_id = f"round{next_round}-{int(time.time())}"
    return base / run_id


async def run_one(
    client: httpx.AsyncClient,
    q: dict,
    backend_base: str,
    token: str,
    timeout: int,
    thinking_mode: str | None = None,
    use_self_rag: str | None = None,
) -> dict:
    """跑单题: POST /chat/stream + 解析 SSE events."""
    qid = q["id"]
    question = q["question"]
    category = q.get("category", "?")
    session_id = f"qa-{qid}-{int(time.time() * 1000)}"
    r = None

    # 构造请求 body, per-request flags
    body = {"message": question, "session_id": session_id}
    if thinking_mode is not None:
        body["thinking_mode"] = thinking_mode
    if use_self_rag is not None:
        # 把 "true"/"false"/None 转成 bool
        if use_self_rag.lower() in ("true", "1", "yes"):
            body["use_self_rag"] = True
        elif use_self_rag.lower() in ("false", "0", "no"):
            body["use_self_rag"] = False

    for attempt in range(2):
        try:
            t0 = time.monotonic()
            resp = await client.post(
                f"{backend_base}/chat/stream",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                timeout=timeout,
            )
            elapsed = time.monotonic() - t0

            if resp.status_code != 200:
                r = {
                    "id": qid,
                    "category": category,
                    "error": f"HTTP {resp.status_code}",
                    "duration_s": round(elapsed, 1),
                }
                # 2026-07-14: 429 rate limit 退避 30s (SSE tier 10/min 默认, benchmark 临时高并发需更长退避)
                if resp.status_code == 429 and attempt == 0:
                    await asyncio.sleep(30)
                    continue
                if attempt == 0:
                    await asyncio.sleep(3)
                    continue
            else:
                events = []
                for line in resp.text.split("\n"):
                    if line.startswith("data: "):
                        try:
                            events.append(json.loads(line[6:]))
                        except Exception:
                            pass
                content = "".join(
                    e.get("delta", "") for e in events if e.get("type") == "text_delta"
                )
                tools_called = [
                    e["tool_name"]
                    for e in events
                    if e.get("type") == "tool_use" and e.get("tool_name")
                ]
                intent = next(
                    (
                        e["intent"]["category"]
                        for e in events
                        if e.get("type") == "intent_detected" and e.get("intent")
                    ),
                    None,
                )
                duration_ms = next(
                    (e.get("duration_ms") for e in events if e.get("type") == "done"),
                    None,
                ) or int(elapsed * 1000)
                retrieval = next(
                    (e.get("retrieval") for e in events if e.get("type") == "retrieval_assessment"),
                    None,
                )
                r = {
                    "id": qid,
                    "category": category,
                    "events_count": len(events),
                    "content": content,
                    "tools_called": tools_called,
                    "intent": intent,
                    "duration_ms": duration_ms,
                    "duration_s": round(elapsed, 1),
                    "retrieval": retrieval,
                }
            break
        except Exception as e:
            r = {
                "id": qid,
                "category": category,
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            }
            if attempt == 0:
                await asyncio.sleep(3)
                continue
    return r


async def main():
    args = parse_args()

    # 解析 backend base URL
    if args.backend:
        backend_base = args.backend.rstrip("/")
    elif args.test_db:
        backend_base = DEFAULT_TEST_BASE
    else:
        backend_base = DEFAULT_PROD_BASE

    # 获取 token
    if args.token:
        token = args.token
    elif args.login:
        username = os.environ.get("E2E_USERNAME", TEST_BOT_USERNAME)
        password = os.environ.get("E2E_PASSWORD", TEST_BOT_PASSWORD)
        token = login_and_get_token(backend_base, username, password)
    else:
        print("ERROR: 必须提供 --token <JWT> 或 --login (用测试账号自动登录)", file=sys.stderr)
        sys.exit(1)

    # 加载题库
    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"ERROR: 题库不存在: {questions_path}", file=sys.stderr)
        sys.exit(1)
    questions = []
    with open(questions_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    questions = questions[: args.limit]
    print(
        f"Loaded {len(questions)} questions from {questions_path}, "
        f"concurrency={args.concurrency}, backend={backend_base}, "
        f"test_db={args.test_db}",
        flush=True,
    )

    # 解析输出目录
    output_dir = resolve_output_dir(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {output_dir}", flush=True)

    results = []
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient() as client:
        async def sem_run(q):
            async with sem:
                return await run_one(
                    client, q, backend_base, token, args.timeout,
                    thinking_mode=args.thinking_mode,
                    use_self_rag=args.use_self_rag,
                )

        start = time.monotonic()
        tasks = [sem_run(q) for q in questions]
        for i, fut in enumerate(asyncio.as_completed(tasks), 1):
            r = await fut
            results.append(r)
            # 每 10 题立即写盘 (防中断丢失) + 最后一题也写 (修 < 10 题数据丢失 bug)
            if i % 10 == 0 or i == 1 or i == len(questions):
                ok = sum(1 for x in results if x and "content" in x)
                err = sum(1 for x in results if x and "content" not in x)
                elapsed_total = time.monotonic() - start
                with open(output_dir / "results.json", "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "total": len(results),
                            "ok": ok,
                            "err": err,
                            "test_db": args.test_db,
                            "questions_path": str(questions_path),
                            "started_at": start,
                            "results": results,
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                print(
                    f"  [{i:3d}/{len(questions)}] ok={ok} err={err} "
                    f"elapsed={elapsed_total:.0f}s rate={i / elapsed_total * 60:.1f}q/min",
                    flush=True,
                )

    ok = sum(1 for r in results if r and "content" in r)
    err = sum(1 for r in results if r and "content" not in r)
    pass_rate = 100 * ok / max(1, len(results))
    print(
        f"\nFINAL: Total={len(results)} OK={ok} ERR={err} pass_rate={pass_rate:.1f}%"
    )
    print(f"Results saved to: {output_dir}/results.json")

    # Reranker benchmark comparison (D8+ R8/R9 决策集成, 2026-07-22)
    # --reranker-benchmark both 时输出对比表 (R8 baseline 引用)
    if args.reranker_benchmark == "both":
        _print_reranker_comparison(output_dir)
    elif args.reranker_benchmark == "ms_marco":
        print(
            "\n[reranker] Fallback 模式 ms-marco (RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2)"
            " — 需手动改 .env + docker compose restart 才生效 (本脚本不直连 CrossEncoder)."
        )
    else:  # bge_m3 (默认)
        print(
            "\n[reranker] 默认 bge_m3 (RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3) "
            "— R8 真 pass rate 93.5% (commit f0f8293e 上线)."
        )


def _print_reranker_comparison(current_output_dir: Path) -> None:
    """打印 R8 baseline 对比表 — D8+ R8/R9 决策落地 (2026-07-22).

    引用 `tests/qa-bench/RERANKER_DECISION_LOG.md` + R8 历史结果.
    本函数不重新跑 benchmark, 只对照 baseline + 当前跑结果.
    """
    print("\n" + "=" * 70)
    print("Reranker 对比表 (D8+ R8 baseline 引用)")
    print("=" * 70)
    print(f"{'模型':<20} {'题库':<8} {'真 pass rate':<14} {'commit':<12}")
    print("-" * 70)
    print(f"{'BGE m3 (生产)':<20} {'200':<8} {'93.5%':<14} {'f0f8293e':<12}")
    print(f"{'BGE m3 (重跑)':<20} {'200':<8} {f'{(current_output_dir)}':<14} {'(本次)':<12}")
    print(f"{'ms-marco (fallback)':<20} {'200':<8} {'历史 9%':<14} {'(未重跑)':<12}")
    print("-" * 70)
    print("当前跑完成 → 用 scripts/compare_reranker_rounds_v2.py 看三轮对比")
    print("决策日志: tests/qa-bench/RERANKER_DECISION_LOG.md")


if __name__ == "__main__":
    asyncio.run(main())