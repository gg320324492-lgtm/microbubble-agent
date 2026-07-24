"""tests/test_drive_v2_pr17_dedupe.py — Drive v2 PR17 文件秒传 (hash dedupe) e2e 测试 (2026-07-24, W68 第 14 批 B-1)

5/5 场景:
1. 首次上传 hash=abc → check_dedupe MISS (返回 None, 走真实上传)
2. 重复上传 hash=abc (同用户) → check_dedupe HIT + mark_dedupe_hit → dedupe_count+1
3. 不同 hash=def → check_dedupe MISS (返回 None)
4. 同 hash 跨用户 → check_dedupe MISS (user_id 隔离, 安全边界)
5. 已软删 file 的 hash → check_dedupe MISS (deleted_at IS NULL 过滤)

设计说明 (W68 第 14 批 B-1):
- 自包含 fixtures (owner / second_user + Knowledge drive 文件), 不依赖 conftest.test_member
  原因: conftest.test_member 在 alembic 057 (wechat_id NOT NULL) 之后未更新 (pre-existing infra bug).
- 用 pytest_asyncio fixture 自管理 transaction + 完整 teardown (SET session_replication_role='replica').
- 直接测 service 层 check_dedupe / mark_dedupe_hit / find_files_by_hash (纯 async, 无 HTTP 依赖).

依赖:
- service: app/services/drive_dedupe_service.py
- alembic: 078_drive_dedupe_audit.py (drive_dedupe_count + drive_dedupe_first_hit_at)
- 已有列: knowledge.file_hash (alembic 044)
"""
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete as sql_delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  # 触发所有 model 注册
from app.core.security import get_password_hash
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_dedupe_service import (
    DriveDedupeServiceError,
    check_dedupe,
    compute_bytes_hash,
    compute_file_hash,
    find_files_by_hash,
    mark_dedupe_hit,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:microbubble2026@db:5432/microbubble_test",
)

# 固定 64-char sha256 hex 常量 (稳定命中断言)
HASH_ABC = "a" * 64
HASH_DEF = "d" * 64


# ==========================================================================
# 自包含 fixtures
# ==========================================================================


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine):
    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as session:
        yield session


