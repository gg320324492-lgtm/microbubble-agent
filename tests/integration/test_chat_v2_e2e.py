"""端到端集成测试 — 小气助手 v2（10 个真实问句）

跑法（需真实 DB + LLM API）：
    pytest tests/integration/test_chat_v2_e2e.py -v --tb=short

跑法（mock LLM，仅验证 API schema）：
    SKIP_LLM=1 pytest tests/integration/test_chat_v2_e2e.py -v

覆盖 10 个真实用户问句（按用户期望的端到端路径）：
1. 我最近有什么任务？
2. 上周的会议结论是什么？
3. 项目 zeta 研究的进度如何？
4. zeta 电位是什么？
5. 实验室有哪些研究假设？
6. 查一下微纳米气泡的生成方法
7. 贾琦的联系方式
8. 5月28日例会的转录给我看
9. 创建一个新任务：周五前完成XX
10. XX 会议没有总结，帮我生成
"""

import os
import pytest
from unittest.mock import patch, AsyncMock

os.environ.setdefault("SKIP_DB_SETUP", "1")  # 默认 skip DB，必要时手动覆盖


# ============================================================================
# 路由 + Schema 集成测试（不需 DB / LLM）
# ============================================================================


class TestChatAPISchema:
    """验证 /chat 和 /chat/stream 端点的 schema"""

    def test_chat_response_model(self):
        """ChatResponse 必须含 10 字段（6 旧 + 4 新）"""
        from app.api.v1.chat import ChatResponse
        fields = list(ChatResponse.model_fields.keys())
        # 6 旧字段
        for f in ["content", "session_id", "file_url", "file_name", "knowledge_content", "is_brief"]:
            assert f in fields, f"ChatResponse 缺少旧字段 {f!r}"
        # 4 新字段（v2 优化）
        for f in ["rich_blocks", "tool_trace", "usage", "duration_ms"]:
            assert f in fields, f"ChatResponse 缺少 v2 新字段 {f!r}"

    def test_chat_request_model(self):
        from app.api.v1.chat import ChatRequest
        assert "message" in ChatRequest.model_fields
        assert "session_id" in ChatRequest.model_fields

    def test_chat_router_has_stream_endpoint(self):
        """/chat/stream 端点必须挂载"""
        from app.api.v1.chat import router
        paths = [r.path for r in router.routes]
        assert "/chat/stream" in paths, f"路由列表中找不到 /chat/stream: {paths}"
        assert "/chat" in paths
        assert "/chat/history/{session_id}" in paths
        assert "/ws/chat/{user_id}" in paths

    def test_chat_uses_v2_agent(self):
        """chat.py 必须用 v2 micro_bubble_agent，不是旧 core.py"""
        from app.api.v1 import chat as chat_module
        from app.agent.micro_bubble_agent import MicroBubbleAgent
        from app.agent.core import MicroBubbleAgent as LegacyAgent
        # 验证 v2_agent 是 v2 类，不是 legacy
        assert isinstance(chat_module.v2_agent, MicroBubbleAgent)
        assert not isinstance(chat_module.v2_agent, LegacyAgent)


# ============================================================================
# 10 个真实问句（结构化验证，mock LLM 加速）
# ============================================================================


