"""2026-07-02 v2 网盘 PR6-P14 单测 — member wechat_id case-insensitive uniqueness

背景:
- PR6-P13 修 username case-insensitive 唯一 (alembic 053)
- PR6-P4 mention 3 路匹配 wechat_id 优先, 用 wechat_id.lower() 同样有 map 撞车风险
- alembic 054 加 UNIQUE INDEX ON LOWER(wechat_id) 兜底
- service _assert_identifier_unique (generic helper) 抛 ConflictException

不依赖真实 DB (mock AsyncSession.execute.scalar_one_or_none),
真实 DB alembic upgrade 由 deploy 阶段验证。

铁律:
1. PR6-P13 通用化: helper 反射 Member 表列名, 支持 'username' / 'wechat_id' (未来可扩 personal_wechat_id)
2. 白名单 column_name, 防 SQL 注入 + 防止任意列 (如 password_hash)
3. 空/None 值跳过 (与 PG UNIQUE 索引 NULL 行为一致)
4. update 自己排除自己 (exclude_member_id)
5. comment_service 3 路匹配中 wechat_id 优先 → DB 索引一致 → mention 解析无歧义
"""
import os
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest


SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))


# ============================================================================
# 通用 mock helpers (与 PR6-P13 test 一致, 复用模式)
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
# TestMemberIdentifierUniqueGeneric — 通用 helper (_assert_identifier_unique)
# ============================================================================

class TestMemberIdentifierUniqueGeneric:
    """MemberService._assert_identifier_unique 通用 helper (PR6-P14 重构)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_username_column_works(self):
        """column_name='username' 仍走 username 唯一检查 (PR6-P13 向后兼容)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=42)
        with pytest.raises(Exception):
            await MemberService._assert_identifier_unique(db, "username", "wangtianzhi")

    @pytest.mark.asyncio(loop_scope="function")
    async def test_wechat_id_column_works(self):
        """column_name='wechat_id' 走 wechat_id 唯一检查 (PR6-P14 新增)"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=99)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(db, "wechat_id", "nuyoah.")

        # 验证 message 含 column 中文标签 "微信号"
        assert "微信号" in str(exc_info.value)
        assert "99" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_invalid_column_name_raises_value_error(self):
        """column_name 不在白名单 → ValueError (防 SQL 注入 + 防任意列)"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        # password_hash 在白名单外 → ValueError
        with pytest.raises(ValueError) as exc_info:
            await MemberService._assert_identifier_unique(db, "password_hash", "anypass")

        assert "password_hash" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_value_skips_check(self):
        """空 / None value 跳过检查 (与 PG UNIQUE NULL 不参与行为一致)"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        await MemberService._assert_identifier_unique(db, "wechat_id", "")
        await MemberService._assert_identifier_unique(db, "wechat_id", None)
        await MemberService._assert_identifier_unique(db, "wechat_id", "   ")
        # 空值时 db.execute 不应被调
        db.execute.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_lowers_value_for_case_insensitive(self):
        """传入大写/小写 → 都 LOWER 后查询 (验证 SQL 用 lower() 列)"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=10)
        with pytest.raises(ConflictException):
            await MemberService._assert_identifier_unique(db, "wechat_id", "NUYOAH.")

        # 验证 SQL 包含 lower(...) 比较
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "lower(" in compiled.lower()
        assert "'nuyoah.'" in compiled.lower()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_exclude_member_id_in_update(self):
        """update 自己时 exclude_member_id (防撞自己假冲突)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)  # 无冲突
        await MemberService._assert_identifier_unique(
            db, "wechat_id", "nuyoah.", exclude_member_id=2
        )

        # SQL WHERE 包含 id != 2
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "id !=" in compiled.lower() or "id <>" in compiled.lower()
        assert "2" in compiled

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_existing_member_passes(self):
        """无冲突 → 通过 (不抛)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        await MemberService._assert_identifier_unique(db, "wechat_id", "new_wechat_2026")


# ============================================================================
# TestMemberServiceCreateWechatId — create_member 集成 wechat_id 检查
# ============================================================================

