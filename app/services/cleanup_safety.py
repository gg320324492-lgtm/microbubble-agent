"""2026-07-02 v2 PR6-P11 — Celery task retention 二次确认守卫

PR6-P9 事故: 我误传 cleanup_old_mentions_task(retention_days=0) → 删 31 条生产 file_mentions
PR6-P10 收官时在"留给 PR6-P11+ 累计后续"里登记了二次确认守卫.

设计:
- retention != settings 默认值时, 延迟 `RETENTION_OVERRIDE_CONFIRM_DELAY_SEC` 秒 (默认 0.5s)
  - 给人手按 Ctrl+C 的窗口 (Celery 启动是 subprocess, 杀 task 可能来得及)
  - 比"hard block" 更友好: 用户如果确认要跑, 等 0.5s 自然继续; 不小心传错值, 0.5s 内来得及 cancel
- logger.warning 必须打印: retention 值 + 默认值 + task 名, 让 docker logs 永久可审计
- 返回值是个 enum-like dict: caller 看到 "skipped" 就 return error dict 不继续执行

调用模式 (3 个 task 顶部统一):
    from app.services.cleanup_safety import confirm_retention_param_auto

    @celery_app.task(...)
    def cleanup_old_X_task(retention_days=None):
        guard = confirm_retention_param_auto(
            retention_days=retention_days,
            default=settings.X_RETENTION_DAYS,
            task_name="cleanup_old_X_task",
        )
        if not guard["proceed"]:
            return {"status": "skipped", "reason": guard["reason"], "retention_days": guard["retention_days"]}
        days = guard["effective_days"]
        # ... 正常 cleanup 逻辑

铁律:
1. 只对 retention_days != default 触发, retention_days=None (用默认) 不触发
2. delay 秒数从 settings 读, 用户可调到 0 关闭 (紧急场景: 真的想快速跑非默认值)
3. warn 必带 task 名 + retention 值 + 默认值, 容器日志里能 grep
4. 不抛异常 (Celery 任务失败会让 beat 重试, 误杀要 return {status: skipped})
5. **守卫模式开关化**: 调用 confirm_retention_param_auto (而非直接调 confirm_retention_param /
   confirm_retention_param_or_skip), 让 helper 读 settings.CLEANUP_CRITICAL_GUARDED_TASKS
   自动选择模式. CRITICAL 任务走严格版 (非默认直接拒绝), 默认任务走友好版 (延迟 + warn).

设计理由:
- 3 个 task 顶层调用点统一 (一行 guard = confirm_retention_param_auto(...))
- 把"友好/严格"决策集中到 settings, 未来改模式不用改 task 代码
- 失败 fast: settings 配错导致延迟还是拒绝, 都不阻断 beat 周期调度 (caller 看 proceed 决定)
"""
import logging
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger("microbubble.cleanup_safety")


def _is_critical_task(task_name: str) -> bool:
    """检查 task_name 是否在 settings.CLEANUP_CRITICAL_GUARDED_TASKS 白名单里

    Args:
        task_name: 任务全限定名 (例 'app.services.file_mention_tasks.cleanup_old_mentions_task')

    Returns:
        bool: True = critical 任务 (走严格模式 or_skip)

    解析规则:
    - settings.CLEANUP_CRITICAL_GUARDED_TASKS 逗号分隔多个 task_name
    - 空字符串 / 全空白 → 全空 (没有 critical 任务)
    - 大小写敏感 (与 task_name @celery_app.task(name=...) 注册名严格匹配)
    - 前后空白自动 strip
    """
    raw = getattr(settings, "CLEANUP_CRITICAL_GUARDED_TASKS", "") or ""
    names = {n.strip() for n in raw.split(",") if n.strip()}
    return task_name in names


def confirm_retention_param_auto(
    retention_days: Optional[int],
    default: int,
    task_name: str,
    delay_sec: Optional[float] = None,
) -> dict:
    """统一守卫入口: 根据 settings.CLEANUP_CRITICAL_GUARDED_TASKS 自动选择友好/严格模式

    任务调用模式 (PR6-P12 收官标准):
        from app.services.cleanup_safety import confirm_retention_param_auto
        guard = confirm_retention_param_auto(retention_days, default, task_name=__name__)
        if not guard["proceed"]: return {"status": "skipped", ...}

    Returns:
        dict: 与 confirm_retention_param / confirm_retention_param_or_skip 兼容
        {
            "proceed": bool,
            "effective_days": int,
            "delay_applied": float,
            "reason": Optional[str],
            "mode": str,               # 新增: "friendly" | "strict" (供 caller 区分 + 日志审计)
        }
    """
    if _is_critical_task(task_name):
        result = confirm_retention_param_or_skip(
            retention_days=retention_days,
            default=default,
            task_name=task_name,
            delay_sec=delay_sec,
        )
        result["mode"] = "strict"
        return result

    result = confirm_retention_param(
        retention_days=retention_days,
        default=default,
        task_name=task_name,
        delay_sec=delay_sec,
    )
    result["mode"] = "friendly"
    return result


