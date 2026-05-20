"""日志配置"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings


class JSONFormatter(logging.Formatter):
    """生产环境 JSON 日志格式"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    log_level = logging.DEBUG if settings.APP_DEBUG else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]

    # 生产环境同时写文件（JSON 格式）
    if not settings.APP_DEBUG:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(JSONFormatter())
        handlers.append(file_handler)

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

    # 降低第三方库日志级别
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.APP_DEBUG else logging.WARNING
    )

    return logging.getLogger("microbubble")


logger = setup_logging()
