"""tests/test_drive_v2_pr10_knowledge_field_authority.py — W68 第 5 批 hot-fix #18 e2e (2026-07-24)

3 核心场景 (验证 Knowledge ORM 字段修正):
1. file owner 走 created_by 字段评论 (drive_comment_service._check_file_comment_authority)
2. Knowledge ORM 验证 (确认没有 uploader_id 字段, 防止重蹈覆辙)
3. DriveFileVersion.uploader_id 仍正常工作 (跨表引用, 不能混淆)

跨会话 agent 报 bug 教训:
- 之前 hot-fix #16 (version_diff) 和 #17 (ws_push) 在 drive_event_publisher.py:185/196/220/231
  修复 DriveFileVersion.uploader_id (真存在字段), 但同时引入错误:
  drive_comment_service.py:94 / drive_permission_service.py:253
  错误引用 Knowledge.uploader_id (不存在字段)
- 主指挥核实: Knowledge ORM 真字段是 created_by (app/models/knowledge.py:64)
- DriveFileVersion 真有 uploader_id (app/models/drive_file_version.py:96)

依赖:
- tests/conftest.py: db / client / test_member / auth_headers fixture
- 模型: app/models/knowledge.py / app/models/drive_file_version.py
- service: app/services/drive_comment_service.py / drive_permission_service.py
"""
import pytest
import pytest_asyncio

from sqlalchemy import inspect

from app.models.knowledge import Knowledge
from app.models.drive_file_version import DriveFileVersion
from app.models.folder import Folder


# ==========================================================================
# 场景 1: file owner 走 created_by 字段评论
# ==========================================================================


@pytest.mark.asyncio
async def test_file_owner_can_comment_via_created_by(client, db, test_member, drive_pr10_folder):
    """场景 1: file owner 通过 created_by 字段获取评论权限

    修复前: drive_comment_service.py:94 引用 file_row.uploader_id (AttributeError)
    修复后: 引用 file_row.created_by (Knowledge ORM 真实字段)
    """
    # 用 created_by 创建 file (不用 uploader_id, Knowledge 没这字段)
    file_row = Knowledge(
        file_name='hotfix_pr10_test.pdf',
        file_path='/tmp/hotfix_pr10_test.pdf',
        file_size=2048,
        file_type='pdf',
        created_by=test_member.id,
        folder_id=drive_pr10_folder.id,
        visibility='public',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)

    # 验证 created_by 持久化
    assert file_row.created_by == test_member.id

    # file owner 创建评论 (走 _check_file_comment_authority 应成功)
    token = __import__('app.core.security', fromlist=['create_access_token']).create_access_token(
        data={"sub": str(test_member.id)}
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        '/api/v1/drive/comments',
        headers=headers,
        json={
            'file_id': file_row.id,
            'content': 'file owner 评论测试 — created_by 字段',
            'mentions': [],
        },
    )
    assert resp.status_code == 201, (
        f"file owner 应有评论权限 (修复前会因 AttributeError 500): {resp.text}"
    )
    data = resp.json()
    assert data['file_id'] == file_row.id
    assert data['author_id'] == test_member.id


# ==========================================================================
# 场景 2: Knowledge ORM 字段验证 (防止再误用 uploader_id)
# ==========================================================================


def test_knowledge_orm_has_created_by_not_uploader_id():
    """场景 2: 静态验证 Knowledge ORM 字段名, 防止再误用 uploader_id

    铁律: Knowledge ORM (app/models/knowledge.py:64) 字段是 created_by,
    没有 uploader_id. DriveFileVersion.uploader_id 才存在.
    跨表引用时必须先确认.
    """
    inspector = inspect(Knowledge)
    columns = {c.name for c in inspector.columns}
    assert 'created_by' in columns, "Knowledge 缺少 created_by 字段"
    assert 'uploader_id' not in columns, (
        "Knowledge 不应有 uploader_id 字段 (跨表引用混淆容易出错)"
    )


def test_knowledge_orm_attribute_access_created_by_works():
    """场景 2 续: 实际访问 Knowledge 实例的 .created_by 属性, 不会 AttributeError

    修复前: drive_comment_service.py:94 / drive_permission_service.py:253
    调 file_row.uploader_id → AttributeError → 整个评论流程 / resolve 流程 500.
    修复后: .created_by 是有效字段.
    """
    file_row = Knowledge(
        file_name='test.pdf',
        file_path='/tmp/test.pdf',
        file_size=100,
        file_type='pdf',
        created_by=42,  # 任意 integer, 仅测字段访问
        storage_mode='drive',
    )
    # 这两个属性访问必须不抛 AttributeError
    assert file_row.created_by == 42
    try:
        _ = file_row.uploader_id
        assert False, "Knowledge 居然有 uploader_id 字段, 这是 hot-fix #18 的反向 case"
    except AttributeError:
        pass  # 预期: Knowledge 没 uploader_id


# ==========================================================================
# 场景 3: DriveFileVersion.uploader_id 仍正常工作 (跨表引用不能混淆)
# ==========================================================================


@pytest.mark.asyncio
async def test_drive_file_version_uploader_id_still_works(db, test_member, drive_pr10_folder):
    """场景 3: DriveFileVersion.uploader_id 是真字段, 不被本次 hot-fix 误删

    app/models/drive_file_version.py:96 真有 uploader_id.
    本次 hot-fix 仅修 Knowledge 引用错误, 不动 DriveFileVersion.
    """
    file_row = Knowledge(
        file_name='versioned.pdf',
        file_path='/tmp/versioned.pdf',
        file_size=3000,
        file_type='pdf',
        created_by=test_member.id,
        folder_id=drive_pr10_folder.id,
        visibility='public',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)

    # DriveFileVersion.uploader_id (真字段)
    version = DriveFileVersion(
        file_id=file_row.id,
        version_number=1,
        minio_object_key=f'uploads/drive/{test_member.id}/v1_abc123_{file_row.id}.pdf',
        size=3000,
        uploader_id=test_member.id,
        is_current=1,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)

    # 验证 DriveFileVersion ORM 字段访问
    assert version.uploader_id == test_member.id

    # 验证 DriveFileVersion ORM 模型结构
    v_inspector = inspect(DriveFileVersion)
    v_columns = {c.name for c in v_inspector.columns}
    assert 'uploader_id' in v_columns, (
        "DriveFileVersion 应有 uploader_id 字段, hot-fix #18 不应误删"
    )


# ==========================================================================
# Fixtures
# ==========================================================================


@pytest_asyncio.fixture
async def drive_pr10_folder(db, test_member):
    """drive 文件夹 fixture (visibility=public 让所有测试用户都能访问)"""
    folder = Folder(
        name='hotfix_pr10_folder',
        owner_id=test_member.id,
        visibility='public',
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    yield folder
    # teardown: 删 folder 及其下 file (CASCADE by FK)
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Folder).where(Folder.id == folder.id))
        await db.commit()
    except Exception:
        pass