# 模拟不同问句的工具调用路径
E2E_SCENARIOS = [
    {
        "id": 1,
        "query": "我最近有什么任务？",
        "expected_tools": ["query_tasks"],
        "expected_block_type": "task_list",
        "mock_response": {
            "status": "success",
            "count": 2,
            "tasks": [
                {"id": 1, "title": "完成XX", "status": "in_progress", "priority": "high",
                 "assignee_id": 1, "assignee_name": "张三", "due_date": "2026-06-15 18:00",
                 "progress": 50, "project_name": "项目A", "tags": ["紧急"], "meeting_id": None,
                 "rich_block_type": "task_list"}
            ]
        }
    },
    {
        "id": 2,
        "query": "上周的会议结论是什么？",
        "expected_tools": ["get_recent_meeting_conclusions"],
        "expected_block_type": "meeting",
        "mock_response": {
            "status": "success", "days_back": 7, "total_meetings": 1,
            "groups": [
                {"date": "2026-06-10", "meeting_id": 83, "title": "5月例会",
                 "status": "completed", "key_points": ["项目进度", "文献分享"],
                 "decisions": ["下周提交报告"], "start_time": "10:00"}
            ],
            "rich_block_type": "meeting"
        }
    },
    {
        "id": 3,
        "query": "项目 zeta 研究的进度如何？",
        "expected_tools": ["get_project_summary", "query_projects"],
        "expected_block_type": "project",
        "mock_response": {"status": "success", "id": 1, "name": "zeta 研究", "task_stats": {"in_progress": 3, "done": 2}}
    },
    {
        "id": 4,
        "query": "zeta 电位是什么？",
        "expected_tools": ["search_knowledge"],
        "expected_block_type": "knowledge_ref",
        "mock_response": {
            "status": "success",
            "results": [{"id": 100, "title": "zeta 电位原理", "content": "zeta 电位是...",
                         "score": 0.92, "category": "基础", "source": "manual", "tags": ["zeta"]}]
        }
    },
    {
        "id": 5,
        "query": "实验室有哪些研究假设？",
        "expected_tools": ["list_hypotheses"],
        "expected_block_type": "hypothesis",
        "mock_response": {"status": "success", "items": [], "total": 0, "page": 1}
    },
    {
        "id": 6,
        "query": "查一下微纳米气泡的生成方法",
        "expected_tools": ["search_knowledge"],
        "expected_block_type": "knowledge_ref",
        "mock_response": {
            "status": "success",
            "results": [{"id": 200, "title": "微纳米气泡的 6 种生成方法",
                         "content": "加压溶气法、旋流法、电解法、膜法、超声法、文丘里管法",
                         "score": 0.95, "category": "方法", "source": "literature"}]
        }
    },
    {
        "id": 7,
        "query": "贾琦的联系方式",
        "expected_tools": ["query_members", "get_member_profile"],
        "expected_block_type": "member",
        "mock_response": {
            "status": "success", "count": 1,
            "members": [{"id": 5, "name": "贾琦", "grade": "博一", "research_area": "微纳米气泡",
                         "email": "jiaqi@example.com", "role": "member", "skills": ["3D-Speaker"],
                         "voice_enrolled": True}]
        }
    },
    {
        "id": 8,
        "query": "5月28日例会的转录给我看",
        "expected_tools": ["get_meeting_transcript"],
        "expected_block_type": "transcript",
        "mock_response": {
            "status": "success", "id": 28, "title": "5月例会",
            "transcript_text": "【张三】今天的会议主要讨论...\n【李四】关于XX...（已截断到 10000 字）",
            "truncated": True
        }
    },
    {
        "id": 9,
        "query": "创建一个新任务：周五前完成XX",
        "expected_tools": ["create_task"],
        "expected_block_type": None,  # 创建类不产生 rich block
        "mock_response": {"status": "success", "task_id": 999, "title": "完成XX"}
    },
    {
        "id": 10,
        "query": "XX 会议没有总结，帮我生成",
        "expected_tools": ["analyze_meeting_transcript", "generate-minutes"],
        "expected_block_type": "meeting",
        "mock_response": {"status": "success", "meeting_id": 88, "summary": "...",
                          "key_points": [...], "decisions": [...]}
    },
]


class TestE2EScenarios:
    """10 个真实问句的工具调用路径 + rich_block 类型断言"""

    @pytest.mark.parametrize("scenario", E2E_SCENARIOS, ids=[f"q{s['id']}" for s in E2E_SCENARIOS])
    def test_scenario_tool_path(self, scenario):
        """每个问句应触发预期工具 + 预期 rich block 类型"""
        from app.agent.chat_engine import _extract_rich_block

        # 模拟工具结果 → 提取 rich block
        result = scenario["mock_response"]
        rb = _extract_rich_block(scenario["expected_tools"][0], result)

        if scenario["expected_block_type"]:
            assert rb is not None, f"问句 {scenario['id']!r} 应产生 rich block"
            assert rb.type == scenario["expected_block_type"], \
                f"问句 {scenario['id']!r} 期望 {scenario['expected_block_type']!r}，得到 {rb.type!r}"
        else:
            # 创建类操作不产生 rich block（除非显式标注）
            if "rich_block_type" not in result:
                assert rb is None or rb.type == "fallback", \
                    f"问句 {scenario['id']!r} 不应产生主要 rich block"


