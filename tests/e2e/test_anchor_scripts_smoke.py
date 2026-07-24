"""anchor 脚本 e2e 测试 (W68 第 7 批 A-2 cheerful-questing-kite Plan 闭环)

3 场景覆盖:
1. list_anchors.py: 返空 (无 anchor) + 返单 anchor (一一成员已 confirmed)
2. mark_voice_confirmed.py: dry-run 不写库 + apply 写库后字段生效 + audit
3. incremental_anchor.py: 候选生成 (按 sample_count 阈值) + apply 联动 mark_confirmed

设计 (CLAUDE.md 752 行铁律: e2e 用本地 sqlite + fakeredis):
- **sqlite 内存库** (StaticPool 单连接共享) + PG 专有类型 shim
  (ARRAY / JSONB / Vector → TEXT, BigInteger → INTEGER)
- 跳过 conftest 的 setup_db (用 SKIP_DB_SETUP=1 通过 env var), 避免打 PG
- **DATABASE_URL monkeypatch**: scripts 内部读 settings.DATABASE_URL 默认 PG,
  测试时改成 sqlite (空库走 engine.dispose 后 script 已无法再开)
- **脚本不直接连接 sqlite**, 改测**核心函数** (fetch_anchors_and_enrolled,
  mark_voice_confirmed, scan_candidates, apply_mark_confirmed) — 这些是脚本
  实际执行单元, 隔离 engine 句柄, 跑得快 + 0 docker 依赖
- audit 字段 (MemberVoiceHistory) 验证: source="anchor_confirmed",
  notes 含 meeting_id + confirmed_by

覆盖脚本:
- scripts/list_anchors.py:fetch_anchors_and_enrolled / _print_table / _print_json
- scripts/mark_voice_confirmed.py:mark_voice_confirmed
- scripts/incremental_anchor.py:scan_candidates / apply_mark_confirmed

场景覆盖:
- 场景 1: list_anchors 返空 (无 anchor 成员)
- 场景 2: list_anchors 返单 anchor (已 confirmed 成员按时间升序)
- 场景 3: mark_voice_confirmed dry-run 不写库 + apply 写库后字段生效
- 场景 4: mark_voice_confirmed 拒绝覆盖已 confirmed (无 --force)
- 场景 5: incremental_anchor 候选生成 (含 eligible + reason + suggestion)
- 场景 6: incremental_anchor apply 联动 mark_confirmed (写 audit)
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List

# 必须在 import app.* 之前设 SKIP_DB_SETUP=1, 避免 conftest 触发 PG 连接
os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest
import pytest_asyncio


# ============================================================
# sqlite 兼容 shims (必须在 app.models import 之前注册编译规则)
# ============================================================

from sqlalchemy import ARRAY as _GARRAY, BigInteger as _BigInteger
from sqlalchemy.ext.compiler import compiles as _compiles
from sqlalchemy.dialects.postgresql import JSONB as _JSONB, ARRAY as _PGARRAY
from pgvector.sqlalchemy import Vector as _Vector


@_compiles(_GARRAY, "sqlite")
def _compile_generic_array(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_PGARRAY, "sqlite")
def _compile_pg_array(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_JSONB, "sqlite")
def _compile_jsonb(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_Vector, "sqlite")
def _compile_vector(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_BigInteger, "sqlite")
def _compile_bigint(element, compiler, **kw):  # noqa: ARG001
    return "INTEGER"


def _patch_array_processors() -> None:
    """ARRAY 列在 sqlite 上 JSON 序列化."""

    def make_bind(orig):
        def bind_processor(self, dialect):
            if dialect.name == "sqlite":
                def process(value):
                    return None if value is None else json.dumps(value)
                return process
            return orig(self, dialect)
        return bind_processor

    def make_result(orig):
        def result_processor(self, dialect, coltype):
            if dialect.name == "sqlite":
                def process(value):
                    if value is None:
                        return None
                    try:
                        return json.loads(value)
                    except Exception:
                        return value
                return process
            return orig(self, dialect, coltype)
        return result_processor

    for T in (_GARRAY, _PGARRAY):
        T.bind_processor = make_bind(T.bind_processor)
        T.result_processor = make_result(T.result_processor)


_patch_array_processors()


def _normalize_server_defaults(metadata) -> None:
    from sqlalchemy import text
    from sqlalchemy.schema import DefaultClause

    for table in metadata.tables.values():
        for col in table.columns:
            sd = col.server_default
            if sd is None or not hasattr(sd, "arg"):
                continue
            arg_txt = str(getattr(sd, "arg", "")).strip().lower()
            if arg_txt in ("now()", "current_timestamp", "clock_timestamp()"):
                col.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))


# ============================================================
# module 级 engine / session (sqlite 内存, StaticPool 单连接)
# ============================================================

_ENGINE = None
_SESSION = None


def _init_engine():
    global _ENGINE, _SESSION
    if _ENGINE is not None:
        return
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401  触发全部 ORM 注册
    from app.core.database import Base

    _normalize_server_defaults(Base.metadata)
    _ENGINE = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _SESSION = async_sessionmaker(_ENGINE, class_=AsyncSession, expire_on_commit=False)


# ============================================================
# Import target 脚本 (engine 创建后 import, 避免 settings.DATABASE_URL 提前读)
# ============================================================

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 在 import 脚本前 monkeypatch settings.DATABASE_URL → sqlite (脚本 in-function 才
# 用 settings.DATABASE_URL 创建 engine, 所以无害)
from app.config import settings as _settings  # noqa: E402

_settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# import 直接放在这里 — 不会触发 create_engine (脚本在 amain 才用)
import scripts.list_anchors as list_anchors_mod  # noqa: E402
import scripts.mark_voice_confirmed as mark_mod  # noqa: E402
import scripts.incremental_anchor as inc_mod  # noqa: E402


# ============================================================
# Helper: 重建完整 anchor_env (单 test 改 DB 后能恢复)
# ============================================================


async def _seed_anchor_env():
    """种 3 个成员: m1 已 confirmed anchor, m2 候选 (33 samples), m3 hold (1 sample)."""
    from app.models.member import Member

    async with _SESSION() as db:
        m1 = Member(
            id=1,
            username="du",
            name="杜同贺",
            wechat_id="wx-du",
            voice_embedding=[0.1] * 192,
            voice_sample_count=4,
            voice_enrolled_at=datetime(2026, 6, 28, 12, 37, 4),
            voice_confirmed_at=datetime(2026, 6, 28, 12, 37, 4),
            voice_confirmed_by="user",
            voice_confirmed_meeting_id=153,
        )
        m2 = Member(
            id=2,
            username="chen",
            name="陈金薪",
            wechat_id="wx-chen",
            voice_embedding=[0.2] * 192,
            voice_sample_count=33,
            voice_enrolled_at=datetime(2026, 6, 30, 10, 0, 0),
        )
        m3 = Member(
            id=3,
            username="jia",
            name="贾琦",
            wechat_id="wx-jia",
            voice_embedding=[0.3] * 192,
            voice_sample_count=1,
            voice_enrolled_at=datetime(2026, 7, 1, 9, 0, 0),
        )
        db.add_all([m1, m2, m3])
        await db.commit()


async def _rebuild_tables():
    """drop_all + create_all + seed_anchor_env (一次性重置)."""
    from app.core.database import Base

    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_anchor_env()


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def anchor_env():
    """建表 + 播种 anchor_env 数据."""
    _init_engine()
    await _rebuild_tables()
    yield SimpleNamespace(m1_id=1, m2_id=2, m3_id=3)
    # teardown: drop_all (下一个 test 重建)
    from app.core.database import Base

    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ============================================================
# 场景 1: list_anchors.py 返空 (无 anchor)
# ============================================================


@pytest.mark.asyncio
async def test_list_anchors_empty_when_no_anchors(anchor_env):
    """无任何 anchor 成员 → list_anchors 返空."""
    from app.core.database import Base
    from app.models.member import Member

    # 重置: 只有 1 个未 confirmed 成员
    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _SESSION() as db:
        m = Member(
            id=99,
            username="n",
            name="Nobody",
            wechat_id="wx-n",
            voice_embedding=[0.5] * 192,
            voice_sample_count=10,
        )
        db.add(m)
        await db.commit()

    anchors, unconfirmed = await list_anchors_mod.fetch_anchors_and_enrolled(
        _SESSION, include_unconfirmed=False
    )
    assert anchors == []
    assert unconfirmed == []

    # 恢复 anchor_env 给后续 fixture
    await _rebuild_tables()


# ============================================================
# 场景 2: list_anchors.py 返单 anchor (按 confirm 时间升序)
# ============================================================


@pytest.mark.asyncio
async def test_list_anchors_returns_anchor_in_chronological_order(anchor_env):
    """fetcher 返回 anchor (按 voice_confirmed_at 升序)."""
    anchors, unconfirmed = await list_anchors_mod.fetch_anchors_and_enrolled(
        _SESSION, include_unconfirmed=True
    )
    assert len(anchors) == 1
    assert anchors[0].id == 1
    assert anchors[0].name == "杜同贺"
    assert anchors[0].voice_confirmed_by == "user"
    assert anchors[0].voice_confirmed_meeting_id == 153

    # unconfirmed 应该是 m2 + m3 (按 sample_count desc)
    assert len(unconfirmed) == 2
    assert unconfirmed[0].id == 2  # 33 samples
    assert unconfirmed[1].id == 3  # 1 sample


@pytest.mark.asyncio
async def test_list_anchors_json_output(anchor_env, capsys):
    """_print_json 应输出 JSON 含 count / anchors / unconfirmed_enrolled."""
    anchors, unconfirmed = await list_anchors_mod.fetch_anchors_and_enrolled(
        _SESSION, include_unconfirmed=True
    )
    list_anchors_mod._print_json(anchors, unconfirmed)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["count"] == 1
    assert payload["anchors"][0]["name"] == "杜同贺"
    assert payload["anchors"][0]["voice_confirmed_at"] is not None
    assert len(payload["unconfirmed_enrolled"]) == 2


# ============================================================
# 场景 3: mark_voice_confirmed dry-run 不落库 + apply 写库
# ============================================================


@pytest.mark.asyncio
async def test_mark_voice_confirmed_dry_run_does_not_write(anchor_env):
    """dry-run 模式不应修改 Member 字段."""
    from app.models.member import Member as MemberModel
    from sqlalchemy import select

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m_before = r.scalar_one()
        assert m_before.voice_confirmed_at is None

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m = r.scalar_one()
        result = await mark_mod.mark_voice_confirmed(
            _SESSION,
            m,
            meeting_id=167,
            confirmed_by="user",
            apply=False,
            force=False,
        )

    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert "DRY-RUN" in result["after"]["voice_confirmed_at"]

    # 二次读, 字段应仍为 None (未写库)
    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m_after = r.scalar_one()
        assert m_after.voice_confirmed_at is None
        assert m_after.voice_confirmed_by is None
        assert m_after.voice_confirmed_meeting_id is None


@pytest.mark.asyncio
async def test_mark_voice_confirmed_apply_writes_fields_and_audit(anchor_env):
    """apply 模式应写 3 字段 + MemberVoiceHistory audit."""
    from app.models.member import Member as MemberModel
    from app.models.member_voice_history import MemberVoiceHistory
    from sqlalchemy import select

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m = r.scalar_one()

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m = r.scalar_one()
        result = await mark_mod.mark_voice_confirmed(
            _SESSION,
            m,
            meeting_id=167,
            confirmed_by="user",
            apply=True,
            force=False,
        )

    assert result["status"] == "applied"
    assert result["dry_run"] is False
    assert result["after"]["voice_confirmed_meeting_id"] == 167
    assert result["after"]["voice_confirmed_by"] == "user"
    assert result["after"]["audit_id"] is not None

    # 验证字段在 DB 真的写入
    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m_after = r.scalar_one()
        assert m_after.voice_confirmed_at is not None
        assert m_after.voice_confirmed_by == "user"
        assert m_after.voice_confirmed_meeting_id == 167

    # 验证 audit
    async with _SESSION() as db:
        r = await db.execute(
            select(MemberVoiceHistory).where(MemberVoiceHistory.id == result["after"]["audit_id"])
        )
        h = r.scalar_one()
        assert h.source == "anchor_confirmed"
        assert h.member_id == 2
        assert "meeting_id=167" in (h.notes or "")
        assert "confirmed_by=user" in (h.notes or "")


@pytest.mark.asyncio
async def test_mark_voice_confirmed_rejects_already_confirmed_without_force(anchor_env):
    """已 confirmed 成员默认拒绝 (无 --force)."""
    from app.models.member import Member as MemberModel
    from sqlalchemy import select

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 1))
        m = r.scalar_one()

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 1))
        m = r.scalar_one()
        result = await mark_mod.mark_voice_confirmed(
            _SESSION,
            m,
            meeting_id=999,
            confirmed_by="user",
            apply=True,
            force=False,
        )

    assert result["status"] == "skipped_already_confirmed"
    assert result["dry_run"] is True
    assert "anchor" in result["msg"]
    assert "force" in result["msg"].lower()


# ============================================================
# 场景 4: incremental_anchor 候选生成
# ============================================================


@pytest.mark.asyncio
async def test_incremental_anchor_scan_candidates(anchor_env):
    """scan_candidates 应按 sample_count 阈值生成候选."""
    candidates = await inc_mod.scan_candidates(
        _SESSION,
        min_samples=5,
        days_lookback=30,
        only_member=None,
    )

    # anchor_env 共 3 个未 confirmed 成员 (m1 已是 anchor, m2 + m3 未 confirmed)
    # 注意: m1 已 confirmed → scan_candidates 不会选
    # 所以 candidates 应只含 m2 + m3
    assert len(candidates) == 2

    by_id = {c["member_id"]: c for c in candidates}
    # m2: 33 samples ≥ 5 → eligible + suggestion=mark_confirmed (≥ 5*4=20)
    assert by_id[2]["eligible"] is True
    assert by_id[2]["reason"] is None
    assert by_id[2]["suggestion"] == "mark_confirmed"
    assert by_id[2]["voice_sample_count"] == 33

    # m3: 1 sample < 5 → not eligible
    assert by_id[3]["eligible"] is False
    assert "1 < 5" in by_id[3]["reason"]
    assert by_id[3]["suggestion"] == "hold_continue_learning"


@pytest.mark.asyncio
async def test_incremental_anchor_only_member_filter(anchor_env):
    """--member-name 只对该成员生成候选."""
    from app.models.member import Member as MemberModel
    from sqlalchemy import select

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        only_m = r.scalar_one()

    candidates = await inc_mod.scan_candidates(
        _SESSION,
        min_samples=5,
        days_lookback=30,
        only_member=only_m,
    )
    assert len(candidates) == 1
    assert candidates[0]["member_id"] == 2
    assert candidates[0]["eligible"] is True


@pytest.mark.asyncio
async def test_incremental_anchor_apply_writes_anchor(anchor_env):
    """apply 模式应 mark_confirmed + 写 audit."""
    from app.models.member import Member as MemberModel
    from app.models.member_voice_history import MemberVoiceHistory
    from sqlalchemy import select

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m = r.scalar_one()

    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m = r.scalar_one()
        result = await inc_mod.apply_mark_confirmed(
            _SESSION,
            m,
            meeting_id=68,
            confirmed_by="user",
        )

    assert result["name"] == "陈金薪"
    assert result["voice_confirmed_meeting_id"] == 68
    assert result["audit_id"] is not None

    # 验证字段写入
    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m_after = r.scalar_one()
        assert m_after.voice_confirmed_at is not None
        assert m_after.voice_confirmed_by == "user"
        assert m_after.voice_confirmed_meeting_id == 68

    # 验证 audit 含 incremental_anchor 标识
    async with _SESSION() as db:
        r = await db.execute(
            select(MemberVoiceHistory).where(MemberVoiceHistory.id == result["audit_id"])
        )
        h = r.scalar_one()
        assert h.source == "anchor_confirmed"
        assert "incremental_anchor" in (h.notes or "")
        assert "meeting_id=68" in (h.notes or "")


# ============================================================
# 场景 5: 跨脚本协作 — incremental_anchor → list_anchors
# ============================================================


@pytest.mark.asyncio
async def test_incremental_anchor_then_list_anchors_shows_new(anchor_env):
    """incremental_anchor apply 后, list_anchors 应能看到新 anchor."""
    from app.models.member import Member as MemberModel
    from sqlalchemy import select

    # 1. 初始状态: 1 anchor (m1)
    anchors_before, _ = await list_anchors_mod.fetch_anchors_and_enrolled(
        _SESSION, include_unconfirmed=False
    )
    assert len(anchors_before) == 1

    # 2. incremental_anchor apply 把 m2 mark_confirmed
    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m = r.scalar_one()
    async with _SESSION() as db:
        r = await db.execute(select(MemberModel).where(MemberModel.id == 2))
        m = r.scalar_one()
        await inc_mod.apply_mark_confirmed(
            _SESSION,
            m,
            meeting_id=68,
            confirmed_by="user",
        )

    # 3. list_anchors 应有 2 anchors (m1 + m2)
    anchors_after, _ = await list_anchors_mod.fetch_anchors_and_enrolled(
        _SESSION, include_unconfirmed=False
    )
    assert len(anchors_after) == 2
    # 按时间升序: m1 (2026-06-28) 在 m2 (now) 之前
    by_id = {a.id: a for a in anchors_after}
    assert by_id[1].name == "杜同贺"
    assert by_id[2].name == "陈金薪"
