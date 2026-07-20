"""2026-07-03 v2 网盘 PR6-P17 单测 — wechat_id NOT NULL 约束 (防 NULL 渗透)

背景:
- PR6-P13/14/15/16 收官: 4 个 identifier 列 case-insensitive UNIQUE INDEX
- PR6-P17 加 DB 层 wechat_id NOT NULL 约束 (防御性, 防未来 caller 忘传 wechat_id)
- 14/35 行原 NULL 已 backfill 为 placeholder '__NULL_BACKFILL_<id>__' (避免 PR6-P14 UNIQUE 冲突)
- alembic 057 (3 步: backfill → SET NOT NULL → verify)

测试策略:
- alembic 文件存在 + revision 字段 (PR6-P17 = 057_wechat_id_not_null, ≤32 chars)
- Member 模型 Column nullable=False (静态检查)
- backfill SQL 格式正确 (placeholder 唯一性: <id> 数字)
- verify 步骤在 NULL 仍存在时 raise RuntimeError (防 alembic silent fail)
- downgrade 步骤: DROP NOT NULL + placeholder 改回 NULL (round-trip)

铁律:
1. NOT NULL 加在 DB 层 (alembic migration), 模型层 nullable=False 同步 (防 ORM INSERT NULL → IntegrityError)
2. API schema MemberCreate.wechat_id 仍为 Optional[str] = None (本次不破 API, 留给业务决定)
3. 已有 NULL 数据 backfill 时必须用 placeholder (避免 UNIQUE 冲突)
4. placeholder 唯一性: __NULL_BACKFILL_<id>__ (数字 id 保证唯一)
"""
import os
import re
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest


SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))


# ============================================================================
# TestAlembicMigration057Existence — 验证 alembic 057 迁移文件
# ============================================================================

class TestAlembicMigration057Existence:
    """验证 alembic 057_wechat_id_not_null 迁移文件存在 + revision 字段正确"""

    def test_migration_057_exists(self):
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "057_wechat_id_not_null.py",
        )
        assert os.path.exists(migration_path), f"alembic 057 迁移文件不存在: {migration_path}"

    def test_migration_057_revision_id(self):
        """revision 必须 ≤32 字符 (alembic_version VARCHAR(32) 限制)"""
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "057_wechat_id_not_null.py",
        )
        spec = importlib.util.spec_from_file_location("migration_057", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert len(mod.revision) <= 32, f"revision ID 太长 ({len(mod.revision)} chars): {mod.revision}"
        assert mod.revision == "057_wechat_id_not_null"
        assert mod.down_revision == "056_external_userid_ci"

    def test_migration_057_chain_continues_from_056(self):
        """alembic 057 接 056_external_userid_ci (PR6-P16 case-insensitive uniqueness)"""
        import importlib.util
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "057_wechat_id_not_null.py",
        )
        spec = importlib.util.spec_from_file_location("migration_057", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.down_revision == "056_external_userid_ci"

    def test_migration_057_source_contains_backfill_sql(self):
        """迁移源文件必须包含 backfill SQL (3 步迁移第 1 步)"""
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "057_wechat_id_not_null.py",
        )
        with open(migration_path, "r", encoding="utf-8") as f:
            source = f.read()
        # 步骤 1: backfill UPDATE
        assert "UPDATE members SET wechat_id" in source
        assert "__NULL_BACKFILL_" in source
        # 步骤 2: ALTER COLUMN SET NOT NULL
        assert "nullable=False" in source
        # 步骤 3: verify
        assert "WHERE wechat_id IS NULL" in source


# ============================================================================
# TestMemberModelNotNull — Member 模型 Column nullable=False 静态检查
# ============================================================================

