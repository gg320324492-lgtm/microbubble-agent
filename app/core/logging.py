"""日志配置

W87-H-1 增量 (派工 v6 §5 反馈类 20.28):
- 新增 RequestContextFilter: 自动附加 request_id + task_id 到每条 log
- JSONFormatter 增加 request_id + task_id 字段 (向后兼容, default '-')
- 控制台 formatter 也接受 (request_id/task_id 默认值不被显示)
- 不替换 stdlib logging, 仅追加 (派工 v6 §5 反馈类 20.28: logger 升级由后续任务推进)
"""
import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.core.request_context import get_request_id, get_task_id


class JSONFormatter(logging.Formatter):
    """生产环境 JSON 日志格式"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # W87-H-1: 透传 request_id + task_id (派工 v6 §5 反馈类 20.28)
            "request_id": getattr(record, "request_id", "-"),
            "task_id": getattr(record, "task_id", "-"),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class RequestContextFilter(logging.Filter):
    """W87-H-1: 在每条 log 自动附加 request_id + task_id

    从 contextvars 读取 (HTTP middleware / Celery signal 入口设).
    默认 '-' (无 context 时), 让 console + JSON 输出都向后兼容.

    Filter 在 Logger → Handler 之间触发 (与 handler 绑), 不修改 record 由
    formatter 输出. 多个 handler 共享同一 filter 实例即可.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.task_id = get_task_id() or "-"
        return True


def setup_logging():
    log_level = logging.DEBUG if settings.APP_DEBUG else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]

    # 生产环境同时写文件（JSON 格式）
    # 2026-08-17 #Step9: 总是写 error.log 文件 (无论 debug 与否)
    # debug 模式原本只 console, 但 #Step9 目标 = 错误监控, 必须持久化
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.ERROR)  # 只记 ERROR + CRITICAL
    file_handler.setFormatter(JSONFormatter())
    handlers.append(file_handler)

    # 生产环境再写 app.log (全 INFO+)
    if not settings.APP_DEBUG:
        file_handler_info = logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler_info.setFormatter(JSONFormatter())
        handlers.append(file_handler_info)

    # 控制台格式
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    console_formatter = logging.Formatter(fmt, datefmt=datefmt)
    handlers[0].setFormatter(console_formatter)

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )

    # W87-H-1 增量: 把 RequestContextFilter 挂到所有 handler
    # (派工 v6 §5 反馈类 20.28: 不替换 stdlib, 仅追加)
    context_filter = RequestContextFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(context_filter)

    # 降低第三方库日志级别
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.APP_DEBUG else logging.WARNING
    )

    return logging.getLogger("microbubble")


logger = setup_logging()
