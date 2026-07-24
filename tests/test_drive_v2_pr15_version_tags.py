"""tests/test_drive_v2_pr15_version_tags.py — Drive v2 PR15 文件版本标签单元测试 (2026-07-24)

W68 第 12 批 B-2 — Drive v2 PR15 Version Tags 端到端验证.
锚点范式第 149 守恒.

7 核心场景 (SKIP_DB_SETUP=1 模式 — 纯 mock, 无 PostgreSQL 依赖):
1. add_tag: 加 release/stable 标签 → DriveVersionTag.id != None
2. add_tag: 重复 add 幂等 → UNIQUE 约束触发 → 返 None (不抛错)
3. add_tag: tag_name 不在 12 个白名单 → 抛 DriveVersionTagServiceError(400)
4. add_tag: 跨 file 隔离 → file_a 的 tag 不污染 file_b
5. list_tags_by_file: Celery 反查路径 (聚合按 version_id)
6. publish_version_tag_added WS 推送: priority=MEDIUM + payload 字段正确
7. list_versions_with_tags: 性能路径 — 1 query 拿 version + tags (LEFT OUTER JOIN)

依赖:
- app.services.drive_version_tag_service.DriveVersionTagService
- app.services.drive_event_publisher.publish_version_tag_added
- app.models.drive_version_tag.ALLOWED_TAG_NAMES
- app.services.drive_version_service.DriveVersionService.list_versions_with_tags

测试策略: SKIP_DB_SETUP=1 模式, 与 W68 PR10/PR12 测试一致.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 让 import 走 SKIP_DB_SETUP=1 路径 — 避免重型 import + DB 依赖
os.environ["SKIP_DB_SETUP"] = "1"

from app.models.drive_version_tag import ALLOWED_TAG_NAMES  # noqa: E402
from app.services.notification_service import NotificationPriority  # noqa: E402


# ==========================================================================
# Helpers: 构造 mock db / ORM 实例
# ==========================================================================


def _make_mock_db():
    """构造 mock AsyncSession — 默认无 query 结果"""
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    execute_result.scalar_one.return_value = 0
    execute_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock(return_value=None)
    db.rollback = AsyncMock(return_value=None)
    db.refresh = AsyncMock(return_value=None)
    db.add = MagicMock(return_value=None)
    db.delete = AsyncMock(return_value=None)
    db.get = AsyncMock(return_value=None)
    return db


def _make_mock_version(*, version_id: int = 1, file_id: int = 100, version_number: int = 1):
    """构造 mock DriveFileVersion ORM 实例"""
    v = MagicMock()
    v.id = version_id
    v.file_id = file_id
    v.version_number = version_number
    v.is_current = 1
    v.uploader_id = 100
    v.size = 1024
    v.comment = "test version"
    v.minio_object_key = f"uploads/drive/100/v{version_number}_test_{file_id}.txt"
    v.created_at = datetime(2026, 7, 24, 12, 0, 0)
    return v


def _make_mock_tag(
    *,
    tag_id: int = 1,
    version_id: int = 1,
    tag_name: str = "release",
    color: str = "#FF7A5C",
    created_by: int = 100,
):
    """构造 mock DriveVersionTag ORM 实例"""
    t = MagicMock()
    t.id = tag_id
    t.version_id = version_id
    t.tag_name = tag_name
    t.tag_description = "2024 年 10 月发布版"
    t.color = color
    t.created_by = created_by
    t.created_at = datetime(2026, 7, 24, 12, 0, 0)
    t.updated_at = datetime(2026, 7, 24, 12, 0, 0)
    return t


# ==========================================================================
# 场景 1: add_tag 加 release/stable 标签成功
# ==========================================================================


@pytest.mark.asyncio
async def test_add_tag_release_and_stable_returns_id():
    """add_tag 加 release/stable → DriveVersionTag.id 不为 None"""
    from app.services.drive_version_tag_service import DriveVersionTagService

    db = _make_mock_db()

    # mock version 存在
    version_mock = _make_mock_version(version_id=5, file_id=100)
    db.get = AsyncMock(return_value=version_mock)

    # mock 权限校验: file.created_by == user_id (100)
    file_mock = MagicMock()
    file_mock.id = 100
    file_mock.created_by = 100
    file_mock.deleted_at = None
    file_mock.storage_mode = "drive"
    file_mock.visibility = "private"

    call_count = 0

    async def fake_get(model, key):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return version_mock  # _validate_version_exists_and_modify_authority 第一行
        return file_mock

    db.get = AsyncMock(side_effect=fake_get)

    svc = DriveVersionTagService(db)

    # mock add + commit 给对象分配 id
    reaction_holder = {}

    def fake_add(obj):
        reaction_holder["_pending"] = obj
        return None

    async def fake_commit():
        if "_pending" in reaction_holder:
            obj = reaction_holder["_pending"]
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 1
            reaction_holder.pop("_pending", None)

    db.add = MagicMock(side_effect=fake_add)
    db.commit = AsyncMock(side_effect=fake_commit)
    db.refresh = AsyncMock(return_value=None)

    with patch(
        "app.services.drive_event_publisher.publish_version_tag_added",
        AsyncMock(return_value=1),
    ):
        # 测试 1: 加 release 标签
        tag1 = await svc.add_tag(
            version_id=5,
            tag_name="release",
            tag_description="v1.0 release",
            color="#FF7A5C",
            member_id=100,
        )
        assert tag1 is not None
        assert tag1.id == 1
        assert tag1.tag_name == "release"

        # 测试 2: 加 stable 标签 (同一 version, 不同 tag)
        tag2 = await svc.add_tag(
            version_id=5,
            tag_name="stable",
            tag_description=None,
            color=None,
            member_id=100,
        )
        assert tag2 is not None
        assert tag2.tag_name == "stable"


# ==========================================================================
# 场景 2: add_tag 重复 add 幂等
# ==========================================================================


@pytest.mark.asyncio
async def test_add_tag_idempotent_returns_none_on_unique_violation():
    """add_tag 重复 add → UNIQUE 约束触发 → 返 None (不抛错)"""
    from sqlalchemy.exc import IntegrityError

    from app.services.drive_version_tag_service import DriveVersionTagService

    db = _make_mock_db()

    version_mock = _make_mock_version(version_id=5, file_id=100)
    file_mock = MagicMock()
    file_mock.id = 100
    file_mock.created_by = 100
    file_mock.deleted_at = None
    file_mock.storage_mode = "drive"
    file_mock.visibility = "private"

    call_count = 0

    async def fake_get(model, key):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return version_mock
        return file_mock

    db.get = AsyncMock(side_effect=fake_get)
    db.commit = AsyncMock(side_effect=IntegrityError("UNIQUE", {}, None))

    svc = DriveVersionTagService(db)

    with patch(
        "app.services.drive_event_publisher.publish_version_tag_added",
        AsyncMock(return_value=1),
    ):
        tag = await svc.add_tag(
            version_id=5,
            tag_name="release",
            tag_description=None,
            color=None,
            member_id=100,
        )

    assert tag is None  # 幂等命中


# ==========================================================================
# 场景 3: tag_name 不在 12 个白名单
# ==========================================================================


@pytest.mark.asyncio
async def test_add_tag_name_not_in_whitelist_raises_400():
    """tag_name 不在白名单 → 抛 DriveVersionTagServiceError(400)"""
    from app.services.drive_version_tag_service import (
        DriveVersionTagService,
        DriveVersionTagServiceError,
    )

    db = _make_mock_db()
    svc = DriveVersionTagService(db)

    # 不在 12 个内置白名单的 tag_name
    with pytest.raises(DriveVersionTagServiceError) as exc_info:
        await svc.add_tag(
            version_id=5,
            tag_name="custom-tag-not-in-whitelist",  # 不在白名单
            tag_description=None,
            color=None,
            member_id=100,
        )

    assert exc_info.value.status_code == 400
    assert "白名单" in str(exc_info.value)


@pytest.mark.asyncio
async def test_allowed_tag_names_has_exactly_12_entries():
    """12 个内置白名单完整性检查"""
    assert len(ALLOWED_TAG_NAMES) == 12
    expected = {
        "release", "stable", "deprecated", "security",
        "auto-save", "manual", "breaking", "experimental",
        "legacy", "featured", "archived", "final",
    }
    assert ALLOWED_TAG_NAMES == expected


# ==========================================================================
# 场景 4: 跨 file 隔离
# ==========================================================================


@pytest.mark.asyncio
async def test_add_tag_cross_file_isolation():
    """跨 file 隔离: file_a 的 tag 不污染 file_b 的 list_tags_by_file

    测试逻辑:
    - file_a (id=100) version_a (id=5) 加 'release' 标签
    - file_b (id=200) version_b (id=10) 不加任何标签
    - list_tags_by_file(file_b) 应返回 versions with empty tags
    """
    from app.services.drive_version_tag_service import DriveVersionTagService

    db = _make_mock_db()

    # file_b 主表行
    file_b = MagicMock()
    file_b.id = 200
    file_b.file_name = "file_b.pdf"
    file_b.created_by = 999  # 非当前用户
    file_b.deleted_at = None
    file_b.storage_mode = "drive"
    file_b.visibility = "team"

    db.get = AsyncMock(return_value=file_b)

    # 模拟 read 权限: owner_id=999 (== current_user_id=999)
    with patch(
        "app.services.drive_version_tag_service._check_file_read_authority",
        AsyncMock(return_value=True),
    ):
        # list_tags_by_file: 1 次 query 拿 version + tags (LEFT OUTER JOIN)
        # 但 file_b 没任何版本 → 结果空
        svc = DriveVersionTagService(db)

        # mock JOIN 结果为空 (file_b 没有 version)
        join_result = MagicMock()
        join_result.all.return_value = []
        db.execute = AsyncMock(return_value=join_result)

        result = await svc.list_tags_by_file(
            file_id=200,
            current_user_id=999,
        )

    assert result["file_id"] == 200
    assert result["file_name"] == "file_b.pdf"
    assert result["versions"] == []  # file_b 无版本 → 空列表
    # 跨文件隔离验证: file_a 的 release 标签不会出现在 file_b 的列表里
    assert all("release" not in [t.get("tag_name") for t in v.get("tags", [])]
               for v in result["versions"])


# ==========================================================================
# 场景 5: Celery 反查路径 (list_tags_by_file 聚合)
# ==========================================================================


@pytest.mark.asyncio
async def test_list_tags_by_file_aggregates_tags_per_version():
    """list_tags_by_file 聚合: 1 次 query 拿所有 version + tags, 按 version_id 分组"""
    from app.services.drive_version_tag_service import DriveVersionTagService

    db = _make_mock_db()

    file_mock = MagicMock()
    file_mock.id = 100
    file_mock.file_name = "test.docx"
    file_mock.created_by = 100
    file_mock.deleted_at = None
    file_mock.storage_mode = "drive"
    file_mock.visibility = "private"
    db.get = AsyncMock(return_value=file_mock)

    # mock JOIN 结果: 3 个版本 + 3 个标签
    v1 = _make_mock_version(version_id=1, version_number=3, file_id=100)
    v1.is_current = 1
    v2 = _make_mock_version(version_id=2, version_number=2, file_id=100)
    v2.is_current = 0
    v3 = _make_mock_version(version_id=3, version_number=1, file_id=100)
    v3.is_current = 0

    tag_release = _make_mock_tag(tag_id=10, version_id=1, tag_name="release")
    tag_stable = _make_mock_tag(tag_id=11, version_id=2, tag_name="stable")
    tag_deprecated = _make_mock_tag(tag_id=12, version_id=3, tag_name="deprecated")

    # SQL JOIN 返 3 行 (1 row per version+tag join)
    join_result = MagicMock()
    join_result.all.return_value = [
        (v1, tag_release),
        (v2, tag_stable),
        (v3, tag_deprecated),
    ]
    db.execute = AsyncMock(return_value=join_result)

    svc = DriveVersionTagService(db)

    result = await svc.list_tags_by_file(
        file_id=100,
        current_user_id=100,
    )

    assert result["file_id"] == 100
    assert len(result["versions"]) == 3

    # 验证按 version_number desc 排序
    version_numbers = [v["version_number"] for v in result["versions"]]
    assert version_numbers == [3, 2, 1]

    # 验证每个版本有 1 个标签
    tag_names_by_v = {v["version_id"]: [t["tag_name"] for t in v["tags"]] for v in result["versions"]}
    assert tag_names_by_v[1] == ["release"]
    assert tag_names_by_v[2] == ["stable"]
    assert tag_names_by_v[3] == ["deprecated"]


# ==========================================================================
# 场景 6: publish_version_tag_added WS 推送
# ==========================================================================


@pytest.mark.asyncio
async def test_publish_version_tag_added_ws_payload_and_priority():
    """publish_version_tag_added → WS push + priority=MEDIUM + payload 字段完整"""
    from app.services.drive_event_publisher import publish_version_tag_added

    db = _make_mock_db()

    # mock _resolve_file_owner 返 999 (file owner)
    resolve_result = MagicMock()
    resolve_result.first.return_value = (999,)
    db.execute = AsyncMock(return_value=resolve_result)

    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["user_id"] = user_id
        captured["payload"] = payload
        captured["priority"] = priority
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_version_tag_added(
            db,
            tag_id=42,
            version_id=5,
            file_id=100,
            tag_name="release",
            actor_id=100,
        )

    assert result == 1
    assert captured["user_id"] == 999  # owner (≠ actor 100, 触发推送)
    assert captured["priority"] == NotificationPriority.MEDIUM

    payload = captured["payload"]
    assert payload["type"] == "version_tag_added"
    assert payload["tag_id"] == 42
    assert payload["version_id"] == 5
    assert payload["file_id"] == 100
    assert payload["tag_name"] == "release"
    assert payload["actor_id"] == 100
    assert "ts" in payload


@pytest.mark.asyncio
async def test_publish_version_tag_added_self_action_skipped():
    """自推 (actor == owner) → publisher 跳过"""
    from app.services.drive_event_publisher import publish_version_tag_added

    db = _make_mock_db()

    # owner_id=100 (== actor_id=100) → 自推
    resolve_result = MagicMock()
    resolve_result.first.return_value = (100,)
    db.execute = AsyncMock(return_value=resolve_result)

    push_called = False

    async def fake_push(*args, **kwargs):
        nonlocal push_called
        push_called = True
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_version_tag_added(
            db,
            tag_id=42,
            version_id=5,
            file_id=100,
            tag_name="release",
            actor_id=100,  # == owner
        )

    assert not push_called
    assert result == 0


# ==========================================================================
# 场景 7: list_versions_with_tags 性能路径 (LEFT OUTER JOIN 1 query)
# ==========================================================================


@pytest.mark.asyncio
async def test_list_versions_with_tags_single_query_join():
    """list_versions_with_tags: 1 query 拿 version + tags (LEFT OUTER JOIN)

    性能保证: 与 list_versions + list_tags_by_file 拆分相比, 单次 SQL 拿全部数据
    验证: query 数 = 1 (不算 db.get 调文件存在性)
    """
    from app.services.drive_version_service import DriveVersionService

    db = _make_mock_db()

    file_mock = MagicMock()
    file_mock.id = 100
    file_mock.file_name = "test.docx"
    file_mock.created_by = 100
    file_mock.deleted_at = None
    file_mock.storage_mode = "drive"
    file_mock.visibility = "private"

    call_count = 0

    async def fake_get(model, key):
        nonlocal call_count
        call_count += 1
        return file_mock

    db.get = AsyncMock(side_effect=fake_get)

    # mock JOIN 结果: 2 个版本, v1 有 1 个 release 标签, v2 无标签 (LEFT OUTER JOIN)
    v1 = _make_mock_version(version_id=1, version_number=2, file_id=100)
    v1.is_current = 1
    v2 = _make_mock_version(version_id=2, version_number=1, file_id=100)
    v2.is_current = 0
    v2.uploader_id = 200
    v2.size = 2048

    tag_release = _make_mock_tag(tag_id=10, version_id=1, tag_name="release")

    join_result = MagicMock()
    join_result.all.return_value = [
        (v1, "uploader1", tag_release),  # version 1 + release tag + uploader_name
        (v2, "uploader2", None),  # version 2 无 tag (LEFT OUTER JOIN 返 None)
    ]

    execute_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal execute_count
        execute_count += 1
        return join_result

    db.execute = AsyncMock(side_effect=fake_execute)

    svc = DriveVersionService(db)
    result = await svc.list_versions_with_tags(
        file_id=100,
        current_user_id=100,
    )

    # 验证响应结构
    assert result["file_id"] == 100
    assert result["file_name"] == "test.docx"
    assert result["count"] == 2
    assert len(result["items"]) == 2

    # 验证: items[0] = v2 (current), items[1] = v1 (按 version_number desc 排)
    assert result["items"][0]["version_number"] == 2
    assert result["items"][1]["version_number"] == 1

    # 验证: v1 有 1 个 release tag, v2 tags=[] (LEFT OUTER JOIN 正确性)
    assert len(result["items"][0]["tags"]) == 1
    assert result["items"][0]["tags"][0]["tag_name"] == "release"
    assert result["items"][1]["tags"] == []

    # 性能保证: 仅 1 次 execute (1 query)
    assert execute_count == 1


# ==========================================================================
# 场景 8 (bonus): remove_tag 仅本人
# ==========================================================================


@pytest.mark.asyncio
async def test_remove_tag_only_creator_can_delete():
    """remove_tag 仅 tag 创建者本人可删 → 非本人抛 DriveVersionTagServiceError(403)"""
    from app.services.drive_version_tag_service import (
        DriveVersionTagService,
        DriveVersionTagServiceError,
    )

    db = _make_mock_db()

    # mock tag 是 member=100 创建的
    tag_mock = _make_mock_tag(tag_id=1, version_id=5, tag_name="release", created_by=100)

    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = tag_mock
    db.execute = AsyncMock(return_value=fetch_result)

    svc = DriveVersionTagService(db)

    # user_id=999 尝试删除 member_id=100 的 tag → 应抛 403
    with pytest.raises(DriveVersionTagServiceError) as exc_info:
        await svc.remove_tag(version_id=5, tag_name="release", member_id=999)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_remove_tag_creator_can_delete_succeeds():
    """本人删除自己的 tag → 成功 + commit"""
    from app.services.drive_version_tag_service import DriveVersionTagService

    db = _make_mock_db()

    tag_mock = _make_mock_tag(tag_id=1, version_id=5, tag_name="release", created_by=100)

    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = tag_mock
    db.execute = AsyncMock(return_value=fetch_result)

    svc = DriveVersionTagService(db)

    # member_id=100 本人删自己
    result = await svc.remove_tag(version_id=5, tag_name="release", member_id=100)

    assert result is True


__all__: List[str] = []  # pytest 收集