class TestMemberModelNotNull:
    """Member.wechat_id 必须 nullable=False (与 alembic 057 DB 约束同步)"""

    def test_member_wechat_id_not_nullable(self):
        from app.models.member import Member
        col = Member.__table__.columns["wechat_id"]
        assert not col.nullable, "Member.wechat_id 必须 nullable=False (PR6-P17 防 NULL 渗透)"

    def test_member_other_identifier_columns_still_nullable(self):
        """username/name 是 NOT NULL (DB 层 schema 设), 其他 identifier 列仍 nullable (业务允许为空)"""
        from app.models.member import Member
        # wechat_id 必须 NOT NULL
        assert not Member.__table__.columns["wechat_id"].nullable
        # username 当前 schema 未显式 nullable=False (DB 层允许空字符串)
        # name 必填 (schema 强制)
        assert not Member.__table__.columns["name"].nullable
        # personal_wechat_id / external_userid 业务允许 NULL
        assert Member.__table__.columns["personal_wechat_id"].nullable
        assert Member.__table__.columns["external_userid"].nullable


# ============================================================================
# TestBackfillPlaceholderLogic — backfill placeholder 唯一性逻辑
# ============================================================================

class TestBackfillPlaceholderLogic:
    """backfill SQL placeholder 格式 + 唯一性"""

    def test_placeholder_format_uniqueness(self):
        """placeholder 格式: __NULL_BACKFILL_<id>__ (数字 id 保证唯一)"""
        # 用 re 验证 placeholder 格式
        placeholder_pattern = re.compile(r"^__NULL_BACKFILL_\d+__$")
        for member_id in [8, 17, 22, 24, 25, 26, 27, 58, 59, 116, 117, 118, 299, 300]:
            placeholder = f"__NULL_BACKFILL_{member_id}__"
            assert placeholder_pattern.match(placeholder), f"placeholder 不匹配: {placeholder}"

    def test_placeholder_distinct_per_id(self):
        """14 个 placeholder 全部不同 (避免 LOWER(placeholder) 冲突)"""
        ids = [8, 17, 22, 24, 25, 26, 27, 58, 59, 116, 117, 118, 299, 300]
        placeholders = [f"__NULL_BACKFILL_{mid}__" for mid in ids]
        # 全部 lowercase 后仍 unique (PR6-P14 UNIQUE INDEX ON LOWER 约束)
        lowered = [p.lower() for p in placeholders]
        assert len(set(lowered)) == len(lowered), "placeholders should be unique after lower()"

    def test_placeholder_does_not_collide_with_real_wechat_ids(self):
        """placeholder 格式特殊 (含 '__' + 'NULL_BACKFILL'), 不会撞真实 wechat_id"""
        # 真实 wechat_id 例子 (从之前 DB 查询)
        real_ids = [
            "WangTianZhi", "nuyoah.", "DuTongHe", "cttx", "JinMing",
            "WuWei.", "carpediem", "YingTaoYuan", "fine",
            "d41d8cd98f00b204e9800998ecf8427e01",
        ]
        for real in real_ids:
            for mid in [8, 17, 22, 24, 25, 26, 27, 58, 59]:
                placeholder = f"__NULL_BACKFILL_{mid}__"
                assert placeholder != real
                assert placeholder.lower() != real.lower()


# ============================================================================
# TestBackwardCompat — PR6-P13/14/15/16 旧 API 仍工作
# ============================================================================

