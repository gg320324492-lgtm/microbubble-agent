"""批次① B1 + B3 — folder 级联删除/恢复对称性测试 (2026-09-05)

覆盖:
- B1: soft_delete_folder(recursive=True) 级联删的整棵子树, restore_folder 一次恢复
      全部复活 (级联批时间戳对称判据, 5s 容差)
- B1(b): 更早单独删除的子夹 (不同批时间戳) 不随父 restore 复活
- B1(c): 未删夹 restore 幂等 no-op (计数 0)
- B3:  级联软删补 original_parent_id/original_path 快照; restore 清快照且落点不变

DB fixture: 复用 tests/conftest.py 的 db fixture (TEST_DATABASE_URL → microbubble_test),
**绝不**走 settings.DATABASE_URL (容器跑测试污染生产事故铁律, 2026-09-05)。
"""
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.folder_service import FolderService


async def _mk_member(db, tag: str) -> Member:
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"frst_{tag}_{u}", name=f"restore-{tag}",
        password_hash="h", role="member", grade="测试", is_active=True,
        wechat_id=f"wx_{tag}_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _mk_drive_file(db, *, title: str, folder_id, created_by) -> Knowledge:
    k = Knowledge(
        content="", title=title, storage_mode="drive", file_name=title,
        file_path=f"drive-test/{title}", folder_id=folder_id,
        created_by=created_by, visibility="team",
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@pytest.fixture
async def env(db):
    alice = await _mk_member(db, "alice")
    return {"db": db, "alice": alice}


async def _tree(env):
    """root(d0) → child(d1); f_root 挂 root, f_child 挂 child"""
    db, alice = env["db"], env["alice"]
    svc = FolderService(db)
    root = await svc.create_folder(name="组会PPT", owner_id=alice.id, visibility="team")
    child = await svc.create_folder(name="2026", owner_id=alice.id, parent_id=root.id, visibility="team")
    f_root = await _mk_drive_file(db, title="root_slides.pptx", folder_id=root.id, created_by=alice.id)
    f_child = await _mk_drive_file(db, title="child_data.xlsx", folder_id=child.id, created_by=alice.id)
    return svc, root, child, f_root, f_child


async def _reload(db, model, pk):
    # populate_existing: 服务层走 ORM bulk UPDATE (synchronize 可能 fallback fetch),
    # 测试断言必须读到 DB 现值而非 identity map 缓存旧值
    stmt = select(model).where(model.id == pk).execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalar_one()


# ---------------------------------------------------------------------------
# (a) 2 层树 + 夹内文件级联删 → restore 根 → 全部复活
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cascade_delete_then_restore_root_revives_everything(env):
    svc, root, child, f_root, f_child = await _tree(env)
    db = env["db"]

    result = await svc.soft_delete_folder(
        root.id, current_user_id=root.owner_id, recursive=True,
    )
    assert result["deleted_folders"] == 2
    assert result["deleted_files"] == 2

    restored = await svc.restore_folder(root.id, current_user_id=root.owner_id)
    assert restored is not None
    assert restored["restored_folders"] == 2, "级联批内 2 个 folder 必须一次全复活"
    assert restored["restored_files"] == 2, "级联批内 2 个 drive 文件必须一次全复活"

    for model, pk in [(Folder, root.id), (Folder, child.id), (Knowledge, f_root.id), (Knowledge, f_child.id)]:
        row = await _reload(db, model, pk)
        assert row.deleted_at is None


# ---------------------------------------------------------------------------
# (b) 子夹 (含文件) 更早单独删除 → 父 restore 不复活它
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restore_does_not_revive_earlier_solo_deleted_child(env):
    svc, root, child, f_root, f_child = await _tree(env)
    db = env["db"]

    # 子夹先被单独级联删 (含其文件)
    await svc.soft_delete_folder(child.id, current_user_id=child.owner_id, recursive=True)
    # 把子批时间戳人为回退 1 小时, 模拟"很久之前的单独删除" (真实操作间隔 >> 5s 容差)
    back = timedelta(hours=1)
    r_child = await _reload(db, Folder, child.id)
    r_fchild = await _reload(db, Knowledge, f_child.id)
    assert r_child.deleted_at is not None and r_fchild.deleted_at is not None
    await db.execute(
        update(Folder).where(Folder.id == child.id).values(
            deleted_at=r_child.deleted_at - back
        )
    )
    await db.execute(
        update(Knowledge).where(Knowledge.id == f_child.id).values(
            deleted_at=r_fchild.deleted_at - back
        )
    )
    await db.commit()

    # 根级联删 (child 已删 → 不在本批; child 的 file 同理)
    result = await svc.soft_delete_folder(root.id, current_user_id=root.owner_id, recursive=True)
    assert result["deleted_folders"] == 1  # 只有 root
    assert result["deleted_files"] == 1    # 只有 f_root

    restored = await svc.restore_folder(root.id, current_user_id=root.owner_id)
    assert restored["restored_folders"] == 1
    assert restored["restored_files"] == 1

    r_child = await _reload(db, Folder, child.id)
    assert r_child.deleted_at is not None, "更早单独删除的子夹不得随父 restore 复活"
    r_fchild = await _reload(db, Knowledge, f_child.id)
    assert r_fchild.deleted_at is not None


# ---------------------------------------------------------------------------
# (c) 未删夹 restore 幂等 no-op
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restore_alive_folder_is_noop(env):
    svc, root, child, f_root, f_child = await _tree(env)

    result = await svc.restore_folder(root.id, current_user_id=root.owner_id)
    assert result == {"folder": result["folder"], "restored_folders": 0, "restored_files": 0}
    assert result["folder"].id == root.id
    assert result["folder"].deleted_at is None

    # 恢复成功后二次 restore 同样 no-op (幂等)
    await svc.soft_delete_folder(root.id, current_user_id=root.owner_id, recursive=True)
    first = await svc.restore_folder(root.id, current_user_id=root.owner_id)
    assert first["restored_folders"] == 2
    second = await svc.restore_folder(root.id, current_user_id=root.owner_id)
    assert second["restored_folders"] == 0
    assert second["restored_files"] == 0


@pytest.mark.asyncio
async def test_restore_missing_folder_returns_none(env):
    db = env["db"]
    svc = FolderService(db)
    assert await svc.restore_folder(999999, current_user_id=env["alice"].id) is None


# ---------------------------------------------------------------------------
# (d) B3 快照: 级联删写入 original_parent_id/original_path; restore 后落点正确 + 快照清
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cascade_delete_snapshots_and_restore_landing(env):
    svc, root, child, f_root, f_child = await _tree(env)
    db = env["db"]

    await svc.soft_delete_folder(root.id, current_user_id=root.owner_id, recursive=True)

    # B3: 级联删现在与 drive_service.soft_delete_file 对称写快照
    k = await _reload(db, Knowledge, f_child.id)
    assert k.deleted_at is not None
    assert k.original_parent_id == child.id, "级联删必须快照原 folder (B3)"
    assert k.original_path == child.path

    await svc.restore_folder(root.id, current_user_id=root.owner_id)
    k = await _reload(db, Knowledge, f_child.id)
    assert k.deleted_at is None
    assert k.folder_id == child.id, "恢复落点 = 原子夹 (子夹同批已复活)"
    assert k.original_parent_id is None and k.original_path is None, "restore 后快照清理"
