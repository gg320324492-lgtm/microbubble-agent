"""工具注册表 — 装饰器 + Pydantic schema 校验

设计目标：
- 用 @tool 装饰器注册工具，自动入注册表
- 自动 Pydantic 校验 input/output
- 统一 dispatch_tool 接口
- 工具定义兼容 Anthropic tool_use 协议（name/description/input_schema）

迁移策略：
- 新工具直接用 @tool 装饰器
- 旧工具（tools.py）暂时通过 LEGACY_TOOL_MAP 桥接到 dispatch_tool
- 全部迁移完后删除 LEGACY 桥接
"""

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel, ValidationError

from app.agent.protocol import (
    RichBlock,
    ToolError,
    ToolInputError,
    ToolNotFoundError,
)

logger = logging.getLogger("microbubble.agent.registry")


# ============================================================================
# ToolContext：工具执行上下文
# ============================================================================


class ToolContext:
    """工具执行上下文 — 每个 chat 一次构造，跨工具共享

    ⚠️ 跨 event loop 安全铁律（CLAUDE.md 752/812）⚠️
    所有外部 IO 客户端（redis/llm/db）通过 ctx 注入，不在模块顶部 import 阶段创建。
    Celery worker 跨 event loop 调用时，必须在 task 内创建新 client 传给 ctx，
    否则触发 "Future attached to different loop" 错误。
    """

    def __init__(
        self,
        db=None,
        user_id: Optional[int] = None,
        channel_user_id: Optional[str] = None,
        trace=None,  # TraceCollector 实例（见 tracing.py）
        event_callback: Optional[Callable] = None,  # 用于流式事件回传
        # 2026-06-14 方案 C 新增：跨 loop 安全注入点（铁律 1）
        redis=None,  # aioredis.Redis | None；intent_classifier / result_compressor 用
        llm=None,    # LLMClient | None；agentic_loop / critic 用，None 时调用方临时创建
        loop_id: str = "",  # debugging：记录当前 event loop 标识，便于排查跨 loop 问题
    ):
        self.db = db
        self.user_id = user_id
        self.channel_user_id = channel_user_id
        self.trace = trace
        self.event_callback = event_callback
        self.redis = redis
        self.llm = llm
        self.loop_id = loop_id


# ============================================================================
# ToolDefinition：工具元数据
# ============================================================================


