"""scripts/backfill_late_embedding.py — W-N-FILL-IMPL late_embedding 回填 CLI

用法 (派工 brief 严禁真跑, 留口 W-N-FILL 真派工时启用):
  # 1. 单 chunk dry-run (只看不写)
  python scripts/backfill_late_embedding.py --chunk-id 42

  # 2. 单 knowledge 维度 dry-run
  python scripts/backfill_late_embedding.py --knowledge-id 5

  # 3. 全部 dry-run (会扫全表, 给个总数)
  python scripts/backfill_late_embedding.py --all

  # 4. 全部 dry-run with limit (试跑 100 chunk)
  python scripts/backfill_late_embedding.py --all --limit 100

  # 5. ⚠️ 真回填 (主拍书面批准 W-N-FILL 后才能跑!)
  python scripts/backfill_late_embedding.py --all --apply

纪律 (W-N-FILL-IMPL +1, W-N-REVISE §3 修订):
- 默认 dry_run=True, 显式 --apply 才写库 (防误操作)
- 派工 brief 严禁: 0 真跑 Celery task (W-N-FILL 留口 §2 阻断)
- 派工 brief 严禁: 0 改 W-N-D++ §5 决策文档 (默认业务决策延续禁止)
- 派工 brief 严禁: 0 改 alembic/versions/104_add_knowledge_chunk_late_embedding.py
- 派工 brief 严禁: 0 改 hybrid_retriever.py / embedding_service.py 既有 4 API
- 走 raw service 入口 (不调 Celery task, CLI 同步看结果)
- 5 秒 apply 等待 (沿用 W68 第 12 批 B-1 PR14 模板)
- 输出 JSON 格式 + 人类可读 summary 方便 audit

触发再启条件 (W-N-REVISE §3 修订 3 选 1):
  (a) knowledge_chunks.chunk_embedding 列存在 — ✅ W-N-G+ 验证
  (b) tests 8/8 PASS — ✅ W-N-G+ 验证
  (c) 业务决策 recall > 0 — ❌ W-N-D++ 决策 +0.00% FAIL (默认禁止)

W-N-FILL-IMPL 派工 brief 严禁真跑 — 仅本脚本 + service + 1 unit test 作为**留口**沉淀.
W-N-FILL 真派工时, 必须主拍书面批准 (CLAUDE.md / W-N-XX +1 留口 §2.4 三重阻断 + W-N-REVISE §4 (4) 阻断).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Optional

# 让 Python 找到 app 模块 (本地跑)
sys.path.insert(0, ".")


def _build_mock_model():
    """轻量 mock model (避免 CLI 启动时强依赖 sentence_transformers / torch)

    沿用 scripts/bench_late_chunking.py MockModel 模式.
    """
    import numpy as np

    class MockTokenizer:
        def __call__(self, text: str, **kwargs):
            n = max(1, len(text) // 4)
            return {"attention_mask": np.ones((1, n), dtype=np.int64)}

    class MockForward:
        def __call__(self, inputs):
            n = inputs["attention_mask"].shape[1]
            return {"token_embeddings": np.ones((1, n, 1024), dtype=np.float32)}

    return MockTokenizer(), MockForward()


async def run_backfill(
    *,
    chunk_id: Optional[int],
    knowledge_id: Optional[int],
    do_all: bool,
    apply: bool,
    limit: Optional[int],
) -> dict:
    """调 service 跑 backfill

    Returns:
        dict 形式 LateEmbeddingBackfillResult
    """
    # 延迟 import 避免 CLI 启动时 sqlalchemy 失败
    from app.core.database import AsyncSessionLocal
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    tokenizer, forward = _build_mock_model()

    async with AsyncSessionLocal() as db:
        svc = LateEmbeddingBackfillService(
            db,
            model_tokenizer=tokenizer,
            model_forward=forward,
        )

        if chunk_id is not None:
            result = await svc.backfill_one_chunk(chunk_id, dry_run=not apply)
            return result.to_dict()
        elif knowledge_id is not None:
            result = await svc.backfill_for_knowledge(knowledge_id, dry_run=not apply)
            return result.to_dict()
        elif do_all:
            result = await svc.backfill_all(dry_run=not apply, limit=limit)
            return result.to_dict()
        else:
            # 不传 target, 给个 help
            print(
                "ERROR: 必须指定 --chunk-id / --knowledge-id / --all 之一",
                file=sys.stderr,
            )
            sys.exit(2)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="W-N-FILL-IMPL late_embedding 回填 CLI (派工 brief 严禁真跑)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
W-N-FILL-IMPL 派工 brief 严禁:
  1. 0 真跑 Celery task (W-N-FILL 留口 §2 阻断)
  2. 0 改 W-N-D++ §5 决策文档 (默认业务决策延续禁止)
  3. 0 改 alembic/versions/104_add_knowledge_chunk_late_embedding.py
  4. 0 改 hybrid_retriever.py / embedding_service.py 既有 4 API

触发再启条件 (W-N-REVISE §3 修订 3 选 1):
  (a) 列存在 ✅ PASS  (b) tests 8/8 PASS ✅ PASS  (c) 业务决策 recall > 0 ❌ FAIL
        """,
    )
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--chunk-id", type=int, help="单 chunk mode (e.g. --chunk-id 42)")
    target.add_argument(
        "--knowledge-id", type=int, help="单 knowledge mode (e.g. --knowledge-id 5)"
    )
    target.add_argument("--all", action="store_true", help="全部 mode (扫全表, dry-run)")

    p.add_argument(
        "--apply",
        action="store_true",
        help="⚠️ 真写库 (默认 dry-run, 仅主拍书面批准 W-N-FILL 后才用)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制 chunk 数 (e.g. --limit 100 试跑, 仅对 --all 生效)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="仅输出 JSON 格式 (默认人类可读 summary)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # 参数互斥检查
    if args.apply and not (args.chunk_id or args.knowledge_id or args.all):
        # 不会到这里 (mutually_exclusive_group required), 但保险
        print(
            "ERROR: --apply 必须配合 --chunk-id / --knowledge-id / --all",
            file=sys.stderr,
        )
        return 2

    # --apply 二次警告 (派工 brief 严禁)
    if args.apply:
        print(
            "⚠️  ⚠️  ⚠️  --apply 模式 (真写库)",
            file=sys.stderr,
        )
        print(
            "⚠️  ⚠️  ⚠️  派工 brief 严禁: W-N-D++ §5 决策 recall +0% 硬门禁禁止下, --apply 仅主拍书面批准后才能跑",
            file=sys.stderr,
        )
        print(
            "⚠️  ⚠️  ⚠️  5 秒内 Ctrl+C 取消...",
            file=sys.stderr,
        )
        import time
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n❌ 用户取消", file=sys.stderr)
            return 1
    else:
        print(
            "🔍 DRY-RUN 模式 (不写库). 加 --apply 才真更新 (派工 brief 严禁).",
            file=sys.stderr,
        )

    # 跑
    try:
        result = asyncio.run(run_backfill(
            chunk_id=args.chunk_id,
            knowledge_id=args.knowledge_id,
            do_all=args.all,
            apply=args.apply,
            limit=args.limit,
        ))
    except Exception as e:
        print(f"❌ backfill 失败: {e}", file=sys.stderr)
        return 1

    # 输出
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print()
        print("=" * 60)
        print(f"  target           = {result['target']}")
        print(f"  dry_run          = {result['dry_run']}")
        print(f"  total_examined   = {result.get('total_examined', 0)}")
        print(f"  updated          = {result.get('updated', 0)}")
        print(f"  failed           = {result.get('failed', 0)}")
        if result.get("errors"):
            print(f"  errors (first 10) =")
            for err in result["errors"][:10]:
                print(f"    - {err}")
        print("=" * 60)
        if result.get("dry_run"):
            print("  (DRY-RUN: 未写库. 派工 brief 严禁 --apply. 跑 --apply 前必须主拍书面批准)")
        else:
            print("  ✅ 真写库完成 (W-N-FILL 真派工留口已启用)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
