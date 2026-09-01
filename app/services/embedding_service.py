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
from abc import ABC, abstractmethod
from sentence_transformers import SentenceTransformer
from typing import List, Optional

from app.services.embedding_prompts import build_embedding_prompt
from app.services.embedding_query_policy import should_use_query_prefix
from app.services.embedding_truncation_policy import (
    MODEL_HAS_QUERY_PROMPT,
    truncate_for_embedding,
)

logger = logging.getLogger("microbubble.embedding")

# 从环境变量读取模型名，默认 Qwen3
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
# 设备策略：auto / cuda / cpu（auto 模式下 torch.cuda.is_available() 自动选）
DEVICE_OVERRIDE = os.getenv("EMBEDDING_DEVICE", "auto").lower()
# 批量大小：GPU 上 64 更舒服，CPU 32 够用
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))

# W-N-C +1: 双后端抽象 (Qwen3 默认 | bge_m3 灰度)
# 注意: 保留原 _model singleton + 通过 EMBEDDING_BACKEND env var 路由,
# 不破坏现有 generate_embedding_sync / generate_embedding / generate_embeddings /
# get_or_compute_query_embedding 调用方.
EMBEDDING_BACKEND_NAME = os.getenv("EMBEDDING_BACKEND", "qwen3").lower()  # qwen3 | bge_m3
BGE_M3_MODEL_NAME = "BAAI/bge-m3"

# W-N-F +3: LoRA adapter 加载逻辑占位 (派工 brief 派工起点, 严禁真加载)
# 派工 brief: 1-2 月长跑训练未实施, 此处仅 env var 占位
# 真加载逻辑待 W-N-G+ 派工 (peft + sentence-transformers 集成)
# 设计意图:
#   - LORA_ENABLED=false (默认) → 走原 base model, 0 改动
#   - LORA_ENABLED=true + LORA_PATH=有效路径 → 加载 peft adapter
#   - 加载失败 → logger.error + 立即回退 base model, 不阻塞生产
LORA_ENABLED = os.getenv("LORA_ENABLED", "false").lower() in ("1", "true", "yes")
LORA_PATH = os.getenv("LORA_PATH", "")  # e.g. data/finetune/lora_adapter/
LORA_DEFAULT_DISABLED_REASON = "W-N-F +3 占位, 真加载待 W-N-G+ 派工"


class EmbeddingBackend(ABC):
    """Embedding 后端抽象 (W-N-C +1, 阶段 C.1).

    设计:
      - 双轨兼容: 现有 _model singleton 仍生效 (Qwen3 路径), BGEM3Backend 通过
        SentenceTransformer 独立加载, 互不干扰
      - from_env() 路由 EMBEDDING_BACKEND env var -> Qwen3Backend / BGEM3Backend
      - encode_async 默认在线程池跑, 不阻塞 event loop
      - 子类提供 name + dim + encode() 即可, 单测用 monkeypatch 替换底层
    """
    name: str = ""
    dim: int = 1024

    @abstractmethod
    def encode(self, texts: List[str]) -> "np.ndarray":
        ...

    async def encode_async(self, texts: List[str]) -> "np.ndarray":
        """默认在线程池跑, 避免阻塞事件循环.

        重写可选, 但 BGEM3Backend / Qwen3Backend 都用默认实现已足够.
        """
        import asyncio
        return await asyncio.to_thread(self.encode, texts)

    @classmethod
    def from_env(cls) -> "EmbeddingBackend":
        if EMBEDDING_BACKEND_NAME == "bge_m3":
            return BGEM3Backend()
        return Qwen3Backend()


class Qwen3Backend(EmbeddingBackend):
    """Qwen3-Embedding-0.6B 后端 (默认, 1024d).

    复用现有 _model singleton — 不重复加载模型.
    现有 generate_embedding_sync / generate_embedding / generate_embeddings 已经
    走 _model 路径, 本 backend 仅作为 from_env() 的返回类型.
    """
    name = "qwen3"
    dim = 1024

    def encode(self, texts: List[str]) -> "np.ndarray":
        """复用 _model singleton. 失败返回空 ndarray (上层 generate_embedding 已 try/except)."""
        import numpy as np
        model = _get_model()
        if model is None:
            return np.zeros((len(texts), self.dim), dtype=np.float32)
        prompt = build_embedding_prompt(False, MODEL_HAS_QUERY_PROMPT)
        return model.encode(
            texts,
            prompt=prompt,
            normalize_embeddings=True,
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
        ).astype(np.float32)


