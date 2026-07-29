import pytest

from app.services.embedding_truncation_policy import (
    MAX_EMBED_INPUT_CHARS,
    MODEL_HAS_QUERY_PROMPT,
    model_has_query_prompt,
    truncate_for_embedding,
)

@pytest.mark.parametrize("length, expected", [(0, 0), (5999, 5999), (6000, 6000), (6001, 6000), (10000, 6000)])
def test_truncation_boundaries(length, expected):
    assert len(truncate_for_embedding("x" * length)) == expected


def test_constant_is_6000():
    assert MAX_EMBED_INPUT_CHARS == 6000


def test_model_prompt_detection():
    assert MODEL_HAS_QUERY_PROMPT is True
    assert model_has_query_prompt("Qwen/Qwen3-Embedding-0.6B") is True
    assert model_has_query_prompt("text2vec-base-chinese") is False
