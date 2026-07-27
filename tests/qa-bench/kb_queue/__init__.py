"""KB queue entry point for the five-defense QA gate."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .five_defenses import apply_five_defenses


def save_to_kb(
    text: str,
    embedding: Sequence[float] | None = None,
    llm_judge_fn: Callable[[str], Any] | None = None,
    *,
    members: Sequence[str] | None = None,
    existing_embeddings: Sequence[Sequence[float]] | None = None,
    sample_rate: float = 0.05,
    rng: Any = None,
    review_sink: Callable[[str], Any] | None = None,
    saver: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Run all five defenses, then invoke the injected KB saver.

    The default saver is intentionally side-effect free; production wiring can
    provide the persistence callback without importing production modules here.
    """
    passed, defense, reason = apply_five_defenses(
        text,
        embedding,
        llm_judge_fn,
        members,
        existing_embeddings=existing_embeddings,
        sample_rate=sample_rate,
        rng=rng,
        review_sink=review_sink,
    )
    if not passed:
        return {"saved": False, "defense": defense, "reason": reason}
    result = saver(text) if saver is not None else {"text": text}
    return {
        "saved": True,
        "defense": defense,
        "reason": reason,
        "item": result,
    }


__all__ = ["save_to_kb"]
