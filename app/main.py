import sys
import warnings
from uuid import uuid4
from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.config import settings
# 2026-06-14 收官：提前 import 触发所有 @tool 装饰器执行，
# 避免 chat 第一次请求时 TOOL_REGISTRY 还是空的（导致模型在 content 里 fake tool_call，
# fake parser 解析后 dispatch_tool 又报 TOOL_NOT_FOUND）
import app.agent.tools  # noqa: F401  ← 关键！触发 tools/__init__.py 链式 import
from app.api.v1 import auth, chat, task, meeting, member, project, knowledge, voice, wechat, upload, tencent_meeting, memory, voiceprint, meeting_progress, meeting_recording, dashboard, admin, analytics, chat_history  # 2026-07-03 模板管理删除 — meeting_template 已下架
from app.api.v1 import drive_folders  # PR2.4 课题组网盘 folder CRUD
from app.api.v1 import drive_files  # PR2.5 课题组网盘 file CRUD + multipart upload
from app.api.v1 import upload_multipart  # PR2.8 通用分片上传 3 端点
from app.api.v1 import ws_notifications  # PR6: WebSocket 通知推送
from app.api.v1 import notifications  # PR6: 通知 + 活动 + 评论 8 REST API
from app.api.v1 import file_requests  # PR7: 文件请求 (Dropbox 招牌)
from app.api.v1 import admin_audit  # PR7: 审计日志查询 (admin)
from app.api.v1 import translation  # 2026-07-20 论文段落/全文翻译 (LLMClient + Redis cache)
from app.api.v1 import mobile as mobile_v1  # PR8: 移动端聚合 API (dashboard + feed + album-auto-backup)
from app.api.v1.dashboard import mobile_router as mobile_aliases  # 2026-06-17 加：/formula /hypothesis /memory /summary 简化路径
from app.core.database import engine, Base
from app.core.redis import close_redis
from app.core.exceptions import AppException, app_exception_handler, generic_exception_handler
from app.core.rate_limit import rate_limit_middleware
# RequestLoggingMiddleware 不再独立注册 — 已集成到 rate_limit_middleware 末尾


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""

    # SECRET_KEY 安全校验
    if not settings.SECRET_KEY or settings.SECRET_KEY in (
        "change-this-to-a-random-string", "secret", "your-secret-key"
    ):
        if settings.APP_ENV == "production":
            print("ERROR: SECRET_KEY 未设置或使用了不安全的默认值，请在 .env 中配置 SECRET_KEY")
            sys.exit(1)
        else:
            warnings.warn("SECRET_KEY 使用了不安全的默认值，生产环境请务必修改")

    # 启动时执行
    # 先尝试安装 pgvector 扩展（单独事务，失败不影响后续操作）
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("pgvector 扩展已安装")
    except Exception as e:
        print(f"pgvector 扩展安装失败（可忽略，语义搜索将不可用）: {e}")

    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表创建完成")

    # 初始化内置公式库（幂等）
    try:
        from app.core.database import async_session
        from app.seed.seeder import seed_formula_library
        async with async_session() as db:
            await seed_formula_library(db)
    except Exception as e:
        print(f"内置公式库初始化失败（可忽略）: {e}")

    # 启动时同步待发送提醒到 Redis（实现秒级精确提醒）
    try:
        from app.core.database import async_session
        from app.models.reminder import Reminder
        from app.services.reminder_scheduler import reminder_scheduler
        from sqlalchemy import select
        async with async_session() as db:
            result = await db.execute(
                select(Reminder).where(Reminder.status == "pending")
            )
            pending = result.scalars().all()
            if pending:
                await reminder_scheduler.sync_from_db([
                    {"id": r.id, "remind_at_ts": r.remind_at.timestamp()}
                    for r in pending
                ])
                print(f"已同步 {len(pending)} 条待发送提醒到 Redis")
    except Exception as e:
        print(f"提醒同步到 Redis 失败（可忽略）: {e}")

    yield
    # 关闭时执行
    await close_redis()
    await engine.dispose()
    print("数据库和 Redis 连接已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description="微纳米气泡课题组智能Agent系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]
