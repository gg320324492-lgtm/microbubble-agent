---
name: v2-drive-pr6-p11-cleanup-safety-guard-2026-07-02
description: PR6-P11 Celery retention 二次确认守卫 — PR6-P9 误删事故后的第二道防线, 守卫后真删的踩坑与修复路径
metadata:
  type: incident + 永久铁律
---

# v2 PR6-P11 — Celery retention 二次确认守卫 (2026-07-02)

## 触发场景

PR6-P9 事故留尾: 我自己验证时 `cleanup_old_mentions_task(retention_days=0)` 误传值 → 删 31 条 production file_mentions 数据。PR6-P10 已补 backup_before_delete 机制 + restore CLI 兜底。
PR6-P11 是**第二道防线**: 在 task 真跑 DELETE 前, 守卫 `retention != settings 默认值` 时延迟 + warn, 让人手 Ctrl+C 取消。

## 设计模式 (双重 API)

| 函数 | 行为 | 应用场景 |
|------|------|---------|
| `confirm_retention_param(retention_days, default, task_name, delay_sec=None)` | 非默认值 → delay + warn + **proceed=True** | 3 task 默认走这个 (用户友好) |
| `confirm_retention_param_or_skip(retention_days, default, task_name, delay_sec=None)` | 非默认值 → **proceed=False** (立即拒绝) | 留给 critical 场景 (Sentry 监控等严禁漂移) |

**默认 0.5s 延迟 (settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC)**: 足够人手按 Ctrl+C 取消 Celery task, 但又不至于让用户"等不耐烦"。

**调用模式 3 task 统一**:
```python
guard = confirm_retention_param(
    retention_days=retention_days,
    default=settings.X_RETENTION_DAYS,
    task_name="cleanup_x_task",
)
if not guard["proceed"]:
    return {"status": "skipped", "reason": guard["reason"], ...}
days = guard["effective_days"]
```

## 首次集成测试踩坑 — 教训沉淀 ⭐

`test_cleanup_soft_deleted_sessions_task_triggers_delay_on_retention_zero` **首次跑时没真 mock service**, 守卫 delay 通过后 task 真跑 cleanup → **真 DELETE 了 4 条 chat_sessions 数据**。

**PR6-P10 补救**: 用 `scripts/restore_from_backup.py --apply --confirm` 真恢复 4 条 chat_sessions (PR6-P11 + PR6-P10 集成测试救了一命)。

**修复**: 测试改用 `_make_async_return(0)` mock service 函数返 0 行, 即使守卫 proceed=True, task 不会真发起任何 SQL DELETE。

```python
def _make_async_return(value):
    """构造 awaitable, mock service 函数直接返 value (绕过真实 await chain)"""
    class _Awaitable:
        def __init__(self, v): self.v = v
        def __await__(self):
            return iter([self.v])
    return _Awaitable(value)
```

## 5 永久铁律

**铁律 1**: Celery retention 类参数必须 `confirm_retention_param` 守卫。
任何 `@celery_app.task` 函数接受 `retention_days` / `*_hours` / `*_seconds` 等可覆盖默认清理窗口的参数, **顶部必须守卫**。
不守卫 = 等于把删除按钮交给 Celery 操作员不带二次确认。

**铁律 2**: 默认值 == settings.X_RETENTION_DAYS 时不触发守卫。
周期性 `task.delay()` 调用永远走 `retention_days=None` 路径, 不延迟不 warn。守卫仅在"显式覆盖默认值"时触发, 不污染日常 beat 调度。

**铁律 3**: 延迟秒数从 settings 读, 紧急场景可设 0 关闭。
`RETENTION_OVERRIDE_CONFIRM_DELAY_SEC=0` 跳过 sleep 直接 proceed (如真要快速跑非默认值)。不改代码就能调 (`.env` 一行 + 重启)。

**铁律 4**: 测试时必须 mock service 函数返 0, 不能让 task 真跑 destructive 路径。
守卫 proceed=True 后面就是真 cleanup, **测试要验证"守卫被触发" 而不是"cleanup 真跑"**。
反例: `with patch("app.services.X_service.cleanup", new=_make_async_return(0))` 才能挡住真 DELETE。

**铁律 5**: 严格版 `confirm_retention_param_or_skip` 留给 critical 场景。
Sentry 监控/严禁漂移场景用 `or_skip` 版本 (非默认就拒绝执行), 默认 3 个 cleanup task 用 `confirm_retention_param` 友好版 (延迟 + warn 让用户决定)。

## 5 个文件改动 (净 +213 行)

| 文件 | 改动 | 行数 |
|------|------|------|
| `app/config.py` | 新增 `RETENTION_OVERRIDE_CONFIRM_DELAY_SEC: float = 0.5` | +7 |
| `app/services/cleanup_safety.py` | **新文件** — `confirm_retention_param` + `confirm_retention_param_or_skip` 双重 API | +115 |
| `tests/test_cleanup_safety.py` | **新文件** — 8 unit + 3 or_skip + 1 settings + 4 integration = 14 test | +155 |
| `app/services/chat_history_tasks.py` | 顶部 + `confirm_retention_param()` 守卫 + skippable return | +18 |
| `app/services/drive_cleanup_tasks.py` | 同上 | +19 |
| `app/services/file_mention_tasks.py` | 同上 | +18 |

净: **+213 行 / -0 行** (PR6-P11 全是新增 + defensive guards, 0 业务逻辑改动)

## 端到端验证

```bash
# 1. 代码同步
docker cp app/services/cleanup_safety.py microbubble-agent-app-1:/app/app/services/
docker cp tests/test_cleanup_safety.py microbubble-agent-app-1:/app/tests/
docker cp app/config.py app/services/{chat_history,drive_cleanup,file_mention}_tasks.py microbubble-agent-app-1:/app/app/

# 2. 重启 (CLAUDE.md 752 铁律变体)
docker compose restart app celery-worker

# 3. 跑测试
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c "cd /app && pytest tests/test_cleanup_safety.py -v"
# 期望: 14 passed

# 4. 真调 task 模拟误传 retention=0
docker exec microbubble-agent-celery-worker-1 bash -c "cd /app && python -c \"
from app.services.file_mention_tasks import cleanup_old_mentions_task
print(cleanup_old_mentions_task(retention_days=0))
\""
# 期望: stdout 看到 delay 0.5s 后继续, 返回 deleted_count (0 真删, 真删场景下应该 warn)
```

## 部署

无需新操作 (commit + push 后 webhook 自动 deploy)。设置可在 `.env`:
```bash
RETENTION_OVERRIDE_CONFIRM_DELAY_SEC=0.5    # 默认
RETENTION_OVERRIDE_CONFIRM_DELAY_SEC=0      # 紧急关闭: 真要快速跑非默认
RETENTION_OVERRIDE_CONFIRM_DELAY_SEC=2.0    # CI/审计场景: 给更多取消窗口
```

## 与 PR6-P10 (backup_before_delete) 互补

| 层级 | 作用 |
|------|------|
| **PR6-P10** (backup_before_delete) | 即便 DELETE 真发生, 先 JSON 备份 + restore CLI 可恢复 |
| **PR6-P11** (cleanup_safety) | 守卫提前拦截, 让 DELETE 不发生 (延迟时人手可 Ctrl+C) |

两道防线=用户既能"恢复已删"又能"主动避免误删"。

## 沉淀位置

- `memory/v2-drive-pr6-p11-cleanup-safety-guard-2026-07-02.md` (本文件)
- CLAUDE.md 顶部任务链 + "不在本次范围" 留给 PR6-P12+
- `MEMORY.md` 索引
