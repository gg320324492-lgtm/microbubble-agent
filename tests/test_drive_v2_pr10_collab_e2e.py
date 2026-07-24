"""Drive v2 PR10 — 协同编辑 e2e 测试 (2026-07-24, W68 第 7 批 B-1)

6 场景 (真实 sqlite + fakeredis, 真 pycrdt merge):
1. get_or_create: 新 file_id → INSERT 空行 + 返 b""; 二次调用返同一行
2. apply_op: 真 pycrdt op apply + snapshot 落库 + op log 落库
3. get_snapshot: 返最新全量 update, 客户端可重建内容
4. subscribe_room: fakeredis pub/sub, publish → subscribe 收到 (跳过自己 origin)
5. flush_task: flush_ydoc_state_to_db(state=None) 从 op log 重放刷盘
6. crash_recovery: 清空 snapshot 后 recover_from_crash 从 op log 重建内容一致

跑法 (本地, 不需 docker):
    cd <worktree> && python -m pytest tests/test_drive_v2_pr10_collab_e2e.py -v

设计要点:
- sqlite 不支持 ''::bytea server_default → 用 sqlite 兼容 raw DDL 建表 (不用 create_all)
- fakeredis.aioredis 提供真 pub/sub (与生产 redis.asyncio 接口一致)
- pycrdt 真 apply_update, 验证 CRDT 收敛 + 内容不丢

参考:
- tests/test_drive_v2_pr10_collab_smoke.py (W68 第 5 批 stub smoke)
- app/services/drive_collab_service.py
- app/services/drive_collab_tasks.py
"""
import asyncio
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from app.services.drive_collab_service import (
    DriveCollabService,
    InvalidOpError,
    room_channel,
)

pytestmark = pytest.mark.asyncio


# ============================================================
# sqlite 兼容建表 (绕开 ''::bytea server_default)
# ============================================================
_CREATE_DRIVE_DOCUMENTS = """
CREATE TABLE drive_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL UNIQUE,
    ydoc_state BLOB NOT NULL DEFAULT '',
    ops_count BIGINT NOT NULL DEFAULT 0,
    version_number INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    last_edited_by INTEGER,
    last_edited_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_DRIVE_DOC_OP_LOGS = """
CREATE TABLE drive_doc_op_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    op BLOB NOT NULL,
    client_id BIGINT NOT NULL,
    user_id INTEGER,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


