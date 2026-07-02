"""2026-07-02 v2 网盘 PR6-P12+ 增量 — drive_service 触发 notification_service 单测

覆盖 3 个 hook 点:
1. create_file (upload): owner != uploader 时通知 owner, 自通知 skip
2. toggle_star_file (star): owner != current_user_id 时通知 owner, 自通知 skip
3. create_share_link (share): owner != current_user_id 时通知 owner, 自通知 skip

不依赖真实 DB (SKIP_DB_SETUP=1 模式 + mock notification_service.create_mention),
集成测试可在后续 PR 加 (用真实 DB 验证 SQL + WS 推送).

铁律:
1. self-notification 必须 skip (owner == actor → 不通知自己)
2. notification 触发失败不能阻塞主流程 (try/except + logger.debug)
3. star 只有 action='star' 时通知, unstar 不通知 (避免噪音)
4. share 与 upload 都是 owner 操作 (current_user_id == created_by), 自通知总是 skip
   (本次实现是为未来 PR3 "team 协作通知 owner" 铺路, 当前都跳过)
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 跳过重型 import (conftest.py 同模式)
SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))


# ============================================================================
# 通用 mock helpers
# ============================================================================

def _make_fake_knowledge(
    *,
    id: int = 100,
    file_name: str = "test.pdf",
    created_by: int = 1,
    is_starred: bool = False,
    storage_mode: str = "drive",
    share_token: Optional[str] = None,
):
    """构造一个假 Knowledge ORM 行 (mock drive_service 内部 SELECT)"""
    fake = MagicMock()
    fake.id = id
    fake.file_name = file_name
    fake.created_by = created_by
    fake.is_starred = is_starred
    fake.storage_mode = storage_mode
    fake.share_token = share_token
    fake.share_expires_at = None
    fake.share_password = None
    return fake


def _make_mock_db(*, knowledge: Optional[object] = None):
    """构造 mock AsyncSession, 默认 SELECT 返 knowledge (None = 0 行)"""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = knowledge
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.commit = AsyncMock()

    # mock refresh: 让 knowledge 行获得 id=100 (模拟 PG 自增 id 赋值)
    async def fake_refresh(k):
        if k.id is None:
            k.id = 100
    db.refresh = fake_refresh
    return db


# ============================================================================
# create_file (upload) notification 触发
# ============================================================================

class TestCreateFileNotificationTrigger:
    """drive_service.create_file() 触发 notification_service.create_mention(context='upload')"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_file_owner_self_notification_skipped(self):
        """uploader == owner (典型场景) → skip 自通知 (避免噪音)"""
        from app.services.drive_service import DriveService
        from app.services.notification_service import NotificationService

        db = _make_mock_db()

        with patch("app.services.drive_service.activity_service") as mock_activity:
            with patch.object(NotificationService, "create_mention", new=AsyncMock()) as mock_create_mention:
                svc = DriveService(db)
                knowledge = await svc.create_file(
                    title="test",
                    file_path="drive/1/test.pdf",
                    file_name="test.pdf",
                    file_type=".pdf",
                    file_size=1024,
                    owner_id=1,
                    created_by=1,  # uploader == owner → skip
                )

                # 自通知应被 skip
                mock_create_mention.assert_not_called()
                assert knowledge.id is not None  # Knowledge 行仍创建成功

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_file_other_uploader_triggers_notification(self):
        """uploader != owner (跨用户上传场景) → 通知 owner"""
        from app.services.drive_service import DriveService
        from app.services.notification_service import NotificationService

        db = _make_mock_db()

        with patch("app.services.drive_service.activity_service"):
            with patch.object(NotificationService, "create_mention", new=AsyncMock()) as mock_create_mention:
                svc = DriveService(db)
                await svc.create_file(
                    title="test",
                    file_path="drive/2/test.pdf",
                    file_name="test.pdf",
                    file_type=".pdf",
                    file_size=1024,
                    owner_id=2,           # owner = user 2
                    created_by=1,         # uploader = user 1 (跨用户上传)
                )

                # 应触发 1 次 mention, 通知 owner_id=2
                mock_create_mention.assert_called_once()
                call_kwargs = mock_create_mention.call_args.kwargs
                assert call_kwargs["mentioned_user_id"] == 2  # owner
                assert call_kwargs["mentioned_by"] == 1        # uploader
                assert call_kwargs["context"] == "upload"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_file_notification_failure_does_not_block(self):
        """notification 抛异常 → create_file 仍返回 Knowledge (best-effort 不阻塞)"""
        from app.services.drive_service import DriveService
        from app.services.notification_service import NotificationService

        db = _make_mock_db()

        with patch("app.services.drive_service.activity_service"):
            with patch.object(
                NotificationService, "create_mention",
                new=AsyncMock(side_effect=Exception("Notification service unavailable")),
            ):
                svc = DriveService(db)
                # 不应抛, 应 try/except 吞掉 + logger.debug
                knowledge = await svc.create_file(
                    title="test",
                    file_path="drive/2/test.pdf",
                    file_name="test.pdf",
                    file_type=".pdf",
                    file_size=1024,
                    owner_id=2,
                    created_by=1,  # 跨用户 → 应触发, 但抛异常
                )
                # Knowledge 行仍创建成功
                assert knowledge.id is not None


