"""一键初始化 test DB — 合并 init_db + ensure_test_user 节省 2× import overhead.

W67 第 41 步 (Agent 21): qa-bench-ci.yml 之前用 3 个 docker exec 跑
init_db.py + alembic stamp head + ensure_test_user.py, 每次都重新加载 ~50+ 模型文件.
合并到 1 个 Python 进程可节省 ~7-8s × 2 = 14-16s.

Usage:
    python scripts/init_test_db_all.py [--with-alembic-stamp]

Args:
    --with-alembic-stamp: 同时跑 alembic stamp head (init_db.create_all 之后确保 _alembic_version 表也有)
"""
import argparse
import asyncio
import os
import sys

# Standalone script pattern (与 init_db.py / ensure_test_user.py 一致)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_init_db():
    """调 init_db.init_database() — 复用脚本内所有逻辑."""
    from scripts.init_db import init_database
    await init_database()


async def run_ensure_test_user():
    """调 ensure_test_user.main() — 走 service 层, 幂等."""
    from scripts.ensure_test_user import main as ensure_main
    # main() 内部调 asyncio.run, 不能再 await
    # 改成直接调 ensure 函数
    from scripts.ensure_test_user import parse_args, ensure
    args = parse_args([])
    return await ensure(args)


def run_alembic_stamp():
    """调 alembic stamp head — 同步, 较慢."""
    from alembic.config import Config
    from alembic import command
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    command.stamp(cfg, "head")
    print("[ALEMBIC] stamp head 完成")


async def main():
    parser = argparse.ArgumentParser(description="一键 init test DB")
    parser.add_argument("--with-alembic-stamp", action="store_true",
                        help="同时跑 alembic stamp head")
    args, _ = parser.parse_known_args()

    print("=" * 60)
    print("STEP 1/2: init_db (create_all + seed 24 members)")
    print("=" * 60)
    await run_init_db()

    if args.with_alembic_stamp:
        print("=" * 60)
        print("STEP 2/3: alembic stamp head")
        print("=" * 60)
        run_alembic_stamp()

    print("=" * 60)
    print("STEP 3/3 (or 2/2): ensure_test_user (xiaoqi_testbot)")
    print("=" * 60)
    exit_code = await run_ensure_test_user()
    if exit_code != 0:
        print(f"[WARN] ensure_test_user 返回非零: {exit_code}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
