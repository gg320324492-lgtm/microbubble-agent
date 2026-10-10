"""agent45 — 整页转写**词法**召回路单测 (PageTranscriptRetriever.search_pages_lexical)

背景 (agent44 实测缺口): 整页 embedding 把罕见拉丁词稀释进整页语义 ——
「只存在于页面转写的罕见词」探针 **0/6 命中 top-5**。本路用
``content_tsvector @@ plainto_tsquery('simple', ...)`` (罕见拉丁整词) +
``content ILIKE`` (中文子串) 把字面页捞回。

覆盖三件易错事:
1. **可见性边界与语义路逐字同款** (deleted_at / storage_mode / visibility)
2. **tsvector 命中排在 ILIKE-only 命中之前** (整词强于子串)
3. **反例 (库内不存在的串) 不返回** + ILIKE 通配符被清洗
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import test_async_session as async_session
from app.models.knowledge import Knowledge
from app.models.knowledge_page_transcript import KnowledgePageTranscript
from app.services.page_transcript_retriever import PageTranscriptRetriever


async def _mk_kb(db: AsyncSession, **kw) -> Knowledge:
    defaults = dict(
        title="a45-twin",
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


async def _mk_page(db, kid, page_number, content):
    row = KnowledgePageTranscript(
        knowledge_id=kid, page_number=page_number,
        content=content, char_count=len(content), blocked=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── 1. 基础: 罕见拉丁整词命中 (tsvector) ───────────────────────────────

@pytest.mark.asyncio
async def test_rare_latin_token_matched_by_tsvector():
    """连字符/下划线罕见词整词命中 —— 这是语义路 0/6 缺口的正解。"""
    async with async_session() as db:
        twin = await _mk_kb(db, title="a45-latin")
        row = await _mk_page(
            db, twin.id, 1,
            "Root_CD Thermomonas acidobacteria_subgroup_6_ge air-nanobubble",
        )
        # 干扰页: 只有高频子串 air (jieba 会被它稀释, tsvector 不会)
        other = await _mk_kb(db, title="a45-noise")
        await _mk_page(db, other.id, 1, "air quality inside the lab")

        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "air-nanobubble", top_k=5
        )
        ids = [h["page_transcript_id"] for h in hits]
        assert row.id in ids, "罕见整词 air-nanobubble 必须命中字面页"
        assert hits[0]["page_transcript_id"] == row.id
        assert hits[0]["lexical_match"] == "tsvector"


# ── 2. 中文子串 (ILIKE 兜底) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chinese_substring_matched_by_ilike():
    """PG simple 不切中文 → 中文子串靠 ILIKE。"""
    async with async_session() as db:
        twin = await _mk_kb(db, title="a45-zh")
        row = await _mk_page(db, twin.id, 2, "微纳米气泡的经济分析")
        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "纳米气泡", top_k=5
        )
        assert [h["page_transcript_id"] for h in hits] == [row.id]
        assert hits[0]["lexical_match"] == "ilike"


# ── 3. tsvector 命中排在 ILIKE-only 命中之前 ─────────────────────────────

@pytest.mark.asyncio
async def test_tsvector_ranks_before_ilike_only():
    async with async_session() as db:
        twin = await _mk_kb(db, title="a45-rank")
        # 页 A: 整词命中 (tsvector)
        page_a = await _mk_page(db, twin.id, 1, "nanobubble 综述")
        # 页 B: 仅子串命中 (ILIKE) —— 例如 "xxnanobubbleyy" 拆不开成整词
        page_b = await _mk_page(db, twin.id, 2, "MNBXnanobubbleXY 附录")

        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "nanobubble", top_k=5
        )
        ids = [h["page_transcript_id"] for h in hits]
        assert page_a.id in ids and page_b.id in ids
        assert ids.index(page_a.id) < ids.index(page_b.id), \
            "tsvector 整词命中必须排在 ILIKE-only 命中之前"


# ── 4. 可见性边界逐字同款 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lexical_visibility_boundaries():
    import inspect
    src = inspect.getsource(PageTranscriptRetriever.search_pages_lexical)
    for needle in (
        "kpt.blocked IS FALSE",
        "k.deleted_at IS NULL",
        "k.storage_mode = 'kb'",
        "k.visibility IN ('team', 'public')",
    ):
        assert needle in src, f"缺可见性边界: {needle}"


@pytest.mark.asyncio
async def test_lexical_excludes_private_and_deleted_parents():
    import datetime
    async with async_session() as db:
        ok = await _mk_kb(db, title="a45-ok")
        dead = await _mk_kb(db, title="a45-dead", deleted_at=datetime.datetime.now())
        priv = await _mk_kb(db, title="a45-priv", visibility="private")
        await _mk_page(db, ok.id, 1, "rareword_alpha_beta")
        await _mk_page(db, dead.id, 1, "rareword_alpha_beta")
        await _mk_page(db, priv.id, 1, "rareword_alpha_beta")

        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "rareword_alpha_beta", top_k=10
        )
        kids = {h["knowledge_id"] for h in hits}
        assert ok.id in kids
        assert dead.id not in kids
        assert priv.id not in kids


@pytest.mark.asyncio
async def test_lexical_excludes_blocked_rows():
    """blocked 行 content IS NULL —— 词法路也不会命中。"""
    async with async_session() as db:
        twin = await _mk_kb(db, title="a45-blocked")
        await _mk_page(db, twin.id, 1, "visible_body_term")
        db.add(KnowledgePageTranscript(
            knowledge_id=twin.id, page_number=2, content=None, char_count=None,
            blocked=True, block_reasons=["chrome_ratio=80%"],
        ))
        await db.commit()
        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "visible_body_term", top_k=5
        )
        assert all(h["page_number"] != 2 for h in hits)


# ── 5. 反例 + 通配符清洗 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_absent_term_returns_empty():
    async with async_session() as db:
        twin = await _mk_kb(db, title="a45-absent")
        await _mk_page(db, twin.id, 1, "some normal transcript text")
        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "zzqx_absent_probe_9911", top_k=5
        )
        assert hits == []


@pytest.mark.asyncio
async def test_ilike_wildcards_are_cleaned():
    """query 里的 % / _ 不能当通配符放大匹配面。"""
    async with async_session() as db:
        twin = await _mk_kb(db, title="a45-wildcard")
        await _mk_page(db, twin.id, 1, "abcdef total nonsense page")
        # 若 % 未被清洗, 这个 query 会匹配任意内容
        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "%", top_k=5
        )
        assert hits == [], "纯通配符 query 不得匹配所有页"


# ── 6. 空 query / top_k 边界 ────────────────────────────────────────────

def test_lexical_empty_query_returns_empty():
    import asyncio
    r = PageTranscriptRetriever(db=None)
    assert asyncio.run(r.search_pages_lexical("", top_k=5)) == []
    assert asyncio.run(r.search_pages_lexical("   ", top_k=5)) == []
    assert asyncio.run(r.search_pages_lexical("x", top_k=0)) == []


# ── 7. 结果形态与语义路兼容 (knowledge_id 合并键) ───────────────────────

@pytest.mark.asyncio
async def test_lexical_result_shape_matches_semantic():
    """hybrid_retriever hook 3b 按 knowledge_id 折算 —— 字段必须齐。"""
    async with async_session() as db:
        twin = await _mk_kb(db, title="a45-shape")
        await _mk_page(db, twin.id, 3, "shape_probe_token_xyz")
        hits = await PageTranscriptRetriever(db).search_pages_lexical(
            "shape_probe_token_xyz", top_k=5
        )
        assert hits
        h = hits[0]
        for key in (
            "id", "knowledge_id", "page_transcript_id", "page_number",
            "content", "similarity", "score", "retrieval_method",
        ):
            assert key in h, f"缺字段 {key}"
        assert h["id"] == twin.id  # 与第 5 路/语义路同款: id=knowledge_id
        assert h["retrieval_method"] == "page_transcript_lexical"


# ── 8. 配置项存在 (pin 槽位 + 词法开关) ──────────────────────────────────

def test_rag_config_has_lexical_and_pin_knobs():
    from app.rag import config as rc
    assert hasattr(rc, "PAGE_TRANSCRIPT_LEXICAL_ENABLED")
    assert hasattr(rc, "PAGE_TRANSCRIPT_PIN_SLOTS")
    assert isinstance(rc.PAGE_TRANSCRIPT_PIN_SLOTS, int)
    assert rc.PAGE_TRANSCRIPT_PIN_SLOTS >= 0
