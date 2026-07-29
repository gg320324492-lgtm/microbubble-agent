"""PR1 pure-logic e2e contract checks.

The embedding runtime test is deliberately guarded because local Windows
workstations may not install sentence-transformers.
"""

import pytest

from app.services.embedding_consistency_check import KNOWN_CALLERS, run
from app.services.embedding_query_policy import should_use_query_prefix
from app.services.embedding_truncation_policy import (
    MODEL_HAS_QUERY_PROMPT,
    model_has_query_prompt,
    truncate_for_embedding,
)


@pytest.mark.parametrize(
    ("length", "expected"),
    [(0, 0), (1, 1), (5999, 5999), (6000, 6000), (6001, 6000),
     (10000, 6000), (60000, 6000)],
)
def test_truncation_contract(length, expected):
    assert len(truncate_for_embedding("x" * length)) == expected


@pytest.mark.parametrize(
    ("caller", "expected"),
    [("kb_qa", True), ("hybrid_retriever", True),
     ("semantic_search", True), ("auto_research", False),
     ("entity_service", False), ("memory_service", False),
     ("knowledge_service", False), ("", False)],
)
def test_query_caller_allowlist(caller, expected):
    assert should_use_query_prefix(caller) is expected


def test_query_model_detection():
    assert MODEL_HAS_QUERY_PROMPT is True
    assert model_has_query_prompt("Qwen/Qwen3-Embedding-0.6B") is True


def test_document_model_detection():
    assert model_has_query_prompt("text2vec-base-chinese") is False


def test_consistency_report_is_green():
    report = run()
    assert report["ok"] is True
    assert report["callers"] == list(KNOWN_CALLERS)


def test_consistency_report_has_three_query_paths():
    report = run()
    assert report["query_prefix_callers"] == [
        "kb_qa", "hybrid_retriever", "semantic_search"
    ]


def test_path_suffix_normalization():
    assert should_use_query_prefix("app/services/kb_qa.py") is True


def test_empty_input_is_stable():
    assert truncate_for_embedding("") == ""


def test_long_unicode_input_is_truncated_by_characters():
    assert len(truncate_for_embedding("气" * 6001)) == 6000
