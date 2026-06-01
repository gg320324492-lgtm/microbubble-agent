import sys
import warnings
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.config import settings
from app.api.v1 import auth, chat, task, meeting, member, project, knowledge, voice, wechat, upload, tencent_meeting, memory, voiceprint, meeting_progress
from app.core.database import engine, Base
from app.core.redis import close_redis


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

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(task.router, prefix="/api/v1", tags=["任务"])
app.include_router(meeting.router, prefix="/api/v1", tags=["会议"])
app.include_router(member.router, prefix="/api/v1", tags=["成员"])
app.include_router(project.router, prefix="/api/v1", tags=["项目"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["知识库"])
app.include_router(voice.router, prefix="/api/v1", tags=["语音"])
app.include_router(wechat.router, prefix="/api/v1", tags=["企业微信"])
app.include_router(upload.router, prefix="/api/v1", tags=["文件上传"])
app.include_router(tencent_meeting.router, prefix="/api/v1", tags=["腾讯会议"])
app.include_router(memory.router, prefix="/api/v1", tags=["长期记忆"])
app.include_router(voiceprint.router, prefix="/api/v1", tags=["声纹识别"])
app.include_router(meeting_progress.router, prefix="/api/v1", tags=["会议进度"])


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
