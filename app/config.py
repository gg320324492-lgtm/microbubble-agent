from pydantic_settings import BaseSettings


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

    # 站点域名（用于构造头像等公网可访问的 URL）
    SITE_DOMAIN: str = "agent.mnb-lab.cn"

    # Claude API
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = ""
    CLAUDE_MODEL: str = ""  # 留空则使用各模块默认模型

    # MiMo API (OpenAI 兼容)
    MIMO_API_KEY: str = ""
    MIMO_BASE_URL: str = "https://api.xiaomimimo.com/v1"
    MIMO_MODEL: str = "mimo-v2.5"

    # Vision MCP 配置（DeepSeek 切换时使用）
    VISION_USE_MCP: bool = False
    VISION_MCP_TRANSPORT: str = "stdio"  # stdio 或 http
    VISION_MCP_SERVER_CMD: str = "python -m mcp_server.server"
    VISION_MCP_BASE_URL: str = "http://vision-mcp:8001"
    VISION_MODEL: str = "mimo-v2.5"  # 视觉服务仍使用多模态模型

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

    # Whisper
    WHISPER_MODEL_SIZE: str = "large-v3"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_SERVICE_URL: str = "http://whisper:8002"

    # Claude 生成参数
    CLAUDE_MAX_TOKENS: int = 8192
    SESSION_WINDOW_SIZE: int = 30

    # 数据库连接池
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # JWT 令牌有效期
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis 会话 TTL（秒）
    SESSION_TTL: int = 172800  # 48小时

    # 文件上传大小限制（MB）
    MAX_UPLOAD_SIZE_MB: int = 50

    # CORS 允许的源（逗号分隔，空则使用默认值）
    CORS_ORIGINS: str = ""

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