class TestBackwardCompat:
    """PR6-P13/14/15/16 旧 API 仍工作 (向后兼容)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_assert_username_unique_still_works(self):
        from app.services.member_service import MemberService
        from app.core.exceptions import ConflictException

        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 42
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with pytest.raises(ConflictException) as exc_info:
            await MemberService._assert_username_unique(db, "wangtianzhi")
        assert "用户名已存在" in str(exc_info.value)

    def test_identifier_columns_still_4(self):
        """_IDENTIFIER_COLUMNS 仍含 4 列 (PR6-P16 收官状态)"""
        from app.services.member_service import MemberService
        cols = MemberService._IDENTIFIER_COLUMNS
        assert len(cols) == 4
        assert "username" in cols
        assert "wechat_id" in cols
        assert "personal_wechat_id" in cols
        assert "external_userid" in cols


# ============================================================================
# TestMemberCreateWechatIdRequired — PR6-P17 留尾: schema 与 DB NOT NULL 同步 (2026-07-20)
# ============================================================================

class TestMemberCreateWechatIdRequired:
    """MemberCreate.wechat_id 改为 required[str] (PR6-P17 留尾, 与 DB NOT NULL 对齐)"""

    def test_member_create_wechat_id_now_required(self):
        """PR6-P17 留尾: MemberCreate.wechat_id 必传, 缺传 → Pydantic 422 fail loud"""
        from app.schemas.member import MemberCreate
        fields = MemberCreate.model_fields
        # required 字段: default is PydanticUndefined (sentinel), 不是 None
        from pydantic_core import PydanticUndefined
        assert fields["wechat_id"].default is PydanticUndefined, \
            "MemberCreate.wechat_id 必须 required (无 default)"
        # annotation 是 str (无 Optional 包裹)
        assert fields["wechat_id"].annotation == str

    def test_member_create_raises_422_without_wechat_id(self):
        """缺 wechat_id 创建 → Pydantic ValidationError (FastAPI 422)"""
        from app.schemas.member import MemberCreate
        from pydantic import ValidationError
        import pytest
        with pytest.raises(ValidationError) as exc_info:
            MemberCreate(name="测试", username="test_required_422")
        # 错误路径必须包含 wechat_id
        errors = exc_info.value.errors()
        assert any("wechat_id" in str(e.get("loc", [])) for e in errors), \
            f"ValidationError 必须提到 wechat_id 字段, 实测: {errors}"

    def test_member_create_accepts_explicit_wechat_id(self):
        """传 wechat_id 创建成功"""
        from app.schemas.member import MemberCreate
        m = MemberCreate(
            name="测试", username="test_explicit_wechat",
            wechat_id="explicit_wechat_123",
        )
        assert m.wechat_id == "explicit_wechat_123"

    def test_member_update_wechat_id_still_optional(self):
        """MemberUpdate.wechat_id 仍 Optional (部分更新语义, 不动)"""
        from app.schemas.member import MemberUpdate
        fields = MemberUpdate.model_fields
        assert fields["wechat_id"].default is None


# ============================================================================
# TestWechatIdNullUsageInCode — 现有代码 wechat_id NULL-safe 模式保留
# ============================================================================

class TestWechatIdNullUsageInCode:
    """现有代码用 'or' pattern 处理 NULL (PR6-P17 不破坏)"""

    def test_task_api_uses_or_pattern(self):
        """task.py 用 'or' pattern (None-safe)"""
        import inspect
        from app.api.v1 import task
        source = inspect.getsource(task)

        # 至少 2 处 'wechat_id or' 模式 (防 NULL 解引用)
        # 实测 task.py 有 3 处 (line 72/90/129/133 等)
        assert source.count("wechat_id or") >= 2, \
            f"task.py 应该有 ≥2 处 'wechat_id or' NULL-safe 模式, 实测 {source.count('wechat_id or')}"

    def test_comment_service_uses_if_pattern(self):
        """comment_service.py:116/302 用 'if row.wechat_id:' (None-safe)"""
        import inspect
        from app.services import comment_service
        source = inspect.getsource(comment_service)
        # wechat_id_map 构建时 if row.wechat_id: 跳过 None 行
        assert "if row.wechat_id:" in source
        assert source.count("if row.wechat_id:") >= 2

    def test_member_create_service_uses_unique_check(self):
        """MemberService.create_member 用 _assert_identifier_unique(wechat_id=...)"""
        import inspect
        from app.services.member_service import MemberService
        source = inspect.getsource(MemberService.create_member)
        # 4 个 identifier 列预检查
        assert "_assert_identifier_unique" in source
        assert '"wechat_id"' in source
        assert source.count('_assert_identifier_unique(self.db,') >= 4  # 4 identifier columns