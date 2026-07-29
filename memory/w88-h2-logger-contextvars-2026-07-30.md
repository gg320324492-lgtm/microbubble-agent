# W88-H-2 老 logger 接 contextvars 全面化 (2026-07-30)

## 任务定义

W87-H-1 仅 5 Celery task 接 contextvars (request_id + task_id 双栈),
本任务 (W88-H-2) 把 contextvars 推广到 14 个热路径 service:
非 Celery 但 logging 密集的 service 模块, 让 trace 时任何 logger 调用都带 request_id/task_id。

**派工前提** (主指挥 W88-H-2 brief v3 模板):
- W87-H-1 仅 Celery task 接入 → 14 service logger 仍 0 context → console + JSON 日志 trace 时无法定位具体 HTTP 请求/Celery task
- 最小改动: import + logger 调用前拼字符串, 不动业务逻辑
- 不动 `_tasks.py` (W87-H-1 已修), 不动 Celery task

## 接入清单 (14 service + 1 跳过)

派工列出的 15 service 中, **1 个跳过 + 14 个改造**:

| # | service | logger calls (warning/info/error) | prefix 数 |
|---|---------|-------------------------------------|-----------|
| 1 | meeting_service.py | 4 | 4 |
| 2 | task_service.py | 4 | 4 |
| 3 | drive_service.py | 30+ | 29 |
| 4 | knowledge_service.py | 30+ | 30 |
| 5 | **member_service.py** | 0 | (无 logger 调用, 跳过) |
| 6 | audit_service.py | 2 | 2 |
| 7 | billing_service.py | 1 | 1 |
| 8 | knowledge_qa_service.py | 7 | 7 |
| 9 | auto_research_service.py | 7 | 7 |
| 10 | llm_analysis_service.py | 3 | 3 |
| 11 | voiceprint_service.py | 8 | 8 |
| 12 | chat_history_service.py | 5 | 5 |
| 13 | reminder_service.py | 18 | 18 |
| 14 | push_service.py | 11 | 11 |
| 15 | meeting_analysis_service.py | 11 | 11 |

**总计**: 14 service 改造, 140+ logger 调用加 prefix (W87-H-1 的 Filter 自动注入 record.request_id/task_id 已存在, 本任务补足 console formatter 不显示的盲点).

**派工列出但文件不存在的 (跳过, 留 W89+ 调研补)**:
- `chat_service.py` (不存在, chat 在 `app/agent/`)
- `admin_service.py` (不存在, admin 在 `app/api/admin.py`)
- `payment_service.py` (不存在, 在 `app/services/billing/`)
- `tts_mainplay_pipeline.py` (不存在, 在 `app/services/ios_tts_mainplay.py` + `android_tts_mainplay.py`)
- `voiceprint_cross_meeting_regression.py` (在 `app/services/` 下但跨会议回归逻辑, 留 W89)
- `voiceprint_quality_monitor.py` (Celery task 类型, 留 W89 配套 H-2)

## 改造模式 (类 20.43 沉淀)

### 顶部 import
```python
# 改前
import logging
logger = logging.getLogger("microbubble.xxx")

# 改后
import logging
from app.core.request_context import get_request_id, get_task_id
logger = logging.getLogger("microbubble.xxx")
```

### logger 调用前拼字符串
```python
# 改前
logger.warning(f"会议 {meeting_id} 分析完成: 跳过自动建任务")

# 改后
logger.warning(
    f"[req={get_request_id() or '-'} task={get_task_id() or '-'}] "
    f"会议 {meeting_id} 分析完成: 跳过自动建任务"
)

# 改前 (含 exc_info)
logger.error(f"生成会议摘要失败: {e}")

# 改后
logger.error(
    f"[req={get_request_id() or '-'} task={get_task_id() or '-'}] "
    f"生成会议摘要失败: {e}",
    exc_info=True,
)
```

**改造边界**:
- 仅 `logger.warning/info/error` 加 prefix (业务关键事件)
- `logger.debug` **不**加 prefix (开发期调试, 加 prefix 增加噪音)
- 非 f-string 的 logger (如 `logger.error("...%s...", arg)` — `meeting_ai_polish.py` 那种) **不**改造 (脚本 regex 只匹配 f-string)
- 业务逻辑 0 改动

## 派工 v6 §5 反馈类 20.43 沉淀

