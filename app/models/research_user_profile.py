"""ResearchUserProfile ORM — Phase 15.0 §1.

Persistent researcher identity for the Phase 14 Research Agent V1.0
productization layer. Additive — does not modify any existing model.

Public API:
- ResearchUserProfile (SQLAlchemy ORM model)
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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ResearchUserProfile(Base, TimestampMixin):
    """Phase 15.0 §1: persistent researcher identity.

    Stores the long-term profile derived in Phase 14.2 from memory +
    history. One row per ``Member``. The ``research_topics`` and
    ``research_preferences`` JSONB columns capture the dynamic
    per-user signals (topics of interest, answer-style preference, etc.).
    """

    __tablename__ = "research_user_profiles"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="members.id; one profile per member",
    )
    name = Column(String(50), nullable=False)
    research_domain = Column(
        String(80),
        nullable=False,
        index=True,
        comment="pollution_control_water_treatment / advanced_oxidation_water_treatment / ...",
    )
    expertise_level = Column(
        String(20),
        nullable=False,
        comment="beginner / student / researcher / expert",
    )
    research_topics = Column(
        JSON,
        nullable=True,
        comment="['microbubble', 'ozone oxidation', 'TC degradation', ...]",
    )
    preferred_answer_style = Column(
        String(40),
        nullable=True,
        comment="narrative / structured / paper_level / equation_heavy",
    )
    research_preferences = Column(
        JSON,
        nullable=True,
        comment="自由 JSONB: {preferred_languages, citation_policy, ...}",
    )
    current_projects = Column(
        JSON,
        nullable=True,
        comment="['project_xxx', 'project_yyy'] active workspace ids",
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_research_user_profiles_user_id"),
        Index(
            "idx_research_user_profiles_domain_expertise",
            "research_domain",
            "expertise_level",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id is not None else None,
            "user_id": int(self.user_id) if self.user_id is not None else None,
            "name": self.name,
            "research_domain": self.research_domain,
            "expertise_level": self.expertise_level,
            "research_topics": list(self.research_topics or []),
            "preferred_answer_style": self.preferred_answer_style,
            "research_preferences": dict(self.research_preferences or {}),
            "current_projects": list(self.current_projects or []),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


__all__ = ["ResearchUserProfile"]
