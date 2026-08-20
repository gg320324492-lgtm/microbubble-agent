"""Research Workspace Manager — Phase 15.0 §4.

CRUD façade over ``research_workspaces``. In-memory snapshot by default
(``db_session=None``) for tests; persists when a session is provided.

Public API:
- WorkspaceSnapshot dataclass (in-memory stand-in)
- ResearchWorkspaceManager
    create_workspace()
    get_workspace()
    update_stage()
    add_hypothesis()
    add_evidence()
    update_progress()
    get_research_status()
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.models.research_workspace import (
    STAGE_CHOICES,
    STAGE_EXPLORATION,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_CHOICES,
    STATUS_COMPLETED,
    STATUS_PAUSED,
)

_logger = logging.getLogger(__name__)


@dataclass
class WorkspaceSnapshot:
    """Phase 15.0 §4: in-memory mirror of a research workspace row."""

    workspace_id: str
    user_id: int
    title: str
    domain: str
    status: str = STATUS_ACTIVE
    current_stage: str = STAGE_EXPLORATION
    description: str = ""
    goal: str = ""
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    progress_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "user_id": int(self.user_id),
            "title": self.title,
            "domain": self.domain,
            "status": self.status,
            "current_stage": self.current_stage,
            "description": self.description,
            "goal": self.goal,
            "hypotheses": [dict(h) for h in self.hypotheses],
            "evidence_summary": dict(self.evidence_summary),
            "progress_payload": dict(self.progress_payload),
        }


class ResearchWorkspaceManager:
    """Phase 15.0 §4: workspace manager (in-memory + optional DB)."""

    def __init__(self, db_session: Optional[Any] = None) -> None:
        self._db = db_session
        self._by_id: Dict[str, WorkspaceSnapshot] = {}
        self._by_user: Dict[int, List[str]] = {}

    # ----- Lifecycle --------------------------------------------------------
    def create_workspace(
        self,
        user_id: int,
        *,
        title: str,
        domain: str,
        goal: str = "",
        description: str = "",
        workspace_id: Optional[str] = None,
        current_stage: str = STAGE_EXPLORATION,
    ) -> WorkspaceSnapshot:
        """Phase 15.0 §4: create a new workspace."""
        if current_stage not in STAGE_CHOICES:
            current_stage = STAGE_EXPLORATION

        wid = workspace_id or f"ws_{uuid.uuid4().hex[:12]}"
        snap = WorkspaceSnapshot(
            workspace_id=wid,
            user_id=int(user_id),
            title=title,
            domain=domain,
            current_stage=current_stage,
            description=description,
            goal=goal,
        )
        self._by_id[wid] = snap
        self._by_user.setdefault(int(user_id), []).append(wid)

        if self._db is not None:
            try:
                from app.models.research_workspace import ResearchWorkspace
                row = ResearchWorkspace(
                    user_id=snap.user_id,
                    title=snap.title,
                    description=snap.description,
                    domain=snap.domain,
                    status=snap.status,
                    goal=snap.goal,
                    current_stage=snap.current_stage,
                    hypotheses=snap.hypotheses,
                    evidence_summary=snap.evidence_summary,
                    progress_payload=snap.progress_payload,
                )
                self._db.add(row)
                self._db.commit()
                # Keep IDs stable
                if row.id is not None:
                    snap.workspace_id = f"ws_{int(row.id)}"
                    self._by_id[snap.workspace_id] = snap
            except Exception as exc:  # pragma: no cover - DB layer
                _logger.debug("create_workspace db commit failed: %s", exc)
        return snap

    def get_workspace(
        self,
        workspace_id: str,
    ) -> Optional[WorkspaceSnapshot]:
        """Phase 15.0 §4: load a workspace by id (snapshot only)."""
        return self._by_id.get(workspace_id)

    def list_workspaces(self, user_id: int) -> List[WorkspaceSnapshot]:
        """Phase 15.0 §4: list all workspaces owned by ``user_id``."""
        ids = self._by_user.get(int(user_id), []) or []
        return [self._by_id[i] for i in ids if i in self._by_id]

    # ----- Mutations --------------------------------------------------------
    def update_stage(
        self,
        workspace_id: str,
        stage: str,
    ) -> Optional[WorkspaceSnapshot]:
        """Phase 15.0 §4: change the current stage."""
        if stage not in STAGE_CHOICES:
            return None
        snap = self._by_id.get(workspace_id)
        if snap is None:
            return None
        snap.current_stage = stage
        # Stage transitions typically imply status movement
        if stage in ("analysis", "writing") and snap.status == STATUS_ACTIVE:
            snap.status = STATUS_ACTIVE  # keep active
        return snap

    def update_status(
        self,
        workspace_id: str,
        status: str,
    ) -> Optional[WorkspaceSnapshot]:
        """Phase 15.0 §4: change the status (active/paused/completed/archived)."""
        if status not in STATUS_CHOICES:
            return None
        snap = self._by_id.get(workspace_id)
        if snap is None:
            return None
        snap.status = status
        return snap

    def add_hypothesis(
        self,
        workspace_id: str,
        *,
        hypothesis_id: str,
        text: str,
        created_by: Optional[str] = None,
    ) -> Optional[WorkspaceSnapshot]:
        """Phase 15.0 §4: append a hypothesis row."""
        snap = self._by_id.get(workspace_id)
        if snap is None:
            return None
        snap.hypotheses.append({
            "id": hypothesis_id,
            "text": text,
            "created_by": created_by or "user",
            "stage": snap.current_stage,
        })
        # Bump stage forward if currently earlier than hypothesis
        if snap.current_stage in (STAGE_EXPLORATION, "literature"):
            snap.current_stage = "hypothesis"
        return snap

    def add_evidence(
        self,
        workspace_id: str,
        *,
        kind: str,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[WorkspaceSnapshot]:
        """Phase 15.0 §4: append an evidence summary entry."""
        snap = self._by_id.get(workspace_id)
        if snap is None:
            return None
        snap.evidence_summary[kind] = {
            "summary": summary,
            "metadata": dict(metadata or {}),
        }
        if snap.current_stage in ("hypothesis", "literature"):
            snap.current_stage = "experiment"
        return snap

    def update_progress(
        self,
        workspace_id: str,
        progress: Dict[str, Any],
    ) -> Optional[WorkspaceSnapshot]:
        """Phase 15.0 §4: overwrite the progress_payload."""
        snap = self._by_id.get(workspace_id)
        if snap is None:
            return None
        snap.progress_payload.update(dict(progress or {}))
        return snap

    # ----- Reporting --------------------------------------------------------
    def get_research_status(
        self,
        workspace_id: str,
    ) -> Dict[str, Any]:
        """Phase 15.0 §4: aggregate status snapshot for a workspace."""
        snap = self._by_id.get(workspace_id)
        if snap is None:
            return {}
        return {
            "workspace_id": snap.workspace_id,
            "title": snap.title,
            "domain": snap.domain,
            "status": snap.status,
            "current_stage": snap.current_stage,
            "hypothesis_count": len(snap.hypotheses),
            "evidence_count": len(snap.evidence_summary),
            "evidence_kinds": list(snap.evidence_summary.keys()),
            "progress": dict(snap.progress_payload),
        }


__all__ = [
    "WorkspaceSnapshot",
    "ResearchWorkspaceManager",
    "STATUS_ACTIVE",
    "STATUS_PAUSED",
    "STATUS_COMPLETED",
    "STATUS_ARCHIVED",
    "STAGE_EXPLORATION",
    "STAGE_LITERATURE",
    "STAGE_HYPOTHESIS",
    "STAGE_EXPERIMENT",
    "STAGE_ANALYSIS",
    "STAGE_WRITING",
]
