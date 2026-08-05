"""Late chunking 真 bench — 真模型 + 真 GPU + 真长文档 (W-N-D+ +2).

与 `scripts/bench_late_chunking.py` (MockModel 全 1 向量, 0 检索信号) 的区别:

    mock bench          真 bench (本文件)
    ----------          ------------------
    全 1 token 向量      真 SentenceTransformer token_embeddings (GPU)
    合成重复文本         DB 里的真实长文档 (knowledge.content)
    人造 query           真实检索 query
    score 恒 1024.0     真 cosine, parent vs chunk 可比较

回答的问题: **late chunking 的多向量召回, 相比 parent-doc 单向量, 是否真的更好?**

方法:
  1. 取 N 篇真实长文档
  2. parent 基线: 整篇一次编码 → 1 个 sentence_embedding
  3. late chunking: 整篇一次编码 → token_embeddings → 滑窗 mean-pool → M 个 chunk 向量
     (关键: 只 forward 一次, 每个 chunk 都看得到全篇上下文 — 这正是 late chunking 的定义)
  4. 每个 query 分别对 parent 向量 / chunk 向量集 (取 max) 算 cosine
  5. 报告 win/lose/tie + delta 分布

模型: 默认 `Qwen/Qwen3-Embedding-0.6B` (生产默认, 已缓存 1.2GB).
`BAAI/bge-m3` 需另行下载 ~2.7GB — 触发条件见
`docs/bench/late_chunking_real_bench_threshold.md`.

用法 (必须在有 GPU + 有模型缓存的容器内跑):

    docker exec microbubble-agent-app-1 python scripts/run_late_chunking_realbench.py
    docker exec microbubble-agent-app-1 python scripts/run_late_chunking_realbench.py \
        --model BAAI/bge-m3 --n-docs 5 --device cuda

前置能力验证见 `docs/capability/gpu-bge-m3-2026-08-05.md`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.late_chunking_service import LateChunkingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_OUTPUT = "results/late_chunking_real_bench_2026-08.json"

# 微纳米气泡课题组真实检索 query (对应 knowledge 库主题域)
DEFAULT_QUERIES: Tuple[str, ...] = (
    "微纳米气泡的 ζ 电位如何影响稳定性",
    "臭氧微纳米气泡对有机污染物的降解机理",
    "气泡尺寸分布的测量方法",
    "微纳米气泡强化传质的实验证据",
    "消毒副产物的控制策略",
)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """余弦相似度. 零向量返回 0.0 (不抛)."""
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def summarize(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """按 (doc, query) 对聚合 win/lose/tie + delta 分位数.

    win = late chunking 的最佳 chunk 分数 > parent 单向量分数.
    纯统计, 不依赖模型/DB — 便于单测.
    """
    if not rows:
        return {"pairs": 0, "chunk_win": 0, "parent_win": 0, "tie": 0}
    deltas = [float(r["chunk_best_score"]) - float(r["parent_score"]) for r in rows]
    eps = 1e-6
    return {
        "pairs": len(rows),
        "chunk_win": sum(1 for d in deltas if d > eps),
        "parent_win": sum(1 for d in deltas if d < -eps),
        "tie": sum(1 for d in deltas if abs(d) <= eps),
        "chunk_win_rate": round(sum(1 for d in deltas if d > eps) / len(deltas), 4),
        "delta_mean": round(float(np.mean(deltas)), 6),
        "delta_p50": round(float(np.percentile(deltas, 50)), 6),
        "delta_p95": round(float(np.percentile(deltas, 95)), 6),
        "delta_min": round(float(np.min(deltas)), 6),
        "delta_max": round(float(np.max(deltas)), 6),
    }


async def fetch_long_documents(
    n_docs: int, min_chars: int, database_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """从 knowledge 表取真实长文档. 只读, 不写库."""
    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    if database_url is None:
        from app.config import settings

        database_url = settings.DATABASE_URL
    db_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as session:
            result = await session.execute(
                sql_text(
                    "SELECT id, title, content FROM knowledge "
                    "WHERE content IS NOT NULL AND length(content) >= :min_chars "
                    "ORDER BY id LIMIT :n"
                ),
                {"min_chars": min_chars, "n": n_docs},
            )
            return [
                {"id": row.id, "title": (row.title or "")[:80], "content": row.content}
                for row in result.fetchall()
            ]
    finally:
        await engine.dispose()


def load_model(model_name: str, device: str):
    """加载 SentenceTransformer. 不下载不存在的模型时会由 HF 抛错 — 故意 fail loud."""
    from sentence_transformers import SentenceTransformer

    t0 = time.time()
    model = SentenceTransformer(model_name, device=device, trust_remote_code=True)
    logger.info(
        "model=%s device=%s load=%.1fs max_seq_length=%s",
        model_name,
        device,
        time.time() - t0,
        model.max_seq_length,
    )
    return model


def encode_parent(model, text: str, max_length: int) -> np.ndarray:
    """parent 基线: 整篇 → 1 个 sentence_embedding."""
    import torch

    feats = model.tokenizer(
        text, return_tensors="pt", truncation=True, max_length=max_length
    )
    feats = {k: v.to(model.device) for k, v in feats.items()}
    with torch.no_grad():
        out = model.forward(feats)
    # .float() 必需: Qwen3 等模型以 bfloat16 推理, numpy 不支持该 dtype
    emb = out["sentence_embedding"].detach().float().cpu().numpy()
    return np.asarray(emb[0], dtype=np.float32)


class _GpuModelAdapter:
    """把 SentenceTransformer 适配成 LateChunkingService 期望的最小接口.

    LateChunkingService 只要 `.tokenizer` 与 `.forward(inputs) -> {token_embeddings}`.
    这里负责搬到 device + no_grad + detach 回 CPU, service 本身保持零 torch 依赖.
    """

    def __init__(self, model) -> None:
        self._model = model
        self.tokenizer = model.tokenizer

    def forward(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        import torch

        moved = {k: v.to(self._model.device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self._model.forward(moved)
        return {
            # .float() 必需: bfloat16 推理产物 numpy 不支持, LateChunkingService 走 np.asarray
            "token_embeddings": out["token_embeddings"].detach().float().cpu(),
            "attention_mask": moved["attention_mask"].detach().cpu(),
        }


def run_benchmark(
    model,
    documents: Sequence[Dict[str, Any]],
    queries: Sequence[str],
    chunk_size: int,
    overlap: int,
    max_length: int,
) -> Dict[str, Any]:
    """每篇文档 × 每个 query 比较 parent 单向量 vs late chunking 多向量."""
    adapter = _GpuModelAdapter(model)
    service = LateChunkingService(
        adapter, chunk_size=chunk_size, overlap=overlap, max_length=max_length
    )

    query_vectors = {
        q: np.asarray(
            model.encode(q, normalize_embeddings=False, convert_to_numpy=True),
            dtype=np.float32,
        )
        for q in queries
    }

    rows: List[Dict[str, Any]] = []
    doc_meta: List[Dict[str, Any]] = []
    for doc in documents:
        text = doc["content"]
        t0 = time.time()
        parent_vec = encode_parent(model, text, max_length)
        parent_ms = (time.time() - t0) * 1000

        t1 = time.time()
        chunk_vecs = service.encode(text)
        chunk_ms = (time.time() - t1) * 1000

        doc_meta.append(
            {
                "doc_id": doc["id"],
                "title": doc["title"],
                "chars": len(text),
                "chunk_count": len(chunk_vecs),
                "parent_encode_ms": round(parent_ms, 2),
                "late_chunk_encode_ms": round(chunk_ms, 2),
            }
        )
        if not chunk_vecs:
            logger.warning("doc %s produced 0 chunks; skipped", doc["id"])
            continue

        for query in queries:
            qv = query_vectors[query]
            chunk_scores = [cosine(qv, cv) for cv in chunk_vecs]
            best_idx = int(np.argmax(chunk_scores))
            rows.append(
                {
                    "doc_id": doc["id"],
                    "query": query,
                    "chunk_count": len(chunk_vecs),
                    "parent_score": round(cosine(qv, parent_vec), 6),
                    "chunk_best_score": round(float(chunk_scores[best_idx]), 6),
                    "chunk_best_index": best_idx,
                    "chunk_mean_score": round(float(np.mean(chunk_scores)), 6),
                }
            )
    return {"rows": rows, "documents": doc_meta, "summary": summarize(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--n-docs", type=int, default=5)
    parser.add_argument("--min-chars", type=int, default=8000)
    parser.add_argument("--chunk-size", type=int, default=256)
    parser.add_argument("--overlap", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=8192)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    documents = asyncio.run(fetch_long_documents(args.n_docs, args.min_chars))
    if not documents:
        raise SystemExit(
            f"no knowledge document with length >= {args.min_chars}; "
            "lower --min-chars or seed the DB first"
        )
    logger.info("fetched %d real documents", len(documents))

    model = load_model(args.model, args.device)
    payload = run_benchmark(
        model,
        documents,
        DEFAULT_QUERIES,
        args.chunk_size,
        args.overlap,
        args.max_length,
    )
    payload.update(
        {
            "mock": False,
            "model": args.model,
            "device": args.device,
            "chunk_size": args.chunk_size,
            "overlap": args.overlap,
            "max_length": args.max_length,
            "n_documents": len(documents),
            "n_queries": len(DEFAULT_QUERIES),
        }
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("summary: %s", json.dumps(payload["summary"], ensure_ascii=False))
    print(output)


if __name__ == "__main__":
    main()
