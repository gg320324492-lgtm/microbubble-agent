"""一次性 wechat_id placeholder 填充脚本（2026-07-03 PR6-P17 follow-up）

背景:
- PR6-P17 (alembic 057_wechat_id_not_null) 加了 wechat_id NOT NULL 约束
- 14/35 行原 NULL 已 backfill 为唯一 placeholder '__NULL_BACKFILL_<id>__'
  (id 数字保证唯一性, 避开 PR6-P14 ix_members_wechat_id_ci UNIQUE 冲突)
- 14 行成员清单 (2026-07-03 psql 验证):
  - 8 个真实成员: 董昊宇/李锐远/周之超/雒培媛(alumni)/孟祥琪/吴怡霏/蒋芦笛/刘子煜
  - 6 个测试账号: xiaoqi_testbot/Alice Drive Test/Bob Drive Test/Charlie Drive Test/pr1_temp_user/xiaoqi_testbot_2

目标:
- 用 admin 提供的真实 wechat_id 替换 14 个 placeholder
- 8 个真实成员 → 找企业微信后台拿真实 userid (e.g. 'WangTianZhi' 格式)
- 6 个测试账号 → 同样给测试用 wechat_id, 或用 purge_test_user_data.py 删除 (本次不做)

设计:
- 3 步范式 (与 migrate_kb_tags.py / migrate_kb_source_type.py 一致):
  1. --scan: 列出 14 行 placeholder + 打印 CSV 模板路径
  2. --validate <csv>: 验证 CSV 内容合法性 (id 存在 / wechat_id 非空 / 唯一)
  3. --apply --mapping <csv> --confirm: 实际 UPDATE placeholder → 真实 wechat_id

安全:
- 单事务包裹 (失败回滚)
- 占位符 UPDATE 只改 placeholder 行 (防御性 WHERE: wechat_id LIKE '__NULL_BACKFILL_%'__)
- PR6-P14 UNIQUE INDEX 兜底 (LOWER(wechat_id) 重复 → IntegrityError → 整批 abort)

不做的事 (本次范围外):
- 不删测试账号 (admin 手工决定)
- 不改其他列 (角色/密码/research_area)
- 不调用 wechat API 自动同步 (admin 手工从企业微信后台复制)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))
# 容器内 app 包路径
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("fill_wechat_id_placeholders")


# ── 规则常量 ──────────────────────────────────────────────────────
PLACEHOLDER_PREFIX = "__NULL_BACKFILL_"
PLACEHOLDER_SUFFIX = "__"
# CSV 必须含 2 列: id, wechat_id
CSV_REQUIRED_COLUMNS = ["id", "wechat_id"]


# ── 数据结构 ──────────────────────────────────────────────────────
@dataclass
class PlaceholderMember:
    """placeholder 成员 (id + 当前 placeholder wechat_id + 名字)"""
    id: int
    username: str
    name: str
    is_active: bool
    current_placeholder: str  # e.g. __NULL_BACKFILL_8__


@dataclass
class CsvMapping:
    """CSV 解析结果 (admin 提供 id → wechat_id 映射)"""
    id: int
    new_wechat_id: str  # admin 提供的真实值


@dataclass
class ApplyReport:
    """apply 步骤结果"""
    total_matched: int
    total_updated: int
    total_skipped: int  # CSV 有但 placeholder 里没 (id 不在 placeholder 列表)
    total_errors: int


# ── Step 1: scan ────────────────────────────────────────────────────
async def scan_placeholders(engine) -> list[PlaceholderMember]:
    """扫描所有 wechat_id LIKE '__NULL_BACKFILL_%' 的成员"""
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        result = await db.execute(
            text(
                "SELECT id, username, name, is_active, wechat_id FROM members "
                "WHERE wechat_id LIKE :pattern "
                "ORDER BY id"
            ),
            {"pattern": f"{PLACEHOLDER_PREFIX}%"},
        )
        rows = result.all()
        return [
            PlaceholderMember(
                id=row.id,
                username=row.username,
                name=row.name,
                is_active=row.is_active,
                current_placeholder=row.wechat_id,
            )
            for row in rows
        ]


def print_scan_table(members: list[PlaceholderMember], limit: int = 30) -> None:
    """打印 placeholder 成员清单 + CSV 模板提示"""
    print("\n=== Placeholder 成员清单 ===")
    if not members:
        print("  (无 placeholder 成员, 可能 PR6-P17 已完成清理)")
        return
    print(f"  总数: {len(members)} 行\n")
    print(f"  {'id':<6}{'username':<22}{'name':<12}{'active':<8}{'placeholder'}")
    print(f"  {'-'*6}{'-'*22}{'-'*12}{'-'*8}{'-'*30}")
    for m in members[:limit]:
        active = "✓" if m.is_active else "✗"
        print(
            f"  {m.id:<6}{m.username:<22}{m.name:<12}{active:<8}{m.current_placeholder}"
        )
    if len(members) > limit:
        print(f"  ... (省略 {len(members) - limit} 行)")
    print(
        "\n=== 提示 ==="
        f"\n  请创建 CSV 文件 (2 列: id, wechat_id) 提供真实 wechat_id"
        f"\n  例:"
        f"\n    id,wechat_id"
        f"\n    8,DongHaoYu"
        f"\n    17,LiRuiYuan"
        f"\n    ..."
        f"\n  然后: python fill_wechat_id_placeholders.py --validate mapping.csv"
        f"\n       python fill_wechat_id_placeholders.py --apply --mapping mapping.csv --confirm"
    )


# ── Step 2: validate ────────────────────────────────────────────────
def parse_csv_mapping(csv_path: str) -> tuple[list[CsvMapping], list[str]]:
    """解析 CSV 文件 → (mappings, errors)

    CSV 格式: id,wechat_id (必需列, 表头)
    返回 (mappings, errors) — errors 为空表示 CSV 合法
    """
    errors = []
    mappings = []

    path = Path(csv_path)
    if not path.exists():
        return [], [f"CSV 文件不存在: {csv_path}"]

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # 检查必需列
        if not all(col in reader.fieldnames for col in CSV_REQUIRED_COLUMNS):
            return [], [
                f"CSV 缺少必需列 {CSV_REQUIRED_COLUMNS}, 实际列: {reader.fieldnames}"
            ]
        for row_num, row in enumerate(reader, start=2):  # row 1 is header
            id_str = row.get("id", "").strip()
            wechat_id = row.get("wechat_id", "").strip()
            if not id_str or not wechat_id:
                errors.append(f"  row {row_num}: id 或 wechat_id 为空 (id={id_str!r}, wechat_id={wechat_id!r})")
                continue
            try:
                member_id = int(id_str)
            except ValueError:
                errors.append(f"  row {row_num}: id 非整数 ({id_str!r})")
                continue
            mappings.append(CsvMapping(id=member_id, new_wechat_id=wechat_id))

    # 检查 CSV 内部 wechat_id 重复 (避免 admin 误填同 id 两次)
    seen_ids = {}
    for mapping in mappings:
        if mapping.id in seen_ids:
            errors.append(f"  CSV 内 id={mapping.id} 重复出现 ({seen_ids[mapping.id]} 和 {mapping.new_wechat_id})")
        else:
            seen_ids[mapping.id] = mapping.new_wechat_id

    return mappings, errors


async def validate_mapping(
    engine,
    mappings: list[CsvMapping],
    placeholders: list[PlaceholderMember],
) -> list[str]:
    """验证 CSV mapping 是否能安全 apply

    检查项:
    1. 每个 id 在 placeholder 列表里 (否则 skip)
    2. new_wechat_id 不为空 + 不以 placeholder 前缀开头 (防 admin 误填)
    3. new_wechat_id 不与 placeholder 里其他 wechat_id LOWER 冲突 (PR6-P14 UNIQUE)
    4. new_wechat_id 不与 DB 已存在的 wechat_id LOWER 冲突 (PR6-P14 UNIQUE)
    """

    errors = []
    placeholder_ids = {m.id: m for m in placeholders}
    new_wechat_ids_lower = {}  # new_wechat_id.lower() → mapping.id (用于 CSV 内部查重)

    for mapping in mappings:
        # 检查 1: id 在 placeholder 列表
        if mapping.id not in placeholder_ids:
            errors.append(
                f"  id={mapping.id} 不在 placeholder 列表里 (已填过或 ID 不存在), skip"
            )
            continue

        # 检查 2: new_wechat_id 合法性
        if not mapping.new_wechat_id or mapping.new_wechat_id.strip() == "":
            errors.append(f"  id={mapping.id}: wechat_id 为空")
            continue
        if mapping.new_wechat_id.startswith(PLACEHOLDER_PREFIX):
            errors.append(
                f"  id={mapping.id}: wechat_id 仍是 placeholder ({mapping.new_wechat_id}), "
                f"无法替换为自身"
            )
            continue

        # 检查 3: CSV 内部 wechat_id LOWER 唯一
        wechat_id_lower = mapping.new_wechat_id.lower()
        if wechat_id_lower in new_wechat_ids_lower:
            errors.append(
                f"  id={mapping.id}: wechat_id LOWER({wechat_id_lower}) 与 id={new_wechat_ids_lower[wechat_id_lower]} 冲突"
            )
        else:
            new_wechat_ids_lower[wechat_id_lower] = mapping.id

    # 检查 4: DB 已存在 wechat_id LOWER 冲突 (PR6-P14 UNIQUE)
    if new_wechat_ids_lower:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as db:
            placeholders_lower = [m.current_placeholder.lower() for m in placeholders]
            # 批量查 DB: 所有 new_wechat_ids_lower 是否已被占用
            result = await db.execute(
                text(
                    "SELECT id, username, wechat_id FROM members "
                    "WHERE LOWER(wechat_id) = ANY(:wechat_ids) "
                    "AND id != ALL(:placeholder_ids)"  # 排除 placeholder 本身
                ),
                {
                    "wechat_ids": list(new_wechat_ids_lower.keys()),
                    "placeholder_ids": list(placeholder_ids.keys()),
                },
            )
            existing_rows = result.all()
            for row in existing_rows:
                # 2026-07-03 P0-4 fix: 不要引用外层 closure 的 mapping 变量
                # (loop 结束时 mapping 是最后一条), 通过 row.wechat_id 反查
                # new_wechat_ids_lower dict 找对应 CSV 行.
                csv_mapping_id = new_wechat_ids_lower.get(row.wechat_id.lower(), "?")
                errors.append(
                    f"  id={csv_mapping_id}: new_wechat_id LOWER({row.wechat_id.lower()}) "
                    f"与 DB 已存在 id={row.id} 的 wechat_id='{row.wechat_id}' 冲突"
                )

    return errors


# ── Step 3: apply ───────────────────────────────────────────────────
async def apply_fill_placeholders(
    engine,
    mappings: list[CsvMapping],
    placeholders: list[PlaceholderMember],
) -> ApplyReport:
    """执行 UPDATE (单事务包裹)

    只改 placeholder 行 (防御性 WHERE: wechat_id LIKE '__NULL_BACKFILL_%'__)
    其他 placeholder 不在 CSV 里 → skip (id 不在 mappings)
    """
    placeholder_ids = {m.id for m in placeholders}
    mapping_by_id = {m.id: m for m in mappings}

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    report = ApplyReport(
        total_matched=len(mappings),
        total_updated=0,
        total_skipped=0,
        total_errors=0,
    )

    async with async_session() as db:
        try:
            for mapping in mappings:
                if mapping.id not in placeholder_ids:
                    log.info(f"  [SKIP] id={mapping.id} 不在 placeholder 列表")
                    report.total_skipped += 1
                    continue
                # 防御性 UPDATE (WHERE 包含 placeholder 检查, 防 admin 误填非 placeholder 的 id)
                result = await db.execute(
                    text(
                        "UPDATE members SET wechat_id = :new_wechat_id "
                        "WHERE id = :id "
                        "AND wechat_id LIKE :placeholder_prefix_pattern"
                    ),
                    {
                        "new_wechat_id": mapping.new_wechat_id,
                        "id": mapping.id,
                        "placeholder_prefix_pattern": f"{PLACEHOLDER_PREFIX}%",
                    },
                )
                if result.rowcount == 0:
                    log.warning(
                        f"  [SKIP] id={mapping.id} UPDATE 0 行 (并发修改或非 placeholder)"
                    )
                    report.total_skipped += 1
                else:
                    log.info(
                        f"  [OK] id={mapping.id} ({placeholder_ids and mapping.id in placeholder_ids and 'placeholder 行'}) → {mapping.new_wechat_id}"
                    )
                    report.total_updated += 1
            await db.commit()
        except Exception as e:
            await db.rollback()
            log.error(f"[APPLY] ❌ 事务失败回滚: {e}", exc_info=True)
            report.total_errors += 1
            raise

    return report


# ── 主流程 ──────────────────────────────────────────────────────
async def main() -> int:
    p = argparse.ArgumentParser(
        description="PR6-P17 follow-up: 把 14 行 wechat_id placeholder 替换为真实值",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--scan",
        action="store_true",
        help="列出所有 placeholder 成员 + 打印 CSV 模板路径",
    )
    mode.add_argument(
        "--validate",
        metavar="CSV",
        help="验证 CSV 文件合法性 (id 存在 + wechat_id 非空 + UNIQUE 不冲突)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="实际 UPDATE placeholder → 真实 wechat_id (要求 --mapping + --confirm)",
    )
    p.add_argument(
        "--mapping",
        metavar="CSV",
        help="apply 时必填: CSV 文件路径 (id,wechat_id 两列)",
    )
    p.add_argument(
        "--confirm",
        action="store_true",
        help="apply 时必填: 二次确认确实要写库 (无此 flag DRY RUN)",
    )
    p.add_argument("--limit", type=int, default=30, help="scan 时打印前 N 条 (默认 30)")
    args = p.parse_args()

    from sqlalchemy.ext.asyncio import create_async_engine
    from app.config import settings

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )

    try:
        if args.scan:
            log.info("[SCAN] 模式: 只查询不写库")
            members = await scan_placeholders(engine)
            print_scan_table(members, args.limit)
            return 0

        # validate / apply 都需要先 scan 拿 placeholder 列表
        log.info("[PRE-SCAN] 拿 placeholder 列表")
        members = await scan_placeholders(engine)
        log.info(f"  placeholder 总数: {len(members)} 行")

        if args.validate:
            log.info(f"[VALIDATE] 模式: 验证 CSV {args.validate}")
            mappings, parse_errors = parse_csv_mapping(args.validate)
            if parse_errors:
                log.error("[VALIDATE] ❌ CSV 解析失败:")
                for err in parse_errors:
                    log.error(err)
                return 1
            log.info(f"  CSV 解析成功: {len(mappings)} 条 mapping")
            validate_errors = await validate_mapping(engine, mappings, members)
            if validate_errors:
                log.error("[VALIDATE] ❌ 验证失败:")
                for err in validate_errors:
                    log.error(err)
                return 1
            log.info("[VALIDATE] ✅ CSV 合法: 所有 mapping 可安全 apply")
            return 0

        # ── apply 流程 ──
        log.info("[APPLY] 模式: 实际写库")
        if not args.mapping:
            log.error("[APPLY] ❌ 必须传 --mapping <csv>")
            return 1
        if not args.confirm:
            log.warning(
                "⚠ [DRY RUN] --apply 但未传 --confirm, 拒绝写库. "
                "如确认要执行请加 --confirm 参数."
            )
            mappings, parse_errors = parse_csv_mapping(args.mapping)
            if parse_errors:
                log.error("[APPLY] ❌ CSV 解析失败:")
                for err in parse_errors:
                    log.error(err)
                return 1
            validate_errors = await validate_mapping(engine, mappings, members)
            if validate_errors:
                log.error("[APPLY] ❌ CSV 验证失败:")
                for err in validate_errors:
                    log.error(err)
            print_scan_table(members, args.limit)
            return 1

        # ── 真正写库 ──
        mappings, parse_errors = parse_csv_mapping(args.mapping)
        if parse_errors:
            log.error("[APPLY] ❌ CSV 解析失败:")
            for err in parse_errors:
                log.error(err)
            return 1
        validate_errors = await validate_mapping(engine, mappings, members)
        if validate_errors:
            log.error("[APPLY] ❌ CSV 验证失败:")
            for err in validate_errors:
                log.error(err)
            return 1

        log.info(f"[APPLY] 开始写库: {len(mappings)} 条 mapping")
        report = await apply_fill_placeholders(engine, mappings, members)
        log.info(
            f"[APPLY] ✅ 完成: 写库 {report.total_updated} 条, skip {report.total_skipped} 条"
        )
        log.info(
            "[APPLY] 验证方法: 重新 --scan 期望 0 行 placeholder (幂等)"
        )
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)