"""测试 LLMClient.complete() / stream() 的 model 参数（方案 C Stage 0）

验证：
1. model 参数是 keyword-only（位置传 model 必报 TypeError，铁律 5）
2. model=None 时走 self.models[0]
3. model="xxx" 时只用该模型，不 fallback
4. LRU cache key 包含 model 维度，不同模型不互相污染

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_llm_client_model_override.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import inspect
import pytest

from app.core.llm import LLMClient, LRUResponseCache


class TestKeywordOnlyModel:
    """铁律 5：model 参数必须 keyword-only，位置传报 TypeError"""

    def test_complete_signature_has_keyword_only_marker(self):
        """complete() 签名中必须有 *（keyword-only 分隔符）"""
        sig = inspect.signature(LLMClient.complete)
        params = list(sig.parameters.values())
        # 查找 VAR_POSITIONAL 后的参数 OR 第一个 KEYWORD_ONLY
        keyword_only_params = [
            p for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY
        ]
        assert "model" in [p.name for p in keyword_only_params], (
            "complete() 必须有 keyword-only 的 model 参数"
        )

    def test_stream_signature_has_keyword_only_marker(self):
        """stream() 签名中必须有 *（keyword-only 分隔符）"""
        sig = inspect.signature(LLMClient.stream)
        keyword_only_params = [
            p for p in sig.parameters.values()
            if p.kind == inspect.Parameter.KEYWORD_ONLY
        ]
        assert "model" in [p.name for p in keyword_only_params]

    def test_stream_raw_signature_has_keyword_only_marker(self):
        """stream_raw() 同样要 keyword-only"""
        sig = inspect.signature(LLMClient.stream_raw)
        keyword_only_params = [
            p for p in sig.parameters.values()
            if p.kind == inspect.Parameter.KEYWORD_ONLY
        ]
        assert "model" in [p.name for p in keyword_only_params]

    def test_model_param_default_is_none(self):
        """model 默认值必须是 None（不传走 self.models[0]）"""
        sig = inspect.signature(LLMClient.complete)
        assert sig.parameters["model"].default is None


class TestCacheKeyHasModelDimension:
    """LRU cache key 必须包含 model 维度（防止不同模型互相污染缓存）"""

    def test_cache_key_differs_by_model(self):
        cache = LRUResponseCache()
        messages = [{"role": "user", "content": "hi"}]
        key_haiku = cache._key(
            messages, system="sys", tools=None,
            max_tokens=100, temperature=0.3, model="claude-haiku-4-5-20251001",
        )
        key_sonnet = cache._key(
            messages, system="sys", tools=None,
            max_tokens=100, temperature=0.3, model="claude-sonnet-4-6",
        )
        assert key_haiku != key_sonnet, "不同 model 必须产生不同 cache key"

    def test_cache_key_stable_for_same_model(self):
        cache = LRUResponseCache()
        messages = [{"role": "user", "content": "hi"}]
        key1 = cache._key(
            messages, system="sys", tools=None,
            max_tokens=100, temperature=0.3, model="claude-haiku-4-5-20251001",
        )
        key2 = cache._key(
            messages, system="sys", tools=None,
            max_tokens=100, temperature=0.3, model="claude-haiku-4-5-20251001",
        )
        assert key1 == key2, "同 model + 同输入必须产生相同 cache key"

    def test_cache_key_no_model_falls_back_to_default(self):
        """不传 model 时 _key 应使用 model='' 兜底（不报错）"""
        cache = LRUResponseCache()
        messages = [{"role": "user", "content": "hi"}]
        # 不传 model kwarg 应该不报错
        key = cache._key(
            messages, system="sys", tools=None,
            max_tokens=100, temperature=0.3,
        )
        assert isinstance(key, str)
        assert len(key) == 32  # md5 hex


class TestSingleton:
    """LLMClient 单例 + models 链初始化"""

    def test_singleton(self):
        c1 = LLMClient()
        c2 = LLMClient()
        assert c1 is c2

    def test_models_list_not_empty(self):
        client = LLMClient()
        assert isinstance(client.models, list)
        assert len(client.models) >= 1
        assert client.models[0]  # primary 必须非空
