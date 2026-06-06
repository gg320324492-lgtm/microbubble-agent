"""Speaker assignment helpers for post-meeting voiceprint clustering.

This module keeps the risky "cluster -> person name" decisions pure and
testable. The voice model can be ambiguous; this layer prevents ambiguous
clusters from being confidently mislabeled as the same known member.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


PHONETIC_CORRECTIONS = {
    "杜同和": "杜同贺",
    "杜同河": "杜同贺",
    "吴梦全": "吴孟铨",
    "吴孟全": "吴孟铨",
    "吴孟栓": "吴孟铨",
    "王天之": "王天志",
    "王田志": "王天志",
    "赵航嘉": "赵航佳",
    "赵航家": "赵航佳",
}


@dataclass(frozen=True)
class SpeakerMatch:
    name: Optional[str]
    member_id: Optional[int]
    confidence: float


@dataclass
class SpeakerAssignmentResult:
    cluster_to_name: dict[int, str]
    ambiguous_clusters: dict[int, dict] = field(default_factory=dict)
    known_member_ids: set[int] = field(default_factory=set)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity, protecting against zero vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def should_force_split(
    embeddings: list[Optional[np.ndarray]],
    std_threshold: float = 0.15,
    min_similarity_threshold: float = 0.55,
) -> bool:
    """Detect a single greedy cluster that likely contains more than one speaker."""
    valid = [e for e in embeddings if e is not None and not np.all(e == 0)]
    if len(valid) < 3:
        return False

    sims = [
        cosine_similarity(valid[i], valid[j])
        for i in range(len(valid))
        for j in range(i + 1, len(valid))
    ]
    if len(sims) < 2:
        return False

    return float(np.std(sims, ddof=1)) > std_threshold and min(sims) < min_similarity_threshold


def _speaker_label(index: int) -> str:
    if index < 26:
        return f"发言人{chr(65 + index)}"
    return f"发言人{index - 25}"


def _next_unknown_label(used_names: set[str], start_index: int = 0) -> tuple[str, int]:
    index = start_index
    label = _speaker_label(index)
    while label in used_names:
        index += 1
        label = _speaker_label(index)
    return label, index + 1


def _is_unknown_label(name: Optional[str]) -> bool:
    return not name or name.startswith("发言人")


def finalize_cluster_speakers(
    cluster_ids: list[int],
    cluster_votes: dict[int, list[str]],
    representative_matches: dict[int, SpeakerMatch],
    min_confidence: float = 0.35,
) -> SpeakerAssignmentResult:
    """Merge per-segment votes and representative voiceprint matches.

    If several clusters map to the same known member, only the highest
    confidence cluster keeps that member name. The rest are explicitly marked
    as unknown speakers so the UI/analysis does not falsely report one person.
    """
    cluster_to_name: dict[int, str] = {}
    cluster_scores: dict[int, float] = {}
    cluster_member_ids: dict[int, int] = {}
    ambiguous: dict[int, dict] = {}
    used_names: set[str] = set()
    unknown_index = 0

    for cid in sorted(set(c for c in cluster_ids if c >= 0)):
        votes = [n for n in cluster_votes.get(cid, []) if not _is_unknown_label(n)]
        if votes:
            name = max(set(votes), key=votes.count)
            cluster_to_name[cid] = name
            cluster_scores[cid] = votes.count(name) / max(len(votes), 1)
            used_names.add(name)
        else:
            label, unknown_index = _next_unknown_label(used_names, unknown_index)
            cluster_to_name[cid] = label
            cluster_scores[cid] = 0.0
            used_names.add(label)

    for cid, match in representative_matches.items():
        if cid not in cluster_to_name or not match.name or match.confidence < min_confidence:
            continue
        cluster_to_name[cid] = match.name
        cluster_scores[cid] = match.confidence
        if match.member_id is not None:
            cluster_member_ids[cid] = match.member_id

    name_to_clusters: dict[str, list[int]] = {}
    for cid, name in cluster_to_name.items():
        if not _is_unknown_label(name):
            name_to_clusters.setdefault(name, []).append(cid)

    used_names = set(cluster_to_name.values())
    for name, cids in name_to_clusters.items():
        if len(cids) < 2:
            continue

        keep = max(cids, key=lambda cid: (cluster_scores.get(cid, 0.0), -cid))
        for cid in cids:
            if cid == keep:
                continue
            label, unknown_index = _next_unknown_label(used_names, unknown_index)
            used_names.add(label)
            cluster_to_name[cid] = label
            cluster_member_ids.pop(cid, None)
            ambiguous[cid] = {
                "reason": "duplicate_known_name",
                "duplicate_of": name,
                "kept_cluster": keep,
                "confidence": cluster_scores.get(cid, 0.0),
            }

    return SpeakerAssignmentResult(
        cluster_to_name=cluster_to_name,
        ambiguous_clusters=ambiguous,
        known_member_ids=set(cluster_member_ids.values()),
    )


def _edit_distance(a: str, b: str) -> int:
    la, lb = len(a), len(b)
    dp = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, lb + 1):
            temp = dp[j]
            dp[j] = min(
                prev + (0 if a[i - 1] == b[j - 1] else 1),
                dp[j] + 1,
                dp[j - 1] + 1,
            )
            prev = temp
    return dp[lb]


def correct_speaker_name(name: str, all_members: dict[str, int]) -> str:
    """Correct ASR/voiceprint name variants to an active member name."""
    if not name or name.startswith("发言人"):
        return name
    if name in all_members:
        return name
    if name in PHONETIC_CORRECTIONS:
        corrected = PHONETIC_CORRECTIONS[name]
        return corrected if corrected in all_members else name

    best_match = None
    best_dist = 99
    for member_name in all_members:
        dist = _edit_distance(name, member_name)
        if dist < best_dist:
            best_dist = dist
            best_match = member_name

    if best_match and best_dist <= 1 and abs(len(name) - len(best_match)) <= 1:
        return best_match
    return name
