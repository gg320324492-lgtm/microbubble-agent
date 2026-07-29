"""Shared embedding input policy.

Keep preprocessing independent from the model runtime so it can be tested in
lightweight CI jobs without importing sentence-transformers.
"""

import os

MAX_EMBED_INPUT_CHARS = 6000


def truncate_for_embedding(text: str) -> str:
    """Return the canonical embedding input, capped at 6000 characters."""
    if not text:
        return ""
    return text[:MAX_EMBED_INPUT_CHARS]


def model_has_query_prompt(model_name: str | None = None) -> bool:
    """Whether the configured embedding model expects an instruction prefix."""
    name = model_name or os.getenv(
        "EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B"
    )
    lowered = name.lower()
    return lowered.startswith("qwen/") or lowered.startswith("bge") or lowered.startswith("bge/")


MODEL_HAS_QUERY_PROMPT = model_has_query_prompt()
# Historical spelling retained for callers/tests that use the policy name.
EMBEDDING_HAS_QUERY_PROMPT = MODEL_HAS_QUERY_PROMPT
