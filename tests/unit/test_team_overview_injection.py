"""测试 _build_team_overview_text 注入 + GROUND TRUTH 反幻觉块 (2026-07-15 #P2)

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_team_overview_injection.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.micro_bubble_agent import _build_team_overview_text


class TestTeamOverviewEmpty:
    """边界情况: db=None / 异常时不抛错, 返空字符串"""

    @pytest.mark.asyncio
    async def test_db_none_returns_empty(self):
        """db=None 必须返空 (上层 caller 据此跳过注入)"""
        result = await _build_team_overview_text(None)
        assert result == ""

    @pytest.mark.asyncio
    async def test_db_raises_exception_returns_empty(self):
        """db.execute 抛异常时返空 (best-effort, 不阻塞 chat)"""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        result = await _build_team_overview_text(mock_db)
        assert result == ""


class TestTeamOverviewGroundTruth:
    """GROUND TRUTH 块: 必须列所有真实成员, 严禁编造"""

    @pytest.mark.asyncio
    async def test_ground_truth_includes_all_member_names(self):
        """输出必须包含 ⚠️ GROUND TRUTH 白名单 块 + 所有真实成员姓名"""
        # Mock 4 个真实成员 (含 admin/leader/member 三种 role)
        def make_member(mid, name, grade, ra, role):
            m = MagicMock()
            m.id = mid
            m.name = name
            m.grade = grade
            m.research_area = ra
            m.role = role
            m.is_active = True
            m.bio = None
            return m
        members = [
            make_member(1, "王天志", "副教授", "微纳米气泡技术", "admin"),
            make_member(2, "杜同贺", "博二", "水处理", "leader"),
            make_member(3, "赵航佳", "博一", "黑臭水体治理", "member"),
            make_member(4, "陈金薪", "研一", "臭氧氧化", "member"),
        ]
        member_result = MagicMock()
        member_result.scalars.return_value.all.return_value = members
        # Mock Project 查询返空
        project_result = MagicMock()
        project_result.scalars.return_value.all.return_value = []

        async def mock_execute(stmt):
            return member_result  # 返回 members（实际实现中只读 scalars().all()）

        mock_db = MagicMock()
        mock_db.execute = mock_execute

        # Mock Redis (cache miss)
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch("app.core.redis.get_redis", AsyncMock(return_value=mock_redis)):
            result = await _build_team_overview_text(mock_db)

        # 关键: 必须包含 GROUND TRUTH 块 + 所有真实姓名
        assert "⚠️ GROUND TRUTH" in result, "must include GROUND TRUTH warning block"
        assert "王天志" in result
        assert "杜同贺" in result
        assert "赵航佳" in result
        assert "陈金薪" in result
        # 反幻觉纪律必须出现
        assert "严禁" in result or "不准" in result or "反幻觉" in result
        # 写缓存
        mock_redis.set.assert_awaited_once()


class TestTeamOverviewAntiHallucination:
    """反幻觉: 输出必须明确禁止 LLM 编造"""

    @pytest.mark.asyncio
    async def test_explicit_no_fabrication_clause(self):
        """输出末尾必须包含 '禁止编造' 类强语气反幻觉句子"""
        m = MagicMock()
        m.id = 1
        m.name = "测试成员A"
        m.grade = None
        m.research_area = "测试方向"
        m.role = "member"
        m.is_active = True
        m.bio = None
        members = [m]
        member_result = MagicMock()
        member_result.scalars.return_value.all.return_value = members
        project_result = MagicMock()
        project_result.scalars.return_value.all.return_value = []

        async def mock_execute(stmt):
            return member_result  # both queries return members (mock doesn't differentiate)

        mock_db = MagicMock()
        mock_db.execute = mock_execute

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch("app.core.redis.get_redis", AsyncMock(return_value=mock_redis)):
            result = await _build_team_overview_text(mock_db)

        # 关键反幻觉句子
        assert "严禁出现以下名单之外" in result
        assert "真实成员姓名" in result
        assert "李晓辉" in result and "张伟杰" in result, "must reference 2026-07-15 hallucination case as warning"


class TestTeamOverviewCache:
    """Redis 缓存: 命中/失效/write 都要正确"""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        """缓存命中时不应再查 DB (性能优化)"""
        cached_data = "## 【课题组概览】（cached）\n\ncached data here"
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=cached_data)

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=AssertionError("DB should not be queried on cache hit"))

        with patch("app.core.redis.get_redis", AsyncMock(return_value=mock_redis)):
            result = await _build_team_overview_text(mock_db)

        assert result == cached_data
        mock_redis.get.assert_awaited_once()
        # db.execute 不应被调用
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_write_on_miss(self):
        """缓存 miss 时查 DB 后必须 set cache (TTL=3600)"""
        m = MagicMock()
        m.id = 1
        m.name = "测试"
        m.grade = None
        m.research_area = "X"
        m.role = "member"
        m.is_active = True
        m.bio = None
        members = [m]
        member_result = MagicMock()
        member_result.scalars.return_value.all.return_value = members

        async def mock_execute(stmt):
            return member_result

        mock_db = MagicMock()
        mock_db.execute = mock_execute

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch("app.core.redis.get_redis", AsyncMock(return_value=mock_redis)):
            await _build_team_overview_text(mock_db)

        # 必须 set, ttl=3600
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "team_overview:v1"
        # ex=3600 可能是 keyword arg 或 positional 第3参
        ttl = call_args[1].get("ex") or (call_args[0][2] if len(call_args[0]) >= 3 else None)
        assert ttl == 3600


class TestTeamOverviewLimits:
    """Limit 限制: 防止注入过大 token 数"""

    @pytest.mark.asyncio
    async def test_max_members_limit(self):
        """max_members=2 时只列 2 个成员 (防止 token 爆炸)
        注: limit 在 SQL 查询时应用 (.limit(max_members)), mock 模拟 SQL 已过滤
        """
        def make_member(mid, name):
            m = MagicMock()
            m.id = mid
            m.name = name
            m.grade = None
            m.research_area = f"方向{mid}"
            m.role = "member"
            m.is_active = True
            m.bio = None
            return m
        # mock 模拟 SQL 已应用 limit=2: 只返 2 个
        members = [make_member(i, f"成员{i}") for i in range(1, 3)]
        member_result = MagicMock()
        member_result.scalars.return_value.all.return_value = members
        project_result = MagicMock()
        project_result.scalars.return_value.all.return_value = []

        async def mock_execute(stmt):
            return member_result

        mock_db = MagicMock()
        mock_db.execute = mock_execute

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch("app.core.redis.get_redis", AsyncMock(return_value=mock_redis)):
            result = await _build_team_overview_text(mock_db, max_members=2)

        # 包含 成员1, 成员2, 不应包含 成员3+ (SQL limit 过滤后)
        assert "成员1" in result
        assert "成员2" in result
        # 验证 GROUND TRUTH 块用了正确的成员数
        assert "**2 位**" in result or "（共 2" in result
        # 写缓存
        mock_redis.set.assert_awaited_once()