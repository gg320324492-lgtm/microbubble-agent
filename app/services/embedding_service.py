"""Embedding service - 向量嵌入生成"""

import asyncio
import logging
from sentence_transformers import SentenceTransformer
from typing import List, Optional

logger = logging.getLogger("microbubble.embedding")

MODEL_NAME = "shibing624/text2vec-base-chinese"

_model = None
_model_loading = False


def _get_model() -> Optional[SentenceTransformer]:
    """获取模型单例（不会阻塞）"""
    global _model, _model_loading
    if _model is None and not _model_loading:
        _model_loading = True
        try:
            _model = SentenceTransformer(MODEL_NAME)
        except Exception as e:
            logger.error(f"Embedding 模型加载失败: {e}")
        finally:
            _model_loading = False
    return _model


def generate_embedding_sync(text: str) -> Optional[List[float]]:
    """同步生成单条文本的embedding，失败返回 None"""
    try:
        model = _get_model()
        if model is None:
            return None
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.warning(f"同步 Embedding 生成失败: {e}")
        return None


async def generate_embedding(text: str) -> Optional[List[float]]:
    """异步生成单条文本的embedding，超时或失败返回 None"""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(generate_embedding_sync, text),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        logger.warning("Embedding 生成超时（60s），返回 None")
        return None
    except Exception as e:
        logger.warning(f"Embedding 生成失败: {e}")
        return None


async def generate_embeddings(texts: List[str]) -> Optional[List[List[float]]]:
    """异步批量生成embedding，失败返回 None"""
    model = _get_model()
    if model is None:
        return None

    def _encode():
        try:
            return model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()
        except Exception as e:
            logger.warning(f"批量 Embedding 生成失败: {e}")
            return None

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_encode),
            timeout=120.0
        )
    except asyncio.TimeoutError:
        logger.warning("批量 Embedding 生成超时（120s），返回 None")
        return None
    except Exception as e:
        logger.warning(f"批量 Embedding 生成失败: {e}")
        return None