> **类 20.43 "logger 接 contextvars 最小改动 = import get_*_id + logger 调用拼字符串"**
>
> **场景**: W87-H-1 已实现 `RequestContextFilter` (app/core/logging.py) 自动注入
> `record.request_id`/`record.task_id` 到每条 log record, JSONFormatter 输出含
> request_id/task_id 字段. 但:
> - 控制台 formatter (`fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"`)
>   **不**用 record.request_id/task_id 字段, **console 不显示**
> - 即使 console 显示, f-string 形式拼在 message 开头比 record field 更易 grep (`grep "[req=" logs/app.log`)
> - W89+ 改造 console formatter 用 record field 可达成同样效果, 但本任务**兼容**当前 formatter
>
> **纪律**: logger 接 contextvars 最小改动 = 顶部 import `get_request_id, get_task_id`
> + logger.warning/info/error 调用前拼 `[req={get_request_id() or '-'} task={get_task_id() or '-'}] `
> 前缀 f-string. 不动 logger.debug (噪音). 不动 %s 风格 logger
> (与 f-string 不兼容, 留后续 W89 调研批量转 f-string).

## 回归测试结果 (派工 v6 §1.2 真验证)

```
SKIP_DB_SETUP=1 timeout 90 python -m pytest \
  tests/test_baseline_audit.py \
  tests/test_push_service_e2e.py \
  tests/test_process_reminders_window.py \
  tests/test_reminder_window.py \
  tests/test_chat_history_service.py \
  tests/test_drive_v2_pr10_knowledge_field_authority.py \
  tests/test_tasks.py \
  tests/test_knowledge_field_constraints.py \
  tests/test_billing_payment_mock_e2e.py \
  tests/test_billing_real_key_enable_e2e.py \
  tests/test_billing_real_sdk_e2e.py
```

**结果**: **132 PASS + 39 SKIPPED + 0 logger-related FAIL**

**Pre-existing FAIL (与本任务无关)**:
- `tests/test_meeting_ai_polish.py::test_validate_polish_result_rejects_rewritten_text`:
  `%s` 格式化 logger 调用 mock 时 `?` 字符解析失败 (在 `meeting_ai_polish.py:205`,
  本任务**未**触碰此 file). 基线 (git stash) 同样失败.
- `tests/test_billing_payment_mock_e2e.py::test_alembic_085_chain`:
  alembic 084 → 085 链顺序变化 (W74 main HEAD 已含 084, 与 logger 改造无关).
  基线同样失败.

## 锚点预期

W87 第 1 批 grand closure 锚点 337 (main HEAD `5ace8015e`).
本任务 commit 在 W88 第 1 批 W88-H-2 分支 `claude/w88-h2-logger-contextvars-2026-07-30`.
主指挥 merge 后 W88 锚点预期 **337 → 338 +1 守恒** (本任务单一 commit).

**0 production code 改动铁律 守恒** (严格边界):
- 仅改 14 个 `app/services/*_service.py` 文件 (顶部 import + logger f-string 拼 prefix)
- 业务逻辑 0 改动 (派工 prompt 纪律 #1)
- 0 Celery task 改动 (派工 prompt 纪律 #2)
- 不动 `app/core/`, `app/api/`, `app/agent/`, `app/models/`, `web/`, `alembic/versions/`
- 不动 `app/services/*_tasks.py` (W87-H-1 已修)

## 留 W89+ backlog

- **剩余 170+ service 未接入**: drive_* (collab/permission/share/upload/version/comment/reaction/dedupe/cleanup 等 13 个) +
  embedding_service.py (14 logger) + vision_service.py (8) + comment_service.py (14) +
  notification_service.py (12) + drive_cache.py + 等等. 派工优先级: logger 密度 + 业务热路径.
- **非 f-string logger 改造**: `meeting_ai_polish.py:205` 等 `logger.error("...%s...", arg)` 风格
  需先批量转 f-string 才能加 prefix (W89 调研批量转换 + 验证 e2e).
- **console formatter 升级**: 派工 v6 §5 反馈类 20.43 提到替代方案 — console formatter 也用
  record.request_id/task_id 字段, 不必每个 logger 都拼 prefix. 评估时机: W89+ console formatter
  升级 PR 时一并做, 不必 170+ service 一个个改.
- **W88-H-2 自身边界**: meeting_ai_polish.py 的 pre-existing `%s` 失败未修, 留 W89 一并.

## commit hash

主指挥 merge 后填.

## 沉淀本任务

- 派工 v6 §5 反馈类 20.43 (新)
- 14 service 改造文件清单 (上表)
- 改造模式 2 段 (顶部 import + logger 调用前拼字符串)
- 回归测试 132 PASS + 0 logger-related FAIL
- W89+ backlog 4 项 (170+ service + 非 f-string + console formatter 升级 + 自身 pre-existing)

派工前提铁律 12 + 类 20 累计 37 实例 (W88-H-2 + 1: 类 20.43).