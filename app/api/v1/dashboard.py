"""项目动态统计 API"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from app.core.redis import get_redis

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

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
