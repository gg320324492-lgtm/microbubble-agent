"""批次① B4 — folder move 子树深度上限测试 (2026-09-05)

旧实现 update_folder move 分支只校验被移动 folder 自身落点 depth ≤ 5,
子树整体平移后最深 descendant 可穿透上限 (5 层铁律名存实亡)。
新校验: new_depth + (max_descendant_depth - folder.depth) ≤ MAX_FOLDER_DEPTH。

DB fixture: conftest db (TEST_DATABASE_URL), 不碰生产库。
"""
import uuid as _uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.folder import MAX_FOLDER_DEPTH, Folder
from app.models.member import Member
from app.services.folder_service import FolderService, FolderServiceError


@pytest_asyncio.fixture
async def svc_env(db):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"mv_{u}", name="mover", password_hash="h",
        role="member", grade="测试", is_active=True, wechat_id=f"wx_mv_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return FolderService(db), m


async def _chain(svc, owner_id, root_name, length):
    """建 length 层链: 顶 depth=0, 最深 depth=length-1; 返 [节点...]"""
    nodes = []
    parent_id = None
    for i in range(length):
        f = await svc.create_folder(
            name=f"{root_name}_{i}", owner_id=owner_id,
            parent_id=parent_id, visibility="team",
        )
        nodes.append(f)
        parent_id = f.id
    return nodes


async def _depth_of(db, folder_id):
    row = (await db.execute(
        select(Folder.depth).where(Folder.id == folder_id).execution_options(populate_existing=True)
    )).scalar()
    return row


@pytest.mark.asyncio
async def test_move_subtree_that_would_exceed_depth_rejected(svc_env):
    """6 层链 (depth 0..5) 的 depth=2 夹 (带 depth=5 孙) 移到 depth=2 新父下
    → 平移后最深将达 6 层 > 5 → 400 拒绝"""
    svc, m = svc_env

    deep = await _chain(svc, m.id, "deep", 6)      # depths 0..5
    target = await _chain(svc, m.id, "t", 3)       # depths 0..2

    moved = deep[2]                                  # depth=2, 子树最深 5, 偏移 3
    with pytest.raises(FolderServiceError) as exc:
        await svc.update_folder(moved.id, m.id, parent_id=target[2].id)  # new_depth=3 → 3+3=6
    assert exc.value.status_code == 400
    assert "移动后子树最深将达 6 层" in str(exc.value)
    assert str(MAX_FOLDER_DEPTH) in str(exc.value)

    # 拒绝后 DB 未动: moved 仍在原父下
    await svc.db.refresh(moved)
    assert moved.parent_id == deep[1].id
    assert moved.depth == 2


@pytest.mark.asyncio
async def test_move_subtree_within_depth_succeeds_and_rebuilds(svc_env):
    """同一 depth=2 夹 (偏移 3) 移到 depth=1 新父下 → 最深 4 ≤ 5 → 成功,
    且子树全部节点 depth/path 重算正确"""
    svc, m = svc_env

    deep = await _chain(svc, m.id, "deep", 6)       # depths 0..5
    shallow = await _chain(svc, m.id, "s", 2)       # depths 0..1

    moved = deep[2]
    new_parent = shallow[1]                          # depth=1 → new_depth=2? 不, = 1+1 = 2
    # new_depth=2 + 偏移 3 = 5 ≤ MAX (5) → 允许 (边界恰好压线)
    result = await svc.update_folder(moved.id, m.id, parent_id=new_parent.id)
    assert result is not None

    db = svc.db
    # x2→2, x3→3, x4→4, x5→5 (相对偏移保持)
    assert await _depth_of(db, deep[2].id) == 2
    assert await _depth_of(db, deep[3].id) == 3
    assert await _depth_of(db, deep[4].id) == 4
    assert await _depth_of(db, deep[5].id) == 5
    # path 前缀已换到新父
    x2 = await db.get(Folder, deep[2].id)
    await db.refresh(x2)
    assert x2.path == f"{new_parent.path}{x2.id}/"


@pytest.mark.asyncio
async def test_move_leaf_folder_unaffected_by_new_check(svc_env):
    """单夹无子树 (偏移 0) 的常规 move 行为不变 (回归锁: 新校验不得误伤)"""
    svc, m = svc_env
    a = await svc.create_folder(name="a", owner_id=m.id, visibility="team")
    b = await svc.create_folder(name="b", owner_id=m.id, visibility="team")
    moved = await svc.update_folder(b.id, m.id, parent_id=a.id)
    assert moved.parent_id == a.id
    assert moved.depth == 1
