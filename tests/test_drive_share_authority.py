"""批次① B5 — folder 分享权限扁平化测试 (2026-09-05)

alembic 132 角色扁平化 + 单一团队空间后, _check_folder_share_authority 与 file 级
先例 (drive_files.py create_share_link 全员可分享) 对齐: 任何在世成员 (is_active)
隐含 admin。已禁/已删号成员 (is_active != True) 不享受 → 走 403 老路径。

注: 任务书原文写 "Member.deleted_at IS NULL", 但 Member 模型无 deleted_at 列,
在世判定取 is_active (与 get_current_user 禁号口径一致)。

DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import uuid as _uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.drive_share import DriveFolderMember, DriveFolderShare
from app.models.member import Member
from app.services.drive_share_service import DriveShareService, DriveShareServiceError
from app.services.folder_service import FolderService


async def _mk_member(db, tag, is_active=True):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"sh5_{tag}_{u}", name=tag, password_hash="h", role="member",
        grade="测试", is_active=is_active, wechat_id=f"wx_sh5_{tag}_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def share_env(db):
    u = _uuid.uuid4().hex[:8]
    owner = await _mk_member(db, "owner")
    stranger = await _mk_member(db, "stranger")
    invitee = await _mk_member(db, "invitee")
    gone = await _mk_member(db, "gone", is_active=False)  # 已删号/禁用
    folder = await FolderService(db).create_folder(
        name="共享夹", owner_id=owner.id, visibility="team",
    )
    return {
        "db": db, "svc": DriveShareService(db), "folder": folder,
        "owner": owner, "stranger": stranger, "invitee": invitee, "gone": gone,
    }


@pytest.mark.asyncio
async def test_non_owner_active_member_can_create_folder_share(share_env):
    """非 owner 的在世成员 create folder share → 成功 (隐含 admin)"""
    e = share_env
    share = await e["svc"].create_folder_share(
        e["folder"].id, e["stranger"].id, permission="read",
    )
    assert share.share_token and len(share.share_token) >= 40
    row = (await e["db"].execute(
        select(DriveFolderShare).where(DriveFolderShare.id == share.id)
    )).scalar_one()
    assert row.created_by == e["stranger"].id


@pytest.mark.asyncio
async def test_non_owner_active_member_can_add_folder_member(share_env):
    """非 owner 的在世成员邀请其他成员 → 成功"""
    e = share_env
    member_row = await e["svc"].add_folder_member(
        e["folder"].id, inviter_id=e["stranger"].id, member_id=e["invitee"].id,
        permission="write",
    )
    assert member_row.permission == "write"
    assert member_row.folder_id == e["folder"].id


@pytest.mark.asyncio
async def test_deleted_member_forbidden(share_env):
    """已删号成员 (is_active=False) 既不隐含 admin 也无 member 行 → 403"""
    e = share_env
    with pytest.raises(DriveShareServiceError) as exc:
        await e["svc"].create_folder_share(e["folder"].id, e["gone"].id)
    assert exc.value.status_code == 403

    with pytest.raises(DriveShareServiceError) as exc2:
        await e["svc"].add_folder_member(
            e["folder"].id, inviter_id=e["gone"].id, member_id=e["invitee"].id,
        )
    assert exc2.value.status_code == 403


@pytest.mark.asyncio
async def test_owner_still_admin(share_env):
    """owner 路径不回归 (仍第一优先级 admin)"""
    e = share_env
    share = await e["svc"].create_folder_share(e["folder"].id, e["owner"].id)
    assert share.folder_id == e["folder"].id
