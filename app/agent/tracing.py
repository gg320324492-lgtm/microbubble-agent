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
- 持久化 mode：异步写 agent_traces 表（见 models/agent_trace.py）

设计目标：
- 不阻塞 chat 主流程
- 失败时 degrade 静默（不影响用户）
- 2026-06-14 方案 C Stage 2：支持 async context manager + abort 同步落库
  （修复 CLAUDE.md 752 行"trace 永不持久化"gap + Plan agent 3 铁律 4）
"""

import asyncio
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


# 2026-06-14 方案 C 新增：trace 状态枚举
class TraceStatus:
    """trace 完成状态

    状态机：
    - 'in_progress' → __init__ 时（未启动）
    - 'completed'   → 正常退出 __aexit__ exc_value=None
    - 'aborted'     → 用户中断（CancelledError 路径），同步落库
    - 'error'       → 其他异常退出，同步落库
    - 'low_score_fallback' → critique 低分但 retry 耗尽（Stage 3 才完整实现）
    """
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ERROR = "error"
    LOW_SCORE_FALLBACK = "low_score_fallback"


class TraceCollector:
    """单次 chat 的 trace 收集器

    用法（方案 C 同步模式）：
        trace = TraceCollector(user_id=1, session_id="default", message="...")
        async with trace:  # Stage 2 改：async context manager
            ... 业务逻辑 ...
            trace.record_tool_call(...)
            trace.record_rich_block(...)
            trace.set_brief("...")  # Stage 2 改：set_brief/set_detail 都映射到 .synthesis_text
        # 退出时：
        #   - exc_value=None → 走 Celery 异步持久化
        #   - exc_value=CancelledError → status='aborted'，同步 await 落库（铁律 4）
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
        # 2026-06-14 方案 C：取消 brief/detail 双层，统一为 synthesis_text
        self.synthesis_text: Optional[str] = None
        self.usage: Optional[dict[str, int]] = None
        self.error: Optional[str] = None
        self.start_ts: float = time.time()
        self.end_ts: Optional[float] = None
        # 2026-06-14 方案 C 新增
        self.status: str = TraceStatus.IN_PROGRESS
        # Stage 3 才会用，先预留：
        self.intent_category: Optional[str] = None
        self.intent_confidence: Optional[float] = None
        self.tool_rounds_used: int = 0
        self.compression_applied_count: int = 0
        self.critique_score: Optional[int] = None
        self.retry_count: int = 0

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
        """兼容老 API — 实际存到 synthesis_text"""
        self.brief = text
        if not self.synthesis_text:
            self.synthesis_text = text

    def set_detail(self, text: str):
        """兼容老 API — 实际存到 synthesis_text（合并到主答案）"""
        self.detail = text
        if not self.synthesis_text:
            self.synthesis_text = text

    def set_synthesis(self, text: str):
        """2026-06-14 新 API：直接设置综合答案（取代 set_brief/set_detail）"""
        self.synthesis_text = text
        self.brief = text  # 兼容老 API

    def set_usage(self, input_tokens: int, output_tokens: int):
        self.usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    def set_error(self, error: str):
        self.error = error

    def set_intent(self, category: str, confidence: float):
        self.intent_category = category
        self.intent_confidence = confidence

    def set_critique(self, score: int, retry_count: int = 0):
        self.critique_score = score
        self.retry_count = retry_count

    # ---- 生命周期：同步 context manager（兼容老代码） ----

    def __enter__(self):
        self.start_ts = time.time()
        self.status = TraceStatus.IN_PROGRESS
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_ts = time.time()
        if exc_val:
            self.error = f"{type(exc_val).__name__}: {exc_val}"
            self.status = TraceStatus.ERROR
        else:
            self.status = TraceStatus.COMPLETED
        # 同步模式下只 schedule，调用方负责 join
        self._schedule_persist()

    # ---- 生命周期：async context manager（2026-06-14 方案 C 新增，铁律 4） ----

    async def __aenter__(self):
        self.start_ts = time.time()
        self.status = TraceStatus.IN_PROGRESS
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """铁律 4 关键路径

        行为：
        - exc_value=None → status=COMPLETED，Celery 异步持久化
        - exc_value=CancelledError → status=ABORTED，**同步** await 落库（不丢 abort 记录）
        - exc_value=其他 Exception → status=ERROR，**同步** await 落库
        """
        self.end_ts = time.time()
        if exc_val is not None:
            self.error = f"{type(exc_val).__name__}: {exc_val}"
            if isinstance(exc_val, asyncio.CancelledError):
                self.status = TraceStatus.ABORTED
                logger.warning(
                    f"trace ABORTED (sync persist): user_id={self.user_id} "
                    f"session_id={self.session_id}"
                )
            else:
                self.status = TraceStatus.ERROR
                logger.error(
                    f"trace ERROR (sync persist): {self.error}",
                    exc_info=False,  # 避免重复 traceback（外层会 trace）
                )
            # 异常路径：同步落库（不走 Celery）
            try:
                await self._persist_now()
            except Exception as e:
                logger.error(f"trace 同步落库失败（已降级 Celery）: {e}")
                # 退路：仍走 Celery
                self._schedule_persist()
        else:
            self.status = TraceStatus.COMPLETED
            # 正常路径：Celery 异步持久化
            self._schedule_persist()

    @property
    def total_duration_ms(self) -> int:
        if self.end_ts is None:
            return int((time.time() - self.start_ts) * 1000)
        return int((self.end_ts - self.start_ts) * 1000)

    # ---- 持久化：Celery 异步路径（正常完成） ----

    def _schedule_persist(self):
        """异步持久化到数据库（不阻塞 chat 流程）

        流程：Celery 任务 persist_trace_task.delay(dict) 异步写 agent_traces 表
        失败：Celery max_retries=2 重试，仍失败时降级到 logger
        """
        try:
            from app.services.agent_trace_tasks import persist_trace_task
            payload = self._build_payload()
            persist_trace_task.delay(payload)
        except Exception as e:
            # Celery 不可用时降级到 log
            logger.warning(f"trace Celery 调度失败（已降级 log）: {e}")
            try:
                log_entry = {
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "status": self.status,
                    "tool_count": len(self.tool_calls),
                    "rich_block_count": len(self.rich_blocks),
                    "total_duration_ms": self.total_duration_ms,
                }
                logger.info(f"AgentTrace(fallback): {log_entry}")
            except Exception:
                pass

    # ---- 持久化：同步路径（abort/error，铁律 4） ----

    async def _persist_now(self):
        """同步落库到 agent_traces 表（用于 abort / error 场景，确保不丢记录）

        与 Celery 任务 persist_trace_task 的区别：
        - 不用 Celery（避免 task 还没拉走就被 SIGTERM）
        - 不用全局 async_session（CLAUDE.md 752 行铁律：Celery 跨 event loop 会爆）
        - 创建独立 NullPool 引擎 + 独立 session（参照 reminder_service 模式）
        """
        from app.config import settings
        from app.core.database import Base  # noqa: F401
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with Session() as db:
                # 直接 insert，不走 ORM 避免 migration race
                from app.models.agent_trace import AgentTrace
                payload = self._build_payload()
                trace_row = AgentTrace(
                    user_id=payload["user_id"],
                    session_id=payload["session_id"],
                    message=payload["message"],
                    tool_calls=payload["tool_calls"],
                    rich_blocks=payload["rich_blocks"],
                    brief=payload["brief"],
                    detail=payload["detail"],
                    usage=payload["usage"],
                    total_duration_ms=payload["total_duration_ms"],
                    error=payload["error"],
                )
                # 2026-06-14 方案 C 新增字段（Stage 2 仅写存在的，Stage 3 加 6 metric 列后写入）
                if hasattr(trace_row, "status"):
                    trace_row.status = self.status
                db.add(trace_row)
                await db.commit()
        finally:
            await engine.dispose()

    def _build_payload(self) -> dict:
        """构造持久化 payload（Celery 路径和 sync 路径共用）"""
        return {
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
            "brief": (self.brief or self.synthesis_text or "")[:5000],
            "detail": self.detail,  # v2+ 不用 detail，但仍兼容
            "usage": self.usage,
            "total_duration_ms": self.total_duration_ms,
            "error": self.error,
            "status": self.status,
        }

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
            "brief": self.brief or self.synthesis_text,
            "detail": self.detail,
            "usage": self.usage,
            "error": self.error,
            "total_duration_ms": self.total_duration_ms,
            "status": self.status,
            # 2026-06-14 方案 C Stage 3 新增字段
            "intent_category": self.intent_category,
            "intent_confidence": self.intent_confidence,
            "tool_rounds_used": self.tool_rounds_used,
            "compression_applied_count": self.compression_applied_count,
            "critique_score": self.critique_score,
            "retry_count": self.retry_count,
        }
