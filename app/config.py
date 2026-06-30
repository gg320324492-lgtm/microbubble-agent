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
    # 2026-06-19 Phase 7 修复：公网可访问的 MinIO URL（bucket 已是 public-read）
    # 不设置时回退到 presigned URL（仅 docker 内网可达，浏览器无法解析）
    # 格式: https://agent.mnb-lab.cn/minio
    MINIO_PUBLIC_URL: str = "https://agent.mnb-lab.cn/minio"

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

    # 多模态知识库 OCR（Phase 7）
    # 后端选择：llm_vision（默认，走 vision_service）/ tesseract（本地备选，需 pytesseract + apt-get install tesseract-ocr）
    MULTIMODAL_OCR_BACKEND: str = "llm_vision"
    # 单文档最大提取图片数（避免 LLM OCR 成本爆炸）
    MULTIMODAL_MAX_IMAGES_PER_DOC: int = 20
    # 单张图片最大像素（超过等比缩小，避免 vision API 报错）
    MULTIMODAL_MAX_IMAGE_PIXELS: int = 1568 * 1568  # ~2.5MP，Anthropic 建议 < 1568×1568
    # 多图并发数（受 vision API rate limit 限制）
    MULTIMODAL_OCR_CONCURRENCY: int = 4
    # 跳过 OCR 的最小图片尺寸（像素，< 该值视为装饰/图标）
    MULTIMODAL_MIN_IMAGE_PIXELS: int = 100 * 100  # 10k 像素 ≈ 316×316
    # 公式/表格识别 prompt 超时（秒）
    MULTIMODAL_OCR_TIMEOUT_SEC: int = 60

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

    # 任务垃圾桶：软删除任务保留多少天后自动永久删除
    # 2026-06-03：硬编码 3 改为可配置，运维/测试时可临时缩短（如 0 立即清空）
    TRASH_RETENTION_DAYS: int = 3

    # 2026-06-30 #043 Phase 7：聊天会话软删除保留天数（与 task 垃圾桶对齐 30 天可配）
    # 软删除 30 天后 Celery beat 物理清除 chat_sessions/messages/shares（CASCADE）
    # 运维/测试时可临时缩短（如 0 立即清空）— 与 TRASH_RETENTION_DAYS 范式一致
    CHAT_HISTORY_RETENTION_DAYS: int = 30

    # 2026-06-19：开始听会 → 不再自动从会议决策/action items 创建任务
    # 关闭后 _auto_create_task_from_meeting 不再被调用，user 需手动建任务
    # 设 True 可恢复旧行为（不推荐，决策不一定都该是任务）
    ENABLE_AUTO_TASK_FROM_MEETING: bool = False

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

    # 会议 AI 润色
    ENABLE_AI_POLISH: bool = True
    POLISH_CACHE_TTL_SECONDS: int = 86400  # 24h
    POLISH_LOCK_TTL_SECONDS: int = 120  # 2min

    # 2026-06-02 三级润色流水线（实时 / 聚批 / 全文）
    POLISH_BATCH_INTERVAL_SECONDS: int = 30  # L2 攒批触发间隔
    POLISH_BATCH_MAX_SEGMENTS: int = 5  # L2 攒批最大段数
    POLISH_BATCH_MIN_CHARS: int = 30  # L2 攒批最少字符数（避免空批）
    ENABLE_FULL_POLISH_ON_HANGUP: bool = True  # L3 全文润色开关
    FULL_POLISH_MODEL: str = ""  # L3 用高质量模型，空则用默认模型
    FULL_POLISH_MAX_TOKENS: int = 8192
    FULL_POLISH_CHUNK_CHARS: int = 4000  # L3 分块大小（避免超 max_tokens）
    TRANSCRIPT_BUFFER_MAX_ENTRIES: int = 1000  # 原 200 → 1000（覆盖长会议）

    # ========================================================================
    # 2026-06-14 方案 C：Agent 单阶段流式渐进综合架构（plan: eager-juggling-dewdrop.md）
    # ========================================================================
    # 模型配置（按职责分配）
    AGENT_COMPRESSOR_MODEL: str = "claude-haiku-4-5-20251001"  # 工具结果压缩（量大但浅）
    AGENT_INTENT_MODEL: str = "claude-haiku-4-5-20251001"  # 意图分类（闭集 6 选 1）
    AGENT_REFLECTION_MODEL: str = "claude-sonnet-4-6"  # 自评（accuracy critical）
    AGENT_SYNTHESIS_MODEL: str = ""  # 综合主模型，空时用 CLAUDE_MODEL
    # 流程控制
    AGENT_MAX_TOOL_ROUNDS: int = 5  # agentic loop 最多轮数
    AGENT_MAX_SYNTHESIS_TOKENS: int = 4000  # 综合阶段 max_tokens
    AGENT_COMPRESSION_THRESHOLD: int = 5  # 工具结果超过 N 条触发 Haiku 压缩
    AGENT_REFLECTION_THRESHOLD: int = 7  # 自评 < 阈值触发 retry
    AGENT_MAX_REFLECTION_RETRIES: int = 1  # 防爆炸：最多 retry 1 次
    AGENT_RESULT_CACHE_TTL_SEC: int = 300  # 同问题 5min 复用 final synthesis
    # 历史（2026-06-29 已删除）: AGENT_REFLECTION_ENABLED / AGENT_COMPRESSION_ENABLED /
    #   AGENT_NEW_ARCHITECTURE_ENABLED — 30 天回滚承诺提前 15 天收官, 真回滚路径: git revert
    AGENT_INTENT_AWARE_PROMPTS: bool = True  # #001b: 根据意图分类附加回复指南（闲聊/数据/深度 三类分支）
    AGENT_PRIMITIVE_RECOGNITION: bool = True  # #083: 在深度场景附加 5 大原意识别 section（任务/会议/知识/公式/假设）
    AGENT_CROSS_DOMAIN_SYNTHESIS: bool = True  # #086: 在 explain_concept 场景附加跨域综合规则 section (≥3 域 4 工具硬下限)
    AGENT_PLAN_STEP_ENABLED: bool = True           # #041: Phase 0 强制 plan_step 总开关 (Haiku suggested_tools → agentic_loop 主动 dispatch)
    AGENT_PLAN_STEP_MAX: int = 5                   # #041: Phase 0 最多 dispatch 几个 tool (建议 1-3 避免过度调度)
    AGENT_PLAN_STEP_MIN_CONFIDENCE: float = 0.5    # #041: intent confidence < 此值不挂计划 (避免 hallucinated tools)
    AGENT_CROSS_DOMAIN_FANOUT_ENABLED: bool = True  # #042: explain_concept 时代码层强制补齐 4 域工具 (不依赖 LLM 自觉, 与 #086 prompt 软规则协同)

    # 2026-06-30 #009: Self-RAG retrieval gate (Phase 0.5)
    # - judge 模型默认 Haiku 4.5 (走 Anthropic 协议, 跟 compressor/intent 同模型, 延迟 ~300ms)
    # - 30 天回滚承诺（2026-07-30 截止）：AGENT_SELF_RAG_ENABLED=false 关闭，无需代码回滚
    AGENT_SELF_RAG_ENABLED: bool = True               # Phase 0.5 总开关 (用户 toggle + settings 双层)
    AGENT_SELF_RAG_THRESHOLD: float = 0.6             # confidence >= 此值 → 不重检索
    AGENT_SELF_RAG_RELAXED_THRESHOLD: float = 0.4     # can_answer=true 且 confidence >= 此值 → 不重检索（有答案优于无）
    AGENT_SELF_RAG_MAX_RERETRIEVE: int = 1            # 最多重检索次数 (硬上限 2 防爆炸)
    AGENT_SELF_RAG_MAX_CONTEXT_DOCS: int = 8          # 合并后上下文最大文档数
    AGENT_SELF_RAG_MODEL: str = ""                    # judge 模型, 空=AGENT_REFLECTION_MODEL (生产建议改 claude-haiku-4-5-20251001)
    AGENT_SELF_RAG_JUDGE_TIMEOUT_MS: int = 3000       # judge 超时, 触发 default-on-fail

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
