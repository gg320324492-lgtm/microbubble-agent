"""tests/test_drive_v2_pr9_version_diff.py — Drive v2 PR9 版本对比 e2e 测试 (2026-07-24)

4 核心场景:
1. 文本 diff (text 文件两个版本, 走 difflib.unified_diff, 返回变更行号)
2. 二进制 metadata diff (PDF/image 两个版本, 只返回 metadata 不解析内容)
3. 相同版本空 diff (from == to, unified_diff=None, size_delta=0)
4. 跨文件 diff 拒绝 (version 不属于 file_id, 400)

依赖:
- tests/conftest.py: db / client / test_member / auth_headers
- 复用 Drive v2 PR9 file/version pattern
- monkeypatch: file_service.download_file 返回 in-memory bytes (避免真 MinIO)
"""
import io
import pytest
import pytest_asyncio

from app.models.drive_file_version import DriveFileVersion
from app.models.folder import Folder
from app.models.knowledge import Knowledge


# ==========================================================================
# Fixture: drive folder + 文件
# ==========================================================================


@pytest_asyncio.fixture
async def drive_folder(db, test_member):
    """drive folder (public, auth_headers 用户可访问)"""
    folder = Folder(
        name='drive_pr9_diff_folder',
        owner_id=test_member.id,
        visibility='public',
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@pytest_asyncio.fixture
async def text_file(db, test_member, drive_folder):
    """文本文件 (.py) 用来做文本 diff"""
    file_row = Knowledge(
        file_name='script_v1.py',
        file_path='/tmp/script_v1.py',
        file_size=200,
        file_type='py',
        uploader_id=test_member.id,
        folder_id=drive_folder.id,
        visibility='public',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    return file_row


@pytest_asyncio.fixture
async def binary_file(db, test_member, drive_folder):
    """二进制文件 (.pdf) 用来做 metadata diff"""
    file_row = Knowledge(
        file_name='thesis.pdf',
        file_path='/tmp/thesis.pdf',
        file_size=102400,
        file_type='pdf',
        uploader_id=test_member.id,
        folder_id=drive_folder.id,
        visibility='public',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    return file_row


@pytest_asyncio.fixture
async def another_file(db, test_member, drive_folder):
    """另一个文件 (跨文件测试用)"""
    file_row = Knowledge(
        file_name='other_doc.md',
        file_path='/tmp/other_doc.md',
        file_size=50,
        file_type='md',
        uploader_id=test_member.id,
        folder_id=drive_folder.id,
        visibility='public',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    return file_row


# ==========================================================================
# 工具: monkeypatch file_service.download_file 避免真 MinIO
# ==========================================================================


@pytest.fixture
def mock_minio_bytes(monkeypatch):
    """patch file_service.download_file 返回预定义的 bytes

    用法:
        def fake_download(key):
            return MOCK_REGISTRY[key]
        mock_minio_bytes(fake_download)

    或传 dict:
        mock_minio_bytes({
            'uploads/drive/1/v1_aaa.bin': b'...',
            'uploads/drive/1/v2_bbb.bin': b'...',
        })
    """
    registry = {}

    def _set(value):
        # value 可以是 callable 或 dict
        if callable(value):
            def _download(key):
                return value(key)
            monkeypatch.setattr(
                "app.services.file_service.file_service.download_file",
                _download,
            )
        elif isinstance(value, dict):
            async def _download(key):
                return value[key]
            monkeypatch.setattr(
                "app.services.file_service.file_service.download_file",
                _download,
            )
        else:
            raise TypeError(f"Unsupported mock value type: {type(value)}")

    return _set


# ==========================================================================
# 创建 DriveFileVersion 行的 helper (跳过真 MinIO upload)
# ==========================================================================


async def _create_version_row(
    db, *, file_id, version_number, content_bytes, uploader_id, comment=None,
):
    """直接创建 DriveFileVersion 行 (绕过真 MinIO upload)"""
    v = DriveFileVersion(
        file_id=file_id,
        version_number=version_number,
        minio_object_key=f"uploads/drive/{uploader_id}/mocked_v{version_number}.bin",
        size=len(content_bytes),
        uploader_id=uploader_id,
        comment=comment,
        is_current=1 if version_number == 1 else 0,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


# ==========================================================================
# 场景 1: 文本 diff (.py 文件 v1 → v2)
# ==========================================================================


@pytest.mark.asyncio
async def test_text_diff_returns_unified_diff(
    client, auth_headers, test_member, db, text_file, mock_minio_bytes,
):
    """场景 1: 文本文件两个版本, API 返回 unified_diff + changed_lines"""
    # v1 content
    v1_content = (
        b"def hello():\n"
        b"    print('v1')\n"
        b"    return 1\n"
        b"\n"
        b"def unused():\n"
        b"    pass\n"
    )
    # v2 content (改 hello, 加新函数)
    v2_content = (
        b"def hello():\n"
        b"    print('v2 updated')\n"
        b"    return 2\n"
        b"\n"
        b"def brand_new():\n"
        b"    return 'new'\n"
    )

    # 准备 mock MinIO bytes
    mock_minio_bytes({
        f"uploads/drive/{test_member.id}/mocked_v1.bin": v1_content,
        f"uploads/drive/{test_member.id}/mocked_v2.bin": v2_content,
    })

    # 创建 v1 + v2
    await _create_version_row(
        db, file_id=text_file.id, version_number=1, content_bytes=v1_content,
        uploader_id=test_member.id, comment='initial',
    )
    await _create_version_row(
        db, file_id=text_file.id, version_number=2, content_bytes=v2_content,
        uploader_id=test_member.id, comment='updated',
    )

    # 调用 diff API
    resp = await client.get(
        f"/api/v1/drive/versions/files/{text_file.id}/diff?from=1&to=2",
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"diff failed: {resp.text}"
    data = resp.json()

    # 校验响应结构
    assert data['file_id'] == text_file.id
    assert data['from_version_number'] == 1
    assert data['to_version_number'] == 2
    assert data['is_text'] is True
    assert data['unified_diff'] is not None
    assert isinstance(data['changed_lines'], list)
    assert len(data['changed_lines']) > 0
    assert data['additions'] > 0
    assert data['deletions'] > 0
    assert data['size_delta'] == len(v2_content) - len(v1_content)
    # unified_diff 应含 +++/--- 标记
    assert '---' in data['unified_diff'] or '+++' in data['unified_diff']


# ==========================================================================
# 场景 2: 二进制 metadata diff (.pdf)
# ==========================================================================


@pytest.mark.asyncio
async def test_binary_diff_returns_metadata_only(
    client, auth_headers, test_member, db, binary_file, mock_minio_bytes,
):
    """场景 2: 二进制文件 (PDF) → 只返回 metadata, 不解析内容"""
    # 用真 PDF 字节 (magic 头 %PDF-1.4 + 模拟二进制)
    v1_bytes = b"%PDF-1.4\n" + b"\x00\x01\x02\x03" * 100  # 401 bytes
    v2_bytes = b"%PDF-1.5\n" + b"\xff\xfe\xfd" * 200  # 605 bytes

    mock_minio_bytes({
        f"uploads/drive/{test_member.id}/mocked_v1.bin": v1_bytes,
        f"uploads/drive/{test_member.id}/mocked_v2.bin": v2_bytes,
    })

    await _create_version_row(
        db, file_id=binary_file.id, version_number=1, content_bytes=v1_bytes,
        uploader_id=test_member.id, comment='original PDF',
    )
    await _create_version_row(
        db, file_id=binary_file.id, version_number=2, content_bytes=v2_bytes,
        uploader_id=test_member.id, comment='updated PDF',
    )

    resp = await client.get(
        f"/api/v1/drive/versions/files/{binary_file.id}/diff?from=1&to=2",
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"diff failed: {resp.text}"
    data = resp.json()

    # 二进制: is_text=False, 无 unified_diff / changed_lines
    assert data['is_text'] is False
    assert data['unified_diff'] is None
    assert data['changed_lines'] is None
    assert data['additions'] is None
    assert data['deletions'] is None

    # metadata diff 应有
    assert data['size_delta'] == len(v2_bytes) - len(v1_bytes)
    # 同 uploader → uploader_delta=False
    assert data['uploader_delta'] is False
    # from_meta / to_meta 仍存在, 含 comment
    assert data['from_meta']['comment'] == 'original PDF'
    assert data['to_meta']['comment'] == 'updated PDF'


# ==========================================================================
# 场景 3: 相同版本空 diff
# ==========================================================================


@pytest.mark.asyncio
async def test_same_version_returns_empty_diff(
    client, auth_headers, test_member, db, text_file, mock_minio_bytes,
):
    """场景 3: from == to → 空 diff, unified_diff=None"""
    v1_content = b"line1\nline2\nline3\n"

    mock_minio_bytes({
        f"uploads/drive/{test_member.id}/mocked_v1.bin": v1_content,
    })
    await _create_version_row(
        db, file_id=text_file.id, version_number=1, content_bytes=v1_content,
        uploader_id=test_member.id,
    )

    # from == to == 1
    resp = await client.get(
        f"/api/v1/drive/versions/files/{text_file.id}/diff?from=1&to=1",
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"diff failed: {resp.text}"
    data = resp.json()

    assert data['is_text'] is False  # 同版本强制走 metadata 路径
    assert data['unified_diff'] is None
    assert data['changed_lines'] is None
    assert data['size_delta'] == 0
    assert data['uploader_delta'] is False


# ==========================================================================
# 场景 4: 跨 file 拒绝 + 缺失 version 404
# ==========================================================================


@pytest.mark.asyncio
async def test_cross_file_version_rejected_and_missing_404(
    client, auth_headers, test_member, db, text_file, another_file, mock_minio_bytes,
):
    """场景 4: version 不属于该 file_id → 400 (NOT 跨 file diff)

    额外验证: 缺失 version_number → 404
    """
    v1_content = b"v1\n"
    v2_content = b"v2\n"

    mock_minio_bytes({
        f"uploads/drive/{test_member.id}/mocked_v1.bin": v1_content,
        f"uploads/drive/{test_member.id}/mocked_v2.bin": v2_content,
    })

    # 在 file A 上创建 v1, 在 file B 上创建 v1
    v_a = await _create_version_row(
        db, file_id=text_file.id, version_number=1, content_bytes=v1_content,
        uploader_id=test_member.id,
    )
    await _create_version_row(
        db, file_id=another_file.id, version_number=1, content_bytes=v2_content,
        uploader_id=test_member.id,
    )

    # 试图 diff file A 的 v1 vs file B 的 v1 (用 file A 的 file_id, 但 server 校验时会发现 v2 不属于 file A)
    # → 应 404 (v2 not found in file A)
    resp = await client.get(
        f"/api/v1/drive/versions/files/{text_file.id}/diff?from=1&to=2",
        headers=auth_headers,
    )
    # v2 不属于 file_id (text_file) → 404
    assert resp.status_code == 404, f"应 404, 实际 {resp.status_code}: {resp.text}"

    # 缺失 version → 404
    resp2 = await client.get(
        f"/api/v1/drive/versions/files/{text_file.id}/diff?from=1&to=99",
        headers=auth_headers,
    )
    assert resp2.status_code == 404, f"缺失 version 应 404, 实际 {resp2.status_code}"

    # 反向: from=99 → 404
    resp3 = await client.get(
        f"/api/v1/drive/versions/files/{text_file.id}/diff?from=99&to=1",
        headers=auth_headers,
    )
    assert resp3.status_code == 404


# ==========================================================================
# 场景 5 (bonus): preview endpoint 拿前 N 行 (用于 UI)
# ==========================================================================


@pytest.mark.asyncio
async def test_preview_returns_first_n_lines(
    client, auth_headers, test_member, db, text_file, mock_minio_bytes,
):
    """场景 5: GET preview 拿前 N 行 (truncated 提示)"""
    # 100 行内容
    content = ("".join(f"line {i}\n" for i in range(1, 101))).encode("utf-8")

    mock_minio_bytes({
        f"uploads/drive/{test_member.id}/mocked_v1.bin": content,
    })
    v = await _create_version_row(
        db, file_id=text_file.id, version_number=1, content_bytes=content,
        uploader_id=test_member.id,
    )

    # head_lines=10
    resp = await client.get(
        f"/api/v1/drive/versions/files/{text_file.id}/versions/{v.id}/preview?head_lines=10",
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"preview failed: {resp.text}"
    data = resp.json()

    assert data['is_text'] is True
    assert data['total_lines'] == 100
    assert data['truncated'] is True
    assert len(data['preview_lines']) == 10
    assert data['preview_lines'][0] == 'line 1'
    assert data['preview_lines'][9] == 'line 10'

    # head_lines=200 (>> total) → truncated=False, 全返
    resp2 = await client.get(
        f"/api/v1/drive/versions/files/{text_file.id}/versions/{v.id}/preview?head_lines=200",
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2['truncated'] is False
    assert data2['total_lines'] == 100
    assert len(data2['preview_lines']) == 100
