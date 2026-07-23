"""tests/test_drive_v2_pr9_comments.py — Drive v2 PR9 评论 thread e2e 测试 (2026-07-24)

5 核心场景:
1. 创建顶层评论 (file_id)
2. 嵌套回复 (parent_id)
3. 编辑评论 (作者本人)
4. 删除评论 (作者本人, CASCADE 子回复)
5. 标记 resolved (author / file owner)

跨用户权限:
- A 创建, B 回复, A 标记 resolved
- C 无权访问 (private folder) → 403
- B 试图编辑 A 的评论 → 403

依赖:
- tests/conftest.py: db / client / test_member / auth_headers fixture
- tests/test_drive_folders_tree_scope.py: Folder fixture 参考
- 模型: app/models/drive_comment.py: DriveComment
- service: app/services/drive_comment_service.py
- API: app/api/v1/drive_comments.py
"""
import pytest
import pytest_asyncio

from app.models.drive_comment import DriveComment
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.core.security import create_access_token, get_password_hash


@pytest_asyncio.fixture
async def drive_folder(db, test_member):
    """创建一个 drive folder 供评论测试用

    visibility=public 让 auth_headers 用户能访问 (无需额外 folder member 邀请)
    """
    folder = Folder(
        name='drive_pr9_folder',
        owner_id=test_member.id,
        visibility='public',  # public 让所有用户都能 read
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@pytest_asyncio.fixture
async def drive_file(db, test_member, drive_folder):
    """创建一个 drive 文件供评论测试用

    storage_mode='drive' (必备, 否则 service 拒绝评论)
    """
    file_row = Knowledge(
        file_name='drive_pr9_test.pdf',
        file_path='/tmp/drive_pr9_test.pdf',
        file_size=1024,
        file_type='pdf',
        uploader_id=test_member.id,
        folder_id=drive_folder.id,
        visibility='public',
        storage_mode='drive',  # PR9 必备
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    return file_row


@pytest_asyncio.fixture
async def second_member(db):
    """创建第二个测试成员 (跨用户场景用)"""
    member = Member(
        username='seconduser',
        name='第二个用户',
        password_hash=get_password_hash('test123456'),
        role='member',
        grade='研二',
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member
    # teardown
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
def second_headers(second_member):
    """第二个用户的认证 headers"""
    token = create_access_token(data={"sub": str(second_member.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def third_member(db):
    """第三个成员 (无权限测试用, private folder 场景)"""
    member = Member(
        username='thirduser',
        name='第三个用户',
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
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
def third_headers(third_member):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(third_member.id)})}"}


# ==========================================================================
# 场景 1: 创建顶层评论 (file_id)
# ==========================================================================


@pytest.mark.asyncio
async def test_create_top_level_file_comment(
    client, auth_headers, drive_file
):
    """场景 1: 创建文件顶层评论 (无 parent_id)"""
    resp = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={
            'file_id': drive_file.id,
            'content': '这个实验数据有疑问 @张三',
            'mentions': [2, 3],
        },
    )
    assert resp.status_code == 201, f"创建失败: {resp.text}"
    data = resp.json()
    assert data['file_id'] == drive_file.id
    assert data['folder_id'] is None
    assert data['parent_id'] is None
    assert data['is_top_level'] is True
    assert data['is_resolved'] is False
    assert data['content'] == '这个实验数据有疑问 @张三'
    assert data['mentions'] == [2, 3]
    assert data['author']['name'] == '测试用户'
    assert 'id' in data
    assert 'created_at' in data


# ==========================================================================
# 场景 2: 嵌套回复 (parent_id)
# ==========================================================================


@pytest.mark.asyncio
async def test_nested_reply_then_deep_reply(
    client, auth_headers, second_headers, drive_file
):
    """场景 2: A 创建顶层 → B 嵌套回复 → A 再嵌套回复 (2 层深度)"""
    # A 创建顶层评论
    r1 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': drive_file.id, 'content': 'A 顶层评论'},
    )
    assert r1.status_code == 201
    parent_id = r1.json()['id']

    # B 嵌套回复
    r2 = await client.post(
        '/api/v1/drive/comments',
        headers=second_headers,
        json={
            'file_id': drive_file.id,
            'parent_id': parent_id,
            'content': 'B 嵌套回复',
        },
    )
    assert r2.status_code == 201, f"B 回复失败: {r2.text}"
    assert r2.json()['parent_id'] == parent_id
    assert r2.json()['is_top_level'] is False

    # A 再嵌套回复 (3 层深度: 顶层 → B → A)
    r3 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={
            'file_id': drive_file.id,
            'parent_id': r2.json()['id'],
            'content': 'A 二次嵌套回复',
        },
    )
    assert r3.status_code == 201, f"A 二次嵌套失败: {r3.text}"
    assert r3.json()['parent_id'] == r2.json()['id']

    # 验证 list 接口返回嵌套树
    list_resp = await client.get(
        f'/api/v1/drive/comments?file_id={drive_file.id}',
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data['total'] == 1, "只返回 1 个顶层评论"
    top = list_data['items'][0]
    assert top['id'] == parent_id
    assert len(top['replies']) == 1, "顶层评论有 1 个直接子回复 (B 的)"
    assert top['replies'][0]['id'] == r2.json()['id']
    assert top['replies'][0]['replies'] == [], "2 层嵌套的子回复列表为空 (当前 list 只显示 1 层)"


# ==========================================================================
# 场景 3: 编辑评论 (作者本人) + 跨用户拒绝
# ==========================================================================


@pytest.mark.asyncio
async def test_update_comment_author_only(
    client, auth_headers, second_headers, drive_file
):
    """场景 3: 仅 author 可编辑; B 试图编辑 A 的评论 → 403"""
    # A 创建
    r1 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': drive_file.id, 'content': '原始内容'},
    )
    assert r1.status_code == 201
    cid = r1.json()['id']

    # A 编辑 (成功)
    r2 = await client.patch(
        f'/api/v1/drive/comments/{cid}',
        headers=auth_headers,
        json={'content': '已修改内容'},
    )
    assert r2.status_code == 200
    assert r2.json()['content'] == '已修改内容'

    # B 试图编辑 (403)
    r3 = await client.patch(
        f'/api/v1/drive/comments/{cid}',
        headers=second_headers,
        json={'content': 'B 试图覆盖'},
    )
    assert r3.status_code == 403, f"B 编辑应被拒, 实际 {r3.status_code}: {r3.text}"


# ==========================================================================
# 场景 4: 删除评论 (CASCADE 子回复)
# ==========================================================================


@pytest.mark.asyncio
async def test_delete_comment_cascades_replies(
    client, auth_headers, second_headers, drive_file
):
    """场景 4: 删除顶层评论 → CASCADE 自动删子回复"""
    # A 创建顶层
    r1 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': drive_file.id, 'content': '顶层'},
    )
    top_id = r1.json()['id']

    # B 嵌套回复
    r2 = await client.post(
        '/api/v1/drive/comments',
        headers=second_headers,
        json={'file_id': drive_file.id, 'parent_id': top_id, 'content': 'B 回复'},
    )
    child_id = r2.json()['id']

    # B 试图删 A 的顶层 (403)
    r_bad = await client.delete(
        f'/api/v1/drive/comments/{top_id}',
        headers=second_headers,
    )
    assert r_bad.status_code == 403

    # A 删除顶层 (204)
    r_ok = await client.delete(
        f'/api/v1/drive/comments/{top_id}',
        headers=auth_headers,
    )
    assert r_ok.status_code == 204

    # 顶层和子回复都已删
    r_get = await client.get(
        f'/api/v1/drive/comments/{top_id}',
        headers=auth_headers,
    )
    assert r_get.status_code == 404, "顶层已删"

    r_get_child = await client.get(
        f'/api/v1/drive/comments/{child_id}',
        headers=auth_headers,
    )
    assert r_get_child.status_code == 404, "子回复 cascade 已删"


