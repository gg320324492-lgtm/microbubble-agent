"""Agent Trace 收集器 — 轻量可观测性

记录每次 chat 的：
- 工具调用链（name/input/output_keys/duration_ms/error）
- 生成的 rich blocks
- brief / detail 文本
- token 消耗
- 总耗时
- 错误

存储：
- 内存 mode：仅在进程内累积（用于实时返回）
- 持久化 mode：异步写 agent_traces 表（见 models/agent_trace.py，未来添加）

设计目标：
- 不阻塞 chat 主流程
- 失败时 degrade 静默（不影响用户）
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("microbubble.agent.tracing")


@dataclass
class ToolCallRecord:
    name: str
    input: dict
    output: Optional[dict]
    duration_ms: int
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class RichBlockRecord:
    block_type: str
    title: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class TraceCollector:
    """单次 chat 的 trace 收集器

    用法：
        trace = TraceCollector(user_id=1, session_id="default", message="...")
        with trace:
            ... 业务逻辑 ...
            trace.record_tool_call(...)
            trace.record_rich_block(...)
            trace.set_brief("...")
            trace.set_detail("...")
        # 退出 with 时自动 finalize（统计耗时 / 异步持久化）
    """

    def __init__(
        self,
        user_id: Optional[int],
        session_id: str,
        message: str,
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.message = message
        self.tool_calls: list[ToolCallRecord] = []
        self.rich_blocks: list[RichBlockRecord] = []
        self.brief: Optional[str] = None
        self.detail: Optional[str] = None
        self.usage: Optional[dict[str, int]] = None
        self.error: Optional[str] = None
        self.start_ts: float = time.time()
        self.end_ts: Optional[float] = None

    # ---- 记录方法 ----

    def record_tool_call(
        self,
        name: str,
        input: dict,
        output: Optional[dict],
        duration_ms: int,
        error: Optional[str] = None,
    ):
        self.tool_calls.append(ToolCallRecord(
            name=name,
            input=input,
            output=output,
            duration_ms=duration_ms,
            error=error,
        ))

    def record_rich_block(self, block_type: str, title: Optional[str] = None):
        self.rich_blocks.append(RichBlockRecord(block_type=block_type, title=title))

    def set_brief(self, text: str):
        self.brief = text

    def set_detail(self, text: str):
        self.detail = text

    def set_usage(self, input_tokens: int, output_tokens: int):
        self.usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    def set_error(self, error: str):
        self.error = error

    # ---- 生命周期 ----

    def __enter__(self):
        self.start_ts = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_ts = time.time()
        if exc_val:
            self.error = f"{type(exc_val).__name__}: {exc_val}"
        # 异步持久化（fire-and-forget）
        self._schedule_persist()

    @property
    def total_duration_ms(self) -> int:
        if self.end_ts is None:
            return int((time.time() - self.start_ts) * 1000)
        return int((self.end_ts - self.start_ts) * 1000)

    # ---- 持久化 ----

    def _schedule_persist(self):
        """异步持久化到数据库（不阻塞 chat 流程）

        流程：Celery 任务 persist_trace_task.delay(dict) 异步写 agent_traces 表
        失败：Celery max_retries=2 重试，仍失败时降级到 logger
        """
        try:
            from app.services.agent_trace_tasks import persist_trace_task
            # 序列化为 dict（Celery 任务参数需要 JSON 兼容）
            payload = {
                "user_id": self.user_id,
                "session_id": self.session_id,
                "message": (self.message or "")[:1000],
                "tool_calls": [
                    {
                        "name": tc.name,
                        "input_keys": list((tc.input or {}).keys()),
                        "output_keys": list((tc.output or {}).keys()) if tc.output else None,
                        "duration_ms": tc.duration_ms,
                        "error": tc.error,
                    }
                    for tc in self.tool_calls
                ],
                "rich_blocks": [
                    {"type": rb.block_type, "title": rb.title}
                    for rb in self.rich_blocks
                ],
                "brief": (self.brief or "")[:5000] if self.brief else None,
                "detail": (self.detail or "")[:20000] if self.detail else None,
                "usage": self.usage,
                "total_duration_ms": self.total_duration_ms,
                "error": self.error,
            }
            persist_trace_task.delay(payload)
        except Exception as e:
            # Celery 不可用时降级到 log
            logger.warning(f"trace Celery 调度失败（已降级 log）: {e}")
            try:
                log_entry = {
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "tool_count": len(self.tool_calls),
                    "rich_block_count": len(self.rich_blocks),
                    "total_duration_ms": self.total_duration_ms,
                }
                logger.info(f"AgentTrace(fallback): {log_entry}")
            except Exception:
                pass

    # ---- 序列化 ----

    def to_dict(self) -> dict:
        """导出为 dict（用于 API 响应）"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "message": self.message,
            "tool_calls": [
                {
                    "name": tc.name,
                    "input_keys": list((tc.input or {}).keys()),
                    "output_keys": list((tc.output or {}).keys()) if tc.output else None,
                    "duration_ms": tc.duration_ms,
                    "error": tc.error,
                }
                for tc in self.tool_calls
            ],
            "rich_blocks": [
                {"type": rb.block_type, "title": rb.title}
                for rb in self.rich_blocks
            ],
            "brief": self.brief,
            "detail": self.detail,
            "usage": self.usage,
            "error": self.error,
            "total_duration_ms": self.total_duration_ms,
        }
