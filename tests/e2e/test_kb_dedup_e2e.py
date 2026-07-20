"""End-to-end coverage for KB duplicate protection and administration.

The module owns its database/client fixtures so the documented container
command (which sets ``SKIP_DB_SETUP=1``) still runs the tests instead of
silently skipping the project's generic DB fixtures.  The test database is
expected to be provisioned by the container before pytest starts.
"""
from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.knowledge import Knowledge
from app.services.knowledge_service import KnowledgeService
from scripts.cleanup_kb_duplicates import (
    CleanupPlan,
    apply_cleanup,
    scan_duplicates,
    validate_cleanup_plan,
)


class _SessionContext(AbstractAsyncContextManager):
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _SessionFactory:
    """Adapt the global async session to the CLI session-factory contract."""

    def __init__(self, session):
        self.session = session

    def __call__(self):
        return _SessionContext(self.session)


@pytest_asyncio.fixture
async def e2e_db():
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def e2e_client(e2e_db):
    async def override_db():
        yield e2e_db

    async def override_user():
        return SimpleNamespace(id=0, role="admin", username="kb-e2e")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://kb-e2e"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_auto_expansion_duplicate_is_idempotent(
    e2e_client, e2e_db, monkeypatch
):
    """Same question/content with different QA ids creates one persisted row."""

    async def no_embedding(self, knowledge_id, title, content):
        return None

    monkeypatch.setattr(KnowledgeService, "_embed_only", no_embedding)
    content = "DLVO 理论用于解释胶体稳定性与颗粒间相互作用。" * 20
    payload = {
        "items": [
            {
                "qa_id": "E2E-KB-DEDUP-001",
                "question": "什么是 DLVO 理论？",
                "content": content,
                "scope": "theory",
                "score": 5,
                "intent": "explain_concept",
            }
        ]
    }

    first = await e2e_client.post(
        "/api/v1/knowledge/from-auto-expansion", json=payload
    )
    assert first.status_code == 201, first.text
    second_payload = {**payload}
    second_payload["items"] = [{**payload["items"][0], "qa_id": "E2E-KB-DEDUP-002"}]
    second = await e2e_client.post(
        "/api/v1/knowledge/from-auto-expansion", json=second_payload
    )
    assert second.status_code == 201, second.text
    assert first.json()["knowledge_ids"] == second.json()["knowledge_ids"]

    question = payload["items"][0]["question"]
    row_count = await e2e_db.scalar(
        select(func.count()).select_from(Knowledge).where(
            Knowledge.source_type == "auto_expansion",
            Knowledge.meta["content_hash"].as_string().is_not(None),
            Knowledge.title.contains(question),
        )
    )
    assert row_count == 1

    await e2e_db.execute(
        delete(Knowledge).where(
            Knowledge.source.in_(
                ["qa-bench:E2E-KB-DEDUP-001", "qa-bench:E2E-KB-DEDUP-002"]
            )
        )
    )
    await e2e_db.commit()


@pytest.mark.asyncio
async def test_search_returns_one_result_for_duplicate_title(
    e2e_client, e2e_db, monkeypatch
):
    """The semantic endpoint's keyword fallback applies title dedup."""

    import app.services.embedding_service as embedding_service

    async def no_embedding(_query):
        return None

    monkeypatch.setattr(embedding_service, "generate_embedding", no_embedding)
    title = "E2E KB 搜索去重标题"
    rows = [
        Knowledge(
            title=title,
            content="搜索去重内容 A",
            storage_mode="kb",
            visibility="team",
            created_by=None,
            quality_score=0.2,
        ),
        Knowledge(
            title=title,
            content="搜索去重内容 B",
            storage_mode="kb",
            visibility="team",
            created_by=None,
            quality_score=0.9,
        ),
    ]
    e2e_db.add_all(rows)
    await e2e_db.commit()
    await e2e_db.refresh(rows[0])
    await e2e_db.refresh(rows[1])

    response = await e2e_client.get(
        "/api/v1/knowledge/search/semantic",
        params={"query": title, "top_k": 10},
    )
    assert response.status_code == 200, response.text
    results = response.json()
    matching = [item for item in results if item["title"] == title]
    assert len(matching) == 1
    assert matching[0]["id"] == max(rows[0].id, rows[1].id)

    await e2e_db.execute(delete(Knowledge).where(Knowledge.id.in_([r.id for r in rows])))
    await e2e_db.commit()


@pytest.mark.asyncio
async def test_cleanup_kb_duplicates_scan_validate_and_apply(e2e_db):
    """The admin CLI scans, validates, dry-runs, and soft-deletes safely."""

    title = "E2E KB 历史重复清理"
    rows = [
        Knowledge(
            title=title,
            content="完全相同的历史内容",
            storage_mode="kb",
            visibility="team",
            created_by=None,
            quality_score=0.1,
        ),
        Knowledge(
            title=title,
            content="完全相同的历史内容",
            storage_mode="kb",
            visibility="team",
            created_by=None,
            quality_score=0.8,
        ),
    ]
    e2e_db.add_all(rows)
    await e2e_db.commit()
    await e2e_db.refresh(rows[0])
    await e2e_db.refresh(rows[1])

    plan = await scan_duplicates(_SessionFactory(e2e_db))
    target_groups = [group for group in plan.groups if group.title == title]
    assert len(target_groups) == 1
    target_plan = CleanupPlan(groups=target_groups)
    target_plan.validation = validate_cleanup_plan(target_plan)
    assert target_plan.validation.valid
    assert len(target_plan.validation.delete_ids) == 1

    dry_run_count = await apply_cleanup(
        _SessionFactory(e2e_db), target_plan, dry_run=True
    )
    assert dry_run_count == 1
    active_before_apply = await e2e_db.scalar(
        select(func.count()).select_from(Knowledge).where(
            Knowledge.id.in_([rows[0].id, rows[1].id]),
            Knowledge.deleted_at.is_(None),
        )
    )
    assert active_before_apply == 2

    deleted = await apply_cleanup(
        _SessionFactory(e2e_db), target_plan, dry_run=False
    )
    assert deleted == 1
    active_after_apply = await e2e_db.scalar(
        select(func.count()).select_from(Knowledge).where(
            Knowledge.id.in_([rows[0].id, rows[1].id]),
            Knowledge.deleted_at.is_(None),
        )
    )
    assert active_after_apply == 1

    await e2e_db.execute(delete(Knowledge).where(Knowledge.id.in_([r.id for r in rows])))
    await e2e_db.commit()
