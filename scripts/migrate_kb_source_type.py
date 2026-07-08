"""一次性 KB 迁移脚本（2026-06-30 续集 4）

目标:
  把 knowledge 表中所有 title 以 '[拓展' 开头的卡片（179 张，dedup_titles 删 1 行后）
  的 source_type 字段从 NULL → 'auto_expansion'。

背景:
  - 这 179 张卡片是 LLM / 上游脚本自动入库的，title 前缀是课题内部科学索引编码
    ('拓展-{V/U/AA/S/Z}{数字}' 格式, 自动打标)
  - 但入库时未写 source_type='auto_expansion', 前端"✨ 自动拓展" chip (走
    source_type 过滤) 看不到这 179 张 → 用户视觉上"自动拓展是空白的"
  - 实际数据完整, 只是没被正确归类

与 migrate_kb_tags.py 关系:
  - 同一项目同一天的第二次 KB 清洁 (第一次删 4 条 + 第一次归并 tags)
  - 本次**只 UPDATE 不 DELETE**, 无需 JSON 备份, 但仍走 dry-run → --confirm
    二次确认门保持一致 UX

参考范式: scripts/migrate_kb_tags.py (282 行, --scan / --apply / --confirm 范式)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
# 容器内 app 包路径
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("migrate_kb_source_type")


# ── 规则常量 ──────────────────────────────────────────────────────
# 目标 source_type (与前端 chip "✨ 自动拓展" 走同一过滤)
TARGET_SOURCE_TYPE = "auto_expansion"
# 匹配模式: title 以 "[拓展" 开头 (含 '拓展-XX' / '拓展-AAXX' / '拓展-V01' 等所有变体)
# 严格相等前缀匹配 (不误伤 '某些拓展性' 这种正文)
# 2026-06-30 fix: SQL 层用 LIKE 'X%' (Knowledge.title.startswith("[拓展")) 而非
# regexp_match, 避开 raw string 转义 + PG regex 解析层级不一致的陷阱
SOURCE_TYPE_NULL = None  # 防御性 WHERE: 只改 NULL 的 (已 'auto_expansion' 的不动)


# ── 数据结构 ──────────────────────────────────────────────────────
@dataclass
class ReclassifyCandidate:
    id: int
    title: str
    category: str
    current_source_type: str  # 期望 'NULL' / ''
    new_source_type: str = TARGET_SOURCE_TYPE
    created_at: str | None = None


@dataclass
class ScanReport:
    total_matched: int = 0
    by_category: dict[str, int] = None  # type: ignore[assignment]
    candidates: list[ReclassifyCandidate] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.by_category is None:
            self.by_category = {}
        if self.candidates is None:
            self.candidates = []


# ── 数据访问层 ────────────────────────────────────────────────────
async def scan_kb(engine) -> ScanReport:
    """扫描所有 title 以 '[拓展' 开头的卡片 (source_type = NULL 防御性过滤)."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    Knowledge = await _ensure_kb_model()
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    report = ScanReport()

    async with sf() as db:
        # 防御性: 只查 source_type IS NULL (已 'auto_expansion' 的不重复改)
        # 2026-06-30 fix: 用 LIKE 'X%' (SQLAlchemy startswith) 而非 regex_match
        # 之前用 regexp_match 报 191 条, psql 报 180, 多 11 条误伤 (id=1/2/3/4/5/6/7/14/16/17/19)
        # 是 raw string 转义 + PG regex 解析层级不一致导致
        stmt = select(
            Knowledge.id,
            Knowledge.title,
            Knowledge.category,
            Knowledge.source_type,
            Knowledge.created_at,
        ).where(
            Knowledge.title.startswith("[拓展"),
            Knowledge.source_type.is_(None),
        )
        rows = (await db.execute(stmt)).all()
        report.total_matched = len(rows)
        for r in rows:
            cat = (r.category or "未分类")
            report.by_category[cat] = report.by_category.get(cat, 0) + 1
            report.candidates.append(
                ReclassifyCandidate(
                    id=r.id,
                    title=(r.title or "")[:100],
                    category=cat,
                    current_source_type=r.source_type or "NULL",
                    created_at=r.created_at.isoformat() if r.created_at else None,
                )
            )
    return report


