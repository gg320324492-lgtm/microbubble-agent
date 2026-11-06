"""确保某成员的登录账号存在且密码可用 — 幂等、可 dry-run。

用途：给已有成员（DB 里已有记录但 username/password_hash 为空）补齐登录账号；
     成员不存在时也可直接新建。

用法:
  # 默认连 settings.DATABASE_URL (生产 DB)
  python scripts/ensure_member_account.py --name 肖佐林 --username xiaozuolin --password 'xxx'

  # 干跑 — 只查不改
  python scripts/ensure_member_account.py --name 肖佐林 --username xiaozuolin --password 'xxx' --dry-run

退出码:
  0 = 成功 (账号可用: username 已落库 + 密码可 verify)
  1 = 参数/状态不合规 (用户名被他人占用 / 写库后回读不一致)
  2 = DB 连接或写入失败

设计原则:
- 复用 app.core.security.get_password_hash / verify_password (bcrypt) — 与生产登录同一套
- 复用 app.services.member_service.MemberService (走 service 层, 不写 raw SQL)
  → create_member 走 username 的 case-insensitive 唯一检查
  → update_member 走同样的唯一检查 (排除自己)
- 写入后**回读 DB** 复核 (类 20.220: 不信状态字段, 验副作用)
- **绝不 print 密码** (类 20.251 的密钥处置纪律) — 只报用户名与校验结论
- 幂等: 已存在且密码能 verify → no-op; 已存在但密码不匹配 → 覆盖更新
"""
import argparse
import asyncio
import os
import sys

# 添加项目根目录到路径 (与 ensure_test_user.py / init_db.py 同模式, 让脚本独立运行)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.member import Member
from app.services.member_service import MemberService


def parse_args():
    p = argparse.ArgumentParser(description="确保成员登录账号存在且密码可用（幂等）")
    p.add_argument("--name", required=True,
                   help="成员显示名 (如 肖佐林)")
    p.add_argument("--username", required=True,
                   help="登录用户名 (全小写; 登录走精确匹配 Member.username == 输入值)")
    p.add_argument("--password", required=True,
                   help="登录密码")
    p.add_argument("--role", default="member",
                   help="角色 (默认 member)")
    p.add_argument("--db-url", default=None,
                   help="asyncpg DSN。默认 settings.DATABASE_URL (替换 postgresql:// → postgresql+asyncpg://)")
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
    """主流程：查 → 补齐/新建 → 回读复核。返回退出码。"""
    db_url = resolve_db_url(args.db_url)
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as s:
            # 1) username 是否已被占用 (case-insensitive, 与 alembic 053 唯一索引一致)
            by_username = (await s.execute(
                select(Member).where(Member.username == args.username)
            )).scalars().first()

            # 2) 名字对应的成员 (肖佐林在 DB 里可能已有记录但没有账号)
            by_name = (await s.execute(
                select(Member).where(Member.name == args.name)
            )).scalars().first()

            if by_username and by_name and by_username.id != by_name.id:
                print(
                    f"[ERROR] username '{args.username}' 已被他人占用 "
                    f"(id={by_username.id}, name={by_username.name}), "
                    f"而 '{args.name}' 是 id={by_name.id}。请换用户名。",
                    file=sys.stderr,
                )
                return 1

            target = by_name or by_username

            if target is None:
                if args.dry_run:
                    print(f"[DRY-RUN] 成员 '{args.name}' 不存在, 将新建 "
                          f"username={args.username} role={args.role}")
                    return 0
                svc = MemberService(s)
                member = await svc.create_member(
                    name=args.name,
                    username=args.username,
                    password_hash=get_password_hash(args.password),
                    role=args.role,
                )
                action = "CREATED"
            else:
                # 已有成员 → 判断是"只缺账号"还是"账号完好"
                already_ok = (
                    target.username == args.username
                    and target.password_hash
                    and verify_password(args.password, target.password_hash)
                    and target.is_active is True
                )
                if already_ok:
                    print(
                        f"[OK] 账号已就绪: id={target.id} name={target.name} "
                        f"username={target.username} role={target.role} "
                        f"is_active={target.is_active} (密码校验通过, 无需改动)"
                    )
                    return 0
                if args.dry_run:
                    print(f"[DRY-RUN] 成员 id={target.id} name={target.name} "
                          f"username={target.username!r} → 将写入 "
                          f"username={args.username} + 新密码 hash "
                          f"(当前 role={target.role}, is_active={target.is_active})")
                    return 0
                svc = MemberService(s)
                member = await svc.update_member(
                    target.id,
                    username=args.username,
                    password_hash=get_password_hash(args.password),
                    role=args.role,
                )
                if member is None:
                    print(f"[ERROR] update_member 未找到 id={target.id}", file=sys.stderr)
                    return 1
                action = "UPDATED"

            # 3) 回读复核 (类 20.220: 验副作用, 不信返回值)
            reread = (await s.execute(
                select(Member).where(Member.id == member.id)
            )).scalar_one_or_none()
            ok = (
                reread is not None
                and reread.username == args.username
                and bool(reread.password_hash)
                and verify_password(args.password, reread.password_hash)
                and reread.is_active is True
            )
            if not ok:
                print(
                    f"[ERROR] 回读复核失败: id={member.id} "
                    f"username={getattr(reread, 'username', None)!r} "
                    f"has_pw={bool(getattr(reread, 'password_hash', None))} "
                    f"is_active={getattr(reread, 'is_active', None)}",
                    file=sys.stderr,
                )
                return 1

            print(
                f"[{action}] 账号可用: id={reread.id} name={reread.name} "
                f"username={reread.username} role={reread.role} "
                f"is_active={reread.is_active} (回读复核: 密码校验通过)"
            )
            return 0
    except Exception as e:
        print(f"[ERROR] DB 连接或写入失败: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()


def main():
    args = parse_args()
    exit_code = asyncio.run(ensure(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
