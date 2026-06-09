"""项目动态统计 API"""
import subprocess
import os
import json
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter
from app.core.redis import get_redis

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 排除的目录和文件扩展名
EXCLUDE_DIRS = {
    "node_modules", ".git", "dist", "__pycache__", ".venv", "venv",
    "models", ".idea", ".vscode", "alembic/versions", ".claude"
}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".so", ".o", ".a", ".dll", ".exe", ".whl"}


def _count_lines_and_files() -> tuple[int, int]:
    """统计项目源码行数和文件数"""
    total_lines = 0
    total_files = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            # 排除扩展名
            if any(file.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                continue

            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    total_lines += len(lines)
                    total_files += 1
            except (IOError, UnicodeDecodeError):
                continue

    return total_lines, total_files


def _get_git_stats() -> tuple[int, str]:
    """获取 Git 提交总数和首次提交日期"""
    try:
        # 提交总数
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        total_commits = int(result.stdout.strip()) if result.returncode == 0 else 0

        # 首次提交日期
        result = subprocess.run(
            ["git", "log", "--reverse", "--format=%ai", "--max-count=1"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        first_commit_str = result.stdout.strip() if result.returncode == 0 else ""

        return total_commits, first_commit_str
    except (subprocess.TimeoutExpired, ValueError):
        return 0, ""


def _calculate_dev_days(first_commit_str: str) -> int:
    """计算开发天数"""
    if not first_commit_str:
        return 0
    try:
        # 解析日期（格式：2026-05-16 22:37:48 +0800）
        first_date = datetime.strptime(first_commit_str[:10], "%Y-%m-%d").date()
        return (date.today() - first_date).days
    except ValueError:
        return 0


@router.get("/project-stats")
async def get_project_stats():
    """获取项目开发统计数据"""
    # 尝试从 Redis 缓存获取
    r = await get_redis()
    cache_key = "dashboard:project-stats"
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)

    # 计算统计数据
    total_lines, total_files = _count_lines_and_files()
    total_commits, first_commit_str = _get_git_stats()
    dev_days = _calculate_dev_days(first_commit_str)

    result = {
        "total_lines": total_lines,
        "total_commits": total_commits,
        "dev_days": dev_days,
        "total_files": total_files
    }

    # 缓存 1 小时
    await r.setex(cache_key, 3600, json.dumps(result))

    return result
