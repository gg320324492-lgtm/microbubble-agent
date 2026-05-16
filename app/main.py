import sys
import warnings
from fastapi import FastAPI

from app.core.logging import logger
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.config import settings
from app.api.v1 import auth, chat, task, meeting, member, project, knowledge, voice, wechat, upload, tencent_meeting
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
    async with engine.begin() as conn:
        # 安装 pgvector 扩展（用于知识库向量搜索）
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表创建完成")
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
    ALLOWED_ORIGINS.append("https://agent.mnb-lan.cn")

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
