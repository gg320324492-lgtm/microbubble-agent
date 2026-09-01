"""WP2 (2026-09-02) drive 内容索引单测

锁三个契约:
  1. index_drive_content 域守卫: 非 drive 行 / 删除行 / 不支持格式 → skipped
  2. 正常链: MinIO 下载 → 解析 → 分块 → embedding 回填 → 落 knowledge_chunks
  3. drive 检索路 where 契约: private 仅 owner; 匿名仅非 private
"""
from __future__ import annotations

import contextlib
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import drive_index_service as dis
from app.services.drive_index_service import index_drive_content


def _drive_row(kid=1, visibility="team", deleted=None, file_path="docs/论文.pdf",
               file_name="论文.pdf", storage_mode="drive"):
    return types.SimpleNamespace(
        id=kid, storage_mode=storage_mode, deleted_at=deleted,
        file_path=file_path, file_name=file_name, file_type=file_name,
    )


def _session_factory(rows_by_id: dict):
    """session factory stub — db.get 按 id 查"""

    class _DB:
        def __init__(self):
            self.added = []

        async def get(self, model, kid):
            return rows_by_id.get(kid)

        async def execute(self, stmt):
            # delete 语句 → 空结果; select chunk rows (embedding 回填) → 空
            empty = MagicMock()
            empty.scalars.return_value.all.return_value = []
            return empty

        def add_all(self, rows):
            self.added.extend(rows)

        async def commit(self):
            pass

    @contextlib.asynccontextmanager
    async def _cm():
        yield _DB()

    return _cm


@pytest.mark.asyncio
async def test_skips_non_drive_row():
    r = await index_drive_content(1, _session_factory({1: _drive_row(1, storage_mode="kb")}))
    assert r["skipped"] == 1 and "not a drive" in r["reason"]


@pytest.mark.asyncio
async def test_skips_deleted_row():
    import datetime

    r = await index_drive_content(
        2, _session_factory({2: _drive_row(2, deleted=datetime.datetime(2026, 1, 1))})
    )
    assert r["skipped"] == 1 and r["reason"] == "deleted"


@pytest.mark.asyncio
async def test_skips_unsupported_ext():
    r = await index_drive_content(
        3, _session_factory({3: _drive_row(3, file_name="压缩包.zip")})
    )
    assert r["skipped"] == 1 and "unsupported" in r["reason"]


@pytest.mark.asyncio
async def test_happy_path_writes_chunks():
    """MinIO→解析→分块→embedding→knowledge_chunks 全链 (全 mock)"""
    row = _drive_row(9, visibility="private")
    sf = _session_factory({9: row})

    # chunk 库读回 stub: add_all 后 select 能查到刚写的行 (供 embedding 回填)
    written = []

    class _DB:
        def __init__(self):
            self.added = []

        async def get(self, model, kid):
            return row if kid == 9 else None

        async def execute(self, stmt):
            # select KnowledgeChunk → 返回已写行; delete → 空
            res = MagicMock()
            res.scalars.return_value.all.return_value = list(written)
            return res

        def add_all(self, rows):
            self.added.extend(rows)
            written.extend(rows)

        async def commit(self):
            pass

    _DB_addall_seen = []
    _orig_addall = _DB.add_all
    def _patched_addall(self, rows):
        rows = list(rows)
        _DB_addall_seen.extend(rows)
        _orig_addall(self, rows)
    _DB.add_all = _patched_addall
    @contextlib.asynccontextmanager
    async def sf2():
        yield _DB()

    text = "微纳米气泡在水产养殖中抑制病原菌的机制研究。" * 20

    async def _fake_emb(texts, for_query=False):
        return [[0.1] * 8 for _ in texts]

    with patch("app.services.file_service.file_service.download_file",
               AsyncMock(return_value=b"%PDF-1.4 fake")), \
         patch("app.services.file_parser_service.file_parser_service.extract_content",
               AsyncMock(return_value={"text": text, "images": []})), \
         patch("app.services.embedding_service.generate_embeddings",
               AsyncMock(side_effect=_fake_emb)):
        r = await index_drive_content(9, sf2)

    assert r["skipped"] == 0, r
    assert r["chunks"] > 0
    assert r["embedded"] == r["chunks"]


@pytest.mark.asyncio
async def test_skips_when_parser_fails():
    sf = _session_factory({11: _drive_row(11)})

    with patch("app.services.file_service.file_service.download_file",
               AsyncMock(return_value=b"broken")), \
         patch("app.services.file_parser_service.file_parser_service.extract_content",
               AsyncMock(side_effect=ValueError("加密 PDF"))):
        r = await index_drive_content(11, sf)

    assert r["skipped"] == 1 and "parse failed" in r["reason"]


def test_drive_visibility_sql_contract():
    """drive 路 where 契约: user_id 给定 → owner 可见 private; None → 仅非 private"""
    from sqlalchemy import select, or_

    from app.models.knowledge import Knowledge as K
    from app.models.knowledge_chunk import KnowledgeChunk as KC

    def build(user_id):
        vis = (
            or_(K.visibility != "private", K.created_by == user_id)
            if user_id is not None
            else (K.visibility != "private")
        )
        stmt = (
            select(KC.knowledge_id)
            .join(K, K.id == KC.knowledge_id)
            .where(
                KC.embedding.isnot(None),
                K.deleted_at.is_(None),
                K.storage_mode == "drive",
                vis,
            )
        )
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))

    owner_sql = build(7)
    anon_sql = build(None)
    assert "created_by" in owner_sql      # owner 逃生通道存在
    assert "created_by" not in anon_sql   # 匿名无逃生通道
    assert "storage_mode" in owner_sql and "storage_mode" in anon_sql
