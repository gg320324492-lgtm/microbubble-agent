"""W-N-E +1 PoC: 冷热分层路由层单元/集成测试

> **范畴**: tests/integration/test_cold_hot_routing.py
> **铁律**: SKIP_DB_SETUP=1 跑过 (mock 即可, 不依赖真实 Postgres)
> **派工 brief**: 1-2 integration test, mock 即可

测试覆盖:
1. route_partition() 关键字匹配 (纯函数, 无 DB 依赖)
2. route_partition() 数字年份兜底
3. get_partition_where_clause() SQL 片段生成
4. list_knowledge_partition() 集成 (mock DB, 验证 SQL 含 created_at 过滤)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.cold_hot_router import (
    COLD_KEYWORDS,
    THRESHOLD_MONTHS,
    get_partition_where_clause,
    route_partition,
)


# === 1. route_partition() 纯函数测试 (无 DB) ===

class TestRoutePartition:
    def test_empty_query_routes_hot(self):
        assert route_partition("") == "hot"

    def test_none_like_query_routes_hot(self):
        assert route_partition("微纳米气泡的应用") == "hot"
        assert route_partition("zeta 电位") == "hot"

    @pytest.mark.parametrize("kw", COLD_KEYWORDS[:5])  # 取前 5 个避免重复
    def test_cold_keywords_route_cold(self, kw):
        """派工 brief 简化的关键字匹配"""
        assert route_partition(f"为什么 {kw} 的实验数据很重要") == "cold"
        assert route_partition(kw) == "cold"  # 单独时间词也算

    def test_year_2024_routes_cold(self):
        """数字年份兜底: 任何 4 位数字年 < 当前年-1 视为 cold"""
        assert route_partition("2024 年的研究") == "cold"
        assert route_partition("2023 年发表") == "cold"
        assert route_partition("2020 年实验") == "cold"

    def test_current_year_routes_hot(self):
        """当前年不视为 cold (2026 现在)"""
        # 注意: 硬编码 2026, 2026 不是 cold (因为 < 2024 才 cold)
        # 但 2025 是 hot (2025 不 < 2024)
        assert route_partition("2025 年") == "hot"
        assert route_partition("2026 年") == "hot"


# === 2. get_partition_where_clause() SQL 片段测试 ===

class TestGetPartitionWhereClause:
    def test_hot_clause(self):
        clause = get_partition_where_clause("hot")
        assert "created_at > NOW()" in clause
        assert "6 months" in clause

    def test_cold_clause(self):
        clause = get_partition_where_clause("cold")
        assert "created_at <=" in clause
        assert "6 months" in clause

    def test_all_clause(self):
        clause = get_partition_where_clause("all")
        assert clause == "1=1"

    def test_custom_threshold(self):
        clause = get_partition_where_clause("hot", threshold_months=12)
        assert "12 months" in clause


# === 3. list_knowledge_partition() 集成测试 (mock DB) ===

class TestListKnowledgePartition:
    @pytest.mark.asyncio
    async def test_hot_partition_builds_correct_query(self):
        """验证生成的 SQL 含 hot 过滤条件"""
        from app.services.knowledge_service import KnowledgeService

        # Mock AsyncSession
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = KnowledgeService(db=mock_db)
        result = await service.list_knowledge_partition(partition="hot", limit=10)

        # 验证 execute 被调用
        mock_db.execute.assert_called_once()
        # 验证 SQL 含 created_at 过滤 (派工 brief 严禁改 schema, 仅 ORM 路径)
        call_args = mock_db.execute.call_args
        stmt = call_args[0][0]  # 第一个位置参数 (SQLAlchemy statement)
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "created_at > NOW()" in stmt_str
        assert "deleted_at IS NULL" in stmt_str
        assert "LIMIT 10" in stmt_str or "limit=10" in stmt_str.lower() or ":limit" in stmt_str

    @pytest.mark.asyncio
    async def test_cold_partition_builds_correct_query(self):
        from app.services.knowledge_service import KnowledgeService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = KnowledgeService(db=mock_db)
        await service.list_knowledge_partition(partition="cold", limit=50)

        call_args = mock_db.execute.call_args
        stmt = call_args[0][0]
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "created_at <=" in stmt_str
        assert "LIMIT" in stmt_str

    @pytest.mark.asyncio
    async def test_all_partition_no_time_filter(self):
        from app.services.knowledge_service import KnowledgeService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = KnowledgeService(db=mock_db)
        await service.list_knowledge_partition(partition="all", limit=100)

        call_args = mock_db.execute.call_args
        stmt = call_args[0][0]
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "1=1" in stmt_str


# === 4. 端到端 smoke: route_partition + get_partition_where_clause 协同 ===

class TestEndToEndSmoke:
    def test_typical_query_routes_to_hot(self):
        """典型用户 query: 走 hot partition"""
        partition = route_partition("zeta 电位如何测量")
        assert partition == "hot"
        clause = get_partition_where_clause(partition)
        assert "created_at > NOW()" in clause

    def test_historical_query_routes_to_cold(self):
        """历史 query: 走 cold partition"""
        partition = route_partition("2024 年的会议纪要")
        assert partition == "cold"
        clause = get_partition_where_clause(partition)
        assert "created_at <=" in clause
