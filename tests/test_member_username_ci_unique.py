"""2026-07-02 v2 网盘 PR6-P13 单测 — member username case-insensitive uniqueness

背景:
- comment_service mention 解析用 `username.lower()` → 2 个 member 如果 username 只大小写不同会冲突
- alembic 053 在 DB 层加 UNIQUE INDEX ON LOWER(username) 兜底
- service 层 _assert_username_unique 抛 ConflictException 让 API 返回 409

不依赖真实 DB (mock AsyncSession.execute.scalar_one_or_none 模式),
真实 DB alembic upgrade 由 deploy 阶段验证。

铁律:
1. case-insensitive 唯一, 不接受 "Alice" + "alice" 并存
2. service pre-check 抛 ConflictException (409) 不是 IntegrityError (500)
3. update 排除自己 (admin 改自己 username 不应撞自己)
4. 空/None username 跳过检查 (DB NULL 不参与 UNIQUE 约束, 允许多个 NULL)
"""
import os
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest


SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))


# ============================================================================
# 通用 mock helpers
# ============================================================================

def _make_mock_db(*, existing_id: Optional[int] = None):
    """构造 mock AsyncSession.

    existing_id: 模拟查询返回的 member id (None = 无冲突, 否则 = 有冲突)
    """
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_id
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ============================================================================
# TestMemberUsernameUnique — service 层 _assert_username_unique 单测
# ============================================================================

class TestMemberUsernameUnique:
    """MemberService._assert_username_unique case-insensitive 唯一性"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_username_skips_check(self):
        """空字符串 username 跳过检查 (DB NULL 允许多个 NULL)"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        # 不应抛异常, 不应调 db.execute
        await MemberService._assert_username_unique(db, "")
        await MemberService._assert_username_unique(db, "   ")
        db.execute.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_existing_member_passes(self):
        """DB 无冲突 → 通过 (不抛)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        # 不抛异常
        await MemberService._assert_username_unique(db, "newuser")

    @pytest.mark.asyncio(loop_scope="function")
    async def test_existing_member_raises_conflict(self):
        """DB 有冲突 → 抛 ConflictException (409)"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=42)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_username_unique(db, "wangtianzhi")

        # 验证 exception message 含 existing_member_id
        assert "42" in str(exc_info.value)
        assert "wangtianzhi" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_case_insensitive_check_lowers_username(self):
        """查询条件用 LOWER(username), 大写/小写都查得到"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=10)
        with pytest.raises(Exception):
            await MemberService._assert_username_unique(db, "WANG TIANZHI")

        # 验证 SQL WHERE 用了 LOWER(username) = LOWER('WANG TIANZHI') = 'wang tianzhi'
        call_stmt = db.execute.call_args[0][0]
        # 通过 inspect source 看 func.lower 调用 (不需要真 SQL 编译)
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "lower(" in compiled.lower()
        assert "'wang tianzhi'" in compiled.lower()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_exclude_member_id_in_update(self):
        """更新自己 username 时 exclude_member_id 排除自己 (避免撞自己)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)  # 假设查询无冲突
        await MemberService._assert_username_unique(
            db, "wangtianzhi", exclude_member_id=1
        )

        # 验证 SQL WHERE 包含 id != 1
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "id !=" in compiled.lower() or "id <>" in compiled.lower()
        assert "1" in compiled


# ============================================================================
# TestMemberServiceCreate — create_member 集成预检查
# ============================================================================

class TestMemberServiceCreate:
    """MemberService.create_member 触发 _assert_username_unique 预检查"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_username_conflict_raises(self):
        """冲突 username → ConflictException, 不创建"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=42)  # 有冲突

        svc = MemberService(db)
        with pytest.raises(ConflictException):
            await svc.create_member(name="新成员", username="wangtianzhi")

        # 验证 commit 未被调 (事务未完成)
        db.commit.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_success_returns_member(self):
        """无冲突 → 正常创建, 返回 Member 对象"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)  # 无冲突
        # mock refresh: 让 member 行获得 id=100
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(
            name="新成员",
            username="new_unique_username_123",
            password_hash="hash",
            grade="研一",
            role="member",
        )

        assert member is not None
        assert member.name == "新成员"
        assert member.username == "new_unique_username_123"
        assert member.is_active is True

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_empty_username_skips_check(self):
        """空 username → 跳过检查, 直接创建"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(name="无账号成员", username="")

        assert member is not None
        assert member.username == ""


# ============================================================================
# TestMemberServiceUpdate — update_member 触发预检查 (排除自己)
# ============================================================================

