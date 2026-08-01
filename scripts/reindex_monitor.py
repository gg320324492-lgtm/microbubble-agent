"""RAG 重建进度监控 (W101 P1 派工)

用法:
    python scripts/reindex_monitor.py --table knowledge
    python scripts/reindex_monitor.py --table knowledge --interval 5 --max-wait 600
    python scripts/reindex_monitor.py --table knowledge --retry --dry-run

监控 Redis 进度键 embedding_recompute:progress:{table}
由 app.services.embedding_recalc._update_progress 写入 (24h TTL)

输出:
    - 进度条 (done / total / percent)
    - 失败行清单 (从 celery 失败任务 / 失败日志)
    - 重试 CLI (--retry 模式打印 retry --row-ids)
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("reindex_monitor")


PROGRESS_KEY_PREFIX = "embedding_recompute:progress:"
FAILURE_KEY_PREFIX = "embedding_recompute:failures:"  # embedding_recalc 失败时写入 (兼容)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RAG 重建进度监控 + 失败重试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--table",
        type=str,
        required=True,
        help="监控表名 (例如 knowledge)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="轮询间隔 (秒, 默认 5)",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=600,
        help="最大等待时间 (秒, 默认 600)",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="监控完后打印失败行清单 + 重试 CLI (E12 防御: 失败重试非无限循环)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印当前快照, 不轮询",
    )
    return parser.parse_args()


def read_redis_snapshot(table: str) -> Optional[Dict]:
    """读 Redis 进度快照, 不存在返 None

    E10 防御: 进度键命名与 embedding_recalc.py:104 完全一致
    """
    try:
        import redis
    except ImportError:
        logger.warning("redis 库不可用, 无法读快照")
        return None

    try:
        from app.config import settings
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        data = client.get(f"{PROGRESS_KEY_PREFIX}{table}")
        client.close()
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"读 Redis 失败 (可能在 worktree 非 docker 环境): {e}")
    return None


def read_redis_failures(table: str) -> List[Dict]:
    """读失败行清单 (E12 防御: 失败重试读取失败列表, 不无限循环)"""
    try:
        import redis
        from app.config import settings
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        data = client.get(f"{FAILURE_KEY_PREFIX}{table}")
        client.close()
        if data:
            return json.loads(data)
    except Exception as e:
        logger.debug(f"读失败清单失败 (无则返回空): {e}")
    return []


def render_progress(snap: Dict) -> str:
    """渲染进度条"""
    table = snap.get("table", "?")
    done = snap.get("done", 0)
    total = snap.get("total", 0)
    percent = snap.get("percent", 0.0)

    if total == 0:
        return f"[{table}] 总数 0 (可能无数据, 或尚未启动)"

    bar_len = 30
    filled = int(bar_len * percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    return f"[{table}] [{bar}] {done}/{total} ({percent}%)"


def monitor_loop(table: str, interval: int, max_wait: int, retry: bool) -> int:
    """主轮询循环, 进度 100% 或超时退出

    E12 防御: 失败重试非无限循环 — 监控完打印 1 次 retry CLI, 手动执行
    """
    if not sys.stdin.isatty():
        # 非 tty 模式 (CI / 测试), 仍能跑
        pass

    elapsed = 0
    last_snap: Optional[Dict] = None
    while elapsed <= max_wait:
        snap = read_redis_snapshot(table)
        if snap is None:
            logger.info(f"[{table}] 无进度数据 (可能尚未启动 reindex_all)")
            if last_snap is None:
                # 启动后 30s 内无数据, 算启动失败
                if elapsed >= 30:
                    logger.error(f"[{table}] 30s 内无进度, 任务可能未启动")
                    return 1
        else:
            last_snap = snap
            logger.info(render_progress(snap))
            if snap.get("percent", 0.0) >= 100.0:
                logger.info(f"[{table}] 重建完成!")
                break

        if elapsed + interval > max_wait:
            break
        time.sleep(interval)
        elapsed += interval

    # 失败清单 + 重试 CLI
    if retry:
        failures = read_redis_failures(table)
        if failures:
            logger.warning(f"[{table}] 失败行数: {len(failures)}")
            row_ids = [f.get("row_id") for f in failures if f.get("row_id") is not None]
            logger.warning(f"重试 CLI: python scripts/reindex_all.py --table {table} --batch-size {min(50, len(row_ids))}")
            logger.warning(f"  (手动逐条重试: celery_app.send_task('app.services.embedding_recalc.recalc_one_embedding', args=['{table}', ROW_ID]))")
        else:
            logger.info(f"[{table}] 无失败记录")

    if last_snap is None:
        logger.warning(f"[{table}] 监控结束 (未观察到任何进度)")
        return 1 if elapsed >= max_wait else 0
    return 0


def main() -> int:
    args = parse_args()
    logger.info(f"=== RAG 重建监控 ===")
    logger.info(f"table: {args.table}, interval: {args.interval}s, max_wait: {args.max_wait}s")

    if args.dry_run:
        snap = read_redis_snapshot(args.table)
        if snap is None:
            logger.info(f"[{args.table}] 无快照 (key: {PROGRESS_KEY_PREFIX}{args.table})")
            return 0
        logger.info(render_progress(snap))
        return 0

    return monitor_loop(args.table, args.interval, args.max_wait, args.retry)


if __name__ == "__main__":
    sys.exit(main())
