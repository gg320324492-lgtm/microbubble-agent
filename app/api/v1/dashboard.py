"""项目动态统计 API + 移动端简化别名（formula / hypothesis / memory / summary）"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.redis import get_redis
from app.models.member import Member

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
# 移动端简化别名（mobile views 用的简单路径，独立 prefix 避免与 /knowledge/* 嵌套路径冲突）
mobile_router = APIRouter(tags=["mobile-aliases"])

_STATS_FILE = Path(__file__).parent.parent.parent / "stats.json"
_CACHE_KEY = "dashboard:project-stats"
_CACHE_TTL = 600  # 10 分钟（开发天数和提交数需准实时）


@router.get("/project-stats")
async def get_project_stats():
    """获取项目开发统计数据。dev_days 每次动态计算。"""
    # 1. Redis 缓存
    r = await get_redis()
    try:
        cached = await r.get(_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # 2. 从 app/stats.json 读取基础数据
    stats = {}
    try:
        if _STATS_FILE.exists():
            with open(_STATS_FILE, "r", encoding="utf-8-sig") as f:
                stats = json.loads(f.read())
    except Exception:
        stats = {}

    # 3. 动态计算 dev_days（每天自动递增）
    first_commit_date = stats.get("first_commit_date", "")
    if first_commit_date:
        try:
            first_dt = datetime.strptime(first_commit_date[:10], "%Y-%m-%d")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            diff_seconds = (now - first_dt).total_seconds()
            stats["dev_days"] = math.ceil(diff_seconds / 86400)
        except (ValueError, TypeError):
            stats["dev_days"] = stats.get("dev_days", 0)
    else:
        # 兜底：用文件中的静态值
        stats["dev_days"] = stats.get("dev_days", 0)

    # 4. 写入 Redis 缓存
    try:
        await r.set(_CACHE_KEY, json.dumps(stats), ex=_CACHE_TTL)
    except Exception:
        pass

    return stats


@router.post("/refresh-stats")
async def refresh_stats():
    """清除缓存，强制下次请求重新读取 stats.json"""
    r = await get_redis()
    try:
        await r.delete(_CACHE_KEY)
        return {"ok": True, "message": "缓存已清除，下次请求将读取最新数据"}
    except Exception:
        return {"ok": False, "message": "Redis 不可用"}


# ============================================================
# 移动端仪表盘 summary（MobileDashboard.vue 用）
# 返回团队核心指标 3 字段：in_progress_tasks / done_tasks / overdue_tasks
# ============================================================
@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """移动端仪表盘汇总（轻量级 3 字段）"""
    from app.models.task import Task, TaskStatus
    from sqlalchemy import func, select

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    base_filter = Task.deleted_at.is_(None)

    # 进行中 = in_progress 状态
    in_progress_q = select(func.count(Task.id)).where(
        base_filter, Task.status == TaskStatus.IN_PROGRESS.value
    )
    # 已完成 = done 状态
    done_q = select(func.count(Task.id)).where(
        base_filter, Task.status == TaskStatus.DONE.value
    )
    # 已逾期 = 未完成 + due_date < now
    overdue_q = select(func.count(Task.id)).where(
        base_filter,
        Task.status != TaskStatus.DONE.value,
        Task.due_date.isnot(None),
        Task.due_date < now,
    )

    in_progress = (await db.execute(in_progress_q)).scalar() or 0
    done = (await db.execute(done_q)).scalar() or 0
    overdue = (await db.execute(overdue_q)).scalar() or 0

    return {
        "in_progress_tasks": in_progress,
        "done_tasks": done,
        "overdue_tasks": overdue,
    }


# ============================================================
# 移动端简化别名端点（mobile views 用，避免嵌套 /knowledge/* 路径）
# - /formula            → /knowledge/formulas
# - /hypothesis         → /knowledge/hypotheses
# - /memory             → /memories
# - /memory/{id}        → /memories/{id}
# ============================================================
@mobile_router.get("/formula")
async def mobile_list_formulas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """移动端公式列表（MobileKnowledgeView.vue 用）"""
    from app.services.formula_service import FormulaService
    svc = FormulaService(db)
    return await svc.list_formulas(page=page, page_size=page_size)


@mobile_router.get("/hypothesis")
async def mobile_list_hypotheses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """移动端假设列表（MobileKnowledgeView.vue 用）"""
    from app.services.hypothesis_service import HypothesisService
    svc = HypothesisService(db)
    return await svc.list_hypotheses(page=page, page_size=page_size)


@mobile_router.get("/memory")
async def mobile_list_memories(
    memory_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """移动端记忆列表（MobileMemoryView.vue 用，路径从 /memories 简化为 /memory）

    复用 app/api/v1/memory.py 的 MemoryResponse schema（from_attributes=True）
    来转换 SQLAlchemy ORM 对象为 dict，避免 FastAPI jsonable_encoder 失败。
    """
    from app.services.memory_service import MemoryService
    from app.api.v1.memory import MemoryResponse
    svc = MemoryService(db)
    items, total = await svc.list_memories(
        user_id=current_user.id,
        memory_type=memory_type,
        page=page,
        page_size=page_size,
    )
    # ORM 对象 → Pydantic → dict 序列化（否则 FastAPI 报 cannot convert dict）
    return {
        "items": [MemoryResponse.model_validate(m).model_dump() for m in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@mobile_router.put("/memory/{memory_id}")
async def mobile_update_memory(
    memory_id: int,
    body: dict = Body(..., example={"content": "新内容"}),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """移动端记忆更新（body 传 {content: "..."}，与 MobileMemoryView.vue:218 一致）"""
    from app.services.memory_service import MemoryService
    from app.api.v1.memory import MemoryResponse
    svc = MemoryService(db)
    content = body.get("content", "")
    memory = await svc.update_memory(
        memory_id=memory_id, content=content, user_id=current_user.id
    )
    if not memory:
        return {"ok": False, "message": "未找到或无权限"}
    return {"ok": True, "data": MemoryResponse.model_validate(memory).model_dump()}


@mobile_router.delete("/memory/{memory_id}")
async def mobile_delete_memory(
    memory_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """移动端记忆删除"""
    from app.services.memory_service import MemoryService
    svc = MemoryService(db)
    ok = await svc.forget_memory(user_id=current_user.id, memory_id=memory_id)
    return {"ok": ok, "message": "已删除" if ok else "未找到或无权限"}
