import asyncio
import os
import sys
import warnings
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
# W67 第 41 步 (Agent 21): SKIP_DB_SETUP 短路 lifespan 内全部 DB 启动操作
# CI 测试场景 (e.g. qa-bench-ci.yml test DB): scripts/init_db.py 由单独的 docker exec 步执行,
# 避免 lifespan 阻塞 /health 端点超时. 默认 False (生产/本地开发仍是幂等 create_all).
SKIP_DB_SETUP = os.environ.get("SKIP_DB_SETUP", "").lower() in ("1", "true", "yes")
# 2026-06-14 收官：提前 import 触发所有 @tool 装饰器执行，
# 避免 chat 第一次请求时 TOOL_REGISTRY 还是空的（导致模型在 content 里 fake tool_call，
# fake parser 解析后 dispatch_tool 又报 TOOL_NOT_FOUND）
import app.agent.tools  # noqa: F401  ← 关键！触发 tools/__init__.py 链式 import
from app.core.database import engine, Base
from app.core.redis import close_redis
from app.core.exceptions import AppException, app_exception_handler, generic_exception_handler
from app.core.rate_limit import rate_limit_middleware
# RequestLoggingMiddleware 不再独立注册 — 已集成到 rate_limit_middleware 末尾


def _import_application_routers():
    """在线程中导入重型业务路由，并返回原注册顺序的 include 参数。"""
    from app.api.v1 import (
        admin,
        admin_audit,
        analytics,
        auth,
        chat,
        chat_history,
        dashboard,
        drive_files,
        drive_folders,
        file_requests,
        knowledge,
        meeting,
        meeting_progress,
        meeting_recording,
        member,
        memory,
        notifications,
        project,
        task,
        tencent_meeting,
        translation,
        upload,
        upload_multipart,
        voice,
        voiceprint,
        wechat,
        ws_notifications,
    )
    from app.api.v1 import mobile as mobile_v1
    from app.api.v1.dashboard import mobile_router as mobile_aliases

    # 顺序必须保持不变：meeting_recording 要在 meeting 的动态参数路由之前。
    return [
        (auth.router, {"prefix": "/api/v1", "tags": ["认证"]}),
        (chat.router, {"prefix": "/api/v1", "tags": ["对话"]}),
        (task.router, {"prefix": "/api/v1", "tags": ["任务"]}),
        (meeting_recording.router, {"prefix": "/api/v1", "tags": ["录音会议"]}),
        (meeting.router, {"prefix": "/api/v1", "tags": ["会议"]}),
        (member.router, {"prefix": "/api/v1", "tags": ["成员"]}),
        (project.router, {"prefix": "/api/v1", "tags": ["项目"]}),
        (knowledge.router, {"prefix": "/api/v1", "tags": ["知识库"]}),
        (mobile_aliases, {"prefix": "/api/v1", "tags": ["移动端别名"]}),
        (voice.router, {"prefix": "/api/v1", "tags": ["语音"]}),
        (wechat.router, {"prefix": "/api/v1", "tags": ["企业微信"]}),
        (upload.router, {"prefix": "/api/v1", "tags": ["文件上传"]}),
        (tencent_meeting.router, {"prefix": "/api/v1", "tags": ["腾讯会议"]}),
        (memory.router, {"prefix": "/api/v1", "tags": ["长期记忆"]}),
        (voiceprint.router, {"prefix": "/api/v1", "tags": ["声纹识别"]}),
        (meeting_progress.router, {"prefix": "/api/v1", "tags": ["会议进度"]}),
        (dashboard.router, {"prefix": "/api/v1", "tags": ["项目动态"]}),
        (analytics.router, {"prefix": "/api/v1", "tags": ["检索质量"]}),
        (chat_history.router, {"prefix": "/api/v1", "tags": ["聊天历史"]}),
        (admin.router, {"prefix": "/api/v1", "tags": ["管理"]}),
        (drive_folders.router, {"prefix": "/api/v1", "tags": ["网盘文件夹"]}),
        (drive_files.router, {"prefix": "/api/v1", "tags": ["网盘文件"]}),
        (drive_files.share_router, {"prefix": "/api/v1", "tags": ["网盘公开分享"]}),
        (upload_multipart.router, {"prefix": "/api/v1", "tags": ["分片上传"]}),
        (ws_notifications.router, {"prefix": "/api/v1"}),
        (notifications.router, {}),
        (file_requests.router, {"prefix": "/api/v1"}),
        (admin_audit.router, {"prefix": "/api/v1"}),
        (translation.router, {}),
        (mobile_v1.router, {"prefix": "/api/v1", "tags": ["移动端聚合"]}),
    ]


async def _load_application_routers(app: FastAPI) -> None:
    routers = await asyncio.to_thread(_import_application_routers)
    if not getattr(app.state, "application_routers_loaded", False):
        for router, include_kwargs in routers:
            app.include_router(router, **include_kwargs)
        app.state.application_routers_loaded = True
        # 防止后台注册前有人请求过 OpenAPI，留下只有 /health 的缓存 schema。
        app.openapi_schema = None
        print(f"[router-loader] loaded; {len(app.routes)} routes ready")


def _router_loader_finished(task: asyncio.Task) -> None:
    """取出后台异常，避免静默丢失；请求侧仍会收到同一异常。"""
    if task.cancelled():
        return
    try:
        task.result()
    except Exception as exc:
        print(f"ERROR: 业务 router 后台加载失败: {exc!r}")


def _start_router_loader(app: FastAPI) -> asyncio.Task:
    task = getattr(app.state, "router_loader_task", None)
    if task is not None and task.done() and (
        task.cancelled() or task.exception() is not None
    ):
        task = None
    if task is None:
        task = asyncio.create_task(
            _load_application_routers(app),
            name="load-application-routers",
        )
        task.add_done_callback(_router_loader_finished)
        app.state.router_loader_task = task
    return task


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
    # W67 第 41 步 (Agent 21): SKIP_DB_SETUP=1 时全量跳过 lifespan 内 DB 启动操作.
    # CI test app (qa-bench-ci.yml) 由 scripts/init_db.py 单独 docker exec 跑 create_all + seed,
    # lifespan 此处只阻塞 /health 端点 ~30s+ 没有任何收益. 见文档 memory/w67-...-init-db-fast-2026-07-23.md
    if SKIP_DB_SETUP:
        print("[SKIP_DB_SETUP] 跳过 lifespan 内 DB 启动操作 (create_all / seed_formula_library / reminder sync)")
    else:
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

    # 不能把加载逻辑直接写在 yield 后：asynccontextmanager 的 yield 后半段只在 shutdown 执行。
    # 后台 task 让 ASGI startup 立即完成；重型同步 import 在线程中执行，不占用事件循环，
    # 因而 /health 会在业务 router 尚未 ready 时也能持续响应。
    router_loader_task = _start_router_loader(app)

    yield
    # 关闭时执行
    if not router_loader_task.done():
        router_loader_task.cancel()
        try:
            await router_loader_task
        except asyncio.CancelledError:
            pass
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


@app.middleware("http")
async def wait_for_application_routers(request: Request, call_next):
    """业务请求等待后台 router ready；早就绪探针永不等待。"""
    if request.url.path not in {"/", "/health"}:
        # httpx.ASGITransport 默认不驱动 lifespan；测试/嵌入式调用也需按需启动 loader。
        # 每次都经 helper，失败或被取消的 task 才能在下一请求自动重试。
        await _start_router_loader(request.app)
    return await call_next(request)


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
