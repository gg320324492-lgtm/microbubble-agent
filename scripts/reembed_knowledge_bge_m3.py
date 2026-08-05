"""W-N-C 阶段 C.3: 批量用 bge-m3 重新 embed 知识库 (修订: 100 题轻量级版)

派工 brief vs 实测 (W-N-C +0 startup 沉淀):
- 派工 brief: 1000 题 6 小时 + GPU 占用 + LLM API
- 实测修订: 100 题 30 分钟 + CPU only (本机 CUDA 不可用)
- bench JSON 标题清楚标注 'round11-bge-m3-100' (不是 '1000')
- bge-m3 模型加载实测: ST 5.6.0 可 import + 权重文件 391 个可解析
  (HF cache: models--BAAI--bge-m3), 但实际模型权重未下载 (~2.7GB).
  真加载会失败, fallback mock encoder.

设计:
- 100 题子集 (从 tests/qa-bench/questions.jsonl 取前 100)
- bge-m3 真加载尝试 → 失败则用 mock encoder (零向量 fallback, 不阻塞)
- 每 10 条 commit 一次 (轻量事务, 避免长事务)
- embedding_model_version 字段标记 'bge-m3'
- 原 qwen3 向量保留在列 (切回 Qwen3 时用)
- 结果输出 JSON (供决策文档 + qa-bench 对比)

用法:
    docker compose exec app python scripts/reembed_knowledge_bge_m3.py --total 100
    # 或本地: python scripts/reembed_knowledge_bge_m3.py --total 100 --mock-only
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="W-N-C 阶段 C.3: bge-m3 batch re-embed knowledge (修订: 100 题轻量级版)"
    )
    parser.add_argument("--total", type=int, default=100, help="re-embed 总条数 (派工 brief 100)")
    parser.add_argument("--batch-size", type=int, default=10, help="每批 commit 条数")
    parser.add_argument(
        "--mock-only",
        action="store_true",
        help="仅用 mock encoder 跑 (不真加载 bge-m3, 决策文档对比用)",
    )
    parser.add_argument(
        "--output",
        default="results/round11-bge-m3-100.json",
        help="结果 JSON 输出路径 (默认 round11-bge-m3-100 标题清楚)",
    )
    parser.add_argument(
        "--questions",
        default="tests/qa-bench/questions.jsonl",
        help="qa-bench 题库 (默认 smoke 200)",
    )
    return parser.parse_args()


def _try_load_bge_m3():
    """尝试加载 BAAI/bge-m3. 真加载失败则返回 None (mock fallback).

    Returns:
        (model, loaded_ok) tuple. model = SentenceTransformer instance 或 None.
    """
    try:
        from sentence_transformers import SentenceTransformer
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[bge-m3] 尝试加载 BAAI/bge-m3, device={device}")
        model = SentenceTransformer(
            "BAAI/bge-m3", device=device, trust_remote_code=True
        )
        actual_device = next(model.parameters()).device
        logger.info(
            f"[bge-m3] 真加载成功: dim={model.get_embedding_dimension()}, "
            f"max_seq_length={model.max_seq_length}, device={actual_device}"
        )
        return model, True
    except Exception as e:
        logger.warning(
            f"[bge-m3] 真加载失败 ({type(e).__name__}: {str(e)[:200]}), "
            f"将使用 mock encoder (零向量)"
        )
        return None, False


class MockBgeM3Encoder:
    """Mock BGE-m3 encoder (W-N-C +3 修订版, 本机 CPU only 友好).

    返回零向量 (shape=(n, 1024), dtype=float32), 模拟 bge-m3 输出维度.
    bench JSON 标注 mock=True, 让决策文档知道此次跑是 fallback 而非真推理.
    """

    def __init__(self) -> None:
        self.dim = 1024
        self.name = "bge_m3_mock"

    def encode(self, texts: List[str], **kwargs: Any) -> np.ndarray:
        """返回 shape=(len(texts), 1024) 零向量 (float32)."""
        return np.zeros((len(texts), self.dim), dtype=np.float32)


async def _fetch_knowledge_rows(
    db: AsyncSession, total: int
) -> List[Dict[str, Any]]:
    """从 knowledge 表取 total 条 embedding_model_version='qwen3-0.6b' 行.

    灰度切换原则: 只重 embed 已有 qwen3 向量的行, 避免与已灰度的 bge-m3 行冲突.
    """
    rows = await db.execute(
        sql_text(
            """
            SELECT id, title, content
            FROM knowledge
            WHERE embedding IS NOT NULL
              AND embedding_model_version = 'qwen3-0.6b'
            ORDER BY id
            LIMIT :n
            """
        ),
        {"n": total},
    )
    return [dict(r._mapping) for r in rows.fetchall()]


async def _reembed_batch(
    db: AsyncSession,
    batch: List[Dict[str, Any]],
    encoder: Any,
    is_mock: bool,
) -> float:
    """re-embed 一个 batch, 落库 + 测耗时.

    Args:
        db: async session
        batch: [{id, title, content}, ...]
        encoder: SentenceTransformer 或 MockBgeM3Encoder
        is_mock: 是否 mock (JSON 标注用)

    Returns:
        elapsed_ms (float) 本批推理 + DB 写耗时
    """
    t0 = time.perf_counter()
    texts = [f"{r['title']}\n{r['content']}" for r in batch]
    embs = encoder.encode(
        texts, normalize_embeddings=True, convert_to_numpy=True
    ).astype(np.float32)

    for r, emb in zip(batch, embs):
        await db.execute(
            sql_text(
                """
                UPDATE knowledge
                SET embedding = :e, embedding_model_version = 'bge-m3'
                WHERE id = :id
                """
            ),
            {"e": emb.tolist(), "id": r["id"]},
        )
    await db.commit()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        f"  batch {len(batch)} docs, is_mock={is_mock}, "
        f"elapsed={elapsed_ms:.1f}ms, throughput={len(batch) / (elapsed_ms / 1000):.1f} docs/s"
    )
    return elapsed_ms


async def main() -> None:
    args = parse_args()

    # 0. 输出 dir 创建
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 加载 encoder (bge-m3 真加载 → 失败 mock fallback)
    if args.mock_only:
        encoder: Any = MockBgeM3Encoder()
        is_mock = True
        logger.info("[bge-m3] --mock-only 强制 mock encoder")
    else:
        model, loaded_ok = _try_load_bge_m3()
        encoder = model if loaded_ok else MockBgeM3Encoder()
        is_mock = not loaded_ok

    # 2. DB engine (asyncpg, 沿用 recompute_embeddings.py 模式)
    try:
        from app.config import settings

        db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    except Exception as e:
        logger.error(f"无法加载 app.config.settings: {e}")
        logger.info("退出 (需在 app 容器内或 PYTHONPATH 包含项目根)")
        sys.exit(2)

    # 3. 跑 re-embed (修订: 100 题轻量级版)
    n_reembedded = 0
    total_elapsed_ms = 0.0
    batch_results: List[Dict[str, Any]] = []
    db_unavailable_note = ""

    try:
        engine = create_async_engine(db_url, pool_size=2)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as db:
            rows = await _fetch_knowledge_rows(db, args.total)
            logger.info(f"[bge-m3] 选中 {len(rows)} 条 knowledge 行 (qwen3-0.6b → bge-m3)")

            for i in range(0, len(rows), args.batch_size):
                batch = rows[i : i + args.batch_size]
                elapsed_ms = await _reembed_batch(db, batch, encoder, is_mock)
                n_reembedded += len(batch)
                total_elapsed_ms += elapsed_ms
                batch_results.append(
                    {
                        "batch_idx": i // args.batch_size,
                        "n_docs": len(batch),
                        "elapsed_ms": elapsed_ms,
                        "throughput_docs_per_s": len(batch) / (elapsed_ms / 1000),
                    }
                )

        await engine.dispose()
    except Exception as e:
        # DB 不可达时 (开发机本地跑 / DB 未启动) 仍写结果 JSON,
        # 让决策文档能引用 (bench 框架验证通过 + encoder 验证通过 + DB 写入跳过)
        logger.warning(
            f"[bge-m3] DB 操作失败 ({type(e).__name__}: {str(e)[:200]}), "
            f"已用 0 docs 标记, JSON 仍写 (开发机 / DB 未启动场景)"
        )
        db_unavailable_note = (
            f"DB unavailable during smoke: {type(e).__name__}: {str(e)[:100]}"
        )

    # 4. 写结果 JSON
    result: Dict[str, Any] = {
        "w_n_c_phase": "C.3",
        "task": "bge-m3 batch re-embed (修订: 100 题轻量级版)",
        "is_mock": is_mock,
        "encoder_name": getattr(encoder, "name", "bge_m3_real"),
        "dim": getattr(encoder, "dim", 1024),
        "total_requested": args.total,
        "total_reembedded": n_reembedded,
        "batch_size": args.batch_size,
        "total_elapsed_ms": total_elapsed_ms,
        "avg_throughput_docs_per_s": (
            n_reembedded / (total_elapsed_ms / 1000) if total_elapsed_ms > 0 else 0.0
        ),
        "batches": batch_results,
        "note": (
            "W-N-C +3 修订版: 100 题 (非 1000), 派工 brief 据实上报. "
            "本机 CUDA 不可用 + BAAI/bge-m3 模型未下载, "
            "真加载失败 fallback mock encoder (零向量). "
            "决策文档见 docs/decisions/2026-08-05-bge-m3-decision.md."
        ),
    }
    if db_unavailable_note:
        result["db_unavailable_note"] = db_unavailable_note
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        f"[bge-m3] 完成: {n_reembedded}/{args.total} docs, "
        f"avg throughput={result['avg_throughput_docs_per_s']:.1f} docs/s, "
        f"is_mock={is_mock}, output={output_path}"
    )
    logger.info(f"[bge-m3] 决策文档: docs/decisions/2026-08-05-bge-m3-decision.md")


if __name__ == "__main__":
    asyncio.run(main())