class TestMemberServiceCreateWechatId:
    """MemberService.create_member 触发 _assert_identifier_unique(wechat_id=...)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_wechat_id_conflict_raises(self):
        """冲突 wechat_id → ConflictException, 不创建"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        # 第一次 (username) 无冲突, 第二次 (wechat_id) 有冲突
        db = MagicMock()
        call_count = [0]

        async def fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            # 第一次 (username 查询) 无冲突, 第二次 (wechat_id 查询) 有冲突
            call_count[0] += 1
            existing_id = 99 if call_count[0] >= 2 else None
            mock_result.scalar_one_or_none.return_value = existing_id
            return mock_result

        db.execute = AsyncMock(side_effect=fake_execute)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        svc = MemberService(db)
        with pytest.raises(ConflictException):
            await svc.create_member(
                name="新成员",
                username="new_unique_username_xyz",
                wechat_id="nuyoah.",
            )

        # commit 不应被调
        db.commit.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_empty_wechat_id_passes(self):
        """空 wechat_id → 跳过检查, 正常创建"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(
            name="无微信成员",
            username="no_wechat_user_2026",
            wechat_id="",
        )

        assert member is not None
        assert member.wechat_id == ""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_full_works(self):
        """完整流程: username + wechat_id 都无冲突 → 正常创建"""
        from app.services.member_service import MemberService

        db = _make_mock_db()  # 全部无冲突
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(
            name="新成员",
            username="complete_user_2026",
            wechat_id="CompleteWechat.",
            grade="研一",
            role="member",
        )

        assert member is not None
        assert member.wechat_id == "CompleteWechat."
        assert member.username == "complete_user_2026"
        assert member.is_active is True


# ============================================================================
# TestMemberServiceUpdateWechatId — update_member 集成 wechat_id 检查
# ============================================================================

class TestMemberServiceUpdateWechatId:
    """MemberService.update_member 触发 _assert_identifier_unique(wechat_id=...)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_wechat_id_to_existing_raises(self):
        """更新 wechat_id 到已存在 (别人的) → ConflictException"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1
        fake_member.username = "user1"
        fake_member.wechat_id = "old_wechat"

        db = MagicMock()
        async def fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = 99  # 99 是别人的 wechat_id
            return mock_result
        db.execute = AsyncMock(side_effect=fake_execute)

        with pytest.raises(ConflictException):
            await MemberService._assert_identifier_unique(
                db, "wechat_id", "new_wechat", exclude_member_id=1
            )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_wechat_id_to_self_excluded(self):
        """更新 wechat_id 到自己原值 → 不抛 (排除自己)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)  # 无冲突
        await MemberService._assert_identifier_unique(
            db, "wechat_id", "nuyoah.", exclude_member_id=2
        )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_non_wechat_id_field_skips_check(self):
        """更新非 wechat_id 字段 → 不触发预检查"""
        from app.services.member_service import MemberService
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1
        fake_member.username = "user1"
        fake_member.research_area = "旧方向"

        db = _make_mock_db()
        svc = MemberService(db)
        svc.get_member = AsyncMock(return_value=fake_member)

        # 更新 research_area (不传 wechat_id) → 应不抛
        result = await svc.update_member(1, research_area="新方向")
        assert result is not None
        assert fake_member.research_area == "新方向"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_both_username_and_wechat_id(self):
        """同时更新 username + wechat_id 都查唯一"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1

        db = MagicMock()
        async def fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            # 模拟 username 查无冲突, wechat_id 查有冲突
            stmt_str = str(args[0].compile(compile_kwargs={"literal_binds": True}))
            if "username" in stmt_str.lower():
                mock_result.scalar_one_or_none.return_value = None
            else:  # wechat_id
                mock_result.scalar_one_or_none.return_value = 99
            return mock_result
        db.execute = AsyncMock(side_effect=fake_execute)

        # username 不冲突 + wechat_id 冲突 → 抛 ConflictException
        with pytest.raises(ConflictException) as exc_info:
            await svc_update_method(self, fake_member, db)

        assert "微信号" in str(exc_info.value)


async def svc_update_method(self, fake_member, db):
    """helper: 直接调 update_member 内部逻辑, 模拟 svc.update_member(id, **kwargs)"""
    from app.services.member_service import MemberService
    svc = MemberService(db)
    svc.get_member = AsyncMock(return_value=fake_member)
    return await svc.update_member(
        1,
        username="new_username_ok",
        wechat_id="collision_wechat",
    )


# ============================================================================
# TestMemberBackwardCompat — PR6-P13 向后兼容 (_assert_username_unique wrapper)
# ============================================================================

class TestMemberBackwardCompat:
    """PR6-P13 旧 API _assert_username_unique 仍工作 (向后兼容)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_assert_username_unique_still_works(self):
        """旧 API _assert_username_unique 仍能抛 ConflictException"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=42)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_username_unique(db, "wangtianzhi")

        # 旧 API 抛 "用户名已存在"
        assert "用户名已存在" in str(exc_info.value)


# ============================================================================
# TestAlembicMigration054Existence — 验证 alembic 054 迁移文件存在
# ============================================================================

class TestAlembicMigration054Existence:
    """验证 alembic 054 迁移文件存在且 revision 字段正确"""

    def test_migration_054_exists(self):
        """alembic 054 迁移文件必须存在"""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "054_member_wechat_id_ci_unique.py",
        )
        assert os.path.exists(migration_path), f"alembic 054 迁移文件不存在: {migration_path}"

    def test_migration_054_revision_id(self):
        """alembic 054 revision 字段正确"""
        import os
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "054_member_wechat_id_ci_unique.py",
        )
        spec = importlib.util.spec_from_file_location("migration_054", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "054_member_wechat_id_ci_unique"
        assert mod.down_revision == "053_member_username_ci_unique"

    def test_migration_054_chain_continues_from_053(self):
        """alembic 054 接 053 (PR6-P13 username case-insensitive uniqueness)"""
        import os
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "054_member_wechat_id_ci_unique.py",
        )
        spec = importlib.util.spec_from_file_location("migration_054", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.down_revision == "053_member_username_ci_unique", \
            "alembic 054 必须接 053 (case-insensitive uniqueness 链)"


# ============================================================================
# TestMentionResolutionRegression — comment_service 3 路匹配未破坏 (PR6-P4)
# ============================================================================

class TestMentionResolutionRegression:
    """PR6-P14 不破坏现有 comment_service mention 解析 (回归保护)"""

    def test_comment_service_wechat_id_lower_pattern_preserved(self):
        """comment_service.py 仍用 wechat_id.lower() 匹配 (PR6-P4 行为不变)"""
        import inspect
        from app.services import comment_service
        source = inspect.getsource(comment_service)

        assert "wechat_id_map" in source
        assert "wechat_id.lower()" in source
        assert "wechat_id_map.get(u_lower)" in source

    def test_three_path_match_priority_preserved(self):
        """3 路匹配优先级: wechat_id > username > name (PR6-P4)"""
        import inspect
        from app.services import comment_service
        source = inspect.getsource(comment_service)

        # 第一优先级: wechat_id_map.get(u_lower)
        assert "wechat_id_map.get(u_lower) or username_map.get(u_lower) or name_map.get(u)" in source