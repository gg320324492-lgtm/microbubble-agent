import warnings
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    APP_NAME: str = "MicroBubble Agent"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    SECRET_KEY: str = ""

    # 数据库
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/microbubble"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "microbubble"
    MINIO_SECURE: bool = False

    # Claude API
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = ""

    # 腾讯会议
    TENCENT_MEETING_APP_ID: str = ""
    TENCENT_MEETING_APP_SECRET: str = ""

    # 企业微信
    WECHAT_CORP_ID: str = ""
    WECHAT_AGENT_ID: str = ""
    WECHAT_SECRET: str = ""
    WECHAT_CALLBACK_TOKEN: str = ""
    WECHAT_ENCODING_AES_KEY: str = ""

    # Whisper
    WHISPER_MODEL_SIZE: str = "large-v3"
    WHISPER_DEVICE: str = "cuda"

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
