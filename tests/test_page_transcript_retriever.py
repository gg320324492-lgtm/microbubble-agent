"""agent44 — knowledge_page_transcripts / PageTranscriptRetriever 单测

覆盖三件容易出错的事:
1. **落点是 kb 孪生行而非 drive 行** —— 落错就过不了 multimodal_retriever 的
   ``storage_mode == 'kb'`` 硬过滤, 整批 2061 页检索不到。
2. **可见性边界一道不少** —— deleted_at / storage_mode / visibility 三条与
   ``multimodal_retriever`` 逐字同款 (类 20.215 逐字段圈界), 少一条就是泄漏。
3. **blocked 行有 metadata 无正文** —— 数据库 CHECK + 检索侧双重保证。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ⚠️ 必须用 conftest 的 test_async_session —— `app.core.database.async_session`
# 绑定的是**生产库** DATABASE_URL, 测试直连会往生产写 debris
# (tests/test_no_prod_db_imports.py 就是这条纪律的守卫测试)。
from tests.conftest import test_async_session as async_session
from app.models.knowledge import Knowledge
from app.models.knowledge_page_transcript import KnowledgePageTranscript
from app.services.multimodal_retriever import MultimodalRetriever
from app.services.page_transcript_retriever import (
    MIN_SIMILARITY,
    PageTranscriptRetriever,
)


async def _mk_kb(db: AsyncSession, **kw) -> Knowledge:
    defaults = dict(
        title="a44-twin",
        content="native text",
        storage_mode="kb",
        visibility="team",
        source_type="drive_extracted",
    )
    defaults.update(kw)
    k = Knowledge(**defaults)
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


# ── 1. 落点: 孪生行 vs drive 行 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_knowledge_id_points_at_kb_twin_not_drive_row():
    """页转写挂 kb 孪生行 —— 这是 multimodal_retriever 硬过滤能放行的前提。"""
    async with async_session() as db:
        twin = await _mk_kb(db, title="a44-twin-1", meta={"drive_source_file_id": 999001})
        drive = await _mk_kb(db, title="a44-drive-1", storage_mode="drive")
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, source_drive_file_id=drive.id,
            page_number=1, content="视觉转写正文", char_count=6, blocked=False,
        ))
        await db.commit()

        rows = (await db.execute(
            select(KnowledgePageTranscript).where(
                KnowledgePageTranscript.source_drive_file_id == drive.id
            )
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].knowledge_id == twin.id
        assert rows[0].knowledge_id != drive.id

        got = (await db.execute(
            select(Knowledge.storage_mode).where(Knowledge.id == rows[0].knowledge_id)
        )).scalar_one()
        assert got == "kb", "挂载目标必须是 storage_mode='kb' 的孪生行"


# ── 2. 可见性边界 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_visibility_boundaries_match_multimodal_retriever():
    """两条路径的 WHERE 边界必须逐字同款 (类 20.215)。"""
    from sqlalchemy import or_

    mm = MultimodalRetriever.__dict__["_load_candidates"]
    pt = PageTranscriptRetriever._load_candidates
    assert callable(mm) and callable(pt)

    # 逐条核对 PageTranscriptRetriever 用到的边界常量
    import inspect
    src = inspect.getsource(pt)
    for needle in (
        "Knowledge.deleted_at.is_(None)",
        'Knowledge.storage_mode == "kb"',
        'Knowledge.visibility.in_(["team", "public"])',
    ):
        assert needle in src, f"缺可见性边界: {needle}"


@pytest.mark.asyncio
async def test_blocked_rows_never_loaded_as_candidates():
    async with async_session() as db:
        twin = await _mk_kb(db, title="a44-blocked")
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, page_number=1, content="可见正文",
            char_count=4, blocked=False,
        ))
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, page_number=2, content=None, char_count=None,
            blocked=True, block_reasons=["chrome_ratio=80% >= 15%（转人工确认）"],
        ))
        await db.commit()

        r = PageTranscriptRetriever(db)
        cands = await r._load_candidates()
        assert all(c["content"] is not None for c in cands)
        assert all(c["page_number"] != 2 for c in cands)


@pytest.mark.asyncio
async def test_deleted_and_private_parents_excluded():
    async with async_session() as db:
        ok = await _mk_kb(db, title="a44-ok")
        dead = await _mk_kb(db, title="a44-dead", deleted_at=__import__("datetime").datetime.now())
        priv = await _mk_kb(db, title="a44-priv", visibility="private")
        for kid in (ok.id, dead.id, priv.id):
            db.add(KnowledgePageTranscript(
                knowledge_id=kid, page_number=1, content="x",
                char_count=1, blocked=False,
            ))
        await db.commit()

        cands = await PageTranscriptRetriever(db)._load_candidates()
        ids = {c["knowledge_id"] for c in cands}
        assert ok.id in ids
        assert dead.id not in ids
        assert priv.id not in ids


# ── 3. blocked 无正文不变量 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_blocked_row_with_body_violates_check_constraint():
    """数据库层强制 blocked 行不得带正文。"""
    import sqlalchemy as sa
    async with async_session() as db:
        twin = await _mk_kb(db, title="a44-ck")
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, page_number=9, content="不该存在的正文",
            char_count=7, blocked=True,
        ))
        with pytest.raises(sa.exc.IntegrityError):
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
async def test_unblocked_row_requires_body():
    import sqlalchemy as sa
    async with async_session() as db:
        twin = await _mk_kb(db, title="a44-ck2")
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, page_number=9, content=None,
            char_count=None, blocked=False,
        ))
        with pytest.raises(sa.exc.IntegrityError):
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
async def test_duplicate_page_rejected():
    import sqlalchemy as sa
    async with async_session() as db:
        twin = await _mk_kb(db, title="a44-dup")
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, page_number=3, content="a", char_count=1, blocked=False,
        ))
        await db.commit()
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, page_number=3, content="b", char_count=1, blocked=False,
        ))
        with pytest.raises(sa.exc.IntegrityError):
            await db.commit()
        await db.rollback()


# ── 4. 结果形态 ─────────────────────────────────────────────────────────

def test_search_pages_empty_query_returns_empty():
    import asyncio
    r = PageTranscriptRetriever(db=None)
    assert asyncio.run(r.search_pages("", top_k=5)) == []
    assert asyncio.run(r.search_pages("   ", top_k=5)) == []
    assert asyncio.run(r.search_pages("x", top_k=0)) == []


# ── 5. 相似度下限 (agent44 实测踩到) ────────────────────────────────────

def test_min_similarity_floor_is_calibrated():
    """下限必须落在「真命中」与「库内不存在的反例」之间。

    实测标定 (scripts/_archive/a44_verify_probe_rank.py):
      真命中语义探针 0.628~0.815 ; 反例探针 0.488~0.517
    取 0.55。若有人把下限调到 0 以下, 「任何 query 都返回 top_k」的缺陷回归。
    """
    assert 0.50 < MIN_SIMILARITY < 0.63, (
        f"MIN_SIMILARITY={MIN_SIMILARITY} 落在标定区间外, "
        f"反例探针(~0.52)或真命中(~0.63)会被误放行/误杀"
    )


def test_similarity_floor_filters_low_scores(monkeypatch):
    """低于下限的候选不进结果 —— 否则反例 query 也会拿满 top_k。"""
    import asyncio
    import app.services.page_transcript_retriever as mod

    async def fake_candidates(self):
        return [
            {"id": 1, "knowledge_id": 1, "page_number": 1, "content": "hi",
             "file_name": "a.pptx", "embedding": [1.0] + [0.0] * 1023},
            {"id": 2, "knowledge_id": 2, "page_number": 1, "content": "hi",
             "file_name": "b.pptx", "embedding": [0.0] * 1024},
        ]

    monkeypatch.setattr(mod.PageTranscriptRetriever, "_load_candidates",
                        fake_candidates)

    class _Emb:
        @staticmethod
        async def get_or_compute_query_embedding(q):
            return [1.0] + [0.0] * 1023   # 与 id=1 正交满分, id=2 正交 0 分

    class _Gen:
        @staticmethod
        async def generate_embeddings(texts, for_query=False):
            return None

    import app.services.embedding_service as es
    monkeypatch.setattr(es, "get_or_compute_query_embedding",
                        _Emb.get_or_compute_query_embedding)
    monkeypatch.setattr(es, "generate_embeddings", _Gen.generate_embeddings)

    r = mod.PageTranscriptRetriever(db=None)
    hits = asyncio.run(r.search_pages("q", top_k=5))
    assert [h["page_transcript_id"] for h in hits] == [1], \
        "sim=0.0 的候选必须被 MIN_SIMILARITY 挡掉"
