"""2026-07-02 v2 网盘 PR6-P15 单测 — member personal_wechat_id case-insensitive uniqueness

背景:
- PR6-P13 username + PR6-P14 wechat_id 已加 case-insensitive 唯一 (alembic 053/054)
- PR6-P15 把 personal_wechat_id 也加入 (防未来 app/wechat/identity.py:79
  resolve_by_wechat_id() 改用 lower() 匹配时出现 map 撞车)
- alembic 055 加 UNIQUE INDEX ON LOWER(personal_wechat_id) 兜底
- service _IDENTIFIER_COLUMNS 白名单扩到 3 列 (username / wechat_id / personal_wechat_id)

不依赖真实 DB (mock AsyncSession.execute.scalar_one_or_none),
真实 DB alembic upgrade 由 deploy 阶段验证。

铁律:
1. PR6-P14 模式复用: 白名单 + 反射 + label map
2. 中文 label 走 _COLUMN_LABELS dict (替代 if-else 硬编码)
3. 业务上 personal_wechat_id 当前 0 行非空, 迁移 0 冲突, 但加约束防未来数据污染
4. wechat/identity.py:79 resolve_by_wechat_id 当前用精确匹配, 防未来 lower() 改写时撞 map
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
    """构造 mock AsyncSession."""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_id
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ============================================================================
# TestPersonalWechatIdHelper — _assert_identifier_unique 通用 helper (PR6-P15)
# ============================================================================

class TestPersonalWechatIdHelper:
    """MemberService._assert_identifier_unique 支持 personal_wechat_id (PR6-P15 新增列)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_personal_wechat_id_column_works(self):
        """column_name='personal_wechat_id' 走 personal_wechat_id 唯一检查"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=88)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(
                db, "personal_wechat_id", "abc123"
            )

        # 验证 message 含中文 label "个人微信号"
        assert "个人微信号" in str(exc_info.value)
        assert "88" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_personal_wechat_id_case_insensitive(self):
        """大小写不敏感查询 (LOWER(personal_wechat_id) = 'abc123')"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=10)
        with pytest.raises(ConflictException):
            await MemberService._assert_identifier_unique(
                db, "personal_wechat_id", "ABC123"
            )

        # 验证 SQL 包含 lower(...) + 'abc123' (lowered)
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "lower(" in compiled.lower()
        assert "'abc123'" in compiled.lower()
        # SQL WHERE 用 LOWER(personal_wechat_id::text)
        assert "personal_wechat_id" in compiled.lower()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_personal_wechat_id_exclude_member_id(self):
        """update 自己时 exclude_member_id (防撞自己)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        await MemberService._assert_identifier_unique(
            db, "personal_wechat_id", "my_wechat_2026", exclude_member_id=5
        )

        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "id !=" in compiled.lower() or "id <>" in compiled.lower()
        assert "5" in compiled

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_personal_wechat_id_skips(self):
        """空 / None personal_wechat_id → 跳过检查 (与 PG UNIQUE NULL 行为一致)"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        await MemberService._assert_identifier_unique(db, "personal_wechat_id", "")
        await MemberService._assert_identifier_unique(db, "personal_wechat_id", None)
        await MemberService._assert_identifier_unique(db, "personal_wechat_id", "   ")
        # 空值时 db.execute 不应被调
        db.execute.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_existing_member_passes(self):
        """无冲突 → 通过"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        await MemberService._assert_identifier_unique(
            db, "personal_wechat_id", "new_unique_wechat_2026"
        )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_username_and_wechat_id_still_work(self):
        """PR6-P13/014 列仍工作 (向后兼容)"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        # username
        db = _make_mock_db(existing_id=1)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(db, "username", "wangtianzhi")
        assert "用户名" in str(exc_info.value)

        # wechat_id
        db = _make_mock_db(existing_id=2)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(db, "wechat_id", "nuyoah.")
        assert "企业微信号" in str(exc_info.value)


# ============================================================================
# TestColumnLabels — label map 正确性
# ============================================================================

