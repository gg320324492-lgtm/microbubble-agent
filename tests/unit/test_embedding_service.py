"""测试 app.services.embedding_prompts query/document 不对称 prefix 行为

覆盖场景 (2026-07-20 实装 query prompt):
  1. 默认参数（for_query=False, has_query_prompt=False）→ prompt=None
  2. for_query=True + has_query_prompt=True → prompt=QUERY_PROMPT_ZH

测试用 build_embedding_prompt 纯函数（无需加载 SentenceTransformer 模型，避免重型依赖），
所有 case 在毫秒级完成。
"""
import pytest

from app.services.embedding_prompts import (
    QUERY_PROMPT_ZH,
    build_embedding_prompt,
)


class TestBuildPrompt:
    """for_query + has_query_prompt 双开关决定是否加 query prefix"""

    def test_default_prompt_is_none(self):
        """默认参数（document 模式 + 不支持 prefix）→ prompt=None"""
        assert build_embedding_prompt(False, False) is None

    def test_query_mode_with_capable_model_returns_prompt(self):
        """for_query=True + has_query_prompt=True → 返回中文 query prefix"""
        result = build_embedding_prompt(True, True)
        assert result == QUERY_PROMPT_ZH
        assert "为这个句子生成表示以用于检索相关文章" in result
        # prefix 必须以冒号结尾（Qwen3/BGE 官方推荐格式）
        assert result.endswith(":")
