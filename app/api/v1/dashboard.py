"""项目动态统计 API"""
import json
from pathlib import Path

from fastapi import APIRouter
from app.core.redis import get_redis

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_STATS_FILE = Path(__file__).parent.parent.parent / "stats.json"
_CACHE_KEY = "dashboard:project-stats"
_CACHE_TTL = 3600  # 1 小时


@router.get("/project-stats")
async def get_project_stats():
    """获取项目开发统计数据"""
    # 1. Redis 缓存
    r = await get_redis()
    try:
        cached = await r.get(_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # 2. 从 app/stats.json 读取
    try:
        if _STATS_FILE.exists():
            with open(_STATS_FILE, "r", encoding="utf-8-sig") as f:
                stats = json.loads(f.read())
            # 缓存 1 小时
            try:
                await r.set(_CACHE_KEY, json.dumps(stats), ex=_CACHE_TTL)
            except Exception:
                pass
            return stats
    except Exception:
        pass

    # 3. 兜底
    return {
        "total_lines": 0, "total_commits": 0, "dev_days": 0, "total_files": 0,
    }


@router.post("/refresh-stats")
async def refresh_stats():
    """清除缓存，强制下次请求重新读取 stats.json"""
    r = await get_redis()
    try:
        await r.delete(_CACHE_KEY)
        return {"ok": True, "message": "缓存已清除，下次请求将读取最新数据"}
    except Exception:
        return {"ok": False, "message": "Redis 不可用"}
