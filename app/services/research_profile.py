"""Research Profile Extractor — Phase 14.2 §2.

Deterministically infers a research user profile from memory hits + project
history. Pure rule-based — never calls an LLM.

Public API:
- ResearchProfile dataclass
- extract_profile_from_memory(memory_hits) -> ResearchProfile
- extract_profile_from_history(history_items) -> ResearchProfile
- merge_profiles(...) -> ResearchProfile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------
# Each rule: (keywords, domain_label, expertise_hint)
DOMAIN_RULES: tuple = (
    (
        ("微纳米气泡", "纳米气泡", "microbubble", "nanobubble",
         "臭氧气泡", "臭氧微气泡", "ozone microbubble"),
        "pollution_control_water_treatment",
        "researcher",
    ),
    (
        ("臭氧", "ozone", "高级氧化", "aop", "aops",
         "羟基自由基", "·oh", "oh radical"),
        "advanced_oxidation_water_treatment",
        "researcher",
    ),
    (
        ("污染控制", "污染", "水处理", "wastewater",
         "water treatment", "水质", "remediation"),
        "pollution_control_water_treatment",
        "practitioner",
    ),
    (
        ("cfd", "computational fluid dynamics", "流体力学",
         "数值模拟", "simulation"),
        "computational_fluid_dynamics",
        "researcher",
    ),
    (
        ("gaussian", "密度泛函", "dft", "b3lyp",
         "分子动力学", "gromacs", "molecular dynamics"),
        "computational_chemistry",
        "researcher",
    ),
    (
        ("膜分离", "membrane", "陶瓷膜", "ceramic membrane", "超滤"),
        "membrane_separation",
        "researcher",
    ),
    (
        ("surfactant", "表面活性剂", "zeta potential", "zeta电位"),
        "interfacial_phenomena",
        "researcher",
    ),
)


EXPERTISE_KEYWORDS: tuple = (
    ("机理", "kLa", "传质系数", "传质", "自由基", "氧化",
     "reaction rate", "kinetics", "·OH", "hydroxyl"),
    "researcher",
)


def _text_blob(memory_hits) -> List[str]:
    """Phase 14.2 §2: pull text from each memory hit safely."""
    blobs: List[str] = []
    for hit in memory_hits or []:
        if isinstance(hit, str):
            blobs.append(hit)
            continue
        if isinstance(hit, dict):
            for key in ("text", "content", "summary", "title", "snippet",
                        "raw_content", "preview"):
                if hit.get(key):
                    blobs.append(str(hit[key]))
                    break
            continue
        for attr in ("text", "content", "summary", "preview", "raw_content"):
            v = getattr(hit, attr, None)
            if v:
                blobs.append(str(v))
                break
    return blobs


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------
@dataclass
class ResearchProfile:
    """Phase 14.2 §2: inferred user research profile."""

    domain: str = ""
    keywords: List[str] = field(default_factory=list)
    expertise_level: str = "general"   # general | practitioner | researcher
    active_topics: List[str] = field(default_factory=list)
    preferred_output_style: str = "structured"

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "keywords": list(self.keywords),
            "expertise_level": self.expertise_level,
            "active_topics": list(self.active_topics),
            "preferred_output_style": self.preferred_output_style,
        }


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------
def _match_rule(text_lower: str) -> Optional[tuple]:
    """Return (domain, expertise) tuple if any keyword from a rule matches."""
    for keywords, domain, expertise in DOMAIN_RULES:
        for kw in keywords:
            if kw.lower() in text_lower:
                return (domain, expertise)
    return None


def _expertise_escalate(current: str, candidate: str) -> str:
    ranks = {"general": 0, "practitioner": 1, "researcher": 2}
    if ranks.get(candidate, 0) > ranks.get(current, 0):
        return candidate
    return current


def extract_profile_from_memory(memory_hits) -> ResearchProfile:
    """Phase 14.2 §2: extract profile from memory retrieval.

    Iterates each memory blob and applies rule matching. No LLM.
    """
    blobs = _text_blob(memory_hits)
    profile = ResearchProfile()
    for blob in blobs:
        text_lower = blob.lower()
        match = _match_rule(text_lower)
        if match is None:
            continue
        domain, expertise = match
        if not profile.domain:
            profile.domain = domain
        profile.expertise_level = _expertise_escalate(
            profile.expertise_level, expertise
        )
        # Capture strongest keyword
        for keywords, d, _e in DOMAIN_RULES:
            if d != domain:
                continue
            for kw in keywords:
                if kw.lower() in text_lower and kw not in profile.keywords:
                    profile.keywords.append(kw)
                    if len(profile.keywords) >= 8:
                        break
            if len(profile.keywords) >= 8:
                break
    # Always populate from keyword scan even if no rule hits, so we record
    # any matching token in active topics.
    for blob in blobs:
        for kw in (
            "微纳米气泡", "臭氧", "kLa", "·OH",
            "membrane", "membrane filtration", "ceramic membrane",
            "CFD", "DFT",
        ):
            if kw.lower() in blob.lower() and kw not in profile.active_topics:
                profile.active_topics.append(kw)
    return profile


def extract_profile_from_history(history_items) -> ResearchProfile:
    """Phase 14.2 §2: extract profile from prior research/projects list."""
    profile = ResearchProfile()
    if not history_items:
        return profile
    items = list(history_items)
    for item in items:
        text = ""
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = " ".join(
                str(v) for v in (
                    item.get("title"),
                    item.get("description"),
                    item.get("summary"),
                    item.get("topic"),
                ) if v
            )
        else:
            for attr in ("title", "description", "summary", "topic", "name"):
                v = getattr(item, attr, None)
                if v:
                    text += " " + str(v)
        text_lower = text.lower()
        match = _match_rule(text_lower)
        if match is None:
            continue
        domain, expertise = match
        if not profile.domain:
            profile.domain = domain
        profile.expertise_level = _expertise_escalate(
            profile.expertise_level, expertise
        )
        if text and text not in profile.active_topics:
            profile.active_topics.append(text[:80])
        if len(profile.active_topics) >= 6:
            break
    return profile


def merge_profiles(*profiles: ResearchProfile) -> ResearchProfile:
    """Phase 14.2 §2: merge multiple profiles, taking strongest signals."""
    out = ResearchProfile()
    for p in profiles:
        if p is None:
            continue
        if p.domain and not out.domain:
            out.domain = p.domain
        out.expertise_level = _expertise_escalate(
            out.expertise_level, p.expertise_level
        )
        for kw in p.keywords:
            if kw not in out.keywords:
                out.keywords.append(kw)
        for t in p.active_topics:
            if t not in out.active_topics:
                out.active_topics.append(t)
    return out


__all__ = [
    "ResearchProfile",
    "extract_profile_from_memory",
    "extract_profile_from_history",
    "merge_profiles",
]
