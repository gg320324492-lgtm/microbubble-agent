"""项目动态统计 API"""
import json
from pathlib import Path

from fastapi import APIRouter
from app.core.redis import get_redis

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def _get_stats_from_file() -> dict:
    """从 stats.json 读取项目统计数据（部署时自动生成）"""
    stats_file = PROJECT_ROOT / "stats.json"
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