class BGEM3Backend(EmbeddingBackend):
    """BAAI/bge-m3 后端 (灰度候选, 1024d, MTEB 多语言).

    独立 _model_holder, 不复用 Qwen3 singleton. 这样:
      1. 现有 Qwen3 路径零影响 (默认 EMBEDDING_BACKEND=qwen3 时 BGEM3Backend 永不实例化)
      2. 灰度时切换 ENV 即可, 不需要清理 Qwen3 _model
      3. 失败回退: 加载失败时 _model_holder = None, encode 返回零向量 (上层 catch)

    注意: 本机 CUDA 不可用时, BGEM3Backend 仍可用 SentenceTransformer(BAAI/bge-m3,
    device="cpu") 加载 (慢但功能正确). GPU pass-through 由 _detect_device() 自动选.
    """
    name = "bge_m3"
    dim = 1024

    def __init__(self) -> None:
        import numpy as np
        self._model_holder: Optional[SentenceTransformer] = None
        try:
            device = _detect_device()
            logger.info(
                f"[bge_m3] 加载模型: {BGE_M3_MODEL_NAME}, device={device}"
            )
            self._model_holder = SentenceTransformer(
                BGE_M3_MODEL_NAME,
                device=device,
                trust_remote_code=True,
            )
            actual_device = next(self._model_holder.parameters()).device
            logger.info(
                f"[bge_m3] 模型加载完成: {BGE_M3_MODEL_NAME}, "
                f"dim={self._model_holder.get_embedding_dimension()}, "
                f"max_seq_length={self._model_holder.max_seq_length}, "
                f"actual_device={actual_device}"
            )
        except Exception as e:
            logger.warning(
                f"[bge_m3] 模型加载失败 ({type(e).__name__}: {str(e)[:200]}), "
                f"encode 将返回零向量"
            )
            self._model_holder = None

    def encode(self, texts: List[str]) -> "np.ndarray":
        """bge-m3 推理. 失败返回零向量 (上层 try/except 不抛)."""
        import numpy as np
        if self._model_holder is None:
            return np.zeros((len(texts), self.dim), dtype=np.float32)
        try:
            return self._model_holder.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
            ).astype(np.float32)
        except Exception as e:
            logger.warning(f"[bge_m3] encode 失败: {e}")
            return np.zeros((len(texts), self.dim), dtype=np.float32)


_backend_singleton: Optional["EmbeddingBackend"] = None


def get_embedding_backend() -> "EmbeddingBackend":
    """获取 EmbeddingBackend singleton (W-N-C +1, 阶段 C.1).

    路由逻辑:
      1. 首次调用: 根据 EMBEDDING_BACKEND env var 实例化对应 backend
      2. 后续调用: 返回同一个 instance (singleton, 不重复加载模型)
      3. 现有 _model (Qwen3 路径) 与 _backend_singleton (双后端路径) 并存,
         不破坏 generate_embedding_sync / generate_embedding 等老 API
    """
    global _backend_singleton
    if _backend_singleton is None:
        _backend_singleton = EmbeddingBackend.from_env()
        logger.info(
            f"Embedding backend (W-N-C +1): {_backend_singleton.name} "
            f"(dim={_backend_singleton.dim})"
        )
    return _backend_singleton

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


def generate_embedding_sync(
    text: str,
    for_query: bool = False,
    has_query_prompt: bool = False,
    caller_path: Optional[str] = None,
) -> Optional[List[float]]:
    """同步生成单条文本的 embedding，失败返回 None

    Args:
        text: 输入文本
        for_query: 是否为 query（True 时用 ST prompt 机制加指令前缀；False=document）
                  注意：当前项目所有调用都用 False (document 模式)，RAG 检索也是 document 模式
        has_query_prompt: 模型是否支持 query prefix（Qwen3-Embedding/BGE-m3 等 instruction-tuned = True）
    """
    try:
        model = _get_model()
        if model is None:
            return None
        # Canonical preprocessing is shared with recalculation and chunking.
        text = truncate_for_embedding(text)
        prompt = build_embedding_prompt(for_query, has_query_prompt)
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


