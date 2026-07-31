"""app/rag/semantic_chunker.py — Semantic Chunker 语义分块

LangChain SemanticChunker:
- 基于 embedding 余弦 gap 检测语义边界
- 一个 chunk 内语义一致 (前半讲工艺参数 + 后半讲设备选型 → 拆成 2 chunk)
- 与 chunking_service.py 3 规则策略并列, 不替换

使用:
    from app.rag.semantic_chunker import semantic_chunk
    chunks = semantic_chunk(text, min_chunk_size=200, breakpoint_percentile=95)

semantic_score 定义:
    chunk 内部连续句子 embedding 余弦相似度均值 (越高 = chunk 内语义越一致,
    单句 chunk = 1.0, embedding 失败 = 0.0)
"""

import inspect
import logging
import math
import re
from typing import List, Optional

from app.rag.config import SEMANTIC_CHUNKER_ENABLED

logger = logging.getLogger("microbubble.rag.semantic_chunker")

# LangChain SemanticChunker 默认 sentence_split_regex 只覆盖英文标点,
# 中文语料 (微纳米气泡文档) 必须显式注入中文句读, 否则整段视为 1 句 → 语义分块失效
SENTENCE_SPLIT_REGEX = r"(?<=[。！？!?；;])\s*"


def semantic_chunk(
    text: str,
    min_chunk_size: int = 200,
    breakpoint_percentile: int = 95,
    embedding_fn=None,
) -> List[dict]:
    """LangChain SemanticChunker 分块

    Args:
        text: 输入文本
        min_chunk_size: 最小 chunk 字符数 (默认 200)
        breakpoint_percentile: 语义边界百分位阈值 (默认 95, 仅 top 5% 余弦 gap 算边界)
        embedding_fn: 注入的 embedding 函数 (默认用 app.services.embedding_service.generate_embedding_sync)

    Returns:
        List[dict]: [{"content": str, "char_start": int, "char_end": int, "semantic_score": float}]

    SEMANTIC_CHUNKER_ENABLED=False 或框架未装时回退到 chunking_service 规则策略。
    """
    if not text:
        return []
    if not SEMANTIC_CHUNKER_ENABLED:
        return _fallback_rule_chunks(text)
    try:
        if embedding_fn is None:
            from app.services.embedding_service import generate_embedding_sync
            embedding_fn = generate_embedding_sync
        from langchain_core.embeddings import Embeddings
        from langchain_experimental.text_splitter import SemanticChunker

        class _EmbeddingsAdapter(Embeddings):
            """把项目 embedding 函数 (text: str) -> List[float] 适配成 LangChain Embeddings 接口

            embedding 失败 (None) 时抛 RuntimeError → 上层 except 兜底回退规则分块
            """

            def __init__(self, fn):
                self._fn = fn

            def embed_documents(self, texts, **kwargs):
                vectors = [self._fn(t) for t in texts]
                for t, v in zip(texts, vectors):
                    if v is None:
                        raise RuntimeError(f"embed_documents 失败: text prefix={t[:30]!r}")
                return vectors

            def embed_query(self, text, **kwargs):
                v = self._fn(text)
                if v is None:
                    raise RuntimeError("embed_query 失败")
                return v

        adapter = _EmbeddingsAdapter(embedding_fn)
        init_params = set(inspect.signature(SemanticChunker.__init__).parameters)
        kwargs = {
            "embeddings": adapter,
            "breakpoint_threshold_type": "percentile",
            "breakpoint_threshold_amount": breakpoint_percentile,
        }
        # 版本兼容: 老版本 SemanticChunker 无 min_chunk_size / sentence_split_regex 参数
        if "min_chunk_size" in init_params:
            kwargs["min_chunk_size"] = min_chunk_size
        if "sentence_split_regex" in init_params:
            kwargs["sentence_split_regex"] = SENTENCE_SPLIT_REGEX
        splitter = SemanticChunker(**kwargs)

        parts = splitter.split_text(text)
        chunks: List[dict] = []
        cursor = 0
        for content in parts:
            if not content:
                continue
            start = text.find(content, cursor)
            if start == -1:
                # chunk 文本未在原文找到 (框架做了空白规整等) → 从游标起顺序切片
                start = cursor
            end = min(start + len(content), len(text))
            if end <= start:
                continue
            chunks.append(
                {
                    "content": content,
                    "char_start": start,
                    "char_end": end,
                    "semantic_score": _semantic_score(content, embedding_fn),
                }
            )
            cursor = end
        return chunks
    except ImportError as e:
        logger.warning(f"langchain_experimental 未安装, 回退规则分块: {e}")
        return _fallback_rule_chunks(text)
    except Exception as e:
        logger.error(f"SemanticChunker 失败, 回退规则分块: {e}", exc_info=True)
        return _fallback_rule_chunks(text)


def _fallback_rule_chunks(text: str) -> List[dict]:
    """回退: 现有 chunking_service 规则策略"""
    from app.services.chunking_service import chunk_text
    chunks = chunk_text(text)
    return [
        {
            "content": c.content,
            "char_start": c.char_start,
            "char_end": c.char_end,
            "semantic_score": 0.0,
        }
        for c in chunks
    ]


def _semantic_score(content: str, embedding_fn) -> float:
    """chunk 内语义一致性: 连续句子 embedding 余弦相似度均值

    - 单句 chunk = 1.0 (无可比句对, 天然一致)
    - 任一句子 embedding 失败 = 0.0
    """
    sentences = [s for s in re.split(r"[。！？!?；;\n]+", content) if s.strip()]
    if len(sentences) < 2:
        return 1.0
    vectors: List[Optional[List[float]]] = []
    for s in sentences:
        v = embedding_fn(s.strip())
        if v is None:
            return 0.0
        vectors.append(v)
    sims = [_cosine(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
    return sum(sims) / len(sims)


def _cosine(a: List[float], b: List[float]) -> float:
    """余弦相似度, 零向量 / 维度不一致返回 0.0"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
