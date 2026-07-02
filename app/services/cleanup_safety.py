"""2026-07-02 v2 PR6-P11 — Celery task retention 二次确认守卫

PR6-P9 事故: 我误传 cleanup_old_mentions_task(retention_days=0) → 删 31 条生产 file_mentions
PR6-P10 收官时在"留给 PR6-P11+ 累计后续"里登记了二次确认守卫.

设计:
- retention != settings 默认值时, 延迟 `RETENTION_OVERRIDE_CONFIRM_DELAY_SEC` 秒 (默认 0.5s)
  - 给人手按 Ctrl+C 的窗口 (Celery 启动是 subprocess, 杀 task 可能来得及)
  - 比"hard block" 更友好: 用户如果确认要跑, 等 0.5s 自然继续; 不小心传错值, 0.5s 内来得及 cancel
- logger.warning 必须打印: retention 值 + 默认值 + task 名, 让 docker logs 永久可审计
- 返回值是个 enum-like dict: caller 看到 "skipped" 就 return error dict 不继续执行
- **v2 PR6-P12+ 增强 (2026-07-02)**: 启用 GUARD_INTERACTIVE_PROMPT_ENABLED=True 时
  友好版不再 time.sleep, 而是向 stdin 输出 [y/N] prompt, 等用户输入.
  - 收到 y: 立即放行 (跳过 sleep, 用户显式确认)
  - 收到 n / timeout / EOF: proceed=False (与 or_skip 行为一致)
  - 容器后台跑 (stdin 非 tty) 自动 fallback 到 time.sleep 旧路径, **永不阻塞**:
    Celery beat .delay() / docker exec -d 都不会卡 stdin 等待输入

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
6. **交互式 prompt 必须 stdin.isatty() 兜底**: 容器后台跑 stdin 是 pipe, 不 tty.
   isatty() == False 永远走 time.sleep 旧路径, 避免 Celery beat .delay() 永久阻塞.
7. **prompt 用户选择必走 logger 审计**: 收到 y/n/timeout 必 logger.warning 留 trace,
   docker logs 永久可追溯 (跟 PR6-P9 事故复盘节奏一致).

设计理由:
- 3 个 task 顶层调用点统一 (一行 guard = confirm_retention_param_auto(...))
- 把"友好/严格"决策集中到 settings, 未来改模式不用改 task 代码
- 失败 fast: settings 配错导致延迟还是拒绝, 都不阻断 beat 周期调度 (caller 看 proceed 决定)
"""
import logging
import select
import sys
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


def _prompt_yes_no(
    question: str,
    default: bool = False,
    timeout_sec: float = 30.0,
) -> Optional[bool]:
    """向 stdin 输出 [y/N] prompt, 等用户输入 y/n.

    行为:
    - 收到 y / yes / Y / YES → True
    - 收到 n / no / N / NO → False
    - 收到 EOF (stdin 关闭 / docker exec -d) → None (与 timeout 等价, caller 自行决定)
    - timeout (默认 30s) 还没输入 → None
    - **stdin 非 tty** (容器后台跑 / Celery beat .delay()) → None (兜底, caller fallback)

    Args:
        question: prompt 文本 (自动加 `[y/N]` 后缀)
        default: 暂未使用 (保留 future '回车即默认' 扩展, 当前必须显式 y/n)
        timeout_sec: 等待用户输入的最大秒数, 超时返 None

    Returns:
        Optional[bool]: True=确认 / False=拒绝 / None=timeout/EOF/非tty (caller 决定 fallback)

    铁律:
    1. 永远先 isatty() 兜底 → None, 不阻塞 beat 周期
    2. 用 select() 轮询 stdin 而非 blocking input(), 实现 timeout
    3. prompt 输出用 sys.stdout.write + flush (input() 内部会先 print 再 read, 我们不依赖它)
    4. KeyboardInterrupt (Ctrl+C) 不抛 → 返 False (按"拒绝"处理, 不让 caller 看到异常)
    """
    # 兜底 1: stdin 不是 tty (容器后台跑 / .delay() / docker exec -d) → 不阻塞
    if not sys.stdin.isatty():
        return None
    # 兜底 2: 明确禁用 settings (即便 stdin 是 tty) → 不 prompt
    # (主入口 confirm_retention_param 已经在 settings.GUARD_INTERACTIVE_PROMPT_ENABLED
    # 控制, 这里双保险防"调用 _prompt_yes_no 时忘了加 settings 判断")
    if not getattr(settings, "GUARD_INTERACTIVE_PROMPT_ENABLED", False):
        return None

    prompt_text = f"{question} [y/N] "
    try:
        sys.stdout.write(prompt_text)
        sys.stdout.flush()
    except (OSError, ValueError):
        # stdout 关闭 (CI / redirect) → 当作 None 处理
        return None

    # 用 select() 轮询 stdin, 实现可中断可超时
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout_sec)
    except (OSError, ValueError):
        # Windows / 某些环境 select 对 stdin 不支持
        # 兜底: 走 blocking input() (没有 timeout, 用户必须输 y/n 才能继续)
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            return None if True else False  # EOF → None; Ctrl+C → False (拒绝)
        return _parse_yes_no(line)

    if not ready:
        # timeout
        try:
            sys.stdout.write("\n")
            sys.stdout.flush()
        except (OSError, ValueError):
            pass
        return None

    try:
        line = sys.stdin.readline()
    except (OSError, ValueError):
        return None
    if not line:
        # EOF
        return None
    return _parse_yes_no(line)