async def apply_reclassify(engine, ids: list[int]) -> int:
    """单事务: UPDATE source_type='auto_expansion' WHERE id IN (...) AND source_type IS NULL.

    返回 (实际更新条数).
    防御性: 双重 WHERE (id + source_type IS NULL), 防止中途有人改 source_type
    """
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    if not ids:
        return 0

    Knowledge = await _ensure_kb_model()
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        try:
            result = await db.execute(
                update(Knowledge)
                .where(
                    Knowledge.id.in_(ids),
                    Knowledge.source_type.is_(None),  # 防御性
                )
                .values(source_type=TARGET_SOURCE_TYPE)
            )
            await db.commit()
            return result.rowcount or 0
        except Exception:
            await db.rollback()
            raise


# ── 输出层 ────────────────────────────────────────────────────────
def print_scan_table(report: ScanReport, limit: int) -> None:
    log.info("=" * 60)
    log.info("=== KB source_type 重分类 ===")
    log.info("  目标: 把 title 以 [拓展 开头的卡片 source_type NULL → %s", TARGET_SOURCE_TYPE)
    log.info("  范围: source_type IS NULL (防御性, 跳过已 'auto_expansion' 的)")
    log.info("")
    log.info("  总命中: %d 条", report.total_matched)
    if report.by_category:
        log.info("  按 category 分布:")
        for cat in sorted(report.by_category, key=report.by_category.get, reverse=True):
            log.info("    %-20s %d", cat, report.by_category[cat])
    log.info("")
    log.info("--- 候选清单 (前 %d 条) ---", limit)
    for c in report.candidates[:limit]:
        log.info(
            "  #%-5d %-20s %-10s | %s",
            c.id, c.title[:20], c.category, c.created_at or "?",
        )
    if len(report.candidates) > limit:
        log.info("  ... (共 %d 条, 仅预览前 %d)", len(report.candidates), limit)
    log.info("")
    log.info("=== 修改范围汇总 ===")
    log.info("  source_type 变更 (NULL → %s): %d 条", TARGET_SOURCE_TYPE, report.total_matched)
    log.info("  真实用户其他数据: 0 条改动 (本脚本不动)")


# ── 辅助 ──────────────────────────────────────────────────────────
async def _ensure_kb_model():
    from app.models.knowledge import Knowledge  # noqa: F401
    return Knowledge


# ── 主流程 ────────────────────────────────────────────────────────
async def main() -> int:
    p = argparse.ArgumentParser(
        description="KB 一次性迁移: 把 title 以 [拓展 开头的卡片 source_type 改写为 auto_expansion",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true", help="只查询不写库, 打印 plan 表")
    g.add_argument("--apply", action="store_true", help="实际写库, 要求显式 --confirm")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="apply 时必填: 二次确认确实要写库 (无此 flag 不写, DRY RUN)",
    )
    p.add_argument("--limit", type=int, default=20, help="打印预览前 N 条 (默认 20)")
    args = p.parse_args()

    from sqlalchemy.ext.asyncio import create_async_engine
    from app.config import settings

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )

    try:
        if args.scan:
            log.info("[SCAN] 模式: 只查询不写库")
            report = await scan_kb(engine)
            print_scan_table(report, args.limit)
            return 0

        # ── apply 流程 ──
        log.info("[APPLY] 模式: 实际写库")

        # 1) re-scan (防数据漂移)
        report = await scan_kb(engine)
        log.info("  re-scan 结果: %d 条候选", report.total_matched)

        # 2) 二次确认门
        if not args.confirm:
            log.warning(
                "⚠ [DRY RUN] --apply 但未传 --confirm, 拒绝写库. "
                "如确认要执行请加 --confirm 参数."
            )
            print_scan_table(report, args.limit)
            return 1

        # 3) 真正写库 (单事务, 失败回滚)
        ids = [c.id for c in report.candidates]
        n_updated = await apply_reclassify(engine, ids)
        log.info("[APPLY] ✅ 完成: source_type 改写 %d 条 (NULL → %s)", n_updated, TARGET_SOURCE_TYPE)
        log.info("[APPLY] 验证方法: 重新 --scan 期望 0 命中 (幂等)")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