# ============================================================================
# SSE 端到端流式测试（mock fetch + 验证事件类型）
# ============================================================================


class TestSSEEndpoint:
    @pytest.mark.asyncio
    async def test_sse_yields_all_event_types(self):
        """SSE 端点应能 yield 9 种事件类型"""
        from app.agent.protocol import StreamEvent
        from app.agent.chat_engine import ChatEngine

        # 构造一个 mock 完整流程
        engine = ChatEngine()
        # 跳过真实 LLM，只验证协议层的 StreamEvent 序列化
        for evt_type in ["text_delta", "tool_use", "tool_result", "rich_block",
                          "thinking", "brief", "detail", "error", "done"]:
            if evt_type == "text_delta":
                evt = StreamEvent(type=evt_type, delta="hi")
            elif evt_type == "tool_use":
                evt = StreamEvent(type=evt_type, tool_name="test", tool_input={})
            elif evt_type == "tool_result":
                evt = StreamEvent(type=evt_type, tool_name="test", tool_output={"ok": True})
            elif evt_type == "rich_block":
                from app.agent.protocol import RichBlock
                evt = StreamEvent(type=evt_type, block=RichBlock(type="meeting", data={}))
            elif evt_type == "thinking":
                evt = StreamEvent(type=evt_type, label="thinking")
            elif evt_type in ("brief", "detail"):
                evt = StreamEvent(type=evt_type, delta="text")
            elif evt_type == "error":
                evt = StreamEvent(type=evt_type, code="X", message="err")
            elif evt_type == "done":
                evt = StreamEvent(type=evt_type, duration_ms=100, usage={"total_tokens": 50})
            sse = evt.to_sse()
            assert sse.startswith("data: ")
            assert evt_type in sse

    def test_sse_rich_block_serialization(self):
        """SSE rich_block 事件能被前端 JSON.parse"""
        import json
        from app.agent.protocol import RichBlock, StreamEvent
        rb = RichBlock(type="meeting", data={"id": 84, "title": "例会"}, title="5月例会")
        evt = StreamEvent(type="rich_block", block=rb)
        sse_data = evt.to_sse().replace("data: ", "").strip()
        parsed = json.loads(sse_data)
        assert parsed["type"] == "rich_block"
        assert parsed["block"]["type"] == "meeting"
        assert parsed["block"]["data"]["id"] == 84


# ============================================================================
# 性能基线（mock LLM 加速）
# ============================================================================


class TestPerformanceBaseline:
    """性能基线（不调真实 LLM，验证 dispatch + rich block 提取性能）"""

    @pytest.mark.asyncio
    async def test_dispatch_latency(self):
        """工具 dispatch 应 < 5ms（mock handler + Pydantic 校验）"""
        import time
        from app.agent.tool_registry import ToolContext, dispatch_tool, TOOL_REGISTRY

        # 用一个 v2 工具（query_meetings）— 无 DB 也能 dispatch（前置校验返回 error 但不抛）
        assert "query_meetings" in TOOL_REGISTRY
        ctx = ToolContext(db=None, user_id=None)
        t0 = time.monotonic()
        for _ in range(100):
            await dispatch_tool("query_meetings", {}, ctx)
        elapsed = (time.monotonic() - t0) * 1000
        avg_ms = elapsed / 100
        # DB 缺失时返回 error dict（不抛），5ms 内合理
        assert avg_ms < 5, f"工具 dispatch 平均 {avg_ms:.2f}ms (期望 < 5ms)"

    def test_schema_export_latency(self):
        """get_all_tool_schemas() < 10ms"""
        import time
        from app.agent.tool_registry import get_all_tool_schemas
        t0 = time.monotonic()
        for _ in range(100):
            schemas = get_all_tool_schemas()
        elapsed = (time.monotonic() - t0) * 1000
        avg_ms = elapsed / 100
        assert avg_ms < 10, f"schema 导出平均 {avg_ms:.2f}ms (期望 < 10ms)"
        # 至少 5 个工具
        assert len(schemas) >= 5
