"""Deterministic five-defense gate used by the KB queue QA harness."""

from __future__ import annotations

import inspect
import math
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from .blacklists import DEFAULT_BLACKLIST

REFUSAL_PATTERNS = (
    "我不知道",
    "不知道",
    "无法回答",
    "无法提供",
    "不能回答",
    "incomplete",
    "i don't know",
    "cannot answer",
    "unable to answer",
    "not enough information",
)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def defense_dedup(
    text: str,
    embedding: Sequence[float] | None = None,
    threshold: float = 0.95,
    existing_embeddings: Iterable[Sequence[float]] | None = None,
) -> tuple[bool, str | None]:
    """Reject an item whose embedding is at least ``threshold`` like an existing row."""
    if embedding is None or existing_embeddings is None:
        return True, None
    for existing in existing_embeddings:
        similarity = _cosine(embedding, existing)
        if similarity >= threshold:
            return False, f"重复内容: cosine={similarity:.4f} >= {threshold:.2f}"
    return True, None


def defense_length(text: str, min_len: int = 50, max_len: int = 4000) -> tuple[bool, str | None]:
    length = len(text)
    if length < min_len or length > max_len:
        return False, f"长度{length}超限 ({min_len}-{max_len})"
    return True, None


def _judge_score(result: Any) -> float:
    if isinstance(result, Mapping):
        for key in ("score", "confidence", "answer_score"):
            if key in result:
                result = result[key]
                break
    if isinstance(result, bool):
        return 1.0 if result else 0.0
    try:
        return float(result)
    except (TypeError, ValueError):
        return 0.0


def defense_llm_reject(
    text: str,
    llm_judge_fn: Callable[[str], Any] | None,
    refusal_patterns: Iterable[str] = REFUSAL_PATTERNS,
    threshold: float = 0.5,
) -> tuple[bool, str | None]:
    """Reject obvious refusal text or a judge score below ``threshold``.

    ``llm_judge_fn`` is deliberately injected: this module never constructs an
    Anthropic client and therefore remains safe to run as an offline test gate.
    It may return a numeric score, a boolean, or ``{"score": ...}``.
    """
    lowered = text.casefold()
    for pattern in refusal_patterns:
        if pattern.casefold() in lowered:
            return False, f"LLM拒答标记: {pattern}"
    if llm_judge_fn is None:
        return True, None
    result = llm_judge_fn(text)
    if inspect.isawaitable(result):
        raise TypeError("llm_judge_fn must be synchronous for this QA gate")
    score = _judge_score(result)
    if score < threshold:
        return False, f"LLM judge score={score:.3f} < {threshold:.2f}"
    return True, None


def defense_sensitive_words(
    text: str,
    blacklist: Iterable[str] | None = None,
) -> tuple[bool, str | None]:
    words = (*DEFAULT_BLACKLIST, *(blacklist or ()))
    lowered = text.casefold()
    for word in words:
        if word.casefold() in lowered:
            return False, f"敏感词/内部占位符: {word}"
    return True, None


def defense_human_review(
    text: str,
    sample_rate: float = 0.05,
    rng: random.Random | None = None,
    review_sink: Callable[[str], Any] | None = None,
) -> tuple[bool, str | None]:
    """Sample 5% of accepted entries into an admin-review sink.

    Sampling does not reject an entry.  A sampled entry is marked for review;
    callers can persist the returned reason alongside the KB row.
    """
    if not 0 <= sample_rate <= 1:
        raise ValueError("sample_rate must be between 0 and 1")
    sampled = (rng or random).random() < sample_rate
    if sampled:
        if review_sink is not None:
            review_sink(text)
        return True, "人工抽检: 已加入 admin 待审核列表"
    return True, None


def apply_five_defenses(
    text: str,
    embedding: Sequence[float] | None = None,
    llm_judge_fn: Callable[[str], Any] | None = None,
    members: Iterable[str] | None = None,
    *,
    existing_embeddings: Iterable[Sequence[float]] | None = None,
    sample_rate: float = 0.05,
    rng: random.Random | None = None,
    review_sink: Callable[[str], Any] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Run dedup, length, refusal, sensitive-word, and human-review gates."""
    checks = (
        ("dedup", lambda: defense_dedup(text, embedding, existing_embeddings=existing_embeddings)),
        ("length", lambda: defense_length(text)),
        ("llm_reject", lambda: defense_llm_reject(text, llm_judge_fn)),
        ("sensitive", lambda: defense_sensitive_words(text, members)),
        ("human_review", lambda: defense_human_review(text, sample_rate, rng, review_sink)),
    )
    review_reason: str | None = None
    for name, check in checks:
        passed, reason = check()
        if not passed:
            return False, name, reason
        if name == "human_review" and reason:
            review_reason = reason
    return True, "human_review" if review_reason else None, review_reason


__all__ = [
    "REFUSAL_PATTERNS",
    "defense_dedup",
    "defense_length",
    "defense_llm_reject",
    "defense_sensitive_words",
    "defense_human_review",
    "apply_five_defenses",
]
