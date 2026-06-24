"""Embedding service - 向量嵌入生成

支持 GPU 加速（sentence-transformers 自动切 device）。
设备自动检测：EMBEDDING_DEVICE=auto 时按 torch.cuda.is_available() 选择。
可选模型通过 EMBEDDING_MODEL_NAME 环境变量切换（默认 shibing624/text2vec-base-chinese）。
"""

import asyncio
import logging
import os
from sentence_transformers import SentenceTransformer
from typing import List, Optional

logger = logging.getLogger("microbubble.embedding")

# 从环境变量读取模型名，默认保持原有 text2vec-base-chinese
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "shibing624/text2vec-base-chinese")
# 设备策略：auto / cuda / cpu（auto 模式下 torch.cuda.is_available() 自动选）
DEVICE_OVERRIDE = os.getenv("EMBEDDING_DEVICE", "auto").lower()
# 批量大小：GPU 上 64 更舒服，CPU 32 够用
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))

_model = None
_model_loading = False
_detected_device: Optional[str] = None


def _detect_device() -> str:
    """自动检测 GPU / CPU
    - 参考 voiceprint_service.py:115-126 的 GPU detect 模式
    - 显式跑 torch.zeros(1).cuda() 验证（避免 bundled-libs 假阳性）
    - DEVICE_OVERRIDE=cuda 强制 GPU；=cpu 强制 CPU；=auto 自动选
    """
    global _detected_device
    if _detected_device is not None:
        return _detected_device

    if DEVICE_OVERRIDE == "cpu":
        _detected_device = "cpu"
        logger.info("Embedding 设备: cpu (EMBEDDING_DEVICE=cpu)")
        return _detected_device

    try:
        import torch
        if torch.cuda.is_available():
            try:
                torch.zeros(1).cuda()  # 真假验证
                _detected_device = "cuda"
                logger.info(
                    f"Embedding 设备: cuda (检测到 GPU, "
                    f"显存 {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB)"
                )
                return _detected_device
            except Exception as e:
                logger.warning(
                    f"torch.cuda.is_available()=True 但 kernel 启动失败 ({type(e).__name__}: {str(e)[:100]}), 回退 CPU"
                )
        else:
            logger.info("Embedding 设备: cpu (torch.cuda.is_available()=False)")
    except ImportError:
        logger.warning("torch 未安装，Embedding 设备: cpu")

    _detected_device = "cpu"
    return _detected_device


def _get_model() -> Optional[SentenceTransformer]:
    """获取模型单例（不会阻塞）"""
    global _model, _model_loading
    if _model is None and not _model_loading:
        _model_loading = True
        try:
            device = _detect_device()
            logger.info(f"加载 embedding 模型: {MODEL_NAME}, device={device}, batch_size={BATCH_SIZE}")
            _model = SentenceTransformer(MODEL_NAME, device=device)
            actual_device = next(_model.parameters()).device
            logger.info(
                f"Embedding 模型加载完成: {MODEL_NAME}, "
                f"dim={_model.get_sentence_embedding_dimension()}, "
                f"max_seq_length={_model.max_seq_length}, "
                f"actual_device={actual_device}"
            )
        except Exception as e:
            logger.error(f"Embedding 模型加载失败: {e}")
            _model = None
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
            return model.encode(texts, normalize_embeddings=True, batch_size=BATCH_SIZE).tolist()
        except Exception as e:
            logger.warning(f"批量 Embedding 生成失败: {e}")
            return None

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_encode),
            timeout=120.0
        )
    except asyncio.TimeoutError:
        logger.warning(f"批量 Embedding 生成超时（120s, batch={BATCH_SIZE}），返回 None")
        return None
    except Exception as e:
        logger.warning(f"Embedding 生成失败: {e}")
        return None
