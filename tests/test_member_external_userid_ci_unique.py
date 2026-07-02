"""2026-07-03 v2 网盘 PR6-P16 单测 — member external_userid case-insensitive uniqueness

背景:
- PR6-P13/14/15 已加 username/wechat_id/personal_wechat_id case-insensitive 唯一 (alembic 053/054/055)
- PR6-P16 把第 4 个 identifier 列 external_userid (微信互通外部用户ID, wm 开头) 也加入
- 防未来 app/wechat/identity.py:41 IdentityResolver.resolve_by_external_userid()
  改用 lower() 匹配时出现 map 撞车 (与 PR6-P15 同模式)
- alembic 056 加 UNIQUE INDEX ON LOWER(external_userid) 兜底

不依赖真实 DB (mock AsyncSession.execute.scalar_one_or_none),
真实 DB alembic upgrade 由 deploy 阶段验证。

铁律:
1. PR6-P15 模式复用: _IDENTIFIER_COLUMNS 白名单加 1 行 + _COLUMN_LABELS 加 1 行
2. 中文 label dict.get 替代 if-else
3. 业务上 external_userid 0 行非空 (迁移 0 冲突), 但加约束防未来数据污染
4. wechat/identity.py:41 resolve_by_external_userid 当前精确匹配, 防未来 lower() 改写
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
# TestExternalUseridHelper — _assert_identifier_unique 支持 external_userid
# ============================================================================

class TestExternalUseridHelper:
    """MemberService._assert_identifier_unique 支持 external_userid (PR6-P16 新增第 4 列)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_external_userid_column_works(self):
        """column_name='external_userid' 走 external_userid 唯一检查"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=77)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(
                db, "external_userid", "wmABC123"
            )

        # 验证 message 含中文 label "微信外部ID"
        assert "微信外部ID" in str(exc_info.value)
        assert "77" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_external_userid_case_insensitive(self):
        """大小写不敏感查询 (LOWER(external_userid) = 'wmabc123')"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=10)
        with pytest.raises(ConflictException):
            await MemberService._assert_identifier_unique(
                db, "external_userid", "WMAbc123"  # 混合大小写
            )

        # 验证 SQL 包含 lower(...) + 'wmabc123' (lowered)
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "lower(" in compiled.lower()
        assert "'wmabc123'" in compiled.lower()
        assert "external_userid" in compiled.lower()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_external_userid_exclude_member_id(self):
        """update 自己时 exclude_member_id (防撞自己假冲突)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        await MemberService._assert_identifier_unique(
            db, "external_userid", "my_wmid_2026", exclude_member_id=3
        )

        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "id !=" in compiled.lower() or "id <>" in compiled.lower()
        assert "3" in compiled

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_external_userid_skips(self):
        """空 / None external_userid → 跳过检查 (PG UNIQUE NULL 不参与)"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        await MemberService._assert_identifier_unique(db, "external_userid", "")
        await MemberService._assert_identifier_unique(db, "external_userid", None)
        await MemberService._assert_identifier_unique(db, "external_userid", "   ")
        # 空值时 db.execute 不应被调
        db.execute.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_existing_member_passes(self):
        """无冲突 → 通过"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        await MemberService._assert_identifier_unique(
            db, "external_userid", "new_unique_wmid_2026"
        )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_three_other_identifier_columns_still_work(self):
        """PR6-P13/14/15 列仍工作 (向后兼容)"""
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

        # personal_wechat_id
        db = _make_mock_db(existing_id=3)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(db, "personal_wechat_id", "abc123")
        assert "个人微信号" in str(exc_info.value)


# ============================================================================
# TestColumnLabels — 4 列中文 label 全部正确
# ============================================================================

class TestColumnLabels:
    """_COLUMN_LABELS dict 正确映射 4 列名 → 中文 label"""

    def test_username_label(self):
        from app.services.member_service import MemberService
        assert MemberService._COLUMN_LABELS["username"] == "用户名"

    def test_wechat_id_label(self):
        from app.services.member_service import MemberService
        assert MemberService._COLUMN_LABELS["wechat_id"] == "企业微信号"

    def test_personal_wechat_id_label(self):
        from app.services.member_service import MemberService
        assert MemberService._COLUMN_LABELS["personal_wechat_id"] == "个人微信号"

    def test_external_userid_label(self):
        from app.services.member_service import MemberService
        assert MemberService._COLUMN_LABELS["external_userid"] == "微信外部ID"

    def test_identifier_columns_includes_external_userid(self):
        """_IDENTIFIER_COLUMNS 白名单必须含 4 个列"""
        from app.services.member_service import MemberService
        cols = MemberService._IDENTIFIER_COLUMNS
        assert "username" in cols
        assert "wechat_id" in cols
        assert "personal_wechat_id" in cols
        assert "external_userid" in cols
        assert len(cols) == 4  # 防意外加列


# ============================================================================
# TestMemberServiceCreateExternalUserid — create_member 集成
# ============================================================================

class TestMemberServiceCreateExternalUserid:
    """MemberService.create_member 触发 _assert_identifier_unique(external_userid=...)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_external_userid_conflict_raises(self):
        """冲突 external_userid → ConflictException, 不创建"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        # username + wechat_id + personal_wechat_id 无冲突, external_userid 有冲突
        call_count = [0]
        async def fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            existing_id = 77 if call_count[0] >= 4 else None
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
                username="new_unique_username_pr16",
                wechat_id="new_unique_wechat_pr16",
                personal_wechat_id="new_unique_pwid_pr16",
                external_userid="wmcollision",
            )

        assert "微信外部ID" in str(exc_info.value)
        db.commit.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_empty_external_userid_passes(self):
        """空 external_userid → 跳过检查, 正常创建"""
        from app.services.member_service import MemberService

        db = _make_mock_db()
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(
            name="无外部ID成员",
            username="no_external_userid_2026",
            external_userid="",
        )

        assert member is not None
        assert member.external_userid == ""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_member_full_4_identifiers(self):
        """完整流程: 4 个 identifier 都无冲突 → 正常创建"""
        from app.services.member_service import MemberService

        db = _make_mock_db()  # 全部无冲突
        async def fake_refresh(m):
            if m.id is None:
                m.id = 100
        db.refresh = fake_refresh

        svc = MemberService(db)
        member = await svc.create_member(
            name="新成员",
            username="complete_4id_user_2026",
            wechat_id="CompleteWechatPr16.",
            personal_wechat_id="CompletePWIDPr16",
            external_userid="wmCompletePr16",
            grade="研一",
        )

        assert member is not None
        assert member.username == "complete_4id_user_2026"
        assert member.wechat_id == "CompleteWechatPr16."
        assert member.personal_wechat_id == "CompletePWIDPr16"
        assert member.external_userid == "wmCompletePr16"


# ============================================================================
# TestMemberServiceUpdateExternalUserid — update_member 集成
# ============================================================================

class TestMemberServiceUpdateExternalUserid:
    """MemberService.update_member 触发 _assert_identifier_unique(external_userid=...)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_external_userid_to_existing_raises(self):
        """更新 external_userid 到已存在 → ConflictException"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1

        db = _make_mock_db(existing_id=99)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_identifier_unique(
                db, "external_userid", "wmcollision",
                exclude_member_id=1,
            )

        assert "微信外部ID" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_external_userid_to_self_excluded(self):
        """更新 external_userid 到自己原值 → 不抛 (排除自己)"""
        from app.services.member_service import MemberService

        db = _make_mock_db(existing_id=None)
        await MemberService._assert_identifier_unique(
            db, "external_userid", "my_wmid", exclude_member_id=2
        )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_non_identifier_field_skips_check(self):
        """更新非 identifier 字段 → 不触发预检查"""
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
    async def test_update_all_4_identifiers_together(self):
        """同时更新 4 个 identifier 字段都查唯一 (external_userid 冲突 → raises)"""
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException
        from app.models.member import Member

        fake_member = MagicMock(spec=Member)
        fake_member.id = 1

        db = MagicMock()
        async def fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            stmt_str = str(args[0].compile(compile_kwargs={"literal_binds": True}))
            # external_userid 第 4 次调用, 应有冲突
            if "external_userid" in stmt_str.lower():
                mock_result.scalar_one_or_none.return_value = 99
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result
        db.execute = AsyncMock(side_effect=fake_execute)

        svc = MemberService(db)
        svc.get_member = AsyncMock(return_value=fake_member)

        # 前 3 个 OK, external_userid 冲突 → 抛
        with pytest.raises(ConflictException) as exc_info:
            await svc.update_member(
                1,
                username="new_username_ok_pr16",
                wechat_id="new_wechat_ok_pr16",
                personal_wechat_id="new_pwid_ok_pr16",
                external_userid="wmcollision_pr16",
            )

        assert "微信外部ID" in str(exc_info.value)


# ============================================================================
# TestAlembicMigration056Existence — 验证 alembic 056 迁移文件存在
# ============================================================================

class TestAlembicMigration056Existence:
    """验证 alembic 056 迁移文件存在 + revision/down_revision 字段正确"""

    def test_migration_056_exists(self):
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "056_external_userid_ci.py",
        )
        assert os.path.exists(migration_path), f"alembic 056 迁移文件不存在: {migration_path}"

    def test_migration_056_revision_id(self):
        import os
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "056_external_userid_ci.py",
        )
        spec = importlib.util.spec_from_file_location("migration_056", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # revision ID 必须 ≤32 字符 (alembic_version.version_num VARCHAR(32))
        assert len(mod.revision) <= 32, f"revision ID 太长 ({len(mod.revision)} chars): {mod.revision}"
        assert mod.revision == "056_external_userid_ci"
        assert mod.down_revision == "055_personal_wechat_ci"

    def test_migration_056_chain_continues_from_055(self):
        """alembic 056 接 055_personal_wechat_ci (PR6-P15)"""
        import os
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "056_external_userid_ci.py",
        )
        spec = importlib.util.spec_from_file_location("migration_056", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.down_revision == "055_personal_wechat_ci", \
            "alembic 056 必须接 055 (PR6-P15 personal_wechat_id case-insensitive uniqueness)"


# ============================================================================
# TestWechatIdentityExternalUseridResolverUnaffected — wechat/identity.py 不被破坏
# ============================================================================

class TestWechatIdentityExternalUseridResolverUnaffected:
    """PR6-P16 不破坏现有 wechat/identity.resolve_by_external_userid() 行为"""

    def test_resolve_by_external_userid_still_uses_exact_match(self):
        """wechat/identity.py:54 仍用精确匹配 `Member.external_userid == external_userid`"""
        import inspect
        from app.wechat.identity import IdentityResolver
        source = inspect.getsource(IdentityResolver.resolve_by_external_userid)

        # 精确匹配 (case-sensitive) — PR6-P16 防未来 lower() 改写, 但当前仍 exact
        assert "Member.external_userid == external_userid" in source
        # 当前**没有** lower() 调用 (防止 mention 解析撞 map)
        assert ".lower()" not in source

    def test_resolve_priority_chain_preserved(self):
        """IdentityResolver.resolve_multi_signal 优先级链: wechat_userid → external_userid → wechat_id → mobile → nickname (PR6-P4)"""
        import inspect
        from app.wechat.identity import IdentityResolver
        source = inspect.getsource(IdentityResolver.resolve_multi_signal)

        # 优先级链任一项都在源码里 (5 步)
        assert "self.resolve(wechat_userid" in source
        assert "resolve_by_external_userid" in source
        assert "resolve_by_wechat_id" in source
        assert "resolve_by_mobile" in source
        assert "resolve_by_nickname" in source


# ============================================================================
# TestBackwardCompat — PR6-P13/14/15 旧 API 仍工作
# ============================================================================

class TestBackwardCompat:
    """PR6-P13/14/15 旧 API `_assert_username_unique` 仍工作 (向后兼容)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_assert_username_unique_still_works(self):
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = _make_mock_db(existing_id=42)
        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_username_unique(db, "wangtianzhi")
        assert "用户名已存在" in str(exc_info.value)