"""统一 SSE 事件协议 — 前后端共享

设计目标：
- 后端 chat_engine 产出 StreamEvent 实例，前端通过 sse.ts 解析同样结构
- 一个文件，前后端各自实现，但字段名/类型必须严格一致
- 新增事件类型时只改这里 + 前后端各加 case 分支

⚠️ SSE 事件 delta 语义铁律（CLAUDE.md 552 行）⚠️
每个事件类型必须在源码注释里标注 [increment] 或 [snapshot]：
- [increment] delta 是新增 token，前端必须 `content += delta`
- [snapshot] delta 是完整快照文本，前端必须 `content = delta`（替换）或不 append
混用会导致 2026-06-12 brief 重复输出 bug（commit cf70ff5）再现。
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
    # 2026-06-14 方案 C 新增：折叠态展示 + LLM-driven 决策
    summary: Optional[str] = None  # 折叠态一行摘要，如「成员推荐 3 人（27→3）」
    expanded: bool = False  # 当前是否展开（前端 toggle 时写入）
    collapsed_by_default: bool = True  # LLM 在 synthesis 阶段可 override（让重要 block 默认展开）


# ============================================================================
# Stream Event：SSE 事件
# ============================================================================

StreamEventType = Literal[
    # ===== 原 9 种事件 =====
    "text_delta",     # [increment] 文本逐字流，delta=新增 token，前端 content += delta
    "tool_use",       # [snapshot] 工具调用开始，含 tool_name/tool_use_id
    "tool_result",    # [snapshot] 工具调用结果，含 tool_output/tool_duration_ms
    "rich_block",     # [snapshot] 富文本块，含完整 block 对象
    "thinking",       # [snapshot] "正在 X..." 提示，含 label
    "brief",          # [snapshot, deprecated] 完整 brief 文本快照，v2+ 客户端忽略，保留为 v1 兼容
    "detail",         # [snapshot, deprecated] 完整 detail 文本快照，v2+ 客户端忽略
    "error",          # [snapshot] 错误，含 code/message
    "done",           # [snapshot] 流结束，含 usage/duration_ms/session_id
    # ===== 2026-06-14 方案 C 新增 6 种事件 =====
    "intent_detected",   # [snapshot] 意图分类结果，含 category/confidence/keywords/reasoning（IntentResult dict）
    "plan_step",         # [snapshot] 工具规划单步，含 step/tool/status（pending/running/done）
    "tool_compressed",   # [snapshot] 工具结果被 Haiku 压缩，附加到对应 tool_result 项
    "synthesis_start",   # [snapshot] 综合阶段开始（无 delta，仅阶段标记），后续 text_delta 是最终答案
    "critique",          # [snapshot] 自评结果，含 score/addresses_question/has_synthesis/suggestion
    "retry",             # [snapshot] critique 低分触发重试，前端必须清空 content 准备接收新 text_delta
    # ===== 2026-06-29 #043 账号持久化聊天历史 — 持久化事件 =====
    "message_persisted", # [snapshot] 消息已落库（chat_messages 表），含 message_id/role/client_msg_id/is_partial
    "sync_required",     # [snapshot] 流式中断，前端需重新拉历史（含 reason: aborted|error）
    # ===== 2026-06-30 #009 Self-RAG 重检索 — retrieval 事件 =====
    "retrieval_assessment", # [snapshot] Self-RAG judge 评估结果，含 confidence/can_answer/missing/reason/reretrieved/attempt/latency_ms
    "reretrieval",         # [snapshot] 正在重新检索（含 refined_query/attempt），前端可显示"🔍 正在重新检索..."动画
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

    # thinking / plan_step
    label: Optional[str] = None  # e.g. "🔍 正在搜索知识库..."

    # error
    code: Optional[str] = None
    message: Optional[str] = None

    # done
    usage: Optional[dict[str, int]] = None  # {input_tokens, output_tokens, total_tokens}
    duration_ms: Optional[int] = None
    session_id: Optional[str] = None
    # done (2026-06-15 修复元话语/thinking 泄露)
    # 流式过程 text_delta 累加的 accumulated 含 LLM 写的"我需要..."等元话语
    # 后处理剥除后的最终干净文本，前端 done 时用它**替换** content
    text_without_json: Optional[str] = None  # 剥除 JSON 段 + fake tool_call + 元话语后的纯文本

    # ========================================================================
    # 2026-06-14 方案 C 新增字段（按事件类型可选填充）
    # ========================================================================
    # intent_detected
    intent: Optional[dict[str, Any]] = None  # {category, confidence, keywords, suggested_tools, reasoning}
    # plan_step
    step: Optional[str] = None
    plan_status: Optional[Literal["pending", "running", "done"]] = None
    # tool_compressed
    compression: Optional[dict[str, Any]] = None  # {original_count, selected_count, reasoning, summary}
    # critique
    critique: Optional[dict[str, Any]] = None  # {score, addresses_question, has_synthesis, has_citations, missing, suggestion}
    # retry
    retry_reason: Optional[str] = None
    retry_count: Optional[int] = None
    # ===== 2026-06-29 #043 持久化事件字段 =====
    # message_persisted
    message_id: Optional[int] = None  # chat_messages.id
    persisted_role: Optional[Literal["user", "assistant", "system", "tool"]] = None
    persisted_client_msg_id: Optional[str] = None
    persisted_is_partial: Optional[bool] = None
    # sync_required
    sync_reason: Optional[str] = None  # "aborted" | "error"
    # ===== 2026-06-30 #009 Self-RAG retrieval 字段 =====
    # retrieval_assessment / reretrieval (同一 retrieval dict, phase 区分)
    retrieval: Optional[dict[str, Any]] = None  # {
                                                #   "phase": "assessment" | "reretrieval",
                                                #   "confidence": float,
                                                #   "can_answer": bool,
                                                #   "missing": str,
                                                #   "reason": str,
                                                #   "reretrieved": bool,
                                                #   "attempt": int,
                                                #   "refined_query": str,
                                                #   "latency_ms": int,
                                                # }

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
