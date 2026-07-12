"""Embedding service - 向量嵌入生成

Phase 2 重构 (2026-06-24 sentence-transformers 5.6.0 升级)：
- 统一用 sentence-transformers SentenceTransformer 加载所有 embedding 模型
- ST 5.6.0 的 Pooling 支持 include_prompt 参数 + Qwen3 native 加载
- 单 ST 路径 = 单代码路径 = 少 bug 表面
- 2026-07-12 死代码清理: 删除孤儿 qwen_embedder_legacy.py (无任何调用方)

设备自动检测：EMBEDDING_DEVICE=auto 时按 torch.cuda.is_available() 选择。
可选模型通过 EMBEDDING_MODEL_NAME 环境变量切换：
  - 默认: Qwen/Qwen3-Embedding-0.6B (1024d, ST 5.6.0 native, 推荐)
  - 备选: shibing624/text2vec-base-chinese (768d, ST 5.6.0 直接支持)
"""

import asyncio
import logging
import os
from sentence_transformers import SentenceTransformer
from typing import List, Optional

logger = logging.getLogger("microbubble.embedding")

# 从环境变量读取模型名，默认 Qwen3
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
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
    """获取 SentenceTransformer 模型单例（不会阻塞）

    Phase 2: 统一用 ST 5.6.0 加载所有模型。
    - Qwen3-Embedding: ST 5.6.0 支持 trust_remote_code + last-token pooling (via Pooling include_prompt)
    - text2vec-base-chinese: 直接支持
    - 其他: 透明

    回退策略: 加载失败时返回 None（generate_embedding 会返回 None）
    """
    global _model, _model_loading
    if _model is None and not _model_loading:
        _model_loading = True
        try:
            device = _detect_device()
            logger.info(f"加载 embedding 模型: {MODEL_NAME}, device={device}, batch_size={BATCH_SIZE}")
            _model = SentenceTransformer(MODEL_NAME, device=device, trust_remote_code=True)
            actual_device = next(_model.parameters()).device
            logger.info(
                f"Embedding 模型加载完成: {MODEL_NAME}, "
                f"dim={_model.get_embedding_dimension()}, "
                f"max_seq_length={_model.max_seq_length}, "
                f"actual_device={actual_device}"
            )
        except Exception as e:
            logger.error(f"Embedding 模型加载失败: {e}")
            _model = None
        finally:
            _model_loading = False
    return _model


def generate_embedding_sync(text: str, for_query: bool = False) -> Optional[List[float]]:
    """同步生成单条文本的 embedding，失败返回 None

    Args:
        text: 输入文本
        for_query: 是否为 query（True 时用 ST prompt 机制加指令前缀；False=document）
                  注意：当前项目所有调用都用 False (document 模式)，RAG 检索也是 document 模式
    """
    try:
        model = _get_model()
        if model is None:
            return None
        # Phase 2: 统一 ST 路径
        # for_query=True 时用 ST 的 prompt 系统加前缀；document 不加前缀
        prompt = None  # TODO: if for_query and has_query_prompt: prompt = ...
        # ST 5.6.0 支持 prompt= 参数（pass 中文 prefix to match old wrapper behavior）
        arr = model.encode(
            [text],
            prompt=prompt,
            normalize_embeddings=True,
        )[0]
        return arr.tolist()
    except Exception as e:
        logger.warning(f"同步 Embedding 生成失败: {e}")
        return None


async def generate_embedding(text: str, for_query: bool = False) -> Optional[List[float]]:
    """异步生成单条文本的 embedding，超时或失败返回 None

    Args:
        text: 输入文本
        for_query: 保留兼容（当前所有调用都用 False）
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(generate_embedding_sync, text, for_query),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        logger.warning("Embedding 生成超时（60s），返回 None")
        return None
    except Exception as e:
        logger.warning(f"Embedding 生成失败: {e}")
        return None


async def generate_embeddings(texts: List[str], for_query: bool = False) -> Optional[List[List[float]]]:
    """异步批量生成 embedding，失败返回 None

    Args:
        texts: 文本列表
        for_query: 保留兼容（当前所有调用都用 False）
    """
    model = _get_model()
    if model is None:
        return None

    def _encode():
        try:
            prompt = None  # TODO: if for_query and has_query_prompt: prompt = ...
            return model.encode(
                texts,
                prompt=prompt,
                normalize_embeddings=True,
                batch_size=BATCH_SIZE,
            ).tolist()
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
