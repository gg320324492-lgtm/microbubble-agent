"""
qa-bench/observer.py — 全自动 KB 入库 observer (D2 灰度增强)

W62 T6.2 D2 决策: KB 全自动入库 5/25/100 三档灰度扩展
- 每次 intake 调 record_intake() 写 JSONL 观察日志
- get_daily_stats() 聚合每日统计 (count + error_rate)
- check_rollback_threshold() 触发自动 rollback (error_rate > 5%)
- get_observer_path() 返回观察日志路径 (QA-BENCH_DATA_DIR 环境变量可覆盖)

设计原则 (W62 D2 沉淀):
- JSONL append-only, 每行 1 条 intake 记录 (timestamp + question_id + success + error_msg)
- 每日 stats 按 YYYY-MM-DD 聚合, 避免时区漂移 (统一 UTC)
- rollback 触发只返回 bool, 不自动切 grayscale (调用方 save_to_kb.py 决策)
- observer_path 默认 tests/qa-bench/data/intake_observer.jsonl, 目录不存在自动创建
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Observer JSONL 路径 (可被环境变量 QA-BENCH_DATA_DIR 覆盖)
DEFAULT_OBSERVER_DIR = Path("tests/qa-bench/data")
DEFAULT_OBSERVER_FILENAME = "intake_observer.jsonl"

# Rollback 触发阈值 (error_rate > 5% → rollback)
DEFAULT_ROLLBACK_THRESHOLD = 0.05


def get_observer_path() -> Path:
    """返回 observer JSONL 路径

    优先级: env QA_BENCH_DATA_DIR > tests/qa-bench/data (相对当前 cwd)
    """
    base = Path(os.environ.get("QA_BENCH_DATA_DIR", str(DEFAULT_OBSERVER_DIR)))
    base.mkdir(parents=True, exist_ok=True)
    return base / DEFAULT_OBSERVER_FILENAME


def record_intake(
    timestamp: Optional[str] = None,
    question_id: str = "",
    success: bool = True,
    error_msg: str = "",
) -> None:
    """记录一次 KB intake 操作

    Args:
        timestamp: ISO 8601 字符串, 默认当前 UTC
        question_id: 题号 (e.g. "S-001")
        success: 是否成功入库
        error_msg: 失败原因 (success=True 时可空)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    record = {
        "timestamp": timestamp,
        "question_id": question_id,
        "success": success,
        "error_msg": error_msg,
    }
    path = get_observer_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_daily_stats(date: Optional[str] = None) -> dict:
    """聚合每日 intake 统计

    Args:
        date: YYYY-MM-DD 格式, 默认 UTC 今日

    Returns:
        {"date": "2026-07-22", "total": 100, "success": 95, "errors": 5, "error_rate": 0.05}
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    path = get_observer_path()
    if not path.exists():
        return {"date": date, "total": 0, "success": 0, "errors": 0, "error_rate": 0.0}

    total = 0
    success = 0
    errors = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not d.get("timestamp", "").startswith(date):
                continue
            total += 1
            if d.get("success"):
                success += 1
            else:
                errors += 1

    error_rate = (errors / total) if total > 0 else 0.0
    return {
        "date": date,
        "total": total,
        "success": success,
        "errors": errors,
        "error_rate": error_rate,
    }


def check_rollback_threshold(
    threshold: float = DEFAULT_ROLLBACK_THRESHOLD,
    date: Optional[str] = None,
) -> bool:
    """检查每日 intake error_rate 是否触发 rollback

    Args:
        threshold: 触发阈值 (默认 5% = 0.05)
        date: 检查日期 (默认 UTC 今日)

    Returns:
        True if error_rate > threshold AND total >= 20 (样本量下限)
        False otherwise
    """
    stats = get_daily_stats(date=date)
    # 样本量下限 20: 避免 1/1 = 100% 误触发
    if stats["total"] < 20:
        return False
    return stats["error_rate"] > threshold


def clear_observer() -> None:
    """清空 observer JSONL (测试 / admin 用, 不暴露给 save_to_kb.py)"""
    path = get_observer_path()
    if path.exists():
        path.unlink()