def confirm_retention_param(
    retention_days: Optional[int],
    default: int,
    task_name: str,
    delay_sec: Optional[float] = None,
) -> dict:
    """retention_days != default 时延迟 + warn, 返回 proceed/effective_days

    Args:
        retention_days: 任务参数 (None 表示用默认, 不触发守卫)
        default: settings 中的默认值 (例 settings.MENTION_RETENTION_DAYS)
        task_name: 任务名 (log 必带, 审计追溯)
        delay_sec: 覆盖 settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC (默认 None 读 settings)

    Returns:
        dict: {
            "proceed": bool,           # True=继续 / False=跳过 (caller 必须 return error dict)
            "effective_days": int,     # 实际 retention 值
            "delay_applied": float,    # 实际 sleep 秒数 (0 表示未延迟)
            "reason": Optional[str],   # 仅 proceed=False 时填: "用户可在 N 秒内按 Ctrl+C 取消"
        }
    """
    effective_days = retention_days if retention_days is not None else default

    # 1. 默认值场景: 不触发守卫, 直接 proceed (Celery beat 调 .delay() 也不传 retention, 走 None 分支)
    if retention_days is None or retention_days == default:
        return {
            "proceed": True,
            "effective_days": effective_days,
            "delay_applied": 0.0,
            "reason": None,
        }

    # 2. 非默认值场景: delay + warn
    actual_delay = delay_sec if delay_sec is not None else getattr(
        settings, "RETENTION_OVERRIDE_CONFIRM_DELAY_SEC", 0.5
    )

    logger.warning(
        f"⚠️ [cleanup_safety] {task_name} 检测到非默认 retention_days={retention_days} "
        f"(settings 默认={default}), 将在 {actual_delay}s 后继续执行 (按 Ctrl+C 可取消)"
    )

    if actual_delay > 0:
        time.sleep(actual_delay)

    logger.warning(
        f"🔶 [cleanup_safety] {task_name} 二次确认已通过, retention_days={retention_days} 生效, "
        f"开始执行清理"
    )

    return {
        "proceed": True,
        "effective_days": effective_days,
        "delay_applied": actual_delay,
        "reason": None,
    }


def confirm_retention_param_or_skip(
    retention_days: Optional[int],
    default: int,
    task_name: str,
    delay_sec: Optional[float] = None,
) -> dict:
    """严格版守卫: 非默认值时 return {proceed: False}, 让 caller 跳过整个任务

    与 confirm_retention_param 的区别: 这个版本"非默认就拒绝执行" (更保守)
    confirm_retention_param 是"非默认就延迟让用户决定" (更宽松)

    用哪个?
    - 默认用 confirm_retention_param_auto (PR6-P12 推荐入口, 自动选模式)
    - 显式调 confirm_retention_param: 不管 settings 都要延迟 (Celery beat 周期调用)
    - 显式调 confirm_retention_param_or_skip: 不管 settings 都要拒绝 (Sentry 监控/严禁漂移)
    """
    effective_days = retention_days if retention_days is not None else default

    if retention_days is None or retention_days == default:
        return {
            "proceed": True,
            "effective_days": effective_days,
            "delay_applied": 0.0,
            "reason": None,
        }

    actual_delay = delay_sec if delay_sec is not None else getattr(
        settings, "RETENTION_OVERRIDE_CONFIRM_DELAY_SEC", 0.5
    )

    logger.warning(
        f"🛑 [cleanup_safety] {task_name} 拒绝执行: 非默认 retention_days={retention_days} "
        f"(settings 默认={default}). 设置 RETENTION_OVERRIDE_CONFIRM_DELAY_SEC={actual_delay}s "
        f"或显式传 retention_days=default 可放行"
    )

    return {
        "proceed": False,
        "effective_days": effective_days,
        "delay_applied": 0.0,
        "reason": (
            f"refused: retention_days={retention_days} != settings default={default}. "
            f"使用 confirm_retention_param() 允许带延迟通过; 或设置 "
            f"RETENTION_OVERRIDE_CONFIRM_DELAY_SEC=0 + 显式确认"
        ),
    }