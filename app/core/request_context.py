"""request_id + task_id 全链路透传 — W87-H-1 实现

派工 v6 §5 反馈类 20.28 沉淀:
- contextvars 必 request_id + task_id 双栈
- 不替换 stdlib logging (派工 v6 §5 反馈 #1: logger 升级由后续任务推进)

设计:
- request_id: HTTP 入口 (FastAPI middleware) 设, 整个请求生命周期可读
- task_id: Celery 入口 (signal) 设, worker 进程内单 task 内可读
- 双栈: HTTP 调用 Celery task 时, request_id 透传为 parent_request_id (TODO W87-H-2)
- reset_token: caller 负责 reset, 避免 background task ContextVar 污染

用法:
    # FastAPI middleware
    from app.core.request_context import set_request_id, reset_request_id
    rid = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    token = set_request_id(rid)
    try:
        response = await call_next(request)
        return response
    finally:
        reset_request_id(token)

    # Celery signal
    from app.core.request_context import set_task_id
    @signals.task_prerun.connect
    def task_prerun_handler(sender=None, task_id=None, **kwargs):
        set_task_id(task_id)

    # 日志 Filter 自动读
    record.request_id = get_request_id() or '-'
    record.task_id = get_task_id() or '-'

# W87-H-1 锚点范式: +1 (326 -> 327 预期)
"""
import contextvars
from typing import Optional

# 两个 ContextVar: request_id (HTTP) + task_id (Celery)
# default=None 让 helper 处理 fallback (logger Filter 内部统一 '-' default)
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'request_id', default=None
)
task_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'task_id', default=None
)


def get_request_id() -> Optional[str]:
    """当前请求的 request_id (HTTP 入口设)"""
    return request_id_var.get()


def get_task_id() -> Optional[str]:
    """当前 Celery task 的 task_id (worker 入口设)"""
    return task_id_var.get()


def set_request_id(rid: str) -> contextvars.Token:
    """设置 request_id, 返回 token 用于 reset (callback 用 finally)"""
    return request_id_var.set(rid)


def set_task_id(tid: str) -> contextvars.Token:
    """设置 task_id, 返回 token 用于 reset"""
    return task_id_var.set(tid)


def reset_request_id(token: contextvars.Token) -> None:
    """重置 request_id (typically in finally block)"""
    request_id_var.reset(token)


def reset_task_id(token: contextvars.Token) -> None:
    """重置 task_id"""
    task_id_var.reset(token)


def clear_request_context() -> None:
    """清空双 ContextVar (调试 / test fixture 用).

    Production 不调 (依赖 finally reset 即可).
    """
    request_id_var.set(None)
    task_id_var.set(None)