# ============================================================================
# toggle_star_file (star) notification 触发
# ============================================================================

class TestToggleStarFileNotificationTrigger:
    """drive_service.toggle_star_file() 触发 notification_service.create_mention(context='star')"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_star_self_notification_skipped(self):
        """toggle star: created_by == current_user_id (自通知 skip)"""
        from app.services.drive_service import DriveService
        from app.services.notification_service import NotificationService

        fake_file = _make_fake_knowledge(id=100, created_by=1)
        db = _make_mock_db(knowledge=fake_file)

        with patch.object(NotificationService, "create_mention", new=AsyncMock()) as mock_create_mention:
            svc = DriveService(db)
            result = await svc.toggle_star_file(file_id=100, current_user_id=1)

            # 自通知 skip
            mock_create_mention.assert_not_called()
            assert result.is_starred is True  # star 成功

    @pytest.mark.asyncio(loop_scope="function")
    async def test_star_other_user_triggers_notification(self):
        """PR3 场景: team member star others' files → 通知 file owner"""
        from app.services.drive_service import DriveService
        from app.services.notification_service import NotificationService

        fake_file = _make_fake_knowledge(id=100, created_by=2)  # owner = user 2
        db = _make_mock_db(knowledge=fake_file)

        with patch.object(NotificationService, "create_mention", new=AsyncMock()) as mock_create_mention:
            svc = DriveService(db)
            # PR3: team member (user 1) star file owned by user 2
            # 当前 drive_service.toggle_star_file 仅 owner 可调, 这里仅做单测模拟未来扩展
            # 测试时需要 bypass owner 校验, 但 mock 已构造 fake_file
            # 这里直接 patch 校验逻辑或测试其他场景
            # 实际: drive_service 当前不容许非 owner star, 所以这条测试仅验证 self-skip
            # 跳过此 case (PR3 未来扩展)
            pytest.skip("PR3 team star 功能未实现, 此 case 留给未来")

    @pytest.mark.asyncio(loop_scope="function")
    async def test_unstar_does_not_trigger_notification(self):
        """unstar 不通知 (避免噪音)"""
        from app.services.drive_service import DriveService
        from app.services.notification_service import NotificationService

        fake_file = _make_fake_knowledge(id=100, created_by=1, is_starred=True)
        db = _make_mock_db(knowledge=fake_file)

        with patch.object(NotificationService, "create_mention", new=AsyncMock()) as mock_create_mention:
            svc = DriveService(db)
            result = await svc.toggle_star_file(file_id=100, current_user_id=1)

            # unstar 不通知
            mock_create_mention.assert_not_called()
            assert result.is_starred is False


# ============================================================================
# create_share_link (share) notification 触发
# ============================================================================

