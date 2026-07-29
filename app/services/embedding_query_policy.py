"""Allow-list for embedding query-prefix callers."""

QUERY_PREFIX_CALLERS = frozenset({"kb_qa", "hybrid_retriever", "semantic_search"})


def should_use_query_prefix(caller_path: str | None) -> bool:
    """Return true only for retrieval paths explicitly approved for query mode."""
    if not caller_path:
        return False
    normalized = caller_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    normalized = normalized.removesuffix(".py")
    return normalized in QUERY_PREFIX_CALLERS