# ==========================================================================
# 场景 5: 标记 resolved (author + file owner)
# ==========================================================================


@pytest.mark.asyncio
async def test_resolve_comment_author_and_owner(
    client, auth_headers, second_headers, drive_file
):
    """场景 5: A 创建 → B 回复 → A 标记 resolved (author 路径)

    额外验证 file owner (test_member) 也是 resolve 权限
    """
    # A 创建
    r1 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': drive_file.id, 'content': '问题描述'},
    )
    cid = r1.json()['id']

    # A 标记 resolved (author 权限)
    r2 = await client.post(
        f'/api/v1/drive/comments/{cid}/resolve',
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()['is_resolved'] is True
    assert r2.json()['resolved_at'] is not None
    assert r2.json()['resolved_by'] is not None

    # 幂等: 再次 resolve 不报错
    r3 = await client.post(
        f'/api/v1/drive/comments/{cid}/resolve',
        headers=auth_headers,
    )
    assert r3.status_code == 200
    assert r3.json()['is_resolved'] is True

    # A 取消 resolved
    r4 = await client.post(
        f'/api/v1/drive/comments/{cid}/unresolve',
        headers=auth_headers,
    )
    assert r4.status_code == 200
    assert r4.json()['is_resolved'] is False

    # B 试图 resolve A 的评论 (B 不是 author 也不是 file owner → 403)
    # 先让 A 重新 unresolved
    # 然后 B 操作
    r5 = await client.post(
        f'/api/v1/drive/comments/{cid}/resolve',
        headers=second_headers,
    )
    assert r5.status_code == 403, f"B resolve 应被拒: {r5.status_code}"


# ==========================================================================
# 跨用户权限: A 创建, B 回复, A resolved (整合场景)
# ==========================================================================


@pytest.mark.asyncio
async def test_cross_user_thread_full_flow(
    client, auth_headers, second_headers, drive_file
):
    """整合: A 创建顶层 → B 回复 → A 标记 resolved → 列表按 is_resolved 过滤"""
    # A 创建
    r1 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': drive_file.id, 'content': 'A 的问题'},
    )
    cid = r1.json()['id']

    # B 回复
    r2 = await client.post(
        '/api/v1/drive/comments',
        headers=second_headers,
        json={'file_id': drive_file.id, 'parent_id': cid, 'content': 'B 的回答'},
    )
    assert r2.status_code == 201

    # A 标记 resolved
    r3 = await client.post(
        f'/api/v1/drive/comments/{cid}/resolve',
        headers=auth_headers,
    )
    assert r3.json()['is_resolved'] is True

    # 列表按 is_resolved=true 过滤 (顶层 only)
    r_list = await client.get(
        f'/api/v1/drive/comments?file_id={drive_file.id}&is_resolved=true',
        headers=auth_headers,
    )
    assert r_list.status_code == 200
    list_data = r_list.json()
    assert list_data['total'] == 1
    assert list_data['items'][0]['id'] == cid

    # 列表按 is_resolved=false 过滤 (B 的回复是子回复, 不计入顶层)
    r_list2 = await client.get(
        f'/api/v1/drive/comments?file_id={drive_file.id}&is_resolved=false',
        headers=auth_headers,
    )
    assert r_list2.status_code == 200
    list_data2 = r_list2.json()
    assert list_data2['total'] == 0, "B 的回复是子回复, 顶层过滤后 total=0"


