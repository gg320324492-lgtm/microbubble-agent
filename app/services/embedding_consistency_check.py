"""Development-time checks for embedding caller policy coverage."""

from .embedding_query_policy import should_use_query_prefix

# Stable inventory used by CI to prevent silent policy expansion.
KNOWN_CALLERS = (
    "kb_qa",
    "hybrid_retriever",
    "semantic_search",
    "auto_research",
    "entity_service",
    "meeting_service",
    "memory_service",
    "knowledge_service",
)


def run(caller_paths=KNOWN_CALLERS) -> dict[str, object]:
    """Return a deterministic policy report for the supplied caller paths."""
    callers = list(caller_paths)
    return {
        "ok": all(isinstance(path, str) and path for path in callers),
        "callers": callers,
        "query_prefix_callers": [
            path for path in callers if should_use_query_prefix(path)
        ],
    }