class TestCreateShareLinkNotificationTrigger:
    """drive_service.create_share_link() 触发 notification_service.create_mention(context='share')"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_share_self_notification_skipped(self):
        """create_share_link: owner 自分享 (created_by == current_user_id, 自通知 skip)"""
        from app.services.drive_service import DriveService
        from app.services.notification_service import NotificationService

        fake_file = _make_fake_knowledge(id=100, created_by=1)
        db = _make_mock_db(knowledge=fake_file)

        with patch("app.services.drive_service.activity_service"):
            with patch.object(NotificationService, "create_mention", new=AsyncMock()) as mock_create_mention:
                svc = DriveService(db)
                # create_share_link 仅 owner 可调, 所以是自通知
                # 未来 PR3 "admin 帮 owner 生成链接" 时, 这里会触发通知
                # 模拟 owner 视角: skip
                result = await svc.create_share_link(file_id=100, current_user_id=1)

                # 自通知 skip
                mock_create_mention.assert_not_called()
                assert result.share_token is not None  # share token 生成成功

    @pytest.mark.asyncio(loop_scope="function")
    async def test_share_other_user_triggers_notification(self):
        """PR3 场景: admin 帮 owner 生成 share link → 通知 owner"""
        # 当前 drive_service.create_share_link 仅 owner 可调, 此 case 留给 PR3
        # 跳过 (本次不实现)
        pytest.skip("PR3 admin share 功能未实现, 此 case 留给未来")


# ============================================================================
# 集成 API 签名验证 (向 chat_history_service 范式对齐)
# ============================================================================

class TestDriveNotificationIntegration:
    """drive_service 调 notification_service 的 API 签名对齐

    验证:
    1. notification_service.create_mention 静态方法签名匹配 (file_id, mentioned_user_id, mentioned_by, context)
    2. context 参数严格匹配 notification_service._build_title_body 模板 (upload / star / share)
    3. 自通知 skip 检查在 3 个 hook 点都生效 (owner_id == current_user_id)
    """

    def test_notification_context_values_match_title_template(self):
        """3 个 hook 用的 context 值 (upload / star / share) 都对应 _build_title_body 模板"""
        if SKIP_DB_SETUP:
            pytest.skip("SKIP_DB_SETUP=1：跳过重型 import")
        # upload → 'actor 在 file_name 提醒了你' (fallback, 因为没 'comment'/'reply'/'star'/'share' 模板)
        # star   → 'actor 收藏了你的文件'
        # share  → 'actor 分享了 file_name 给你'
        # (与 notification_service.py:233-242 一致)
        from app.services.notification_service import NotificationService
        # 静态读取 _build_title_body 源码, 验证 3 个 context 都在分支里
        import inspect
        source = inspect.getsource(NotificationService._build_title_body)
        assert "ctx == \"star\"" in source
        assert "ctx == \"share\"" in source
        # upload 走 else fallback (与 mention 同语义)

    def test_drive_service_uses_correct_context_for_each_hook(self):
        """drive_service 3 个 hook 使用的 context 字符串与 notification_service 模板一致"""
        import inspect
        from app.services import drive_service as ds_module
        source = inspect.getsource(ds_module)
        # upload (create_file)
        assert 'context="upload"' in source
        # star (toggle_star_file)
        assert 'context="star"' in source
        # share (create_share_link)
        assert 'context="share"' in source

    def test_self_notification_skipped_in_all_3_hooks(self):
        """3 个 hook 都有 self-notification skip 检查 (created_by == current_user_id)"""
        import inspect
        from app.services import drive_service as ds_module
        source = inspect.getsource(ds_module)
        # 3 个 hook 都用 `if f.created_by != current_user_id:` 或 `if owner_id_for_notify != uploader_id:` 守卫
        self_skip_count = source.count("created_by != current_user_id") + source.count("owner_id_for_notify != uploader_id")
        assert self_skip_count >= 3, f"期望 ≥3 个 self-notification skip 检查, 实测 {self_skip_count}"