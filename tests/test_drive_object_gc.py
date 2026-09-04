"""批次① B2 + N1 — MinIO 版本对象统一回收测试 (2026-09-05)

断言核心 = "永久删一条带 2 个历史版本的文件时, delete_file 必须收到 3 个 key
(当前对象 + 2 个版本对象)"。

N1 回归锁 (cleanup 路径): clean_old_drive_files 旧实现先 DELETE 后 SELECT →
MinIO key 恒空。若顺序回退, 本测试 mock 的 delete_file 收不到 key 即红。

打点 (类 20.181): purge_minio_keys 走调用时 inline import, 因此
patch("app.services.file_service.file_service") 对整个 service 链生效 —
与重构前 drive_cleanup_service 的旧打点完全一致, 老测试 patch 不失效。

DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.drive_file_star import DriveFileStar  # noqa: F401  (确保 create_all 覆盖 134 表)
from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_object_gc import collect_object_keys, purge_minio_keys


def _naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest_asyncio.fixture
async def gc_env(db):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"gc_{u}", name="gc", password_hash="h", role="member",
        grade="测试", is_active=True, wechat_id=f"wx_gc_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return {"db": db, "m": m}


async def _mk_trashed_drive_file(db, owner, name, *, deleted_at, versions=0):
    k = Knowledge(
        content="", title=name, storage_mode="drive", file_name=name,
        file_path=f"drive-test/{name}", created_by=owner.id,
        visibility="team", deleted_at=deleted_at,
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    keys = []
    for i in range(versions):
        vk = f"drive-test/{name}.v{i}"
        keys.append(vk)
        db.add(DriveFileVersion(
            file_id=k.id, version_number=i + 1, minio_object_key=vk,
            size=10, uploader_id=owner.id, is_current=0,
        ))
    await db.commit()
    return k, keys


# ---------------------------------------------------------------------------
# collect_object_keys 单元
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collect_keys_union_dedup(gc_env):
    db, m = gc_env["db"], gc_env["m"]
    k, keys = await _mk_trashed_drive_file(
        db, m, "union.pdf", deleted_at=_naive_now() - timedelta(days=40), versions=2,
    )
    result = await collect_object_keys(db, [k])
    assert k.file_path in result
    assert set(result) == {k.file_path} | set(keys)
    assert len(result) == len(set(result)), "去重"
    assert await collect_object_keys(db, []) == []


# ---------------------------------------------------------------------------
# (a) permanent_delete: 当前对象 + 2 个版本对象 = 3 个 key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_permanent_delete_purges_current_and_versions(gc_env):
    from app.services.drive_service import DriveService
    db, m = gc_env["db"], gc_env["m"]
    k, vkeys = await _mk_trashed_drive_file(
        db, m, "three_objects.pdf", deleted_at=_naive_now(), versions=2,
    )
    expected = {k.file_path} | set(vkeys)

    mock_fs = MagicMock()
    with patch("app.services.file_service.file_service", mock_fs):
        ok = await DriveService(db).permanent_delete(k.id, current_user_id=m.id)
    assert ok is True
    called = {c.args[0] for c in mock_fs.delete_file.call_args_list}
    assert called == expected, f"应清 3 个对象 (B2), 实收 {called}"

    left = (await db.execute(select(Knowledge).where(Knowledge.id == k.id))).scalar_one_or_none()
    assert left is None


# ---------------------------------------------------------------------------
# (b) cleanup 路径 N1 回归锁
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_purges_all_keys_n1_regression_lock(gc_env):
    """若 clean_old_drive_files 回退成"先 DELETE 后 SELECT"旧顺序 → expired_files
    恒空 → delete_file 收不到 key → 本测试即红 (N1 回归锁)。"""
    from app.services.drive_cleanup_service import clean_old_drive_files
    db, m = gc_env["db"], gc_env["m"]
    k1, v1 = await _mk_trashed_drive_file(
        db, m, "expired_v1.doc", deleted_at=_naive_now() - timedelta(days=40), versions=1,
    )
    k2, _ = await _mk_trashed_drive_file(
        db, m, "expired_v2.doc", deleted_at=_naive_now() - timedelta(days=45), versions=0,
    )
    # 不超期的对照组 (30 天内, 不该被动)
    k3, _ = await _mk_trashed_drive_file(
        db, m, "fresh.doc", deleted_at=_naive_now() - timedelta(days=1), versions=0,
    )
    expected = {k1.file_path, k2.file_path} | set(v1)

    mock_fs = MagicMock()
    with patch("app.services.file_service.file_service", mock_fs), \
         patch("app.services.drive_cleanup_service.backup_rows_to_json",
               new=AsyncMock(return_value=(2, None))):
        result = await clean_old_drive_files(db, _naive_now() - timedelta(days=30))

    assert result["deleted_files"] == 2
    assert result["minio_cleanup_failures"] == 0
    called = {c.args[0] for c in mock_fs.delete_file.call_args_list}
    assert called == expected, f"N1: cleanup 从未真正清 MinIO 的回归 {called}"
    assert k3.file_path not in called, "未超期文件对象不得被碰"
    left = (await db.execute(select(Knowledge).where(Knowledge.id == k3.id))).scalar_one_or_none()
    assert left is not None


# ---------------------------------------------------------------------------
# (c) purge 单 key 失败不抛、其余继续
# ---------------------------------------------------------------------------

def test_purge_continues_after_failure_and_counts():
    keys = ["ok1", "bad", "ok2"]
    mock_fs = MagicMock()

    def _delete(p):
        if p == "bad":
            raise IOError("MinIO connection refused")
    mock_fs.delete_file.side_effect = _delete

    with patch("app.services.file_service.file_service", mock_fs):
        failures = purge_minio_keys(keys)  # 不得抛
    assert failures == 1
    assert [c.args[0] for c in mock_fs.delete_file.call_args_list] == keys, "失败后继续逐 key 删"
