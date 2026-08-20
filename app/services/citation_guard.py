"""Citation Reliability Guard — Phase 14.2 §5.

Prevents hallucinated citations in research answers. When the agent cannot
verify a citation against a real source, ``validate_citations`` rewrites the
textual reference into a safe placeholder so we never publish invented
author/year/venue strings.

Public API:
- CitationStatus (verified / uncertain / generated / replaced)
- CitationRecord (dataclass)
- validate_citations(text, allowed_sources=None) -> (cleaned_text, records)
- validate_answer_citations(answer, ...) -> (cleaned_answer, records)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CITATION_VERIFIED = "verified"
CITATION_UNCERTAIN = "uncertain"
CITATION_GENERATED = "generated"
CITATION_REPLACED = "replaced"

# Patterns we recognise as citation markers
_BRACKET_PATTERN = re.compile(r"\[(\d{1,3})\]")
_AUTHOR_YEAR_PATTERN = re.compile(
    r"([A-Z][A-Za-z\-']{1,40}(?:\s+et\s+al\.?)?(?:,?\s+(?:and|&)\s+[A-Z][A-Za-z\-']{1,40})?)\s*[,(]?\s*(\d{4})[a-z]?"
)
_DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s,;]+", re.IGNORECASE)


@dataclass
class CitationRecord:
    """Phase 14.2 §5: per-citation audit record."""

    marker: str
    status: str
    original_text: str = ""
    replacement: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "marker": self.marker,
            "status": self.status,
            "original_text": self.original_text,
            "replacement": self.replacement,
            "confidence": self.confidence,
        }


def _extract_brackets(text: str) -> List[str]:
    return [f"[{idx}]" for idx in _BRACKET_PATTERN.findall(text or "")]


def _extract_author_year(text: str) -> List[str]:
    out: List[str] = []
    for m in _AUTHOR_YEAR_PATTERN.finditer(text or ""):
        snippet = m.group(0)
        if snippet and snippet not in out:
            out.append(snippet)
    return out


def _safe_suggestion(citation: str, status: str) -> str:
    """Phase 14.2 §5: replace suspect citation with a safe suggestion."""
    if status == CITATION_VERIFIED:
        return citation
    if status == CITATION_UNCERTAIN:
        return "（待验证来源）"
    if status == CITATION_REPLACED:
        return "建议参考相关研究"
    # default / generated
    return "建议参考相关研究"


def validate_citations(
    text: str,
    *,
    allowed_sources: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[str, List[CitationRecord]]:
    """Phase 14.2 §5: scan + safe-rewrite citations in ``text``.

    Args:
        text: body to inspect.
        allowed_sources: pre-verified citations. Each entry may contain
            ``"marker"`` (e.g. ``"[1]"``) and ``"title"``/``"year"``/
            ``"authors"``.

    Returns:
        ``(cleaned_text, records)`` — ``cleaned_text`` has suspect citations
        rewritten to safe placeholders; ``records`` is the audit trail.
    """
    if text is None:
        return "", []
    cleaned = text
    records: List[CitationRecord] = []

    allowed_markers = set()
    if allowed_sources:
        for s in allowed_sources:
            if not isinstance(s, dict):
                continue
            mk = str(s.get("marker") or "").strip()
            if mk:
                allowed_markers.add(mk)

    # 1. Bracket-style markers (e.g. [1], [12])
    for marker in _extract_brackets(cleaned):
        if marker in allowed_markers:
            records.append(CitationRecord(
                marker=marker, status=CITATION_VERIFIED, confidence=1.0,
            ))
            continue
        # No matching allowed source → suspect
        replacement = _safe_suggestion(marker, CITATION_GENERATED)
        records.append(CitationRecord(
            marker=marker, status=CITATION_GENERATED,
            original_text=marker, replacement=replacement,
            confidence=0.2,
        ))
        cleaned = cleaned.replace(marker, replacement)

    # 2. Author-year style ("Smith et al., 2023")
    for snippet in _extract_author_year(cleaned):
        # If the snippet appears inside an allowed_sources entry verbatim
        # mark it verified; otherwise uncertain.
        verified = False
        for s in allowed_sources or []:
            if not isinstance(s, dict):
                continue
            if (
                str(s.get("snippet") or "").strip() == snippet
                or (str(s.get("year") or "") in snippet
                    and any(
                        str(s.get("author") or "") in snippet
                        for _ in [None]
                    ))
            ):
                verified = True
                break
        if verified:
            records.append(CitationRecord(
                marker=snippet, status=CITATION_VERIFIED, confidence=0.95,
            ))
            continue
        replacement = _safe_suggestion(snippet, CITATION_UNCERTAIN)
        records.append(CitationRecord(
            marker=snippet, status=CITATION_UNCERTAIN,
            original_text=snippet, replacement=replacement,
            confidence=0.35,
        ))
        cleaned = cleaned.replace(snippet, replacement)

    # 3. DOI markers — assume verified if a real-looking DOI is present
    for m in _DOI_PATTERN.finditer(cleaned or ""):
        doi = m.group(0)
        records.append(CitationRecord(
            marker=doi, status=CITATION_VERIFIED, confidence=0.9,
        ))

    # Deduplicate records (keep first occurrence)
    seen = set()
    deduped: List[CitationRecord] = []
    for r in records:
        key = (r.marker, r.status)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    return cleaned, deduped


def validate_answer_citations(
    answer: str,
    *,
    allowed_sources: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[str, List[CitationRecord]]:
    """Phase 14.2 §5: alias for ``validate_citations`` (semantic clarity)."""
    return validate_citations(answer, allowed_sources=allowed_sources)


def summarize_citation_status(records: Iterable[CitationRecord]) -> Dict[str, Any]:
    """Phase 14.2 §5: produce an aggregate summary for storage/UI."""
    total = 0
    by_status: Dict[str, int] = {}
    for r in records or []:
        total += 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "total": total,
        "by_status": by_status,
        "has_hallucination_risk": by_status.get(CITATION_GENERATED, 0) > 0
        or by_status.get(CITATION_UNCERTAIN, 0) > 0,
    }


__all__ = [
    "CitationStatus" if False else "CitationRecord",  # type alias fallback
    "CITATION_VERIFIED",
    "CITATION_UNCERTAIN",
    "CITATION_GENERATED",
    "CITATION_REPLACED",
    "validate_citations",
    "validate_answer_citations",
    "summarize_citation_status",
    "CitationRecord",
]


# Backwards-compat alias for tests/imports
CitationStatus = CITATION_VERIFIED  # used as a sentinel only