# ==========================================================================
# 权限校验: 无访问权限用户 → 403
# ==========================================================================


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_comment(
    client, third_headers, db, test_member, drive_folder
):
    """无权限用户 (folder visibility=private, 无 member 邀请) 评论 → 403"""
    # 修改 folder 为 private
    drive_folder.visibility = 'private'
    await db.commit()

    # 在 private folder 下创建文件
    private_file = Knowledge(
        file_name='private.pdf',
        file_path='/tmp/private.pdf',
        file_size=1024,
        file_type='pdf',
        uploader_id=test_member.id,
        folder_id=drive_folder.id,
        visibility='private',
        storage_mode='drive',
    )
    db.add(private_file)
    await db.commit()
    await db.refresh(private_file)

    # third_headers 用户评论 private file → 403
    resp = await client.post(
        '/api/v1/drive/comments',
        headers=third_headers,
        json={'file_id': private_file.id, 'content': '试图评论'},
    )
    assert resp.status_code == 403, f"应有 403, 实际 {resp.status_code}: {resp.text}"


# ==========================================================================
# 嵌套 target 错配校验
# ==========================================================================


@pytest.mark.asyncio
async def test_reply_to_parent_with_wrong_target(
    client, auth_headers, drive_file, drive_folder
):
    """嵌套回复必须与父评论同 target (file vs folder)"""
    # A 在 file 上创建顶层
    r1 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': drive_file.id, 'content': 'file 评论'},
    )
    parent_id = r1.json()['id']

    # 试图用 folder_id 嵌套回复 file 评论 (错配 → 400)
    r2 = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={
            'folder_id': drive_folder.id,
            'parent_id': parent_id,
            'content': '错配',
        },
    )
    assert r2.status_code == 400, f"target 错配应被拒, 实际 {r2.status_code}: {r2.text}"