if settings.APP_ENV == "production":
    ALLOWED_ORIGINS.extend([
        "http://agent.mnb-lab.cn",
        "https://agent.mnb-lab.cn",
    ])
if settings.CORS_ORIGINS:
    ALLOWED_ORIGINS.extend([o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一异常处理
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 全站限流中间件
app.middleware("http")(rate_limit_middleware)

# PR7: 自动审计 (集成在 rate_limit_middleware 内部末尾 — BaseHTTPMiddleware 单独 add_middleware 范式不 fire)
# 见 app/core/rate_limit.py 末尾的 audit 集成代码

# 安全响应头中间件
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """安全响应头 + 请求追踪 + Cache-Control"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = str(uuid4())
    # API 响应：max-age=0 满足 webhint 规则（只接受 max-age，不接受 no-store/must-revalidate）
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "max-age=0"
    return response

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(task.router, prefix="/api/v1", tags=["任务"])
app.include_router(meeting_recording.router, prefix="/api/v1", tags=["录音会议"])  # 必须在 meeting.router 之前，否则 /meetings/start-recording 会被 /meetings/{meeting_id} 拦截
app.include_router(meeting.router, prefix="/api/v1", tags=["会议"])
app.include_router(member.router, prefix="/api/v1", tags=["成员"])
app.include_router(project.router, prefix="/api/v1", tags=["项目"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["知识库"])
app.include_router(mobile_aliases, prefix="/api/v1", tags=["移动端别名"])  # 2026-06-17 加：/formula /hypothesis /memory /summary 简化路径
app.include_router(voice.router, prefix="/api/v1", tags=["语音"])
app.include_router(wechat.router, prefix="/api/v1", tags=["企业微信"])
app.include_router(upload.router, prefix="/api/v1", tags=["文件上传"])
app.include_router(tencent_meeting.router, prefix="/api/v1", tags=["腾讯会议"])
app.include_router(memory.router, prefix="/api/v1", tags=["长期记忆"])
app.include_router(voiceprint.router, prefix="/api/v1", tags=["声纹识别"])
app.include_router(meeting_progress.router, prefix="/api/v1", tags=["会议进度"])
# 2026-07-03 模板管理删除 — meeting_template.router 已下架
app.include_router(dashboard.router, prefix="/api/v1", tags=["项目动态"])
app.include_router(analytics.router, prefix="/api/v1", tags=["检索质量"])  # v31 检索质量监控埋点
app.include_router(chat_history.router, prefix="/api/v1", tags=["聊天历史"])  # #043 账号持久化
app.include_router(admin.router, prefix="/api/v1", tags=["管理"])
app.include_router(drive_folders.router, prefix="/api/v1", tags=["网盘文件夹"])  # PR2.4
app.include_router(drive_files.router, prefix="/api/v1", tags=["网盘文件"])  # PR2.5
app.include_router(drive_files.share_router, prefix="/api/v1", tags=["网盘公开分享"])  # PR2.7
app.include_router(upload_multipart.router, prefix="/api/v1", tags=["分片上传"])  # PR2.8
app.include_router(ws_notifications.router, prefix="/api/v1")  # PR6: WebSocket /api/v1/ws/notifications
app.include_router(notifications.router)  # PR6: 通知 + 活动 + 评论 (router 自带 /api/v1 prefix)  # noqa
app.include_router(file_requests.router, prefix="/api/v1")  # PR7: 文件请求 (router 自带 /file-requests prefix)
app.include_router(admin_audit.router, prefix="/api/v1")  # PR7: 审计 admin 端点 (router 自带 /admin/audit prefix)
app.include_router(translation.router)  # 2026-07-20 论文翻译 (router 自带 /api/v1/translation prefix)
app.include_router(mobile_v1.router, prefix="/api/v1", tags=["移动端聚合"])  # PR8: dashboard + feed + album-auto-backup


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
