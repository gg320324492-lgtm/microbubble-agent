"""sentence-transformers 5.6.0 升级验证测试

这些测试验证 sentence-transformers 升级到 5.6.0 后的关键不变量：
- API 兼容（SentenceTransformer / CrossEncoder / Pooling）
- text2vec + Qwen3 仍能加载和推理
- deprecation 全部修完

注意：这些是集成测试，需要真实 GPU + HF 模型缓存。
不在默认 CI 跑，加 --run-integration 跑。
"""
import os
import sys
import warnings

import pytest


# 标记为集成测试，默认跳过，需要显式 --run-integration
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"),
    reason="Integration test - requires GPU + HF model cache. Set RUN_INTEGRATION=1 to run.",
)


def test_st_version():
    """验证 sentence-transformers 已是 5.6.0"""
    import sentence_transformers
    assert sentence_transformers.__version__ == "5.6.0", (
        f"Expected sentence-transformers==5.6.0, got {sentence_transformers.__version__}"
    )


def test_st_imports():
    """验证 SentenceTransformer / CrossEncoder 都可 import"""
    from sentence_transformers import SentenceTransformer, CrossEncoder
    assert SentenceTransformer is not None
    assert CrossEncoder is not None


def test_pooling_has_include_prompt():
    """验证 Pooling 支持 include_prompt (Qwen3 关键)"""
    from sentence_transformers.models import Pooling
    import inspect
    sig = inspect.signature(Pooling.__init__)
    assert "include_prompt" in sig.parameters, (
        "Pooling.__init__ should have include_prompt param for Qwen3 native loading"
    )


def test_crossencoder_has_backend():
    """验证 CrossEncoder 支持 backend 参数 (ONNX 加速关键)"""
    from sentence_transformers import CrossEncoder
    import inspect
    sig = inspect.signature(CrossEncoder.__init__)
    assert "backend" in sig.parameters, (
        "CrossEncoder.__init__ should have backend param for ONNX/OpenVINO"
    )


def test_deprecated_method_removed_from_codebase():
    """验证代码不再用已弃用的 get_sentence_embedding_dimension"""
    # 这是一个"未来友好"测试：每次 ST 升级都应该跑这个
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "get_sentence_embedding_dimension",
         "app/", "scripts/", "tests/"],
        capture_output=True, text=True
    )
    # 只允许注释/文档中提到，不允许代码调用
    matches = [line for line in result.stdout.split("\n")
               if line and "deprecated" not in line.lower() and "# " not in line]
    assert len(matches) == 0, (
        f"Deprecated method still in use: {matches}\n"
        f"Use get_embedding_dimension() instead."
    )


def test_text2vec_loads_and_encodes():
    """验证 shibing624/text2vec-base-chinese 加载和推理"""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("shibing624/text2vec-base-chinese", device="cuda")
    emb = model.encode(["微纳米气泡的zeta电位"], normalize_embeddings=True)
    assert emb.shape == (1, 768), f"Expected (1, 768), got {emb.shape}"
    norm = float(np.sqrt((emb ** 2).sum()))
    assert 0.99 < norm < 1.01, f"Expected normalized embedding, got norm={norm}"


def test_qwen3_native_loads_and_encodes():
    """验证 Qwen3-Embedding-0.6B 用 ST 原生加载（无需 wrapper）"""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        "Qwen/Qwen3-Embedding-0.6B",
        device="cuda",
        trust_remote_code=True,
    )
    emb = model.encode(["微纳米气泡的zeta电位"], normalize_embeddings=True)
    assert emb.shape == (1, 1024), f"Expected (1, 1024), got {emb.shape}"
    norm = float(np.sqrt((emb ** 2).sum()))
    assert 0.99 < norm < 1.01, f"Expected normalized embedding, got norm={norm}"


# 2026-07-12: test_qwen3_native_vs_wrapper_output_match 已删除 — wrapper (qwen_embedder_legacy.py) 已清理
# 删后只剩 ST 原生路径, 无对比对象


def test_embedding_service_qwen3_dim():
    """Phase 2: 验证 embedding_service 走 ST 原生 Qwen3 (默认模型)"""
    import asyncio
    from app.services.embedding_service import generate_embedding
    v = asyncio.run(generate_embedding("微纳米气泡的zeta电位"))
    assert v is not None
    # 1024 = Qwen3 dim
    assert len(v) == 1024, f"Expected 1024 (Qwen3), got {len(v)}"


def test_embedding_service_text2vec_dim():
    """Phase 2: 验证 embedding_service 切换 EMBEDDING_MODEL_NAME=text2vec 后 dim 改变"""
    os.environ["EMBEDDING_MODEL_NAME"] = "shibing624/text2vec-base-chinese"
    # Force model reload
    import importlib
    import app.services.embedding_service as es
    es._model = None  # 重置单例

    import asyncio
    from app.services.embedding_service import generate_embedding
    v = asyncio.run(generate_embedding("微纳米气泡的zeta电位"))
    assert v is not None
    # 768 = text2vec dim
    assert len(v) == 768, f"Expected 768 (text2vec), got {len(v)}"

    # Reset
    os.environ["EMBEDDING_MODEL_NAME"] = "Qwen/Qwen3-Embedding-0.6B"
    es._model = None


def test_embedding_service_batch():
    """Phase 2: 验证 generate_embeddings 批量接口"""
    import asyncio
    from app.services.embedding_service import generate_embeddings
    texts = ["text1", "text2", "text3"]
    vecs = asyncio.run(generate_embeddings(texts))
    assert vecs is not None
    assert len(vecs) == 3
    assert len(vecs[0]) == 1024  # Qwen3 dim


def test_embedding_service_for_query_param():
    """Phase 2: for_query 参数保留但当前不传 (所有调用都用 document 模式)"""
    import asyncio
    from app.services.embedding_service import generate_embedding
    # for_query=True 也能调通（虽然项目里没人用）
    v_doc = asyncio.run(generate_embedding("微纳米气泡", for_query=False))
    v_query = asyncio.run(generate_embedding("微纳米气泡", for_query=True))
    # 至少都能调通 + 维度正确
    assert v_doc is not None and len(v_doc) == 1024
    assert v_query is not None and len(v_query) == 1024


# 2026-07-12: test_legacy_wrapper_still_importable 已删除 — qwen_embedder_legacy.py 已清理
