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
    CLAUDE_MODEL: str = ""  # 留空则使用各模块默认模型

    # 腾讯会议
    TENCENT_MEETING_SDK_ID: str = ""
    TENCENT_MEETING_SDK_KEY: str = ""
    TENCENT_MEETING_USERID: str = ""  # 默认主持人企业用户ID

    # 企业微信
    WECHAT_CORP_ID: str = ""
    WECHAT_AGENT_ID: str = ""
    WECHAT_SECRET: str = ""
    WECHAT_CALLBACK_TOKEN: str = ""
    WECHAT_ENCODING_AES_KEY: str = ""
    WECHAT_API_BASE_URL: str = "https://qyapi.weixin.qq.com"
    WECHAT_EXTERNAL_SENDER: str = ""  # 外部联系人消息的发送者（企业微信userid）
    WECHAT_NOTIFY_CHAT_ID: str = ""  # 会议/任务通知推送的默认群聊ID

    # Whisper
    WHISPER_MODEL_SIZE: str = "large-v3"
    WHISPER_DEVICE: str = "cuda"

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