class ToolDefinition:
    """工具定义：name/description/input_model/output_model/handler"""

    def __init__(
        self,
        name: str,
        description: str,
        input_model: Type[BaseModel],
        output_model: Type[BaseModel],
        handler: Callable,
        examples: Optional[list[dict]] = None,
        requires_db: bool = True,
        requires_user: bool = False,
    ):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.output_model = output_model
        self.handler = handler
        self.examples = examples or []
        self.requires_db = requires_db
        self.requires_user = requires_user

    def to_anthropic_schema(self) -> dict:
        """转换为 Anthropic tool_use input_schema 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


# ============================================================================
# Registry：全局注册表
# ============================================================================


TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def tool(
    name: str,
    description: str,
    input_model: Type[BaseModel],
    output_model: Type[BaseModel],
    examples: Optional[list[dict]] = None,
    requires_db: bool = True,
    requires_user: bool = False,
):
    """@tool 装饰器：注册一个工具

    用法：
        class CreateTaskInput(BaseModel):
            title: str

        class CreateTaskOutput(BaseModel):
            status: str
            task_id: int

        @tool(
            name="create_task",
            description="创建新任务",
            input_model=CreateTaskInput,
            output_model=CreateTaskOutput,
        )
        async def create_task(input: CreateTaskInput, ctx: ToolContext) -> dict:
            task = await ...
            return {"status": "success", "task_id": task.id}
    """
    def deco(fn: Callable):
        if name in TOOL_REGISTRY:
            raise ValueError(f"工具 {name!r} 已存在（重复注册）")
        TOOL_REGISTRY[name] = ToolDefinition(
            name=name,
            description=description,
            input_model=input_model,
            output_model=output_model,
            handler=fn,
            examples=examples,
            requires_db=requires_db,
            requires_user=requires_user,
        )
        logger.debug(f"注册工具: {name} -> {fn.__qualname__}")
        return fn
    return deco


def get_all_tool_schemas() -> list[dict]:
    """导出所有工具的 Anthropic tool_use schema — 喂给 LLM"""
    return [td.to_anthropic_schema() for td in TOOL_REGISTRY.values()]


# ============================================================================
# dispatch_tool：统一调度
# ============================================================================


async def dispatch_tool(
    name: str,
    raw_input: dict,
    ctx: ToolContext,
) -> dict:
    """统一工具调度：注册表查找 → input 校验 → 调 handler → output 校验 → trace 记录

    异常处理：
    - ToolNotFoundError: 工具不存在
    - ToolInputError: Pydantic 校验失败（input 字段错）
    - ToolPermissionError: 权限不足
    - 其他 Exception: 包成 {"status": "error", "message": ...} 返回，不上抛
    """
    td = TOOL_REGISTRY.get(name)
    if not td:
        raise ToolNotFoundError(name)

    # 1. 校验 db / user 前置条件
    if td.requires_db and ctx.db is None:
        return {
            "status": "error",
            "code": "DB_UNAVAILABLE",
            "message": f"工具 {name} 需要数据库连接",
        }
    if td.requires_user and not ctx.user_id:
        return {
            "status": "error",
            "code": "AUTH_REQUIRED",
            "message": f"工具 {name} 需要用户身份",
        }

    # 2. input 校验
    try:
        validated_input = td.input_model.model_validate(raw_input or {})
    except ValidationError as e:
        raise ToolInputError(name, e.errors())

    # 3. 调 handler + 计时 + trace
    t0 = time.monotonic()
    error_msg: Optional[str] = None
    output_dump: Optional[dict] = None
    try:
        result = await td.handler(validated_input, ctx)
        # 4. output 校验
        if not isinstance(result, dict):
            raise ValueError(
                f"工具 {name} 处理器返回类型 {type(result).__name__}，期望 dict"
            )
        # 宽松校验：缺字段时补 None，类型不对时报错
        try:
            validated_output = td.output_model.model_validate(result)
            output_dump = validated_output.model_dump()
        except ValidationError as e:
            # 输出 schema 不严格，warn 但不阻断（避免一次小差异导致整个工具失败）
            logger.warning(f"工具 {name} output 校验警告: {e.errors()[:3]}")
            output_dump = result
        return result
    except ToolError:
        raise
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(f"工具 {name} 执行失败: {e}", exc_info=True)
        return {
            "status": "error",
            "code": "TOOL_EXECUTION_ERROR",
            "message": f"工具 {name} 执行失败: {str(e)}",
        }
    finally:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if ctx.trace is not None:
            ctx.trace.record_tool_call(
                name=name,
                input=raw_input or {},
                output=output_dump,
                duration_ms=elapsed_ms,
                error=error_msg,
            )


# ============================================================================
# 兼容性：让旧 core.py 的 if/elif 调度仍然可用
# ============================================================================


async def dispatch_legacy(name: str, input_data: dict, ctx: ToolContext) -> dict:
    """兼容旧 _execute_tool 调用 — 如果工具未注册到装饰器，回退到旧的 if/elif 链

    迁移期使用。完全迁移后删除。
    """
    # 如果新装饰器注册了，直接走新路径
    if name in TOOL_REGISTRY:
        return await dispatch_tool(name, input_data, ctx)

    # 否则回退到旧 core.py._execute_tool
    from app.agent.core import MicroBubbleAgent
    legacy_agent = MicroBubbleAgent()
    return await legacy_agent._execute_tool(
        name=name,
        input_data=input_data,
        db=ctx.db,
        user_id=ctx.user_id,
        channel_user_id=ctx.channel_user_id,
    )
