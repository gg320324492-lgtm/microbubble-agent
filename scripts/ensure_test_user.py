"""确保测试账号 xiaoqi_testbot 在目标 DB 存在 — 幂等、可 dry-run。

2026-07-01 新增：把 e2e/脚本化测试从生产 admin (wangtianzhi) 物理隔离。

用法:
  # 默认连 settings.DATABASE_URL (生产 DB)
  python scripts/ensure_test_user.py

  # 干跑 — 只查不改
  python scripts/ensure_test_user.py --dry-run

  # 指定测试 DB
  python scripts/ensure_test_user.py --db-url "postgresql+asyncpg://postgres:password@localhost:5432/microbubble_test"

  # 自定义账号名/密码 (CI 用临时账号场景)
  python scripts/ensure_test_user.py --username ci_bot --password ci_pass_2026

退出码:
  0 = 成功 (新建或已存在且 role=admin, is_active=True)
  1 = 用户存在但 role/is_active 不合规（告警不强制改）
  2 = DB 连接失败

设计原则:
- 复用 app.core.security.get_password_hash (bcrypt) — 与 init_db.py / MemberService 一致
- 复用 app.services.member_service.MemberService.create_member — 走 service 层不走 raw SQL
- 不强制覆盖已存在的非合规账号 — "幂等存在即可" 语义，避免误改生产数据
- 不引入新依赖 — 仅用 sqlalchemy + app.core + app.services 已有的
"""
import argparse
import asyncio
import os
import sys

# 添加项目根目录到路径 (与 init_db.py 同模式, 让脚本独立运行)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import get_password_hash
from app.models.member import Member
from app.services.member_service import MemberService

DEFAULT_USERNAME = "xiaoqi_testbot"
DEFAULT_PASSWORD = "testbot_pass_2026"
DEFAULT_NAME = "测试小助手"
DEFAULT_ROLE = "admin"


def parse_args():
    p = argparse.ArgumentParser(description="确保测试账号 xiaoqi_testbot 存在（幂等）")
    p.add_argument("--db-url", default=None,
                   help="asyncpg DSN。默认 settings.DATABASE_URL (替换 postgresql:// → postgresql+asyncpg://)")
    p.add_argument("--username", default=DEFAULT_USERNAME,
                   help=f"测试账号 username (默认 {DEFAULT_USERNAME})")
    p.add_argument("--password", default=DEFAULT_PASSWORD,
                   help=f"测试账号 password (默认 {DEFAULT_PASSWORD}, 仅新建时用)")
    p.add_argument("--name", default=DEFAULT_NAME,
                   help=f"测试账号 display name (默认 {DEFAULT_NAME}, 仅新建时用)")
    p.add_argument("--dry-run", action="store_true",
                   help="只查询，不写入；用于安全预览")
    return p.parse_args()


def resolve_db_url(arg_url: str | None) -> str:
    """arg 优先；否则 settings.DATABASE_URL 转 asyncpg 协议。"""
    if arg_url:
        return arg_url
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def ensure(args) -> int:
    """主流程：查 → 校验 → (可选) 创建。返回退出码。"""
    db_url = resolve_db_url(args.db_url)
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as s:
            existing = (await s.execute(
                select(Member).where(Member.username == args.username)
            )).scalar_one_or_none()

            if existing:
                ok = existing.role == DEFAULT_ROLE and existing.is_active is True
                print(
                    f"[OK] 测试账号已存在: id={existing.id} username={existing.username} "
                    f"name={existing.name} role={existing.role} is_active={existing.is_active}"
                )
                if not ok:
                    print(
                        f"[WARN] 已存在账号 role/is_active 不合规 "
                        f"(期望 role={DEFAULT_ROLE}, is_active=True). "
                        f"如需修正请手动 SQL — 脚本不强制覆盖避免误改。",
                        file=sys.stderr,
                    )
                    return 1
                return 0

            # 不存在 → 检查 dry-run / 创建
            if args.dry_run:
                print(f"[DRY-RUN] 不存在账号 {args.username}，但 --dry-run 模式跳过创建")
                return 0

            svc = MemberService(s)
            member = await svc.create_member(
                name=args.name,
                username=args.username,
                password_hash=get_password_hash(args.password),
                role=DEFAULT_ROLE,
            )
            print(
                f"[CREATED] 测试账号: id={member.id} username={member.username} "
                f"name={member.name} role={member.role} is_active={member.is_active}"
            )
            return 0
    except Exception as e:
        print(f"[ERROR] DB 连接或查询失败: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()


def main():
    args = parse_args()
    exit_code = asyncio.run(ensure(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()