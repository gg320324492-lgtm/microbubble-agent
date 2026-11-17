"""MiniMax embo-01 云端 Embedding 后端 (2026-11-17).

2026-11-17 评测 (data/tmp/embed_eval.py):
  与 Qwen3-Embedding-0.6B 在 5 组中文 query→7 文档检索上 top-1 5/5 一致,
  质量等效; 切云端可省本地 1.2GB 模型与加载显存。

端点: POST https://api.minimaxi.com/v1/embeddings
  body: {"model": "embo-01", "texts": [...], "type": "query"|"db"}
  返回: {"vectors": [[...1536 维...]]}
⚠️ 维度 1536 ≠ 本地 Qwen3 1024 ⇒ 切换后必须全量重建存量向量。
"""
import logging
import os
import time
from typing import List, Optional

import httpx

from app.config import settings

logger = logging.getLogger("microbubble.minimax_embedding")

MINIMAX_EMBED_URL = "https://api.minimaxi.com/v1/embeddings"
EMBED_MODEL = "embo-01"
DIM = 1536
# 单批条数上限 (云端稳定优先)
BATCH_SIZE = 32


def _get_api_key() -> str:
    """复用 MiniMax 对话链路同源 key。"""
    return (
        getattr(settings, "LLM_OPENAI_COMPAT_API_KEY", "")
        or getattr(settings, "MIMO_API_KEY", "")
        or os.getenv("MINIMAX_EMBED_API_KEY", "")
    )


async def embed_texts(
    texts: List[str],
    text_type: str = "db",
) -> Optional[List[List[float]]]:
    """批量生成 embedding, 失败返回 None (与本地后端失败语义一致).

    text_type: "query" (检索侧) | "db" (入库侧)。
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("[minimax-embed] key 未配置 (LLM_OPENAI_COMPAT_API_KEY/MIMO_API_KEY)")
        return None
    if not texts:
        return []

    out: List[List[float]] = []
    t0 = time.time()
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            payload = {"model": EMBED_MODEL, "texts": batch, "type": text_type}
            ok = False
            last_err = None
            for attempt in range(3):
                try:
                    resp = await client.post(
                        MINIMAX_EMBED_URL,
                        json=payload,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    if resp.status_code == 200:
                        vectors = resp.json().get("vectors") or []
                        if len(vectors) != len(batch):
                            last_err = f"返回 {len(vectors)} 条 != 请求 {len(batch)} 条"
                        else:
                            out.extend(vectors)
                            ok = True
                            break
                    if 400 <= resp.status_code < 500 and resp.status_code not in (408, 429):
                        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        break
                    last_err = f"HTTP {resp.status_code}, attempt {attempt + 1}"
                    time.sleep(min(30, 2 ** attempt))
                except Exception as e:
                    last_err = f"attempt {attempt + 1}: {e}"
                    time.sleep(min(30, 2 ** attempt))
            if not ok:
                logger.warning(
                    f"[minimax-embed] 批 {i // BATCH_SIZE + 1} 失败: {last_err}")
                return None
    logger.info(
        f"[minimax-embed] {len(texts)} 条完成, dim={DIM}, "
        f"{round(time.time() - t0, 1)}s")
    return out
