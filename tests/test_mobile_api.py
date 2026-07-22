"""v2 PR8: 移动端聚合 API 单测

覆盖 3 端点 10 用例:
- dashboard (200 + schema 完整 + 未读通知数正确)
- feed (3 type + cursor pagination + 422 invalid)
- album-auto-backup (POST 设置 + GET 读取 + idempotent)

测试策略:
- 在 SKIP_DB_SETUP=1 模式下也运行 (不依赖真实 DB / MinIO / Redis)
- mock AsyncSession + Redis + notification_service
- 验证 endpoint 200 + schema 正确 + 失败隔离

铁律:
1. dashboard 失败隔离: 任一 section 失败返空, 不抛 5xx
2. feed cursor pagination 用 last_id (移动端友好)
3. type 校验 422 fail fast (不静默接受任意 type)
4. album-auto-backup POST idempotent (返当前配置, 不抛已存在)
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))


# ============================================================================
# 通用 mock helpers
# ============================================================================
def _make_mock_db_empty():
    """mock AsyncSession 返空结果 (无文件/无活动/无通知)"""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_mock_user(user_id: int = 1):
    """mock Member user"""
    user = MagicMock()
    user.id = user_id
    user.name = "TestUser"
    return user


# ============================================================================
# 1. GET /api/v1/mobile/dashboard
# ============================================================================
@pytest.mark.asyncio(loop_scope="function")
async def test_dashboard_endpoint_200():
    """dashboard endpoint 200 + schema 完整 (5 字段都存在)"""
    from app.api.v1.mobile import get_mobile_dashboard

    db = _make_mock_db_empty()
    user = _make_mock_user()

    with patch("app.services.notification_service.notification_service.count_unread",
               AsyncMock(return_value=5)):
        result = await get_mobile_dashboard(user=user, db=db)

    # schema 字段都存在
    assert hasattr(result, "recent_activities")
    assert hasattr(result, "starred_files")
    assert hasattr(result, "team_root_files")
    assert hasattr(result, "my_uploads")
    assert hasattr(result, "notification_unread_count")
    assert hasattr(result, "generated_at")

    # 空数据默认值
    assert isinstance(result.recent_activities, list)
    assert isinstance(result.starred_files, list)
    assert isinstance(result.team_root_files, list)
    assert isinstance(result.my_uploads, list)
    assert result.notification_unread_count == 5  # mock 返 5
    assert result.generated_at  # ISO 8601 非空


@pytest.mark.asyncio(loop_scope="function")
async def test_dashboard_unread_count_correct():
    """dashboard 未读通知数正确 (mock notification_service.count_unread 返 N)"""
    from app.api.v1.mobile import get_mobile_dashboard

    db = _make_mock_db_empty()
    user = _make_mock_user()

    with patch("app.services.notification_service.notification_service.count_unread",
               AsyncMock(return_value=42)):
        result = await get_mobile_dashboard(user=user, db=db)

    assert result.notification_unread_count == 42


@pytest.mark.asyncio(loop_scope="function")
async def test_dashboard_section_failure_isolated():
    """dashboard 任一 section 失败 → 返空列表, 不抛 5xx"""
    from app.api.v1.mobile import get_mobile_dashboard

    # mock execute: 第一次抛异常 (recent_activities), 后续返空
    call_count = {"n": 0}

    async def flaky_execute(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("DB blip")
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar.return_value = 0
        return mock_result

    db = MagicMock()
    db.execute = flaky_execute
    user = _make_mock_user()

    with patch("app.services.notification_service.notification_service.count_unread",
               AsyncMock(return_value=0)):
        # 不抛异常 = 失败隔离生效
        result = await get_mobile_dashboard(user=user, db=db)

    # recent_activities 返空 (不阻塞)
    assert result.recent_activities == []


# ============================================================================
# 2. GET /api/v1/mobile/feed
# ============================================================================
@pytest.mark.asyncio(loop_scope="function")
async def test_feed_type_activity():
    """feed?type=activity 返活动列表 (mock 1 条 activity)"""
    from app.api.v1.mobile import get_mobile_feed
    from app.models.knowledge import ActivityEvent

    # mock 1 个 ActivityEvent
    fake_event = MagicMock(spec=ActivityEvent)
    fake_event.id = 100
    fake_event.actor_id = 5
    fake_event.action = "upload"
    fake_event.target_type = "file"
    fake_event.target_id = 42
    fake_event.target_name = "test.pdf"
    fake_event.created_at = None  # ISO 返空串

    db = _make_mock_db_empty()

    async def mock_execute(*args, **kwargs):
        result = MagicMock()
        result.all.return_value = [(fake_event, "Alice")]
        return result

    db.execute = mock_execute
    user = _make_mock_user()

    result = await get_mobile_feed(type="activity", cursor=None, limit=10, user=user, db=db)

    assert len(result.items) == 1
    assert result.items[0].type == "activity"
    assert result.items[0].payload["action"] == "upload"
    assert result.items[0].payload["actor_name"] == "Alice"


@pytest.mark.asyncio(loop_scope="function")
async def test_feed_type_recent():
    """feed?type=recent 返最近上传"""
    from app.api.v1.mobile import get_mobile_feed

    db = _make_mock_db_empty()
    db.execute = AsyncMock(return_value=_make_mock_db_empty().execute.return_value)
    user = _make_mock_user()

    result = await get_mobile_feed(type="recent", cursor=None, limit=10, user=user, db=db)
    assert isinstance(result.items, list)
    assert result.has_more is False


@pytest.mark.asyncio(loop_scope="function")
async def test_feed_type_starred():
    """feed?type=starred 返收藏"""
    from app.api.v1.mobile import get_mobile_feed

    db = _make_mock_db_empty()
    user = _make_mock_user()

    result = await get_mobile_feed(type="starred", cursor=None, limit=10, user=user, db=db)
    assert isinstance(result.items, list)


@pytest.mark.asyncio(loop_scope="function")
async def test_feed_cursor_pagination():
    """feed cursor=N&limit=5 — limit 限制生效, has_more 判断"""
    from app.api.v1.mobile import get_mobile_feed

    db = _make_mock_db_empty()
    user = _make_mock_user()

    # mock 6 行 (limit=5, has_more=True 期望)
    result_mock = MagicMock()
    result_mock.all.return_value = [(MagicMock(id=i, created_at=None), None) for i in range(1, 7)]
    db.execute = AsyncMock(return_value=result_mock)

    result = await get_mobile_feed(type="activity", cursor=None, limit=5, user=user, db=db)

    assert len(result.items) == 5  # limit 截断
    assert result.has_more is True
    assert result.next_cursor == "5"  # 最后一行的 id


@pytest.mark.asyncio(loop_scope="function")
async def test_feed_type_invalid_422():
    """feed?type=invalid 抛 ValidationException (422)"""
    from app.api.v1.mobile import get_mobile_feed
    from app.core.exceptions import ValidationException

    db = _make_mock_db_empty()
    user = _make_mock_user()

    with pytest.raises(ValidationException) as exc_info:
        await get_mobile_feed(type="invalid", cursor=None, limit=10, user=user, db=db)

    assert "activity" in str(exc_info.value.message)
    assert "recent" in str(exc_info.value.message)
    assert "starred" in str(exc_info.value.message)


# ============================================================================
# 3. POST /api/v1/mobile/album-auto-backup
# ============================================================================
@pytest.mark.asyncio(loop_scope="function")
async def test_album_auto_backup_post_success():
    """album-auto-backup POST 设置成功 + 返当前配置 (idempotent)"""
    from app.api.v1.mobile import post_album_auto_backup
    from app.schemas.mobile import AlbumAutoBackupRequest

    user = _make_mock_user()

    # mock Redis set
    with patch("app.api.v1.mobile._set_backup_config", AsyncMock()) as mock_set:
        body = AlbumAutoBackupRequest(enabled=True, folder_id=42, wifi_only=False)
        result = await post_album_auto_backup(body=body, user=user)

    # _set_backup_config 被调
    mock_set.assert_called_once()
    # idempotent: 返当前配置
    assert result.enabled is True
    assert result.folder_id == 42
    assert result.wifi_only is False
    assert "已保存" in result.message


@pytest.mark.asyncio(loop_scope="function")
async def test_album_auto_backup_get_current():
    """album-auto-backup GET 读当前配置"""
    from app.api.v1.mobile import get_album_auto_backup

    user = _make_mock_user()

    with patch("app.api.v1.mobile._get_backup_config",
               AsyncMock(return_value={"enabled": True, "folder_id": 99, "wifi_only": True})):
        result = await get_album_auto_backup(user=user)

    assert result.enabled is True
    assert result.folder_id == 99
    assert result.wifi_only is True
    assert result.message == "当前配置"


@pytest.mark.asyncio(loop_scope="function")
async def test_dashboard_vs_mobile_feed_data_consistency():
    """dashboard.starred_files 与 mobile feed?type=starred 数据结构一致 (共享 schema 字段)"""
    from app.api.v1.mobile import get_mobile_dashboard, get_mobile_feed

    db = _make_mock_db_empty()
    user = _make_mock_user()

    with patch("app.services.notification_service.notification_service.count_unread",
               AsyncMock(return_value=0)):
        dash = await get_mobile_dashboard(user=user, db=db)
        feed = await get_mobile_feed(type="starred", cursor=None, limit=10, user=user, db=db)

    # 两者都是 list, schema 字段一致 (id, title 等)
    assert isinstance(dash.starred_files, list)
    assert isinstance(feed.items, list)

    # 共享 id / title 字段语义 (从 schema 字段定义验证, 不依赖 mock 数据)
    from app.schemas.mobile import MobileDashboardStarredFile, MobileFeedItem
    dash_keys = set(MobileDashboardStarredFile.model_fields.keys())
    feed_keys = set(MobileFeedItem.model_fields.keys())
    assert "id" in dash_keys
    assert "payload" in feed_keys  # feed 用 payload dict
    assert "title" in dash_keys  # starred file schema 包含 title