def _parse_yes_no(line: str) -> Optional[bool]:
    """解析用户输入 y/n (不区分大小写, 接受 yes/no 简写)

    Args:
        line: 用户输入的一行 (含或不含换行符)

    Returns:
        Optional[bool]: True=y / False=n / None=无效输入 (caller 重新 prompt 或 fallback)
    """
    s = (line or "").strip().lower()
    if s in ("y", "yes"):
        return True
    if s in ("n", "no"):
        return False
    return None


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
            "delay_applied": float,    # 实际 sleep 秒数 (0 表示未延迟, prompt 模式必为 0)
            "reason": Optional[str],   # 仅 proceed=False 时填: "用户拒绝" / "timeout"
            "prompt_used": bool,       # 新增: True=走了 prompt 路径 / False=走了 time.sleep 旧路径
        }

    v2 PR6-P12+ 行为 (2026-07-02):
    - settings.GUARD_INTERACTIVE_PROMPT_ENABLED=True + sys.stdin.isatty():
        → 走 prompt 路径, 用户输 y 才 proceed
    - 否则: 走旧 time.sleep 路径, 与 PR6-P11 行为完全一致 (向后兼容)
    """
    effective_days = retention_days if retention_days is not None else default

    # 1. 默认值场景: 不触发守卫, 直接 proceed (Celery beat 调 .delay() 也不传 retention, 走 None 分支)
    if retention_days is None or retention_days == default:
        return {
            "proceed": True,
            "effective_days": effective_days,
            "delay_applied": 0.0,
            "reason": None,
            "prompt_used": False,
        }

    # 2. 非默认值场景: warn 必带 (无论后续走 prompt 还是 time.sleep)
    actual_delay = delay_sec if delay_sec is not None else getattr(
        settings, "RETENTION_OVERRIDE_CONFIRM_DELAY_SEC", 0.5
    )
    prompt_timeout = getattr(settings, "GUARD_INTERACTIVE_PROMPT_TIMEOUT_SEC", 30.0)

    logger.warning(
        f"⚠️ [cleanup_safety] {task_name} 检测到非默认 retention_days={retention_days} "
        f"(settings 默认={default})"
    )

    # 3. 决策: prompt 路径 vs time.sleep 路径
    # 兜底逻辑: stdin 非 tty (容器后台跑 / Celery beat .delay() / docker exec -d) → 永远走 sleep
    use_prompt = (
        getattr(settings, "GUARD_INTERACTIVE_PROMPT_ENABLED", False)
        and sys.stdin.isatty()
    )

    if use_prompt:
        # 路径 A: 交互式 prompt (运维手动 docker exec 触发时, 用户能真 y/n)
        prompt_question = (
            f"{task_name} 即将以非默认 retention_days={retention_days} "
            f"(默认={default}) 执行清理. 确认继续吗?"
        )
        user_choice = _prompt_yes_no(
            prompt_question,
            default=False,
            timeout_sec=prompt_timeout,
        )
        if user_choice is True:
            # 用户显式 y: 立即放行 (跳过 sleep, 用户已确认)
            logger.warning(
                f"✅ [cleanup_safety] {task_name} 用户显式确认 y, "
                f"retention_days={retention_days} 生效, 开始执行清理 (prompt_used=True)"
            )
            return {
                "proceed": True,
                "effective_days": effective_days,
                "delay_applied": 0.0,
                "reason": None,
                "prompt_used": True,
            }
        if user_choice is False:
            # 用户显式 n
            logger.warning(
                f"🚫 [cleanup_safety] {task_name} 用户拒绝 n, "
                f"retention_days={retention_days} 被拒绝, task 跳过"
            )
            return {
                "proceed": False,
                "effective_days": effective_days,
                "delay_applied": 0.0,
                "reason": (
                    f"refused: 用户在交互式 prompt 中输入 n, "
                    f"retention_days={retention_days} != default={default} 被拒绝"
                ),
                "prompt_used": True,
            }
        # user_choice is None: timeout / EOF / 无效输入 → 走 time.sleep 兜底 (保留旧行为)
        logger.warning(
            f"⏱️ [cleanup_safety] {task_name} prompt timeout/EOF/无效输入 "
            f"({prompt_timeout}s), fallback 到 time.sleep 旧路径"
        )

    # 路径 B: 旧 time.sleep (向后兼容 / prompt 不可用兜底)
    logger.warning(
        f"⚠️ [cleanup_safety] {task_name} 将在 {actual_delay}s 后继续执行 (按 Ctrl+C 可取消)"
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
        "prompt_used": False,
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
            "prompt_used": False,
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
        "prompt_used": False,
    }