class TestColumnLabels:
    """_COLUMN_LABELS dict 正确映射列名 → 中文 label"""

    def test_username_label(self):
        from app.services.member_service import MemberService
        assert MemberService._COLUMN_LABELS["username"] == "用户名"

    def test_wechat_id_label(self):
        from app.services.member_service import MemberService
        assert MemberService._COLUMN_LABELS["wechat_id"] == "企业微信号"

    def test_personal_wechat_id_label(self):
        from app.services.member_service import MemberService
        assert MemberService._COLUMN_LABELS["personal_wechat_id"] == "个人微信号"

    def test_identifier_columns_includes_personal_wechat_id(self):
        """_IDENTIFIER_COLUMNS 白名单必须含 3 个列"""
        from app.services.member_service import MemberService
        cols = MemberService._IDENTIFIER_COLUMNS
        assert "username" in cols
        assert "wechat_id" in cols
        assert "personal_wechat_id" in cols
        assert len(cols) == 3  # 防意外加列


# ============================================================================
# TestMemberServiceCreatePersonalWechatId — create_member 集成
# ============================================================================

class TestMemberServiceCreatePersonalWechatId:
    """MemberService.create_member 触发 _assert_identifier_unique(personal_wechat_id=...)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_personal_wechat_id_conflict_raises(self):
        """冲突 personal_wechat_id → ConflictException, 不创建"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        # username + wechat_id 无冲突, personal_wechat_id 有冲突
        call_count = [0]
        async def fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            existing_id = 99 if call_count[0] >= 3 else None  # 第 3 次 (personal_wechat_id) 有冲突
            mock_result.scalar_one_or_none.return_value = existing_id
            return mock_result

        db = MagicMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        svc = MemberService(db)
        with pytest.raises(ConflictException) as exc_info:
            await svc.create_member(
                name="新成员",
                username="new_unique_username_pr15",
                wechat_id="new_unique_wechat_pr15",
                personal_wechat_id="collision_pwid",
            )

        assert "个人微信号" in str(exc_info.value)
        db.commit.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_empty_personal_wechat_id_passes(self):
        """空 personal_wechat_id → 跳过检查, 正常创建"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(
            name="无个人微信成员",
            username="no_pwid_user_2026",
            personal_wechat_id="",
        )

        assert member is not None
        assert member.personal_wechat_id == ""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_full_3_identifiers(self):
        """完整流程: username + wechat_id + personal_wechat_id 都无冲突 → 正常创建"""
        from app.services.member_service import MemberService

        db = _make_mock_db()  # 全部无冲突
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(
            name="新成员",
            username="complete_3id_user_2026",
            wechat_id="CompleteWechatID.",
            personal_wechat_id="CompletePWID2026",
            grade="研一",
        )

        assert member is not None
        assert member.username == "complete_3id_user_2026"
        assert member.wechat_id == "CompleteWechatID."
        assert member.personal_wechat_id == "CompletePWID2026"


# ============================================================================
# TestMemberServiceUpdatePersonalWechatId — update_member 集成
# ============================================================================

class TestMemberServiceUpdatePersonalWechatId:
    """MemberService.update_member 触发 _assert_identifier_unique(personal_wechat_id=...)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_personal_wechat_id_to_existing_raises(self):
        """更新 personal_wechat_id 到已存在 → ConflictException"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1

        db = _make_mock_db(existing_id=88)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(
                db, "personal_wechat_id", "collision_pwid",
                exclude_member_id=1,
            )

        assert "个人微信号" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_personal_wechat_id_to_self_excluded(self):
        """更新 personal_wechat_id 到自己原值 → 不抛"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        await MemberService._assert_identifier_unique(
            db, "personal_wechat_id", "my_pwid", exclude_member_id=2
        )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_non_identifier_field_skips_check(self):
        """更新非 identifier 字段 (research_area) → 不触发预检查"""
        from app.services.member_service import MemberService
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1
        fake_member.research_area = "旧方向"

        db = _make_mock_db()
        svc = MemberService(db)
        svc.get_member = AsyncMock(return_value=fake_member)

        result = await svc.update_member(1, research_area="新方向")
        assert result is not None
        assert fake_member.research_area == "新方向"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_all_3_identifiers_together(self):
        """同时更新 3 个 identifier 字段都查唯一"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1

        db = MagicMock()
        async def fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            stmt_str = str(args[0].compile(compile_kwargs={"literal_binds": True}))
            # personal_wechat_id 第 3 次调用, 应有冲突
            if "personal_wechat_id" in stmt_str.lower():
                mock_result.scalar_one_or_none.return_value = 99
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result
        db.execute = AsyncMock(side_effect=fake_execute)

        svc = MemberService(db)
        svc.get_member = AsyncMock(return_value=fake_member)

        # username + wechat_id OK, personal_wechat_id 冲突 → 抛
        with pytest.raises(ConflictException) as exc_info:
            await svc.update_member(
                1,
                username="new_username_ok_pr15",
                wechat_id="new_wechat_ok_pr15",
                personal_wechat_id="collision_pwid_pr15",
            )

        assert "个人微信号" in str(exc_info.value)


# ============================================================================
# TestAlembicMigration055Existence — 验证 alembic 055 迁移文件存在
# ============================================================================

class TestAlembicMigration055Existence:
    """验证 alembic 055 迁移文件存在 + revision/down_revision 字段正确"""

    def test_migration_055_exists(self):
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "055_member_personal_wechat_id_ci_unique.py",
        )
        assert os.path.exists(migration_path), f"alembic 055 迁移文件不存在: {migration_path}"

    def test_migration_055_revision_id(self):
        import os
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "055_member_personal_wechat_id_ci_unique.py",
        )
        spec = importlib.util.spec_from_file_location("migration_055", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "055_member_personal_wechat_id_ci_unique"
        assert mod.down_revision == "054_member_wechat_id_ci_unique"

    def test_migration_055_chain_continues_from_054(self):
        """alembic 055 接 054 (PR6-P14 wechat_id case-insensitive uniqueness)"""
        import os
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "055_member_personal_wechat_id_ci_unique.py",
        )
        spec = importlib.util.spec_from_file_location("migration_055", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.down_revision == "054_member_wechat_id_ci_unique", \
            "alembic 055 必须接 054 (PR6-P14 wechat_id case-insensitive uniqueness)"


# ============================================================================
# TestWechatIdentityResolverUnaffected — wechat/identity.py 不被破坏 (回归保护)
# ============================================================================

class TestWechatIdentityResolverUnaffected:
    """PR6-P15 不破坏现有 wechat/identity.resolve_by_wechat_id() 行为"""

    def test_resolve_by_wechat_id_still_uses_exact_match(self):
        """wechat/identity.py:IdentityResolver.resolve_by_wechat_id 仍用精确匹配 `Member.personal_wechat_id == wechat_id`"""
        import inspect
        from app.wechat.identity import IdentityResolver
        source = inspect.getsource(IdentityResolver.resolve_by_wechat_id)

        # 精确匹配 (case-sensitive) — PR6-P15 防未来 lower() 改写, 但当前仍 exact
        assert "Member.personal_wechat_id == wechat_id" in source
        # 当前**没有** lower() 调用 (防止 mention 解析撞 map)
        assert ".lower()" not in source

    def test_personal_wechat_id_not_in_comment_service_mention(self):
        """comment_service.py 当前**不**用 personal_wechat_id (mention 3 路仅 wechat_id)"""
        import inspect
        from app.services import comment_service
        source = inspect.getsource(comment_service)

        # 3 路匹配只用 wechat_id + username + name, 不含 personal_wechat_id
        assert "personal_wechat_id" not in source


# ============================================================================
# TestBackwardCompat — PR6-P13/014 旧 API 仍工作
# ============================================================================

class TestBackwardCompat:
    """PR6-P13/014 旧 API `_assert_username_unique` 仍工作 (向后兼容)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_assert_username_unique_still_works(self):
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=42)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_username_unique(db, "wangtianzhi")
        assert "用户名已存在" in str(exc_info.value)