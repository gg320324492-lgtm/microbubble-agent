"""Research Memory Service — Phase 15.0 §3.

Promotes short-term interactions (Phase 14 follow-ups + intent
classification results) into long-term researcher memory by writing to
``research_user_profiles``. In-memory simulation mode: when no DB
session is available the service operates on a thread-local snapshot
dict so unit tests stay deterministic and ad-hoc callers don't need
to wire up an ``AsyncSession``.

Public API:
- ResearchMemoryCategory (string enum, 7 categories)
- ResearchMemoryService
    save_profile()
    load_profile()
    update_profile()
    save_project_memory()
    retrieve_project_context()
    summarize_research_history()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Memory category constants — Phase 15.0 §3
# ---------------------------------------------------------------------------
CATEGORY_USER_FACT = "user_fact"
CATEGORY_RESEARCH_TOPIC = "research_topic"
CATEGORY_METHOD_PREFERENCE = "method_preference"
CATEGORY_CURRENT_PROBLEM = "current_problem"
CATEGORY_IMPORTANT_DECISION = "important_decision"
CATEGORY_FAILED_ATTEMPT = "failed_attempt"
CATEGORY_RESEARCH_DIRECTION = "research_direction"

DEFAULT_CATEGORIES: tuple = (
    CATEGORY_USER_FACT,
    CATEGORY_RESEARCH_TOPIC,
    CATEGORY_METHOD_PREFERENCE,
    CATEGORY_CURRENT_PROBLEM,
    CATEGORY_IMPORTANT_DECISION,
    CATEGORY_FAILED_ATTEMPT,
    CATEGORY_RESEARCH_DIRECTION,
)


@dataclass
class ResearchMemoryEntry:
    """Phase 15.0 §3: single in-memory research memory entry."""

    category: str
    content: str
    workspace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "content": self.content,
            "workspace_id": self.workspace_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


class ResearchMemoryService:
    """Phase 15.0 §3: long-term memory service.

    In-memory simulation by default (``db_session=None``); persists to
    ``research_user_profiles`` when a DB session is provided. Designed
    to be safe to call without any DB context.
    """

    def __init__(self, db_session: Optional[Any] = None) -> None:
        self._db_session = db_session
        # Memory snapshot per user_id (used for in-memory simulation).
        self._snapshot: Dict[str, List[ResearchMemoryEntry]] = {}

    # ----- Profile operations ------------------------------------------------
    def save_profile(
        self,
        user_id: int,
        *,
        name: str,
        research_domain: str,
        expertise_level: str,
        research_topics: Optional[List[str]] = None,
        preferred_answer_style: Optional[str] = None,
        research_preferences: Optional[Dict[str, Any]] = None,
        current_projects: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Phase 15.0 §3: persist (or simulate-persist) a profile snapshot."""
        payload = {
            "user_id": int(user_id),
            "name": name,
            "research_domain": research_domain,
            "expertise_level": expertise_level,
            "research_topics": list(research_topics or []),
            "preferred_answer_style": preferred_answer_style,
            "research_preferences": dict(research_preferences or {}),
            "current_projects": list(current_projects or []),
        }

        # Mirror into the in-memory snapshot so load_profile sees it.
        self._snapshot[str(user_id)] = [
            ResearchMemoryEntry(
                category="_profile_snapshot",
                content=name,
                metadata=payload,
            ),
        ]

        if self._db_session is not None:
            try:
                from app.models.research_user_profile import ResearchUserProfile
                existing = (
                    self._db_session.query(ResearchUserProfile)
                    .filter(ResearchUserProfile.user_id == user_id)
                    .one_or_none()
                )
                if existing is None:
                    profile = ResearchUserProfile(
                        user_id=payload["user_id"],
                        name=payload["name"],
                        research_domain=payload["research_domain"],
                        expertise_level=payload["expertise_level"],
                        research_topics=payload["research_topics"],
                        preferred_answer_style=payload["preferred_answer_style"],
                        research_preferences=payload["research_preferences"],
                        current_projects=payload["current_projects"],
                    )
                    self._db_session.add(profile)
                else:
                    existing.name = payload["name"]
                    existing.research_domain = payload["research_domain"]
                    existing.expertise_level = payload["expertise_level"]
                    existing.research_topics = payload["research_topics"]
                    existing.preferred_answer_style = (
                        payload["preferred_answer_style"]
                    )
                    existing.research_preferences = payload["research_preferences"]
                    existing.current_projects = payload["current_projects"]
                self._db_session.commit()
            except Exception as exc:  # pragma: no cover - DB layer
                _logger.debug("save_profile db commit failed: %s", exc)

        return payload

    def load_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Phase 15.0 §3: load a profile snapshot by user_id."""
        if self._db_session is not None:
            try:
                from app.models.research_user_profile import ResearchUserProfile
                row = (
                    self._db_session.query(ResearchUserProfile)
                    .filter(ResearchUserProfile.user_id == user_id)
                    .one_or_none()
                )
                if row is not None:
                    return row.to_dict()
            except Exception as exc:  # pragma: no cover - DB layer
                _logger.debug("load_profile db read failed: %s", exc)
        # Snapshot may still contain a record from save_profile side-effect.
        snap = self._snapshot.get(str(user_id))
        if snap:
            meta = snap[-1].metadata or {}
            return {
                "user_id": int(meta.get("user_id", user_id)),
                "name": meta.get("name", ""),
                "research_domain": meta.get("research_domain", "general"),
                "expertise_level": meta.get("expertise_level", "researcher"),
                "research_topics": list(meta.get("research_topics") or []),
                "preferred_answer_style": meta.get("preferred_answer_style"),
                "research_preferences": dict(meta.get("research_preferences") or {}),
                "current_projects": list(meta.get("current_projects") or []),
            }
        return None

    def update_profile(
        self,
        user_id: int,
        *,
        research_topics: Optional[List[str]] = None,
        current_projects: Optional[List[str]] = None,
        research_preferences: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Phase 15.0 §3: merge-update an existing profile."""
        existing = self.load_profile(user_id)
        if existing is None:
            return None
        if research_topics is not None:
            merged_topics = list(existing.get("research_topics") or [])
            for t in research_topics:
                if t not in merged_topics:
                    merged_topics.append(t)
            existing["research_topics"] = merged_topics
        if current_projects is not None:
            merged_projects = list(existing.get("current_projects") or [])
            for p in current_projects:
                if p not in merged_projects:
                    merged_projects.append(p)
            existing["current_projects"] = merged_projects
        if research_preferences is not None:
            existing.setdefault("research_preferences", {}).update(
                research_preferences
            )
        # Re-save (updates DB row if any)
        return self.save_profile(
            user_id,
            name=existing["name"],
            research_domain=existing["research_domain"],
            expertise_level=existing["expertise_level"],
            research_topics=existing["research_topics"],
            preferred_answer_style=existing.get("preferred_answer_style"),
            research_preferences=existing.get("research_preferences", {}),
            current_projects=existing["current_projects"],
        )

    # ----- Project memory ---------------------------------------------------
    def save_project_memory(
        self,
        user_id: int,
        *,
        workspace_id: str,
        category: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ResearchMemoryEntry:
        """Phase 15.0 §3: append an in-memory research memory entry."""
        if category not in DEFAULT_CATEGORIES:
            category = CATEGORY_RESEARCH_TOPIC
        entry = ResearchMemoryEntry(
            category=category,
            content=content,
            workspace_id=workspace_id,
            metadata=dict(metadata or {}),
            created_at="",
        )
        self._snapshot.setdefault(str(user_id), []).append(entry)
        return entry

    def retrieve_project_context(
        self,
        user_id: int,
        *,
        workspace_id: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> List[ResearchMemoryEntry]:
        """Phase 15.0 §3: retrieve memory entries for a user / workspace."""
        entries = self._snapshot.get(str(user_id), []) or []
        out: List[ResearchMemoryEntry] = []
        cat_filter = set(categories or DEFAULT_CATEGORIES)
        for e in entries:
            if e.category not in cat_filter:
                continue
            if workspace_id and e.workspace_id and e.workspace_id != workspace_id:
                continue
            out.append(e)
        return out

    def summarize_research_history(
        self,
        user_id: int,
    ) -> Dict[str, Any]:
        """Phase 15.0 §3: aggregate counts + grouped content by category."""
        entries = self._snapshot.get(str(user_id), []) or []
        by_category: Dict[str, List[str]] = {c: [] for c in DEFAULT_CATEGORIES}
        for e in entries:
            by_category.setdefault(e.category, []).append(e.content)
        return {
            "user_id": int(user_id),
            "total_entries": len(entries),
            "by_category": {
                k: {
                    "count": len(v),
                    "excerpt": v[-1] if v else "",
                }
                for k, v in by_category.items()
            },
        }


__all__ = [
    "DEFAULT_CATEGORIES",
    "ResearchMemoryEntry",
    "ResearchMemoryService",
    "CATEGORY_USER_FACT",
    "CATEGORY_RESEARCH_TOPIC",
    "CATEGORY_METHOD_PREFERENCE",
    "CATEGORY_CURRENT_PROBLEM",
    "CATEGORY_IMPORTANT_DECISION",
    "CATEGORY_FAILED_ATTEMPT",
    "CATEGORY_RESEARCH_DIRECTION",
]