async def _make_member(db, tag):
    member = Member(
        username=f"pr17_{tag}_{uuid.uuid4().hex[:8]}",
        name=f"PR17 {tag}",
        password_hash=get_password_hash("test123456"),
        role="member",
        grade="研一",
        wechat_id=f"wx_pr17_{tag}_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@pytest_asyncio.fixture
async def owner(db):
    member = await _make_member(db, "owner")
    yield member
    try:
        await db.execute(text("SET session_replication_role = 'replica'"))
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        await db.rollback()


@pytest_asyncio.fixture
async def second_user(db):
    member = await _make_member(db, "second")
    yield member
    try:
        await db.execute(text("SET session_replication_role = 'replica'"))
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        await db.rollback()


async def _make_drive_file(db, *, owner_id, file_hash, deleted=False, name="doc.pdf"):
    """创建一条活跃 drive Knowledge 文件 (可选软删)"""
    from datetime import datetime

    knowledge = Knowledge(
        title=f"pr17 {name}",
        content=f"[drive upload] {name}",
        file_path=f"drive/{owner_id}/{uuid.uuid4().hex}/{name}",
        file_name=name,
        file_type=".pdf",
        file_size=5 * 1024 * 1024,
        file_hash=file_hash,
        is_latest=True,
        version_number=1,
        storage_mode="drive",
        visibility="team",
        created_by=owner_id,
        deleted_at=datetime.utcnow() if deleted else None,
    )
    db.add(knowledge)
    await db.commit()
    await db.refresh(knowledge)
    return knowledge


@pytest_asyncio.fixture
async def cleanup_files(db):
    """收集测试建的 Knowledge id, teardown 时物理删"""
    ids = []
    yield ids
    if ids:
        try:
            await db.execute(text("SET session_replication_role = 'replica'"))
            await db.execute(sql_delete(Knowledge).where(Knowledge.id.in_(ids)))
            await db.commit()
        except Exception:
            await db.rollback()


# ==========================================================================
# 测试: compute hash helpers (不依赖 DB)
# ==========================================================================


def test_compute_bytes_hash_sha256():
    """sha256 hex 长度 64 + 稳定"""
    h1 = compute_bytes_hash(b"hello world")
    h2 = compute_bytes_hash(b"hello world")
    assert len(h1) == 64
    assert h1 == h2
    assert h1 != compute_bytes_hash(b"different")


def test_compute_file_hash_missing_raises(tmp_path):
    """文件不存在 → DriveDedupeServiceError(404)"""
    with pytest.raises(DriveDedupeServiceError) as exc:
        compute_file_hash(str(tmp_path / "nope.bin"))
    assert exc.value.status_code == 404


def test_compute_file_hash_matches_bytes(tmp_path):
    """流式文件 hash == 内存字节 hash"""
    p = tmp_path / "f.bin"
    data = b"content-for-hash" * 1000
    p.write_bytes(data)
    assert compute_file_hash(str(p)) == compute_bytes_hash(data)


def test_check_dedupe_invalid_hash_raises():
    """空 / 非法长度 hash → DriveDedupeServiceError(400)"""
    import asyncio

    async def _run():
        # _normalize_hash 在 check_dedupe 内部先跑, DB 不会被触碰
        with pytest.raises(DriveDedupeServiceError) as e1:
            await check_dedupe(None, 1, "")
        assert e1.value.status_code == 400
        with pytest.raises(DriveDedupeServiceError) as e2:
            await check_dedupe(None, 1, "tooshort")
        assert e2.value.status_code == 400

    asyncio.get_event_loop().run_until_complete(_run())


# ==========================================================================
# 场景 1-5: check_dedupe DB 行为 (需 PostgreSQL)
# ==========================================================================


@pytest.mark.asyncio
async def test_scenario_1_first_upload_miss(db, owner, cleanup_files):
    """场景 1: 首次上传 hash=abc → MISS (库里没有 → 返回 None)"""
    hit = await check_dedupe(db, owner.id, HASH_ABC)
    assert hit is None


@pytest.mark.asyncio
async def test_scenario_2_duplicate_upload_hit(db, owner, cleanup_files):
    """场景 2: 重复上传 hash=abc (同用户) → HIT + mark_dedupe_hit → count+1"""
    f = await _make_drive_file(db, owner_id=owner.id, file_hash=HASH_ABC)
    cleanup_files.append(f.id)

    hit = await check_dedupe(db, owner.id, HASH_ABC)
    assert hit is not None
    assert hit.id == f.id
    assert (hit.drive_dedupe_count or 0) == 0  # 尚未 mark

    new_count = await mark_dedupe_hit(db, f.id)
    assert new_count == 1

    # 再命中一次 → count=2 + first_hit_at 不变
    await db.refresh(f)
    first_hit = f.drive_dedupe_first_hit_at
    assert first_hit is not None
    new_count2 = await mark_dedupe_hit(db, f.id)
    assert new_count2 == 2
    await db.refresh(f)
    assert f.drive_dedupe_first_hit_at == first_hit  # 首次时间戳不被覆盖


@pytest.mark.asyncio
async def test_scenario_3_different_hash_miss(db, owner, cleanup_files):
    """场景 3: 库里有 hash=abc, 查 hash=def → MISS"""
    f = await _make_drive_file(db, owner_id=owner.id, file_hash=HASH_ABC)
    cleanup_files.append(f.id)

    hit = await check_dedupe(db, owner.id, HASH_DEF)
    assert hit is None


@pytest.mark.asyncio
async def test_scenario_4_cross_user_no_dedupe(db, owner, second_user, cleanup_files):
    """场景 4: owner 持有 hash=abc, second_user 查同 hash → MISS (user_id 隔离)"""
    f = await _make_drive_file(db, owner_id=owner.id, file_hash=HASH_ABC)
    cleanup_files.append(f.id)

    # second_user 不该秒传命中 owner 的文件
    hit = await check_dedupe(db, second_user.id, HASH_ABC)
    assert hit is None

    # 但审计工具 find_files_by_hash 应能发现跨用户重复
    others = await find_files_by_hash(db, HASH_ABC, exclude_user_id=second_user.id)
    assert any(o.id == f.id for o in others)


@pytest.mark.asyncio
async def test_scenario_5_soft_deleted_no_dedupe(db, owner, cleanup_files):
    """场景 5: 已软删 file 的 hash → MISS (deleted_at IS NULL 过滤)"""
    f = await _make_drive_file(
        db, owner_id=owner.id, file_hash=HASH_ABC, deleted=True
    )
    cleanup_files.append(f.id)

    hit = await check_dedupe(db, owner.id, HASH_ABC)
    assert hit is None


@pytest.mark.asyncio
async def test_mark_dedupe_hit_missing_raises(db):
    """mark_dedupe_hit 不存在 id → DriveDedupeServiceError(404)"""
    with pytest.raises(DriveDedupeServiceError) as exc:
        await mark_dedupe_hit(db, 999_999_999)
    assert exc.value.status_code == 404