async def generate_embedding(
    text: str,
    for_query: Optional[bool] = None,
    has_query_prompt: bool = MODEL_HAS_QUERY_PROMPT,
    caller_path: Optional[str] = None,
) -> Optional[List[float]]:
    """异步生成单条文本的 embedding，超时或失败返回 None

    Args:
        text: 输入文本
        for_query: 保留兼容（当前所有调用都用 False）
    """
    if for_query is None:
        for_query = should_use_query_prefix(caller_path)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                generate_embedding_sync,
                text,
                for_query,
                has_query_prompt,
                caller_path,
            ),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        logger.warning("Embedding 生成超时（60s），返回 None")
        return None
    except Exception as e:
        logger.warning(f"Embedding 生成失败: {e}")
        return None


async def generate_embeddings(
    texts: List[str],
    for_query: bool = False,
    has_query_prompt: bool = False,
) -> Optional[List[List[float]]]:
    """异步批量生成 embedding，失败返回 None

    Args:
        texts: 文本列表
        for_query: 保留兼容（当前所有调用都用 False）
        has_query_prompt: 模型是否支持 query prefix（同 generate_embedding_sync）
    """
    model = _get_model()
    if model is None:
        return None

    def _encode():
        try:
            prompt = build_embedding_prompt(for_query, has_query_prompt)
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


# ============================================================================
# W99 P2 RAG 性能优化 (commit +4): query 侧 embedding Redis 缓存复用
# ============================================================================
# 设计原则:
#   1. 只缓存 query 侧 (for_query=True) — document 侧无限且低重复率
#   2. key = sha256(query)[:16] — 16 hex 字符 64-bit 空间, 足以区分常用 query
#   3. TTL 24h — query 变化多, 1 天合理 (用户重复问相似问题)
#   4. 失败 best-effort — Redis 不可用时 silently 走原路径, 不阻塞主流程
#   5. 缓存命中 < 5ms (本地 Redis round-trip), 未命中 = 原计算时间
# ============================================================================

QUERY_EMBEDDING_CACHE_PREFIX = "emb:q:"
QUERY_EMBEDDING_CACHE_TTL_SECONDS = 86400  # 24h


def _query_cache_key(query: str) -> str:
    """生成 query embedding 缓存 key (sha256[:16])

    2026-09-01 WP4.1: 键中拼入 EMBEDDING_BACKEND — 模型/后端切换后旧缓存
    自动失配 (向量空间不同), 老键走 TTL 自然过期, 不会污染新模型检索。
    """
    import hashlib
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    return f"{QUERY_EMBEDDING_CACHE_PREFIX}{EMBEDDING_BACKEND_NAME}:{digest}"


async def get_or_compute_query_embedding(
    query: str,
    has_query_prompt: bool = MODEL_HAS_QUERY_PROMPT,
) -> Optional[List[float]]:
    """query 侧 embedding 缓存复用 (W99 P2)

    行为契约:
      - 缓存命中: 返回 list[float], < 5ms
      - 缓存未命中: 调 generate_embedding 计算, 写缓存, 返回
      - Redis 不可用: silently 降级到 generate_embedding, 不抛异常
      - 计算失败: 返回 None (与 generate_embedding 一致)

    Args:
        query: 用户查询文本
        has_query_prompt: 模型是否支持 query prefix (默认走 BGE-m3 / Qwen3-Embedding 默认)
    """
    cache_key = _query_cache_key(query)

    # 1. 查缓存 (best-effort)
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached is not None:
            # JSON 反序列化
            import json
            embedding = json.loads(cached)
            logger.debug(f"[emb cache HIT] {cache_key} dim={len(embedding)}")
            return embedding
    except Exception as e:
        # Redis 不可用 / 连接失败 → 降级到计算路径
        logger.debug(f"[emb cache lookup miss/fail] {cache_key}: {e}")

    # 2. 计算 (调用现有 async 路径)
    embedding = await generate_embedding(
        text=query,
        for_query=True,
        has_query_prompt=has_query_prompt,
    )
    if embedding is None:
        return None

    # 3. 写缓存 (best-effort, 不阻塞主流程)
    try:
        from app.core.redis import get_redis
        import json
        redis = await get_redis()
        await redis.setex(
            cache_key,
            QUERY_EMBEDDING_CACHE_TTL_SECONDS,
            json.dumps(embedding),
        )
        logger.debug(f"[emb cache SET] {cache_key} dim={len(embedding)} ttl={QUERY_EMBEDDING_CACHE_TTL_SECONDS}s")
    except Exception as e:
        # Redis 写失败 — 不影响主流程
        logger.debug(f"[emb cache set fail] {cache_key}: {e}")

    return embedding
