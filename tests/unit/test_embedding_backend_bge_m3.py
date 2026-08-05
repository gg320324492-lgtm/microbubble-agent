"""Unit tests for EmbeddingBackend dual-backend abstraction (W-N-C +1, 阶段 C.1)

TDD 顺序:
1. 写失败测试 → 跑 → FAIL → 写实现 → 跑 → PASS → commit
2. lightweight mock — 不真加载 BAAI/bge-m3 模型 (本机 CUDA 不可用, 模型未下载)
3. 验证接口契约: from_env() 路由 + get_embedding_backend() singleton + encode 返回 numpy float32

设计:
- 默认 backend = qwen3 (沿用现有 MODEL_NAME 路径)
- EMBEDDING_BACKEND=bge_m3 env var 切换到 BGEM3Backend (MTEB 多语言 1024d)
- 双轨兼容: 现有 generate_embedding_sync / generate_embedding / generate_embeddings /
  get_or_compute_query_embedding 全部仍可用 (不破坏老调用方)
"""
import os
import importlib
import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _reload_module():
    """每个 test 重新 load embedding_service, 确保 EMBEDDING_BACKEND env var 生效."""
    import app.services.embedding_service as es
    importlib.reload(es)
    yield


def test_qwen3_backend_default_name_and_dim():
    """默认 backend = qwen3, dim=1024 (Qwen3-Embedding-0.6B native)."""
    from app.services.embedding_service import EmbeddingBackend
    backend = EmbeddingBackend.from_env()
    assert backend.name == "qwen3"
    assert backend.dim == 1024


def test_bge_m3_backend_from_env(monkeypatch):
    """EMBEDDING_BACKEND=bge_m3 → BGEM3Backend, name=bge_m3, dim=1024."""
    monkeypatch.setenv("EMBEDDING_BACKEND", "bge_m3")
    import app.services.embedding_service as es
    importlib.reload(es)
    backend = es.EmbeddingBackend.from_env()
    assert backend.name == "bge_m3"
    assert backend.dim == 1024


def test_get_embedding_backend_singleton(monkeypatch):
    """get_embedding_backend() 返回同一个 instance (singleton 模式, 不重复加载模型)."""
    from app.services.embedding_service import get_embedding_backend
    a = get_embedding_backend()
    b = get_embedding_backend()
    assert a is b


def test_backend_encode_returns_float32_ndarray(monkeypatch):
    """encode(texts) 返回 numpy ndarray, dtype=float32, shape=(n, dim).

    用 monkeypatch 替换底层 SentenceTransformer.encode, 避免真加载 bge-m3 模型
    (本机 CUDA 不可用 + BAAI/bge-m3 模型未下载 ~2.7GB).
    """
    monkeypatch.setenv("EMBEDDING_BACKEND", "bge_m3")
    import app.services.embedding_service as es
    importlib.reload(es)

    # 重新替换 _model singleton 的 encode 方法 (mock)
    backend = es.get_embedding_backend()
    # BGEM3Backend._model 应该已经被 SentenceTransformer(...) 初始化, 真加载会失败
    # 我们 monkeypatch encode 返回固定 shape
    def fake_encode(texts, **kwargs):
        return np.random.RandomState(42).rand(len(texts), 1024).astype(np.float32)

    if hasattr(backend, "_model") and backend._model is not None:
        # 真模型加载成功 (有 cache), 替换其 encode
        backend._model.encode = fake_encode

    vecs = backend.encode(["测试中文", "BGE m3 灰度"])
    assert isinstance(vecs, np.ndarray)
    assert vecs.shape == (2, 1024)
    assert vecs.dtype == np.float32


def test_backend_encode_async_runs_in_thread(monkeypatch):
    """encode_async 默认在线程池跑, 避免阻塞事件循环."""
    monkeypatch.setenv("EMBEDDING_BACKEND", "bge_m3")
    import app.services.embedding_service as es
    importlib.reload(es)

    backend = es.get_embedding_backend()

    async def run():
        return await backend.encode_async(["async 测试"])

    # 替换 encode 避免真模型推理
    def fake_encode(texts, **kwargs):
        return np.zeros((len(texts), 1024), dtype=np.float32)

    if hasattr(backend, "_model") and backend._model is not None:
        backend._model.encode = fake_encode

    import asyncio
    vec = asyncio.run(run())
    assert vec.shape == (1, 1024)
    assert vec.dtype == np.float32