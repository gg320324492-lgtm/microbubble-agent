"""统一 SSE 事件协议 — 前后端共享

设计目标：
- 后端 chat_engine 产出 StreamEvent 实例，前端通过 sse.ts 解析同样结构
- 一个文件，前后端各自实现，但字段名/类型必须严格一致
- 新增事件类型时只改这里 + 前后端各加 case 分支
"""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Rich Block：结构化富文本块
# ============================================================================

RichBlockType = Literal[
    "meeting",        # 会议纪要卡片
    "task_list",      # 任务列表
    "knowledge_ref",  # 知识库引用
    "formula",        # 公式（LaTeX + 变量）
    "hypothesis",     # 研究假设
    "member",         # 成员卡片
    "project",        # 项目摘要
    "transcript",     # 会议转录（折叠）
    "chart",          # 图表（ECharts）
    "table",          # 表格
    "fallback",       # 兜底（未识别 type）
]


class RichBlock(BaseModel):
    """结构化富文本块 — 前端 RichContent.vue 按 type 分发渲染"""
    type: RichBlockType
    data: dict[str, Any] = Field(default_factory=dict)
    title: Optional[str] = None
    compact: bool = False  # 紧凑模式（折叠）
    timestamp: Optional[str] = None  # ISO 时间戳


# ============================================================================
# Stream Event：SSE 事件
# ============================================================================

StreamEventType = Literal[
    "text_delta",     # 文本逐字流
    "tool_use",       # 工具调用开始（含 input）
    "tool_result",    # 工具调用结果（含 output）
    "rich_block",     # 富文本块（前端按 type 渲染）
    "thinking",       # 思考中（"正在 X..." 提示）
    "brief",          # 【简要】回复（一次完整 brief 文本）
    "detail",         # 【详细】回复（一次完整 detail 文本）
    "error",          # 错误
    "done",           # 流结束
]


class StreamEvent(BaseModel):
    """SSE 流式事件 — 后端 yield，前端 await"""
    type: StreamEventType

    # text_delta / brief / detail
    delta: Optional[str] = None

    # tool_use
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_use_id: Optional[str] = None

    # tool_result
    tool_output: Optional[dict[str, Any]] = None
    tool_duration_ms: Optional[int] = None
    tool_error: Optional[str] = None

    # rich_block
    block: Optional[RichBlock] = None

    # thinking
    label: Optional[str] = None  # e.g. "🔍 正在搜索知识库..."

    # error
    code: Optional[str] = None
    message: Optional[str] = None

    # done
    usage: Optional[dict[str, int]] = None  # {input_tokens, output_tokens, total_tokens}
    duration_ms: Optional[int] = None
    session_id: Optional[str] = None

    def to_sse(self) -> str:
        """序列化为 SSE data 帧"""
        return f"data: {self.model_dump_json()}\n\n"


# ============================================================================
# ToolError：工具调度异常
# ============================================================================


class ToolError(Exception):
    """工具执行异常基类"""
    def __init__(self, name: str, message: str, code: str = "TOOL_ERROR"):
        self.name = name
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {name}: {message}")


class ToolNotFoundError(ToolError):
    def __init__(self, name: str):
        super().__init__(name, f"工具 {name!r} 不存在", code="TOOL_NOT_FOUND")


class ToolInputError(ToolError):
    def __init__(self, name: str, errors: list[dict]):
        self.errors = errors
        msg = f"输入校验失败: {errors[0].get('msg', '?') if errors else '?'}"
        super().__init__(name, msg, code="TOOL_INPUT_INVALID")


class ToolPermissionError(ToolError):
    def __init__(self, name: str, message: str):
        super().__init__(name, message, code="TOOL_PERMISSION_DENIED")
