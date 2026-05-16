"""Embedding service - 向量嵌入生成"""

import asyncio
from sentence_transformers import SentenceTransformer
from typing import List

MODEL_NAME = "shibing624/text2vec-base-chinese"

_model = None


def _get_model() -> SentenceTransformer:
    """获取模型单例"""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def generate_embedding_sync(text: str) -> List[float]:
    """同步生成单条文本的embedding"""
    model = _get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


async def generate_embedding(text: str) -> List[float]:
    """异步生成单条文本的embedding"""
    return await asyncio.to_thread(generate_embedding_sync, text)


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """异步批量生成embedding"""
    model = _get_model()

    def _encode():
        return model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()

    return await asyncio.to_thread(_encode)
