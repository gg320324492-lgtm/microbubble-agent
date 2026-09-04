"""批次① 收藏个人化 (alembic 134) — drive_file_stars service 层测试 (2026-09-05)

覆盖:
- A star → A 视角 is_starred=True, B 视角 False; B 的 /starred 列表不含该文件
- toggle 取消 (本人视角 360°)
- batch_star_files 幂等 (重复调用不产生重复行; starred=False 未收藏 id 不报错)
- storage_mode != 'drive' 的 kb 行不参与收藏
- 回归锁: Knowledge.is_starred/starred_at legacy 列不再被 toggle 写入 (列值守恒)
- _to_item starred_ids 覆盖 (API 响应字段名不变, 语义 per-user)

DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import uuid as _uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.api.v1.drive_files import _to_item
from app.models.drive_file_star import DriveFileStar
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_service import DriveService


async def _mk_member(db, tag):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"st_{tag}_{u}", name=tag, password_hash="h",
        role="member", grade="测试", is_active=True, wechat_id=f"wx_st_{tag}_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _mk_file(db, owner, file_name, storage_mode="drive"):
    k = Knowledge(
        content="", title=file_name, storage_mode=storage_mode, file_name=file_name,
        file_path=f"drive-test/{file_name}" if storage_mode == "drive" else None,
        created_by=owner.id, visibility="team",
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@pytest_asyncio.fixture
async def star_env(db):
    a = await _mk_member(db, "ann")
    b = await _mk_member(db, "bob")
    f1 = await _mk_file(db, a, "notes.pdf")
    f2 = await _mk_file(db, b, "data.xlsx")
    kb = await _mk_file(db, a, "kb_card.md", storage_mode="kb")
    return {"db": db, "a": a, "b": b, "f1": f1, "f2": f2, "kb": kb,
            "svc_a": DriveService(db), "svc_b": DriveService(db)}


# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_toggle_is_per_user(star_env):
    """A star f1 → A 列表 is_starred=True, B 的列表 False 且 B/starred 不含"""
    e = star_env
    f, starred_a, ts_a = await e["svc_a"].toggle_star_file(e["f1"].id, current_user_id=e["a"].id)
    assert starred_a is True and ts_a is not None

    assert await e["svc_a"].get_starred_ids([e["f1"].id], e["a"].id) == {e["f1"].id}
    assert await e["svc_b"].get_starred_ids([e["f1"].id], e["b"].id) == set()

    a_items, a_total = await e["svc_a"].list_files(
        current_user_id=e["a"].id, starred_only=True, include_subfolders=True,
    )
    assert {k.id for k in a_items} == {e["f1"].id}

    b_items, b_total = await e["svc_b"].list_files(
        current_user_id=e["b"].id, starred_only=True, include_subfolders=True,
    )
    assert e["f1"].id not in {k.id for k in b_items}
    assert b_total == 0


@pytest.mark.asyncio
async def test_toggle_unstar(star_env):
    """本人再 toggle 一次 → 取消收藏 (star 行删除)"""
    e = star_env
    svc = e["svc_a"]
    await svc.toggle_star_file(e["f1"].id, current_user_id=e["a"].id)
    _, starred_now, ts_now = await svc.toggle_star_file(e["f1"].id, current_user_id=e["a"].id)
    assert starred_now is False and ts_now is None
    assert await svc.get_starred_ids([e["f1"].id], e["a"].id) == set()
    n = (await e["db"].execute(
        select(func.count(DriveFileStar.id)).where(DriveFileStar.file_id == e["f1"].id)
    )).scalar()
    assert n == 0


@pytest.mark.asyncio
async def test_legacy_columns_never_written(star_env):
    """回归锁: toggle 后 Knowledge.is_starred/starred_at legacy 列值守恒 (不再被写)"""
    e = star_env
    await e["svc_a"].toggle_star_file(e["f1"].id, current_user_id=e["a"].id)
    k = (await e["db"].execute(
        select(Knowledge).where(Knowledge.id == e["f1"].id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert k.is_starred is False
    assert k.starred_at is None


@pytest.mark.asyncio
async def test_batch_star_idempotent(star_env):
    """batch_star 重复调用: updated 数稳定, star 行不翻倍; kb 行/不存在 id 被跳过"""
    e = star_env
    ids = [e["f1"].id, e["f2"].id, e["kb"].id, 999999]

    n1 = await e["svc_a"].batch_star_files(ids, e["a"].id, starred=True)
    assert n1 == 2  # 仅 2 个 drive 行有效
    rows_a = (await e["db"].execute(
        select(DriveFileStar).where(DriveFileStar.member_id == e["a"].id)
    )).scalars().all()
    assert {r.file_id for r in rows_a} == {e["f1"].id, e["f2"].id}
    assert e["kb"].id not in {r.file_id for r in rows_a}

    n2 = await e["svc_a"].batch_star_files(ids, e["a"].id, starred=True)
    assert n2 == 2
    rows_a = (await e["db"].execute(
        select(DriveFileStar).where(DriveFileStar.member_id == e["a"].id)
    )).scalars().all()
    assert len(rows_a) == 2, "ON CONFLICT DO NOTHING 幂等: 不得产生重复行"

    n3 = await e["svc_a"].batch_star_files(ids, e["a"].id, starred=False)
    assert n3 == 2
    rows_a = (await e["db"].execute(
        select(DriveFileStar).where(DriveFileStar.member_id == e["a"].id)
    )).scalars().all()
    assert rows_a == []

    # 空列表
    assert await e["svc_a"].batch_star_files([], e["a"].id, starred=True) == 0


@pytest.mark.asyncio
async def test_toggle_rejects_non_drive_row(star_env):
    """kb 行 toggle → None (404 语义), 且不写 star 行"""
    e = star_env
    assert await e["svc_a"].toggle_star_file(e["kb"].id, current_user_id=e["a"].id) is None


@pytest.mark.asyncio
async def test_list_starred_default_sort_uses_own_star_time(star_env):
    """/starred 默认 sort=starred_at desc → 标量子查询走本人 star 时间, 不炸且倒序"""
    e = star_env
    await e["svc_a"].toggle_star_file(e["f1"].id, current_user_id=e["a"].id)
    await e["svc_a"].toggle_star_file(e["f2"].id, current_user_id=e["a"].id)
    items, total = await e["svc_a"].list_starred(current_user_id=e["a"].id)
    assert total == 2
    assert {k.id for k in items} == {e["f1"].id, e["f2"].id}
    # 后收藏的 f2 排在前 (desc)
    assert items[0].id == e["f2"].id


@pytest.mark.asyncio
async def test_to_item_starred_ids_override(star_env):
    """_to_item: 传 starred_ids → per-user 视图覆盖; 不传 → legacy fallback"""
    e = star_env
    k = e["f1"]
    assert _to_item(k).is_starred is False              # legacy 列 (False)
    assert _to_item(k, starred_ids={k.id}).is_starred is True
    assert _to_item(k, starred_ids=set()).is_starred is False
    assert _to_item(k, starred_ids=None).is_starred == bool(k.is_starred)
