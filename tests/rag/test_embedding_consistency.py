from app.services.embedding_consistency_check import KNOWN_CALLERS, run
from app.services.embedding_query_policy import should_use_query_prefix


def test_query_prefix_allowlist():
    assert should_use_query_prefix("kb_qa") is True
    assert should_use_query_prefix("hybrid_retriever") is True
    assert should_use_query_prefix("semantic_search") is True
    assert should_use_query_prefix("auto_research") is False


def test_policy_report_covers_known_callers():
    report = run()
    assert report["ok"] is True
    assert report["callers"] == list(KNOWN_CALLERS)
    assert set(report["query_prefix_callers"]) == {
        "kb_qa", "hybrid_retriever", "semantic_search"
    }
