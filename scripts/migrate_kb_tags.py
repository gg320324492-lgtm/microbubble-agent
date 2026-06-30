"""一次性 KB 迁移脚本（2026-06-30）

目标:
  1. 把 source_type='auto_expansion'（自动对话生成）的 knowledge 条目
     中, tags 数组里凡是等于 "拓展"/"自动拓展"/"拓展测试" 的标签
     统一规范为单一的 "自动拓展", 保留其他不相关 tag, 去重.
  2. 同范围内 title 含 "测试" 子串的条目物理删除.
  3. 真实用户条目 (source_type != 'auto_expansion') 完全不动.

三段式执行 (必须按序):
  $ docker cp scripts/migrate_kb_tags.py microbubble-agent-app-1:/tmp/
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/migrate_kb_tags.py --scan
    <- 人工审核计划表 + 删除清单
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/migrate_kb_tags.py \\
        --apply --confirm
    <- --confirm 二次确认门, 不传则拒绝写库 (DRY RUN)

设计原则:
  - 删除不可逆 → 必须 dry-run + 二次确认 + JSON 文件备份
  - 真实用户数据不动 → source_type 防御性 WHERE 子句
  - 严格相等匹配 → 防止 micro拓展22 / method:拓展论 误伤
  - 幂等 → 二次跑 tag_change=0 + delete=0
  - 单事务包裹 → 失败整批回滚

参考范式: scripts/reprocess_meeting.py (9 步流程 + async engine + JSON 备份)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# 让脚本能找到 app 包 (本地 + 容器内都兼容)
# 容器内 /tmp/migrate_kb_tags.py → 需要把 /app 加进 path (本地运行时 parent.parent 是项目根)
sys.path.insert(0, str(Path(__file__).parent.parent))
# 容器内 app 包路径 (兼容本地没有 app/ 子目录的位置)
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("migrate_kb_tags")


# ── 规则常量 ──────────────────────────────────────────────────────
AUTO_SOURCE_TYPE = "auto_expansion"  # 自动对话生成 source_type
EXPANSION_TAGS = {"拓展", "自动拓展", "拓展测试"}  # 严格相等命中（仅在 auto_expansion 范围内）
NORMALIZED_TAG = "自动拓展"  # 归并目标
# 删除关键词 (子串匹配任一) — 中英双语都覆盖 ([自动拓展-S-TEST01] 这类测试样板)
TITLE_DELETE_KEYWORDS = ("测试", "TEST")  # tuple: 子串命中任一即删
TITLE_DELETE_KEYWORD_LEGACY = "测试"  # 仅用于备份 JSON metadata label (向后兼容)

# 输出
BACKUP_PREFIX = "kb_migrate_backup"


@dataclass
class TagChange:
    id: int
    title: str
    old_tags: list[str]
    new_tags: list[str]
    created_at: datetime | None = None


@dataclass
class DeleteCandidate:
    id: int
    title: str
    tags: list[str]
    source_type: str
    created_at: datetime | None = None


@dataclass
class ScanReport:
    auto_total: int = 0  # source_type='auto_expansion' 总条目数
    tag_changes: list[TagChange] = field(default_factory=list)  # 待 tag 变更
    delete_candidates: list[DeleteCandidate] = field(default_factory=list)  # 待删除
    real_user_with_expansion_tag_count: int = 0  # 真实用户条目带"拓展"tag（只展示）
    real_user_with_expansion_tag_sample: list[dict] = field(default_factory=list)


# ── 纯函数层（无副作用，单测可独立跑） ─────────────────────────
def normalize_tags(tags: list[str] | None) -> tuple[list[str], bool]:
    """严格相等归并 + 去重保序.

    规则:
      - tags 中凡是等于 "拓展/自动拓展/拓展测试" 的元素 → 替换为 "自动拓展"
      - 保留其他不相关 tag
      - 去重 (保首次出现顺序)
      - 输入 None 或空 list 透传

    返回 (new_tags, changed)
    """
    if not tags:
        return (list(tags) if tags else [], False)

    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        new_t = NORMALIZED_TAG if t in EXPANSION_TAGS else t
        if new_t not in seen:
            seen.add(new_t)
            out.append(new_t)
    changed = out != list(tags)  # Python list 相等比较保序
    return (out, changed)


def should_delete(title: str | None) -> bool:
    """title 子串包含任一关键字 → True (中英双语 + 自动生成的 [自动拓展-S-TEST##] 样板覆盖)"""
    if not title:
        return False
    return any(kw in title for kw in TITLE_DELETE_KEYWORDS)


# ── 数据访问层（async SQLAlchemy） ───────────────────────────────
async def _ensure_kb_model():
    """延迟导入避免脚本开头缺 DB 驱动时也加载失败."""
    from app.models.knowledge import Knowledge  # noqa: F401
    return Knowledge


async def scan_kb(engine) -> ScanReport:
    """全表扫描:
      1. WHERE source_type='auto_expansion' → 分两类（tag_changes / delete_candidates）
      2. WHERE source_type != 'auto_expansion' → 统计真实用户条目带"拓展"tag 数
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    Knowledge = await _ensure_kb_model()
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    report = ScanReport()

    async with sf() as db:
        # 1) 自动生成范围
        stmt_auto = select(
            Knowledge.id,
            Knowledge.title,
            Knowledge.tags,
            Knowledge.source_type,
            Knowledge.created_at,
        ).where(Knowledge.source_type == AUTO_SOURCE_TYPE)
        rows_auto = (await db.execute(stmt_auto)).all()
        report.auto_total = len(rows_auto)

        tag_distribution: dict[str, int] = {}
        for r in rows_auto:
            new_tags, changed = normalize_tags(list(r.tags) if r.tags else None)
            if changed:
                report.tag_changes.append(
                    TagChange(
                        id=r.id,
                        title=(r.title or "")[:100],
                        old_tags=list(r.tags) if r.tags else [],
                        new_tags=new_tags,
                        created_at=r.created_at,
                    )
                )
            # 顺便统计实际 tag 分布
            if r.tags:
                for t in r.tags:
                    tag_distribution[t] = tag_distribution.get(t, 0) + 1
            if should_delete(r.title):
                report.delete_candidates.append(
                    DeleteCandidate(
                        id=r.id,
                        title=(r.title or "")[:100],
                        tags=list(r.tags) if r.tags else [],
                        source_type=r.source_type or "",
                        created_at=r.created_at,
                    )
                )

        # 2) 真实用户范围（不在本次修改范围内，只为公示）
        stmt_real = select(Knowledge.id, Knowledge.title, Knowledge.tags).where(
            (Knowledge.source_type.is_(None) | (Knowledge.source_type != AUTO_SOURCE_TYPE))
            & Knowledge.tags.op("&&")(list(EXPANSION_TAGS))
        )
        rows_real = (await db.execute(stmt_real)).all()
        report.real_user_with_expansion_tag_count = len(rows_real)
        report.real_user_with_expansion_tag_sample = [
            {"id": r.id, "title": (r.title or "")[:80], "tags": list(r.tags)}
            for r in rows_real[:10]
        ]

        # 把 tag 分布附到 report 上（用 attribute 动态赋值，避开 dataclass 字段定义）
        report.tag_distribution = tag_distribution  # type: ignore[attr-defined]

    return report


async def fetch_backup_rows(engine, ids: list[int]) -> list[dict]:
    """按 ID 拉全字段用于备份（含 content/meta/embedding/created_at/updated_at）."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    if not ids:
        return []

    Knowledge = await _ensure_kb_model()
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        rows = (
            await db.execute(select(Knowledge).where(Knowledge.id.in_(ids)))
        ).scalars().all()
        out = []
        for k in rows:
            d = {
                "id": k.id,
                "title": k.title,
                "content": k.content,
                "category": k.category,
                "topic": k.topic,
                "tags": list(k.tags) if k.tags else None,
                "key_concepts": list(k.key_concepts) if k.key_concepts else None,
                "related_topics": list(k.related_topics) if k.related_topics else None,
                "source_type": k.source_type,
                "meta": k.meta,
                "analysis_status": k.analysis_status,
                "created_by": k.created_by,
                "created_at": k.created_at.isoformat() if k.created_at else None,
                "updated_at": k.updated_at.isoformat() if k.updated_at else None,
            }
            # embedding 列是 Vector(1024), 直接转 list[float]
            try:
                if k.embedding is not None:
                    d["embedding"] = list(k.embedding)
            except Exception:
                d["embedding"] = None
            out.append(d)
        return out


async def apply_changes(engine, tag_changes: list[TagChange], delete_ids: list[int]) -> tuple[int, int]:
    """单事务: 先 DELETE 后 UPDATE (仅 source_type='auto_expansion' 防御性 WHERE).

    返回 (实际更新条数, 实际删除条数).
    """
    from sqlalchemy import delete, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    Knowledge = await _ensure_kb_model()
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    n_updated = 0
    n_deleted = 0
    async with sf() as db:
        try:
            # 先 DELETE
            if delete_ids:
                result = await db.execute(
                    delete(Knowledge).where(
                        Knowledge.id.in_(delete_ids),
                        Knowledge.source_type == AUTO_SOURCE_TYPE,
                    )
                )
                n_deleted = result.rowcount or 0

            # 后 UPDATE（逐行）
            for c in tag_changes:
                # 跳过同时在 delete 列表里的（已被删除，无需更新）
                if c.id in set(delete_ids):
                    continue
                result = await db.execute(
                    update(Knowledge)
                    .where(
                        Knowledge.id == c.id,
                        Knowledge.source_type == AUTO_SOURCE_TYPE,  # 防御性
                    )
                    .values(tags=c.new_tags)
                )
                if (result.rowcount or 0) > 0:
                    n_updated += 1

            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return (n_updated, n_deleted)


# ── 备份层 ────────────────────────────────────────────────────────
def write_backup_file(candidates: list[dict], workdir: str) -> str:
    """写 JSON 备份. 返回备份文件绝对路径."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    workdir_p = Path(workdir)
    workdir_p.mkdir(parents=True, exist_ok=True)
    path = workdir_p / f"{BACKUP_PREFIX}_{ts}.json"
    payload = {
        "backup_at": ts,
        "operator_hint": "scripts/migrate_kb_tags.py",
        "delete_keywords": list(TITLE_DELETE_KEYWORDS),
        "tag_normalization": {old: NORMALIZED_TAG for old in sorted(EXPANSION_TAGS)},
        "items": candidates,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return str(path.resolve())


# ── 输出层 ────────────────────────────────────────────────────────
def print_scan_table(report: ScanReport, limit: int) -> None:
    auto_changed = len(report.tag_changes)
    auto_delete = len(report.delete_candidates)
    tag_distribution = getattr(report, "tag_distribution", {})

    log.info("=" * 60)
    log.info("=== 自动生成 (source_type='%s') 总览 ===", AUTO_SOURCE_TYPE)
    log.info("  总条目: %d", report.auto_total)
    log.info("  Tags 命中 EXPANSION_TAGS: %d 条", auto_changed)
    if tag_distribution:
        # 仅展示在 EXPANSION_TAGS 内的 tag 分布
        rel_dist = {k: v for k, v in tag_distribution.items() if k in EXPANSION_TAGS}
        if rel_dist:
            log.info("    分布: %s", rel_dist)
    log.info(
        "  删除候选 (title 含 %s 任一): %d 条",
        " OR ".join(repr(k) for k in TITLE_DELETE_KEYWORDS),
        auto_delete,
    )
    log.info("")

    log.info("--- Tags 归并预览 (前 %d 条) ---", limit)
    for c in report.tag_changes[:limit]:
        log.info(
            "  #%-5d %-30s  %r → %r  | %s",
            c.id,
            c.title[:30],
            c.old_tags,
            c.new_tags,
            c.created_at.strftime("%Y-%m-%d") if c.created_at else "?",
        )
    if len(report.tag_changes) > limit:
        log.info("  ... (共 %d 条, 仅预览前 %d)", len(report.tag_changes), limit)
    log.info("")

    log.info("--- 删除候选 (前 %d 条, 红色高亮) ---", limit)
    for d in report.delete_candidates[:limit]:
        log.warning(
            "  ⚠ #%-5d %-30s  tags=%r  src=%s  | %s",
            d.id,
            d.title[:30],
            d.tags,
            d.source_type,
            d.created_at.strftime("%Y-%m-%d") if d.created_at else "?",
        )
    if len(report.delete_candidates) > limit:
        log.warning("  ... (共 %d 条, 仅预览前 %d)", len(report.delete_candidates), limit)
    log.info("")

    log.info("--- 真实用户条目命中'拓展'tag (仅展示, 不动) ---")
    log.info(
        "  共 %d 条 (source_type != '%s') 带'拓展'类 tag → 本脚本不动",
        report.real_user_with_expansion_tag_count,
        AUTO_SOURCE_TYPE,
    )
    for s in report.real_user_with_expansion_tag_sample:
        log.info("  [%d] %s | tags=%r", s["id"], s["title"][:40], s["tags"])
    log.info("")

    log.info("=== 修改范围汇总 ===")
    log.info("  自动生成内 tags 变更: %d 条", auto_changed)
    log.info("  自动生成内删除: %d 条", auto_delete)
    log.info("  真实用户条目: 0 条改动 (本脚本不动)")


# ── 主流程 ────────────────────────────────────────────────────────
async def main() -> int:
    p = argparse.ArgumentParser(
        description="KB 一次性迁移: 自动生成条目 tags 归并 + title 测试删除",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true", help="只查询不写库, 打印 plan 表")
    g.add_argument("--apply", action="store_true", help="实际写库, 要求显式 --confirm")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="apply 时必填: 二次确认确实要写库 (无此 flag 不写)",
    )
    p.add_argument("--workdir", default="/tmp", help="备份输出目录 (默认 /tmp)")
    p.add_argument("--limit", type=int, default=20, help="打印预览前 N 条 (默认 20)")
    args = p.parse_args()

    # ── 准备 DB engine ──
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
        log.info(
            "  re-scan 结果: tags 变更 %d 条, 删除候选 %d 条",
            len(report.tag_changes),
            len(report.delete_candidates),
        )

        # 2) 二次确认门 (防误跑: 没 --confirm 直接拒, 不写库 + 不写备份)
        if not args.confirm:
            log.warning(
                "⚠ [DRY RUN] --apply 但未传 --confirm, 拒绝写库. "
                "如确认要执行请加 --confirm 参数.",
            )
            print_scan_table(report, args.limit)
            return 1

        # 3) 写备份 (含待删条目完整字段, 100% 可恢复)
        delete_ids = [d.id for d in report.delete_candidates]
        backup_rows = await fetch_backup_rows(engine, delete_ids)
        backup_path = write_backup_file(backup_rows, args.workdir)
        log.info(
            "  备份已写: %s (含 %d 条候选条目, 大小: 见 file)",
            backup_path,
            len(backup_rows),
        )

        # 4) 真正写库 (单事务, 失败回滚)
        n_updated, n_deleted = await apply_changes(
            engine,
            report.tag_changes,
            delete_ids,
        )
        log.info("[APPLY] ✅ 完成: tags 替换 %d 条, 删除 %d 条", n_updated, n_deleted)
        log.info("[APPLY] 备份文件保留: %s", backup_path)
        log.info("[APPLY] 💡 拷回宿主机: docker cp <container>:%s ./backups/", backup_path)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