# ==========================================================================
# XOR 校验: 同时传 file_id + folder_id → 400
# ==========================================================================


@pytest.mark.asyncio
async def test_create_with_both_file_and_folder_rejected(
    client, auth_headers, drive_file, drive_folder
):
    """Pydantic XOR 校验: file_id + folder_id 同时传 → 422"""
    resp = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={
            'file_id': drive_file.id,
            'folder_id': drive_folder.id,
            'content': 'test',
        },
    )
    assert resp.status_code == 422, f"XOR 失败应 422, 实际 {resp.status_code}"


# ==========================================================================
# file 不是 storage_mode=drive → 400
# ==========================================================================


@pytest.mark.asyncio
async def test_comment_on_non_drive_file_rejected(
    client, auth_headers, test_member, db
):
    """普通 kb 文件 (storage_mode != drive) 不支持评论 → 400"""
    kb_file = Knowledge(
        file_name='kb_file.pdf',
        file_path='/tmp/kb.pdf',
        file_size=1024,
        file_type='pdf',
        uploader_id=test_member.id,
        folder_id=None,
        visibility='private',
        storage_mode='kb',  # 非 drive
    )
    db.add(kb_file)
    await db.commit()
    await db.refresh(kb_file)

    resp = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': kb_file.id, 'content': 'test'},
    )
    assert resp.status_code == 400, f"kb 文件应被拒, 实际 {resp.status_code}"


# ==========================================================================
# folder 评论 (单独场景)
# ==========================================================================


@pytest.mark.asyncio
async def test_create_folder_level_comment(
    client, auth_headers, drive_folder
):
    """场景: 创建 folder 级别顶层评论 (无 file_id)"""
    resp = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'folder_id': drive_folder.id, 'content': 'folder 讨论'},
    )
    assert resp.status_code == 201, f"folder 评论失败: {resp.text}"
    data = resp.json()
    assert data['folder_id'] == drive_folder.id
    assert data['file_id'] is None
    assert data['is_top_level'] is True

    # 按 folder 过滤列表
    list_resp = await client.get(
        f'/api/v1/drive/comments?folder_id={drive_folder.id}',
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert list_resp.json()['total'] == 1


# ==========================================================================
# 列表分页
# ==========================================================================


@pytest.mark.asyncio
async def test_list_pagination(
    client, auth_headers, drive_file
):
    """分页测试: 创建 5 条顶层评论, page_size=2 应返回 2 条, total=5"""
    for i in range(5):
        r = await client.post(
            '/api/v1/drive/comments',
            headers=auth_headers,
            json={'file_id': drive_file.id, 'content': f'评论 #{i}'},
        )
        assert r.status_code == 201

    # page=1, page_size=2
    r1 = await client.get(
        f'/api/v1/drive/comments?file_id={drive_file.id}&page=1&page_size=2',
        headers=auth_headers,
    )
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1['total'] == 5
    assert len(data1['items']) == 2

    # page=3, page_size=2 (剩余 1 条)
    r3 = await client.get(
        f'/api/v1/drive/comments?file_id={drive_file.id}&page=3&page_size=2',
        headers=auth_headers,
    )
    assert r3.json()['total'] == 5
    assert len(r3.json()['items']) == 1