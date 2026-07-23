"""tests/test_drive_v2_pr9_permissions.py — Drive v2 PR9 folder admin 权限 e2e 测试 (2026-07-24)

5 核心场景 (聚焦 drive_permission_service 3 个公开方法):
1. file owner 通过 — check_file_owner_or_folder_admin (file.created_by == user_id)
2. folder admin 通过 — check_file_owner_or_folder_admin (DriveFolderMember.permission='admin')
3. 普通成员拒绝 — check_file_owner_or_folder_admin (write member 返回 False)
4. 文件 owner 通过 (resolve) — check_comment_resolver (file.uploader_id == user_id 路径)
5. 删除中间版本被业务层禁止 — drive_version_service.delete_version (max_non_current 校验)

依赖:
- tests/conftest.py: db / client / test_member / auth_headers fixture
- 模型: app/models/drive_share.py: DriveFolderMember
- service: app/services/drive_permission_service.py (新建)
- service: app/services/drive_version_service.py (改造后)

设计要点:
- W68 PR9 anchor 第 31 守恒验证 (锚点范式从 W68 30 → 31)
- 0 production code 改动铁律 (drive_version_service 仅在 PR9 内改, 不动 v1 老路径)
- 全部场景在隔离 transaction 内跑 (fixture 自动 rollback)
- 场景 5 单独测试 drive_version_service.delete_version 业务规则 (不动 MinIO)
"""
import pytest
import pytest_asyncio

from app.models.drive_comment import DriveComment
from app.models.drive_file_version import DriveFileVersion
from app.models.drive_share import DriveFolderMember
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.core.security import create_access_token, get_password_hash


# ==========================================================================
# Fixture: Drive 场景基础
# ==========================================================================