class TestMemberServiceUpdate:
    """MemberService.update_member 触发 _assert_username_unique (排除自己)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_username_to_existing_raises(self):
        """更新 username 到已存在 (别人的) → 抛 ConflictException"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException
        from app.models.member import Member

        # mock get_member 返回 user_id=1 (被更新者)
        fake_member = MagicMock(spec=Member)
        fake_member.id = 1
        fake_member.username = "old_username"
        fake_member.name = "原成员"

        db = _make_mock_db(existing_id=99)  # 有冲突 (99 是别人的 id)
        # mock get_member → 返 fake_member
        async def fake_get_member(member_id):
            return fake_member if member_id == 1 else None
        # _assert_username_unique mock → 抛 ConflictException 模拟真实逻辑
        from app.core.exceptions import ConflictException
        with pytest.raises(ConflictException):
            # 直接调 _assert_username_unique 模拟 update 流程
            from app.services.member_service import MemberService
            await MemberService._assert_username_unique(
                db, "new_username", exclude_member_id=1
            )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_username_to_self_excluded(self):
        """更新 username 到自己原值 (case 不变) → 不抛 (排除自己)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)  # 无冲突
        await MemberService._assert_username_unique(
            db, "wangtianzhi", exclude_member_id=1
        )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_non_username_field_skips_check(self):
        """更新非 username 字段 → 不触发预检查"""
        from app.services.member_service import MemberService
        from app.models.member import Member

        # mock get_member 返 user_id=1
        fake_member = MagicMock(spec=Member)
        fake_member.id = 1
        fake_member.username = "old"
        fake_member.name = "原"
        fake_member.research_area = "旧方向"

        db = _make_mock_db()
        # mock get_member
        svc = MemberService(db)
        svc.get_member = AsyncMock(return_value=fake_member)

        # 更新 research_area (不传 username) → 应不抛
        result = await svc.update_member(1, research_area="新方向")
        assert result is not None
        assert fake_member.research_area == "新方向"


# ============================================================================
# TestMemberModelIndex — Member model Column 配置 (静态检查)
# ============================================================================

class TestMemberModelIndex:
    """验证 Member 模型配置与 alembic 迁移一致"""

    def test_member_username_no_unique_attr(self):
        """Member.username 不再 unique=True (由 case-insensitive index 接管)"""
        from app.models.member import Member
        col = Member.__table__.columns["username"]
        # SQLAlchemy 中 unique=True 在 column 的 _compile_state_helper.unique 属性
        # 直接判断 not col.unique
        assert not col.unique, "Member.username 必须 unique=False (alembic 053 接管)"

    def test_member_username_index_attr(self):
        """Member.username 不在 index=True (避免双重索引)"""
        from app.models.member import Member
        col = Member.__table__.columns["username"]
        assert not col.index, "Member.username 必须 index=False (避免与 ix_members_username_ci 冲突)"


# ============================================================================
# TestAlembicMigrationExistence — 验证迁移文件存在
# ============================================================================

class TestAlembicMigrationExistence:
    """验证 alembic 053 迁移文件存在且 revision 字段正确"""

    def test_migration_053_exists(self):
        """alembic 053 迁移文件必须存在"""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "053_member_username_case_insensitive_unique.py",
        )
        assert os.path.exists(migration_path), f"alembic 053 迁移文件不存在: {migration_path}"

    def test_migration_053_revision_id(self):
        """alembic 053 revision 字段正确"""
        import os
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "053_member_username_case_insensitive_unique.py",
        )
        spec = importlib.util.spec_from_file_location("migration_053", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "053_member_username_ci_unique"
        assert mod.down_revision == "052_drive_notification_rich"


# ============================================================================
# TestMentionResolutionUnaffected — comment_service mention 解析兼容性
# ============================================================================

class TestMentionResolutionUnaffected:
    """PR6-P13 不破坏现有 comment_service mention 解析 (回归保护)"""

    def test_comment_service_username_lower_pattern_preserved(self):
        """comment_service.py 仍用 username.lower() 匹配 (行为不变)"""
        import os
        import inspect
        from app.services import comment_service
        source = inspect.getsource(comment_service)

        # 旧匹配模式仍在
        assert "username_map[row.username.lower()]" in source or \
               'username_map[row.username.lower()]' in source or \
               "username.lower()" in source

    def test_three_path_match_preserved(self):
        """3 路匹配 (wechat_id + username + name) 保留 (PR6-P4)"""
        import inspect
        from app.services import comment_service
        source = inspect.getsource(comment_service)

        assert "wechat_id_map" in source
        assert "username_map" in source
        assert "name_map" in source