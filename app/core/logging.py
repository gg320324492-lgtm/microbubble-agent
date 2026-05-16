"""日志配置"""

import logging
import logging.handlers
import sys
from pathlib import Path

from app.config import settings


def setup_logging():
    log_level = logging.DEBUG if settings.APP_DEBUG else logging.INFO

    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]

    # 生产环境同时写文件
    if not settings.APP_DEBUG:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=datefmt,
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
