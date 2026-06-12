"""测试 v2 工具集 — 5 个迁移/新增工具

覆盖：
- @tool 装饰器正确注册到 TOOL_REGISTRY
- Anthropic tool_use schema 转换正确
- Pydantic input 校验（happy / 缺字段 / 类型错）
- schema 锁定（关键字段存在）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_v2_tools.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

# 触发所有工具注册
import app.agent.tools  # noqa: F401

import pytest
from pydantic import BaseModel

from app.agent.tool_registry import TOOL_REGISTRY, get_all_tool_schemas


# ============================================================================
# 注册表完整性测试
# ============================================================================


class TestToolRegistryIntegration:
    def test_all_v2_tools_registered(self):
        """5 个 v2 工具应全部注册"""
        expected = [
            "query_meetings",
            "get_meeting_detail",
            "get_recent_meeting_conclusions",
            "query_tasks",
            "query_members",
        ]
        for name in expected:
            assert name in TOOL_REGISTRY, f"工具 {name!r} 未注册"

    def test_tool_definitions_have_required_fields(self):
        for name in [
            "query_meetings",
            "get_meeting_detail",
            "get_recent_meeting_conclusions",
            "query_tasks",
            "query_members",
        ]:
            td = TOOL_REGISTRY[name]
            assert td.name == name
            assert td.description, f"{name} 缺少 description"
            assert td.input_model is not None
            assert td.output_model is not None
            assert callable(td.handler)

    def test_anthropic_schemas_exportable(self):
        """所有工具能导出为 Anthropic tool_use 格式"""
        schemas = get_all_tool_schemas()
        names = {s["name"] for s in schemas}
        assert "query_meetings" in names
        assert "get_meeting_detail" in names
        assert "get_recent_meeting_conclusions" in names
        assert "query_tasks" in names
        assert "query_members" in names

        # 验证 schema 结构
        for s in schemas:
            assert s["input_schema"]["type"] == "object"
            assert "properties" in s["input_schema"]


# ============================================================================
# Input/Output schema 锁定测试
# ============================================================================


class TestQueryMeetingsSchema:
    def test_input_minimal(self):
        from app.agent.tools.meeting_tools import QueryMeetingsInput
        inp = QueryMeetingsInput()
        assert inp.date_from is None
        assert inp.date_to is None
        assert inp.keyword is None

    def test_input_full(self):
        from app.agent.tools.meeting_tools import QueryMeetingsInput
        inp = QueryMeetingsInput(
            date_from="2026-06-01", date_to="2026-06-12", keyword="远紫外"
        )
        assert inp.date_from == "2026-06-01"
        assert inp.keyword == "远紫外"

    def test_output_has_enriched_fields(self):
        """query_meetings 输出必须含字段补全（key_points_count / decisions_count / participants / audio_url / task_count）"""
        from app.agent.tools.meeting_tools import MeetingListItem
        item = MeetingListItem(
            id=84, title="例会", start_time="2026-06-12 10:00",
            status="completed", summary="...",
            key_points_count=3, decisions_count=2,
            agenda_summary="项目进度、文献分享",
            participants=[{"id": 1, "name": "张三", "role": "host"}],
            location="会议室A", audio_url="audio/84.webm",
            audio_duration=3600,
            task_count=2,
        )
        assert item.key_points_count == 3
        assert item.decisions_count == 2
        assert item.agenda_summary == "项目进度、文献分享"
        assert len(item.participants) == 1
        assert item.audio_url == "audio/84.webm"
        assert item.task_count == 2
        assert item.rich_block_type == "meeting"


class TestGetMeetingDetailSchema:
    def test_input_meeting_id(self):
        from app.agent.tools.meeting_tools import GetMeetingDetailInput
        inp = GetMeetingDetailInput(meeting_id=84)
        assert inp.meeting_id == 84
        assert inp.title_keyword is None

    def test_input_title_keyword(self):
        from app.agent.tools.meeting_tools import GetMeetingDetailInput
        inp = GetMeetingDetailInput(title_keyword="远紫外")
        assert inp.title_keyword == "远紫外"

    def test_output_full(self):
        from app.agent.tools.meeting_tools import GetMeetingDetailOutput
        out = GetMeetingDetailOutput(
            status="success", id=84, title="例会",
            summary="...", key_points=["要点1"], decisions=["决定1"],
            agenda=[{"title": "议程1"}], location="A",
            audio_url="audio/84.webm", audio_duration=3600,
            start_time="2026-06-12 10:00",
            participants=[{"id": 1, "name": "张三", "role": "host"}],
            task_count=2,
            transcript_meta={"has_raw": True, "has_polished": True, "entries_count": 50},
        )
        assert out.key_points == ["要点1"]
        assert out.transcript_meta["has_polished"] is True
        assert out.rich_block_type == "meeting"

    def test_output_error_shape(self):
        """错误返回也必须符合 schema"""
        from app.agent.tools.meeting_tools import GetMeetingDetailOutput
        out = GetMeetingDetailOutput(
            status="error",
            message="未找到",
        )
        assert out.status == "error"
        assert out.id is None


class TestGetRecentConclusionsSchema:
    def test_input_defaults(self):
        from app.agent.tools.meeting_tools import GetRecentConclusionsInput
        inp = GetRecentConclusionsInput()
        assert inp.days_back == 7
        assert inp.min_decisions == 1
        assert inp.status_filter == "completed"

    def test_input_bounds(self):
        from app.agent.tools.meeting_tools import GetRecentConclusionsInput
        with pytest.raises(Exception):  # ValidationError
            GetRecentConclusionsInput(days_back=0)  # 违反 ge=1
        with pytest.raises(Exception):
            GetRecentConclusionsInput(days_back=200)  # 违反 le=90

    def test_output_groups_structure(self):
        from app.agent.tools.meeting_tools import (
            GetRecentConclusionsOutput,
            RecentConclusionGroup,
        )
        # 验证 schema 接受 BaseModel 实例（不是只 dict）
        out = GetRecentConclusionsOutput(
            status="success", days_back=7, total_meetings=2,
            groups=[
                RecentConclusionGroup(
                    date="2026-06-12", meeting_id=84, title="例会",
                    status="completed", key_points=["a"], decisions=["b"],
                    start_time="10:00",
                )
            ],
        )
        assert out.total_meetings == 2
        assert len(out.groups) == 1
        assert out.groups[0].meeting_id == 84
        assert out.groups[0].decisions == ["b"]


class TestQueryTasksSchema:
    def test_input_minimal(self):
        from app.agent.tools.task_tools import QueryTasksInput
        inp = QueryTasksInput()
        assert inp.assignee_name is None
        assert inp.status is None
        assert inp.project_name is None
        assert inp.overdue is False

    def test_output_enriched_fields(self):
        """query_tasks 输出必须含字段补全（description/project_name/tags/meeting_id）"""
        from app.agent.tools.task_tools import TaskListItem
        item = TaskListItem(
            id=1, title="完成XX", status="in_progress", priority="high",
            assignee_id=2, assignee_name="张三", progress=50,
            description="详细描述", project_id=3, project_name="项目A",
            tags=["紧急", "重要"], meeting_id=84,
        )
        assert item.description == "详细描述"
        assert item.project_name == "项目A"
        assert "紧急" in item.tags
        assert item.meeting_id == 84
        assert item.rich_block_type == "task_list"


class TestQueryMembersSchema:
    def test_input_minimal(self):
        from app.agent.tools.member_tools import QueryMembersInput
        inp = QueryMembersInput()
        assert inp.name is None
        assert inp.research_area is None
        assert inp.grade is None

    def test_output_enriched_fields(self):
        """query_members 输出必须含字段补全（skills/custom_instructions/voice_enrolled/bio）"""
        from app.agent.tools.member_tools import MemberListItem
        item = MemberListItem(
            id=1, name="张三", grade="研二", research_area="微纳米气泡",
            email="zhang@example.com", role="member",
            skills=["Python", "微纳米气泡"],
            custom_instructions="回复要简洁",
            voice_enrolled=True,
            voice_enrolled_at="2026-06-01T10:00:00",
            bio="专注于...",
        )
        assert "Python" in item.skills
        assert item.custom_instructions == "回复要简洁"
        assert item.voice_enrolled is True
        assert item.bio == "专注于..."
        assert item.rich_block_type == "member"


# ============================================================================
# Handler 错误处理测试（不调 LLM / 不需 DB）
# ============================================================================


class TestHandlerErrors:
    @pytest.mark.asyncio
    async def test_get_meeting_detail_missing_param(self):
        """不传 meeting_id 也不传 title_keyword 时返回 error"""
        from app.agent.tool_registry import ToolContext, dispatch_tool
        ctx = ToolContext(db=None, user_id=None)  # 无 DB 也能跑
        result = await dispatch_tool("get_meeting_detail", {}, ctx)
        # 校验顺序：requires_db → 参数校验。当前 db=None 应先返回 DB_UNAVAILABLE
        assert result["status"] == "error"
        # 接受任一 error message（DB 或 参数缺失）
        assert "数据库" in result["message"] or "必须提供" in result["message"]

    @pytest.mark.asyncio
    async def test_get_meeting_detail_no_db(self):
        """无 DB 时返回 DB_UNAVAILABLE 错误"""
        from app.agent.tool_registry import ToolContext, dispatch_tool
        ctx = ToolContext(db=None, user_id=None)
        result = await dispatch_tool("get_meeting_detail", {"meeting_id": 1}, ctx)
        # 注：get_meeting_detail 没有 requires_db=True（默认 True），所以应该是 DB 错误
        # 但实际我们的工具需要 DB 才能 query，因此期望 error
        assert result["status"] == "error"


# ============================================================================
# 工具描述质量测试（防止 description 退化）
# ============================================================================


class TestToolDescriptions:
    """防止描述退化 — 关键关键词必须出现"""

    def test_query_meetings_description_has_critical_keywords(self):
        td = TOOL_REGISTRY["query_meetings"]
        desc = td.description
        # 不检查 self-reference "query_meetings"（描述是给 LLM 看的，自然语言）
        for kw in ["会议", "必调", "禁止", "系统故障"]:
            assert kw in desc, f"query_meetings description 缺少关键词 {kw!r}"

    def test_get_meeting_detail_description(self):
        td = TOOL_REGISTRY["get_meeting_detail"]
        desc = td.description
        for kw in ["key_points", "decisions", "上次例会", "会议详情"]:
            assert kw in desc, f"get_meeting_detail description 缺少关键词 {kw!r}"

    def test_get_recent_conclusions_description(self):
        td = TOOL_REGISTRY["get_recent_meeting_conclusions"]
        desc = td.description
        for kw in ["批量", "按时间", "上周", "会议结论"]:
            assert kw in desc, f"get_recent_conclusions description 缺少关键词 {kw!r}"
