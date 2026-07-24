"""W68 D6 / W69 verdict consensus v2 — confidence-weighted majority.

Sits alongside ``phase2_dry_runner._majority_verdict`` and adds a
**confidence score** derived from the round-level verdict entropy.

Design goals:

*   Confidence is monotonically decreasing in the round entropy: a
    unanimous ``pass`` (entropy 0) yields ``confidence = 1.0``; a
    fully uniform distribution yields ``confidence ≈ 0``.
*   ``confidence_verdict`` returns ``"answered"`` when the model is
    sufficiently confident (``confidence >= CONFIDENCE_THRESHOLD``)
    and ``"declined"`` otherwise.  The seven-dimension scorer drops
    ``declined`` rounds from the accuracy / recall numerators but
    keeps them in the totals for transparency.
*   ``confidence_for_question`` returns the raw ``[0, 1]`` confidence
    so callers can apply their own threshold (e.g. the seven-dim
    scorer reports ``confidence_high`` vs ``confidence_low`` against
    the configured threshold).

Lives in ``tests/qa-bench/scoring/`` only — no production change.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence

from seven_d_scoring import VerdictRecord  # noqa: E402 -- sibling-module import

# Default confidence threshold: above this we treat the verdict as
# answered, below it as declined.  Phase 2 baseline 0.5; Phase 3 may
# raise to 0.66 for stricter acceptance.
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.5

# When the model returned *no* rounds, we treat the verdict as
# declined with zero confidence.
EMPTY_CONFIDENCE: float = 0.0
PERFECT_CONFIDENCE: float = 1.0


@dataclass(slots=True)
class ConsensusV2:
    """Result of the v2 consensus decision for a single question."""

    majority_verdict: str
    confidence: float
    decision: str  # "answered" or "declined"
    entropy: float
    round_count: int
    verdict_counts: dict[str, int]


def _entropy(verdicts: Sequence[str]) -> float:
    if not verdicts:
        return 0.0
    counts = Counter(verdicts)
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log(p)
    return entropy


def _max_entropy_for(n: int) -> float:
    if n <= 1:
        return 0.0
    return math.log(n)


def confidence_for_question(
    rounds: Iterable[VerdictRecord],
) -> float:
    """Confidence in ``[0, 1]`` derived from the round-verdict entropy.

    ``confidence = 1 - (entropy / max_entropy)`` clamped to ``[0, 1]``.
    Empty input returns 0.  A unanimous verdict returns 1.
    """

    verdicts = [r.verdict for r in rounds]
    if not verdicts:
        return EMPTY_CONFIDENCE
    entropy = _entropy(verdicts)
    max_entropy = _max_entropy_for(len(verdicts))
    if max_entropy <= 0:
        return PERFECT_CONFIDENCE
    raw = 1.0 - (entropy / max_entropy)
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def majority_verdict(rounds: Iterable[VerdictRecord]) -> str:
    """Majority verdict across rounds (ties broken alphabetically)."""

    verdicts = [r.verdict for r in rounds]
    if not verdicts:
        return "unknown"
    counts = Counter(verdicts)
    top_count = counts.most_common(1)[0][1]
    tied = sorted([v for v, c in counts.items() if c == top_count])
    return tied[0]


def confidence_verdict(
    rounds: Iterable[VerdictRecord],
    *,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> ConsensusV2:
    """Combine majority verdict + confidence into a v2 decision payload.

    ``decision`` is ``"answered"`` when ``confidence >= threshold`` and
    ``"declined"`` otherwise.  Declined rounds are not counted as hits
    in accuracy / recall but are still kept in ``verdict_counts`` and
    latency aggregates for traceability.
    """

    materialised = list(rounds)
    verdicts = [r.verdict for r in materialised]
    counts = Counter(verdicts)
    entropy = _entropy(verdicts)
    confidence = confidence_for_question(materialised)
    decision = "answered" if confidence >= threshold else "declined"
    return ConsensusV2(
        majority_verdict=majority_verdict(materialised),
        confidence=round(confidence, 4),
        decision=decision,
        entropy=round(entropy, 4),
        round_count=len(materialised),
        verdict_counts=dict(counts),
    )


__all__ = [
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "ConsensusV2",
    "confidence_for_question",
    "confidence_verdict",
    "majority_verdict",
]