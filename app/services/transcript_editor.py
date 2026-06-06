"""Helpers for manually correcting transcript speakers."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TranscriptSpeakerUpdate:
    transcript: list[dict[str, Any]]
    transcript_polished: list[dict[str, Any]]
    speaker_mapping: dict[str, str]


def _copy_entries(entries: Optional[Any]) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    return [dict(item) for item in entries if isinstance(item, dict)]


def update_transcript_speaker(
    transcript: Optional[Any],
    transcript_polished: Optional[Any],
    speaker_mapping: Optional[Any],
    entry_index: int,
    speaker: str,
) -> TranscriptSpeakerUpdate:
    """Update one transcript row's speaker in raw and polished transcript lists."""
    if entry_index < 0:
        raise IndexError("entry_index out of range")

    raw_entries = _copy_entries(transcript)
    polished_entries = _copy_entries(transcript_polished)
    mapping = dict(speaker_mapping) if isinstance(speaker_mapping, dict) else {}

    has_raw = entry_index < len(raw_entries)
    has_polished = entry_index < len(polished_entries)
    if not has_raw and not has_polished:
        raise IndexError("entry_index out of range")

    speaker = speaker.strip()
    if not speaker:
        raise ValueError("speaker is required")

    speaker_label = None
    if has_raw:
        speaker_label = raw_entries[entry_index].get("speaker_label")
        raw_entries[entry_index]["speaker"] = speaker
    if has_polished:
        polished_entries[entry_index]["speaker"] = speaker

    if speaker_label:
        mapping[str(speaker_label)] = speaker

    return TranscriptSpeakerUpdate(
        transcript=raw_entries,
        transcript_polished=polished_entries,
        speaker_mapping=mapping,
    )
