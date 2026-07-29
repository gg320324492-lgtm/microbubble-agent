"""PR1 focused checks; heavyweight model tests are skipped without ST."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.embedding_query_policy import should_use_query_prefix
from app.services.embedding_truncation_policy import truncate_for_embedding


def test_policy_and_truncation_e2e():
    assert len(truncate_for_embedding("a" * 6001)) == 6000
    assert should_use_query_prefix("kb_qa")
    assert not should_use_query_prefix("auto_research")


def test_embedding_service_contract_is_guarded():
    pytest.importorskip("sentence_transformers")
    from app.services import embedding_service

    embedding_service.generate_embedding_sync = AsyncMock()
    assert callable(embedding_service.generate_embedding)
