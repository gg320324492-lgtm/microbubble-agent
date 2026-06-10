"""项目动态统计 API"""
import json
from pathlib import Path

from fastapi import APIRouter
from app.core.redis import get_redis

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# stats.json 位置（app/ 目录有 Docker volume 挂载，云端和本地都能读到）
_STATS_DIR = Path(__file__).parent.parent.parent
# 优先本地 app/stats.json，回退到项目根 stats.json（兼容旧版）
_STATS_PATHS = [
    _STATS_DIR / "stats.json",
    _STATS_DIR.parent / "stats.json",
]


def _get_stats_from_file() -> dict:
    """从 stats.json 读取项目统计数据（部署时自动生成）"""
    for stats_file in _STATS_PATHS:
        try:
            if stats_file.exists():
                with open(stats_file, "r", encoding="utf-8") as f:
                    return json.loads(f.read())
        except Exception:
            continue
    return None
    try:
        if stats_file.exists():
            with open(stats_file, "r", encoding="utf-8") as f:
                return json.loads(f.read())
    except Exception:
        pass
    return None


@router.get("/project-stats")
async def get_project_stats():
    """获取项目开发统计数据"""
    # 优先从 stats.json 读取（部署时自动生成）
    stats = _get_stats_from_file()
    if stats:
        return stats

    # 如果 stats.json 不存在，尝试从 Redis 缓存获取
    r = await get_redis()
    cache_key = "dashboard:project-stats"
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)

    # 都不存在时返回默认值
    return {
        "total_lines": 0,
        "total_commits": 0,
        "dev_days": 0,
        "total_files": 0
    }
