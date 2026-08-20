"""ResearchWorkspace ORM — Phase 15.0 §2.

One workspace == one research project. Holds persistent project state
across sessions: status, current stage, hypotheses, evidence summary.

Public API:
- ResearchWorkspace (SQLAlchemy ORM model)
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# Status enum (Phase 15.0 §2)
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_ARCHIVED = "archived"

STATUS_CHOICES: tuple = (
    STATUS_ACTIVE,
    STATUS_PAUSED,
    STATUS_COMPLETED,
    STATUS_ARCHIVED,
)

# Stage enum (Phase 15.0 §2)
STAGE_EXPLORATION = "exploration"
STAGE_LITERATURE = "literature"
STAGE_HYPOTHESIS = "hypothesis"
STAGE_EXPERIMENT = "experiment"
STAGE_ANALYSIS = "analysis"
STAGE_WRITING = "writing"

STAGE_CHOICES: tuple = (
    STAGE_EXPLORATION,
    STAGE_LITERATURE,
    STAGE_HYPOTHESIS,
    STAGE_EXPERIMENT,
    STAGE_ANALYSIS,
    STAGE_WRITING,
)


class ResearchWorkspace(Base, TimestampMixin):
    """Phase 15.0 §2: persistent research project workspace.

    Captures the persistent state of a single research project: title,
    domain, status, current stage, hypotheses list, evidence summary, and
    a free-form progress payload. Each workspace is owned by a single
    user.
    """

    __tablename__ = "research_workspaces"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="members.id; workspace owner",
    )
    title = Column(String(200), nullable=False)
    description = Column(String(2000), nullable=True)
    domain = Column(
        String(80),
        nullable=False,
        index=True,
        comment="research domain string",
    )
    status = Column(
        String(20),
        nullable=False,
        server_default=STATUS_ACTIVE,
        comment=(
            "active / paused / completed / archived (Phase 15.0 §2 enum)"
        ),
    )
    goal = Column(String(1000), nullable=True)
    hypotheses = Column(
        JSON,
        nullable=True,
        comment="[{'id':'H1','text':'...','created_at':'...'}, ...]",
    )
    evidence_summary = Column(
        JSON,
        nullable=True,
        comment="{'EPR': {...}, 'LC-MS': {...}, 'kinetics': {...}}",
    )
    current_stage = Column(
        String(20),
        nullable=False,
        server_default=STAGE_EXPLORATION,
        comment="exploration / literature / hypothesis / experiment / analysis / writing",
    )
    progress_payload = Column(
        JSON,
        nullable=True,
        comment="arbitrary progress metadata (literature_progress, etc.)",
    )

    __table_args__ = (
        Index(
            "idx_research_workspaces_user_status",
            "user_id",
            "status",
        ),
        Index(
            "idx_research_workspaces_domain_stage",
            "domain",
            "current_stage",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id is not None else None,
            "user_id": int(self.user_id) if self.user_id is not None else None,
            "title": self.title,
            "description": self.description,
            "domain": self.domain,
            "status": self.status,
            "goal": self.goal,
            "hypotheses": list(self.hypotheses or []),
            "evidence_summary": dict(self.evidence_summary or {}),
            "current_stage": self.current_stage,
            "progress_payload": dict(self.progress_payload or {}),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


__all__ = ["ResearchWorkspace"]