@pytest_asyncio.fixture
async def db():
    """内存 sqlite session (每 test 独立)"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_DRIVE_DOCUMENTS))
        await conn.execute(text(_CREATE_DRIVE_DOC_OP_LOGS))
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis():
    """fakeredis 异步 client (真 pub/sub)"""
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


def _make_op(text_content: str) -> bytes:
    """用 pycrdt 生成一个插入 text_content 的全量 update 字节"""
    import pycrdt

    doc = pycrdt.Doc()
    t = doc.get("content", type=pycrdt.Text)
    t += text_content
    return doc.get_update()


# ============================================================
# 场景 1: get_or_create
# ============================================================
async def test_get_or_create_ydoc_state(db):
    """新 file_id → INSERT 空行 + 返 b""; 二次调用不重复 INSERT"""
    state = await DriveCollabService.get_or_create_ydoc_state(db, file_id=101)
    assert state == b"", "新 file_id 应返回空字节"

    # 行已创建
    row = (await db.execute(
        text("SELECT COUNT(*) FROM drive_documents WHERE file_id=101")
    )).scalar()
    assert row == 1, "应创建 1 行"

    # 二次调用不重复 INSERT
    state2 = await DriveCollabService.get_or_create_ydoc_state(db, file_id=101)
    assert state2 == b""
    row2 = (await db.execute(
        text("SELECT COUNT(*) FROM drive_documents WHERE file_id=101")
    )).scalar()
    assert row2 == 1, "二次调用不应重复 INSERT"


# ============================================================
# 场景 2: apply_op
# ============================================================
async def test_apply_remote_op(db):
    """真 pycrdt op apply + snapshot 落库 + op log 落库"""
    import pycrdt

    op = _make_op("hello")
    new_state = await DriveCollabService.apply_remote_op(
        db, file_id=102, op_bytes=op, client_id=42, user_id=7,
    )
    assert new_state, "apply 后应返回非空 state"

    # snapshot 可重建内容
    doc = pycrdt.Doc()
    doc.apply_update(new_state)
    assert str(doc.get("content", type=pycrdt.Text)) == "hello"

    # op log 落库
    op_count = (await db.execute(
        text("SELECT COUNT(*) FROM drive_doc_op_logs WHERE file_id=102")
    )).scalar()
    assert op_count == 1, "应落 1 条 op log"

    # ops_count + last_edited_by
    row = (await db.execute(text(
        "SELECT ops_count, last_edited_by FROM drive_documents WHERE file_id=102"
    ))).first()
    assert row[0] == 1, "ops_count 应为 1"
    assert row[1] == 7, "last_edited_by 应为 user_id"

    # 空 op 抛 InvalidOpError
    with pytest.raises(InvalidOpError):
        await DriveCollabService.apply_remote_op(db, file_id=102, op_bytes=b"", client_id=42)


# ============================================================
# 场景 3: get_snapshot
# ============================================================
async def test_get_snapshot(db):
    """连续 apply 2 个 op, snapshot 含全部内容 (CRDT 收敛)"""
    import pycrdt

    # 客户端 1 插 "foo"
    op1 = _make_op("foo")
    await DriveCollabService.apply_remote_op(db, file_id=103, op_bytes=op1, client_id=1, user_id=1)

    # 客户端 2 (独立 doc) 插 "bar", 拿其 update apply
    op2 = _make_op("bar")
    await DriveCollabService.apply_remote_op(db, file_id=103, op_bytes=op2, client_id=2, user_id=2)

    snapshot = await DriveCollabService.get_snapshot(db, file_id=103)
    doc = pycrdt.Doc()
    doc.apply_update(snapshot)
    merged = str(doc.get("content", type=pycrdt.Text))
    assert "foo" in merged, f"应含 foo, 实际 {merged!r}"
    assert "bar" in merged, f"应含 bar, 实际 {merged!r}"

    # export_text 一致
    exported = await DriveCollabService.export_text(db, file_id=103)
    assert exported == merged


# ============================================================
# 场景 4: subscribe_room (fakeredis pub/sub)
# ============================================================
async def test_subscribe_and_publish_room(fake_redis):
    """publish → subscribe 收到; 跳过自己 origin 逻辑由调用方处理, 这里验证扇出"""
    received = []

    async def _consumer():
        async for origin_cid, op_bytes in DriveCollabService.subscribe_to_room(fake_redis, 200):
            received.append((origin_cid, op_bytes))
            if len(received) >= 2:
                break

    consumer = asyncio.create_task(_consumer())
    await asyncio.sleep(0.1)  # 等订阅就绪

    await DriveCollabService.publish_op_to_room(fake_redis, 200, b"\x01\x02op-A", origin_client_id=11)
    await DriveCollabService.publish_op_to_room(fake_redis, 200, b"\x03\x04op-B", origin_client_id=22)

    await asyncio.wait_for(consumer, timeout=3.0)

    assert len(received) == 2, f"应收到 2 条, 实际 {len(received)}"
    assert received[0] == (11, b"\x01\x02op-A")
    assert received[1] == (22, b"\x03\x04op-B")


async def test_room_channel_naming():
    """频道名 helper"""
    assert room_channel(555) == "drive:collab:room:555"


# ============================================================
# 场景 5: flush task (从 op log 重放刷盘)
# ============================================================
async def test_flush_ydoc_state_from_oplog(db):
    """flush_ydoc_state_to_db(state=None) 从 op log 重建后刷盘"""
    import pycrdt

    # 落 2 条 op log, 但故意把 snapshot 清空模拟未刷盘
    op1 = _make_op("aaa")
    await DriveCollabService.apply_remote_op(db, file_id=104, op_bytes=op1, client_id=1, user_id=1)
    op2 = _make_op("bbb")
    await DriveCollabService.apply_remote_op(db, file_id=104, op_bytes=op2, client_id=2, user_id=2)

    # 清空 snapshot (模拟崩溃 / 刷盘丢失)
    await db.execute(text("UPDATE drive_documents SET ydoc_state=x'' WHERE file_id=104"))
    await db.commit()

    # flush(state=None) 从 op log 重放刷盘
    ok = await DriveCollabService.flush_ydoc_state_to_db(db, file_id=104, state=None, version=5)
    assert ok is True

    row = (await db.execute(text(
        "SELECT ydoc_state, version_number FROM drive_documents WHERE file_id=104"
    ))).first()
    rebuilt = bytes(row[0])
    assert len(rebuilt) > 0, "刷盘后 snapshot 应非空"
    assert row[1] == 5, "version_number 应更新为 5"

    doc = pycrdt.Doc()
    doc.apply_update(rebuilt)
    merged = str(doc.get("content", type=pycrdt.Text))
    assert "aaa" in merged and "bbb" in merged


# ============================================================
# 场景 6: crash recovery
# ============================================================
async def test_recover_from_crash(db):
    """清空 snapshot 后 recover_from_crash 从 op log 重建内容一致"""
    import pycrdt

    op1 = _make_op("recover-me")
    await DriveCollabService.apply_remote_op(db, file_id=105, op_bytes=op1, client_id=1, user_id=1)

    # 记录崩溃前内容
    before = await DriveCollabService.export_text(db, file_id=105)
    assert before == "recover-me"

    # 模拟崩溃: 清空 snapshot
    await db.execute(text("UPDATE drive_documents SET ydoc_state=x'' WHERE file_id=105"))
    await db.commit()

    # 崩溃后 get_snapshot 走 op log 兜底 (仍能重建)
    recovered_state = await DriveCollabService.recover_from_crash(db, file_id=105)
    assert len(recovered_state) > 0

    doc = pycrdt.Doc()
    doc.apply_update(recovered_state)
    assert str(doc.get("content", type=pycrdt.Text)) == "recover-me"

    # snapshot 已写回
    after = await DriveCollabService.export_text(db, file_id=105)
    assert after == "recover-me", "recover 后 snapshot 应写回"