@pytest_asyncio.fixture
async def drive_folder(db, test_member):
    """创建一个 drive folder 供测试用 (owner=test_member)"""
    folder = Folder(
        name='drive_pr9_perm_folder',
        owner_id=test_member.id,
        visibility='private',  # private 让非成员访问受限
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@pytest_asyncio.fixture
async def drive_file(db, test_member, drive_folder):
    """创建一个 drive 文件 (created_by=test_member, folder=上面)"""
    file_row = Knowledge(
        file_name='drive_pr9_perm_test.pdf',
        file_path='/tmp/drive_pr9_perm_test.pdf',
        file_size=1024,
        file_type='pdf',
        created_by=test_member.id,
        folder_id=drive_folder.id,
        visibility='private',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    return file_row


@pytest_asyncio.fixture
async def admin_member_user(db):
    """folder admin 成员 (有 DriveFolderMember permission='admin' 邀请)"""
    member = Member(
        username='folderadmin',
        name='Folder Admin',
        password_hash=get_password_hash('test123456'),
        role='member',
        grade='研三',
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member
    try:
        from sqlalchemy import text
        from sqlalchemy import delete as sql_delete
        await db.execute(text("SET session_replication_role = 'replica'"))
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
def admin_member_headers(admin_member_user):
    """folder admin 用户的认证 headers"""
    token = create_access_token(data={"sub": str(admin_member_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def write_member_user(db):
    """write 权限成员 (有 DriveFolderMember permission='write' 邀请)"""
    member = Member(
        username='writemember',
        name='Write Member',
        password_hash=get_password_hash('test123456'),
        role='member',
        grade='研二',
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member
    try:
        from sqlalchemy import text
        from sqlalchemy import delete as sql_delete
        await db.execute(text("SET session_replication_role = 'replica'"))
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
def write_member_headers(write_member_user):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(write_member_user.id)})}"}


@pytest_asyncio.fixture
async def platform_admin_user(db):
    """平台管理员 (Member.role='admin', 用于验证 is_platform_admin 兜底分支)"""
    member = Member(
        username='platformadmin',
        name='Platform Admin',
        password_hash=get_password_hash('test123456'),
        role='admin',
        grade='教师',
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member
    try:
        from sqlalchemy import text
        from sqlalchemy import delete as sql_delete
        await db.execute(text("SET session_replication_role = 'replica'"))
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
async def invite_admin(db, drive_folder, admin_member_user, test_member):
    """邀请 admin_member_user 为 drive_folder 的 admin"""
    invite = DriveFolderMember(
        folder_id=drive_folder.id,
        member_id=admin_member_user.id,
        permission='admin',
        invited_by=test_member.id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


@pytest_asyncio.fixture
async def invite_write(db, drive_folder, write_member_user, test_member):
    """邀请 write_member_user 为 drive_folder 的 write"""
    invite = DriveFolderMember(
        folder_id=drive_folder.id,
        member_id=write_member_user.id,
        permission='write',
        invited_by=test_member.id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


# ==========================================================================
# 场景 1: file owner 通过 (走 check_file_owner_or_folder_admin file owner 分支)
# ==========================================================================


@pytest.mark.asyncio
async def test_check_file_owner_or_folder_admin_owner_passes(
    db, drive_file, test_member
):
    """场景 1: file.created_by == user_id → True (file owner 路径)

    验证 check_file_owner_or_folder_admin 异步权限检查的文件 owner 分支.
    """
    from app.services.drive_permission_service import DrivePermissionService

    perm_svc = DrivePermissionService(db)
    has_perm = await perm_svc.check_file_owner_or_folder_admin(
        test_member.id, drive_file.id
    )
    assert has_perm is True, "file owner 应有权限"


# ==========================================================================
# 场景 2: folder admin 通过 (走 check_file_owner_or_folder_admin folder admin 分支)
# ==========================================================================


@pytest.mark.asyncio
async def test_check_file_owner_or_folder_admin_folder_admin_passes(
    db, drive_file, invite_admin, admin_member_user
):
    """场景 2: folder admin → True (走 folder admin 分支)

    验证 DriveFolderMember.permission='admin' 路径.
    user 既不是 file owner 也不是 platform admin, 走 folder admin 分支.
    """
    from app.services.drive_permission_service import DrivePermissionService

    perm_svc = DrivePermissionService(db)
    admin_id = admin_member_user.id

    has_perm = await perm_svc.check_file_owner_or_folder_admin(
        admin_id, drive_file.id
    )
    assert has_perm is True, "folder admin 应有权限"


# ==========================================================================
# 场景 3: 普通 write 成员拒绝
# ==========================================================================


@pytest.mark.asyncio
async def test_check_file_owner_or_folder_admin_write_member_denied(
    db, drive_file, invite_write, write_member_user
):
    """场景 3: write member → False (无 admin/owner/platform admin 权限)

    验证 check_file_owner_or_folder_admin 的拒绝路径.
    write permission 不够 (要 admin 才能改 version).
    """
    from app.services.drive_permission_service import DrivePermissionService

    perm_svc = DrivePermissionService(db)
    write_user_id = write_member_user.id

    has_perm = await perm_svc.check_file_owner_or_folder_admin(
        write_user_id, drive_file.id
    )
    assert has_perm is False, "write member 应被拒"


@pytest.mark.asyncio
async def test_check_file_owner_or_folder_admin_no_folder_no_owner_denied(
    db, test_member
):
    """场景 3 补充: file 无 folder + 非 owner → False

    验证 file.folder_id is None 时的安全路径 (孤儿 file 只能 owner 改).
    """
    from app.services.drive_permission_service import DrivePermissionService

    # 创建一个孤儿 file (无 folder)
    orphan_file = Knowledge(
        file_name='orphan.pdf',
        file_path='/tmp/orphan.pdf',
        file_size=512,
        file_type='pdf',
        created_by=test_member.id,
        folder_id=None,  # 关键: 无 folder
        visibility='private',
        storage_mode='drive',
    )
    db.add(orphan_file)
    await db.commit()
    await db.refresh(orphan_file)

    perm_svc = DrivePermissionService(db)
    # 用其他 user id 测试 (非 file owner)
    has_perm = await perm_svc.check_file_owner_or_folder_admin(
        99999, orphan_file.id  # 不存在的 user
    )
    assert has_perm is False, "非 owner + 孤儿 file 应被拒"


# ==========================================================================
# 场景 4: 文件 owner 通过 resolve 路径 (走 check_comment_resolver file owner 分支)
# ==========================================================================


@pytest.mark.asyncio
async def test_check_comment_resolver_file_owner_passes(
    db, drive_file, write_member_user, test_member
):
    """场景 4: comment.file_id → file.owner_id == user_id → True (file owner 路径)

    验证 check_comment_resolver 的 file owner 分支 (非 author, 非 folder admin, 但 file owner).
    """
    from app.services.drive_permission_service import DrivePermissionService

    # write 成员创建评论 (非 author 路径)
    comment = DriveComment(
        file_id=drive_file.id,
        author_id=write_member_user.id,
        content='write 成员提的问题',
        mentions=[],
        is_top_level=True,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    # file owner (test_member) 走 check_comment_resolver file owner 分支
    perm_svc = DrivePermissionService(db)
    has_perm = await perm_svc.check_comment_resolver(test_member.id, comment)
    assert has_perm is True, "file owner 应能 resolve"


@pytest.mark.asyncio
async def test_check_comment_resolver_folder_admin_passes(
    db, drive_file, invite_admin, admin_member_user, test_member
):
    """场景 4 补充: folder admin 也能 resolve (走 folder admin 分支)

    user 既不是 author 也不是 file owner, 但有 folder admin 权限.
    """
    from app.services.drive_permission_service import DrivePermissionService

    # test_member (file owner) 创建评论 (让 admin 走 folder admin 路径)
    comment = DriveComment(
        file_id=drive_file.id,
        author_id=test_member.id,
        content='file owner 提的问题',
        mentions=[],
        is_top_level=True,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    perm_svc = DrivePermissionService(db)
    has_perm = await perm_svc.check_comment_resolver(
        admin_member_user.id, comment
    )
    assert has_perm is True, "folder admin 应能 resolve"


@pytest.mark.asyncio
async def test_check_comment_resolver_write_member_denied(
    db, drive_file, invite_write, write_member_user, test_member
):
    """场景 4 补充: write member 不能 resolve (folder write 权限不够)

    验证 check_comment_resolver 拒绝路径.
    """
    from app.services.drive_permission_service import DrivePermissionService

    # test_member (file owner + folder owner) 创建评论
    comment = DriveComment(
        file_id=drive_file.id,
        author_id=test_member.id,
        content='file owner 提的问题',
        mentions=[],
        is_top_level=True,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    perm_svc = DrivePermissionService(db)
    has_perm = await perm_svc.check_comment_resolver(
        write_member_user.id, comment
    )
    assert has_perm is False, "write member 不能 resolve"


# ==========================================================================
# 场景 5: 删除中间版本被业务层禁止 (drive_version_service.delete_version 业务规则)
# ==========================================================================


@pytest.mark.asyncio
async def test_delete_version_business_rule_rejects_middle(
    db, drive_file, test_member, monkeypatch
):
    """场景 5: 即使是 file owner, 业务层禁止删除中间版本 (max_non_current 校验)

    这个测试是 drive_version_service 的业务规则回归测试:
    - 创建 v1 (is_current=1) - 通过 fixture 或 monkeypatch file_service 后手动创建
    - 创建 v2 → max_non_current = v1
    - 创建 v3 → max_non_current = v2
    - 试图删 v1 (中间版本, max_non_current=v2) → 400 不是 403

    注意: 本测试 monkeypatch file_service.upload_to_path / copy_object_async,
    避免真打 MinIO. 不测 create_version 的 MinIO 上传路径, 只测 delete_version 业务规则.
    """
    from app.services import file_service
    from app.services.drive_version_service import (
        DriveVersionService,
        DriveVersionServiceError,
    )

    # Mock file_service 避免真打 MinIO
    store = {}

    async def fake_upload(object_name, content, content_type=None):
        store[object_name] = content

    async def fake_copy(src, dst):
        if src not in store:
            # rollback 时若 store 没 src, 主动写入 (兜底)
            store[dst] = b""
            return 0
        store[dst] = store[src]
        return len(store[dst])

    def fake_delete(object_name):
        store.pop(object_name, None)

    monkeypatch.setattr(file_service.file_service, "upload_to_path", fake_upload)
    monkeypatch.setattr(file_service.file_service, "copy_object_async", fake_copy)
    monkeypatch.setattr(file_service.file_service, "delete_file", fake_delete)

    svc = DriveVersionService(db)
    owner_id = test_member.id

    # 创建 v2
    v2 = await svc.create_version(
        file_id=drive_file.id,
        new_content=b"v2 content",
        new_filename='drive_pr9_perm_test.pdf',
        new_content_type='application/pdf',
        uploader_id=owner_id,
        comment='v2',
    )
    assert v2.version_number == 2

    # 创建 v3 (让 max_non_current = v2)
    v3 = await svc.create_version(
        file_id=drive_file.id,
        new_content=b"v3 content",
        new_filename='drive_pr9_perm_test.pdf',
        new_content_type='application/pdf',
        uploader_id=owner_id,
        comment='v3',
    )
    assert v3.version_number == 3

    # v1 是中间版本 (max_non_current = v2)
    # 试图删 v1 → 400 业务规则拒绝
    v1_id = (await db.execute(
        db.query(DriveFileVersion).filter(
            DriveFileVersion.file_id == drive_file.id,
            DriveFileVersion.version_number == 1,
        ).statement
    )).scalars().first().id

    with pytest.raises(DriveVersionServiceError) as exc_info:
        await svc.delete_version(
            version_id=v1_id,
            user_id=owner_id,
        )
    assert exc_info.value.status_code == 400
    assert "中间版本" in exc_info.value.message or "最新非当前版本" in exc_info.value.message


# ==========================================================================
# 补充: check_folder_admin 平台管理员兜底
# ==========================================================================


@pytest.mark.asyncio
async def test_check_folder_admin_platform_admin_passes(
    db, drive_folder, platform_admin_user
):
    """补充: Member.role='admin' 平台管理员 → True (走 is_platform_admin 兜底)

    验证 check_folder_admin 的兜底分支 (既不是 owner 也不是 folder admin member,
    但是平台管理员).
    """
    from app.services.drive_permission_service import DrivePermissionService

    perm_svc = DrivePermissionService(db)
    has_perm = await perm_svc.check_folder_admin(
        platform_admin_user.id, drive_folder.id
    )
    assert has_perm is True, "平台管理员应有 folder admin 权限"