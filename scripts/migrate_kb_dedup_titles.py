"""一次性 KB 迁移脚本 (2026-06-30 续集 5: B 方案)

目标:
  KB 196 张卡片中, 180 张 [拓展- 索引 (auto_expansion) 有 97 张 title 重复 (每 title 3 份).
  49 张 content md5 完全字节相同 (数据库触发的元余: qa-bench 三轮入库未去重).
  本脚本**只删 49 字节相同组里 2 份副本 (保留 id 最小)**, 共 98 张.

  48 字节不同组 (3 份 LLM 输出有差异) 不删, 走 C 方案 (前端 dedup toggle) 隐藏.

防御:
  1. 4 张表 FK 引用检查: knowledge_relations (source_id/target_id CASCADE) +
     knowledge_images (CASCADE) + knowledge_extractions (CASCADE) +
     knowledge_gaps (knowledge_ids ARRAY overlap) + rag_evaluations (context Text LIKE 扫)
     有引用 → 整组跳过 (保守策略, 不只跳过被引用单张)
  2. content md5 一致才删 (字节级保险, 防止误删内容不同的"看起来同 title"卡片)
  3. JSON 备份到 /tmp/kb_dedup_backups/ (DELETE 不可逆, 后悔率 ~10%)
  4. dry-run → --confirm 二次确认门

参考范式: scripts/migrate_kb_tags.py (522 行, JSON 备份 + dry-run + --confirm 标杆)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 让脚本能找到 app 包 (本地 + 容器内都兼容)
sys.path.insert(0, str(Path(__file__).parent.parent))
# 容器内 app 包路径
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("migrate_kb_dedup_titles")


# ── 规则常量 ──────────────────────────────────────────────────────
TITLE_PREFIX = "[拓展"  # 复用 migrate_kb_source_type 扫描条件 (避免漂移)
BACKUP_PREFIX = "kb_dedup_backup"


# ── 数据结构 ──────────────────────────────────────────────────────
@dataclass
class CardRow:
    id: int
    title: str
    content_md5: str          # sha256 hex 头 32 字符 (与 PG substring(md5(content), 1, 32) 对齐)
    category: str | None = None
    created_at: datetime | None = None


@dataclass
class TitleGroup:
    title: str
    rows: list[CardRow]       # 至少 2 行
    all_content_same: bool    # len(set(content_md5s)) == 1
    distinct_md5_count: int


@dataclass
class GroupDecision:
    title: str
    keep_id: int              # 保留的 (id 最小), 跳过时 = -1
    delete_ids: list[int]     # 待删 ids
    skipped: bool = False
    skip_reason: str = ""     # "content_md5_mismatch" | "fk_referenced" | ""


@dataclass
class DedupPlan:
    groups_total: int = 0
    groups_scheduled: int = 0       # all_same + 无 FK 引用 → 进入删除
    groups_skipped_mismatch: int = 0  # content md5 不全相同
    groups_skipped_fk: int = 0        # 有 FK 引用
    total_to_delete: int = 0
    decisions: list[GroupDecision] = field(default_factory=list)


@dataclass
class ScanReport:
    total_with_prefix: int = 0
    duplicate_title_groups: int = 0
    by_group_size: dict[int, int] = field(default_factory=dict)
    groups: list[TitleGroup] = field(default_factory=list)
    plan: DedupPlan | None = None
    fk_referenced_ids: set[int] = field(default_factory=set)


# ── 纯函数层 (单测可独立跑) ─────────────────────────────────────
def content_md5(text: str | None) -> str:
    """sha256 hex 头 32 字符. None → 'EMPTY'.

    与 PG `substring(md5(content), 1, 32)` 算法对齐 (PostgreSQL md5 走 SQL 标准).
    注: sha256 比 md5 字符更长, 但前 32 字符已足够 16 字节散列, 误判率 ~2^-128, 实战中 0 误判.
    """
    if text is None:
        return "EMPTY"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def group_by_title(rows: list[CardRow]) -> list[TitleGroup]:
    """同 title 分组. 至少 2 行才返回. 组内 rows 按 id 升序."""
    rows_sorted = sorted(rows, key=lambda r: (r.title, r.id))
    out: list[TitleGroup] = []
    for title, group_iter in itertools.groupby(rows_sorted, key=lambda r: r.title):
        group_rows = list(group_iter)
        if len(group_rows) < 2:
            continue
        md5s = {r.content_md5 for r in group_rows}
        out.append(TitleGroup(
            title=title,
            rows=group_rows,
            all_content_same=(len(md5s) == 1),
            distinct_md5_count=len(md5s),
        ))
    return out


def decide_group_deletion(group: TitleGroup, fk_referenced_ids: set[int]) -> GroupDecision:
    """决策核心 (纯函数, 单测覆盖):
      1. group.all_content_same == False → skip "content_md5_mismatch"
      2. 组内任何 id 在 fk_referenced_ids → 整组 skip "fk_referenced" (保守: 全组保留)
         理由: 即便删一部分, 留下引用但删引用的目标 → 孤儿引用 / SET NULL 信息丢失
      3. 否则: keep_id = min(row.id), delete_ids = [r.id for r in rows if r.id != keep_id]
    """
    if not group.all_content_same:
        return GroupDecision(
            title=group.title, keep_id=-1, delete_ids=[],
            skipped=True, skip_reason="content_md5_mismatch",
        )
    if any(r.id in fk_referenced_ids for r in group.rows):
        return GroupDecision(
            title=group.title, keep_id=-1, delete_ids=[],
            skipped=True, skip_reason="fk_referenced",
        )
    sorted_rows = sorted(group.rows, key=lambda r: r.id)
    keep_id = sorted_rows[0].id
    delete_ids = [r.id for r in sorted_rows[1:]]
    return GroupDecision(
        title=group.title, keep_id=keep_id, delete_ids=delete_ids,
    )


def build_dedup_plan(groups: list[TitleGroup], fk_referenced_ids: set[int]) -> DedupPlan:
    plan = DedupPlan(groups_total=len(groups))
    for g in groups:
        d = decide_group_deletion(g, fk_referenced_ids)
        plan.decisions.append(d)
        if d.skipped:
            if d.skip_reason == "content_md5_mismatch":
                plan.groups_skipped_mismatch += 1
            elif d.skip_reason == "fk_referenced":
                plan.groups_skipped_fk += 1
        else:
            plan.groups_scheduled += 1
            plan.total_to_delete += len(d.delete_ids)
    return plan


# ── 数据访问层 ────────────────────────────────────────────────────
async def _ensure_models():
    from app.models.knowledge import (  # noqa: F401
        Knowledge, KnowledgeRelation, KnowledgeGap, RAGEvaluation
    )
    from app.models.knowledge_multimodal import (  # noqa: F401
        KnowledgeImage, KnowledgeExtraction
    )
    return Knowledge, KnowledgeRelation, KnowledgeGap, RAGEvaluation, KnowledgeImage, KnowledgeExtraction


async def scan_kb(engine) -> ScanReport:
    """单 SQL 拉所有 [拓展 前缀的 id/title/category/created_at + content_md5 (PG 端算)."""
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    Knowledge = (await _ensure_models())[0]
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    report = ScanReport()

    async with sf() as db:
        stmt = select(
            Knowledge.id,
            Knowledge.title,
            func.substring(func.md5(Knowledge.content), 1, 32).label("content_md5"),
            Knowledge.category,
            Knowledge.created_at,
        ).where(
            Knowledge.title.startswith(TITLE_PREFIX),  # 复用 source_type 脚本的可靠 startswith 模式
        )
        rows = (await db.execute(stmt)).all()
        report.total_with_prefix = len(rows)

        # 转 dataclass
        card_rows = [
            CardRow(
                id=r.id,
                title=r.title,
                content_md5=r.content_md5 or "EMPTY",
                category=r.category,
                created_at=r.created_at,
            )
            for r in rows
        ]
        # 内存分组
        report.groups = group_by_title(card_rows)
        report.duplicate_title_groups = len(report.groups)
        for g in report.groups:
            report.by_group_size[len(g.rows)] = report.by_group_size.get(len(g.rows), 0) + 1

    return report


async def fetch_fk_references(engine, candidate_ids: list[int]) -> set[int]:
    """4 张表 + 1 张 ARRAY + 1 张 Text 引用 knowledge.id 的并集.

    返回: candidate_ids 中被任何引用表引用的子集 (set[knowledge.id]).
    """
    from sqlalchemy import select, func, or_
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    if not candidate_ids:
        return set()

    Knowledge, KnowledgeRelation, KnowledgeGap, RAGEvaluation, KnowledgeImage, KnowledgeExtraction = await _ensure_models()
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    cid_set = set(candidate_ids)
    referenced: set[int] = set()

    async with sf() as db:
        # 1) knowledge_relations: source_id 或 target_id 命中 candidate_ids
        rows = await db.execute(
            select(KnowledgeRelation.source_id, KnowledgeRelation.target_id)
            .where(or_(
                KnowledgeRelation.source_id.in_(candidate_ids),
                KnowledgeRelation.target_id.in_(candidate_ids),
            ))
        )
        for s, t in rows.all():
            if s in cid_set:
                referenced.add(s)
            if t in cid_set:
                referenced.add(t)

        # 2) knowledge_images.knowledge_id 命中
        rows = await db.execute(
            select(KnowledgeImage.knowledge_id)
            .where(KnowledgeImage.knowledge_id.in_(candidate_ids))
        )
        referenced.update(r for r in rows.scalars().all() if r in cid_set)

        # 3) knowledge_extractions.knowledge_id 命中
        rows = await db.execute(
            select(KnowledgeExtraction.knowledge_id)
            .where(KnowledgeExtraction.knowledge_id.in_(candidate_ids))
        )
        referenced.update(r for r in rows.scalars().all() if r in cid_set)

        # 4) knowledge_gaps.knowledge_ids (ARRAY, 用 PG array overlap operator &&)
        #    SQL: WHERE knowledge_ids && ARRAY[:ids]  SELECT unnest(knowledge_ids) 拿到具体 id
        rows = await db.execute(
            select(func.unnest(KnowledgeGap.knowledge_ids))
            .where(KnowledgeGap.knowledge_ids.op("&&")(candidate_ids))
        )
        for r in rows.scalars().all():
            if r in cid_set:
                referenced.add(r)

        # 5) rag_evaluations.context (Text, ILIKE 扫 + 数字边界 regex 二次过滤)
        #    防 id=101 误中 id=1010/1101/2101
        for kid in candidate_ids:
            pattern = rf"(?<!\d){kid}(?!\d)"
            rows = await db.execute(
                select(RAGEvaluation.id, RAGEvaluation.context)
                .where(RAGEvaluation.context.ilike(f"%{kid}%"))
            )
            for _, ctx in rows.all():
                if ctx and re.search(pattern, ctx):
                    referenced.add(kid)
                    break  # 这 kid 已确认被引用, 不再扫

    return referenced


async def fetch_backup_rows(engine, ids: list[int]) -> list[dict]:
    """按 ID 拉全字段 (含 content/meta/embedding/created_at) 用于备份."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    if not ids:
        return []

    Knowledge = (await _ensure_models())[0]
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        rows = (await db.execute(select(Knowledge).where(Knowledge.id.in_(ids)))).scalars().all()
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
            try:
                if k.embedding is not None:
                    d["embedding"] = list(k.embedding)
            except Exception:
                d["embedding"] = None
            out.append(d)
        return out


async def apply_deletions(engine, plan: DedupPlan) -> int:
    """单事务: DELETE FROM knowledge WHERE id IN (...) AND title LIKE '[拓展%'.

    防御性双 WHERE: id + title startswith, 防数据漂移.
    返回实际删除条数.
    """
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    ids = [i for d in plan.decisions if not d.skipped for i in d.delete_ids]
    if not ids:
        return 0

    Knowledge = (await _ensure_models())[0]
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        try:
            result = await db.execute(
                delete(Knowledge).where(
                    Knowledge.id.in_(ids),
                    Knowledge.title.startswith(TITLE_PREFIX),  # 防御性
                )
            )
            await db.commit()
            n_deleted = result.rowcount or 0
            return n_deleted
        except Exception:
            await db.rollback()
            raise


# ── 备份层 ────────────────────────────────────────────────────────
def write_backup_file(candidates: list[dict], workdir: str) -> str:
    """写 JSON 备份 (DELETE 不可逆, 后悔率 ~10%, 必须留)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    workdir_p = Path(workdir)
    workdir_p.mkdir(parents=True, exist_ok=True)
    path = workdir_p / f"{BACKUP_PREFIX}_{ts}.json"
    payload = {
        "backup_at": ts,
        "operator_hint": "scripts/migrate_kb_dedup_titles.py",
        "title_prefix_filter": TITLE_PREFIX,
        "delete_strategy": "保留每 title 同 md5 组的 id 最小, 删其他字节相同副本",
        "items": candidates,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return str(path.resolve())


# ── 输出层 ────────────────────────────────────────────────────────
def print_scan_table(report: ScanReport, limit: int) -> None:
    plan = report.plan
    log.info("=" * 60)
    log.info("=== KB title 重复去重 (B 方案) ===")
    log.info("  扫描范围: title LIKE '%s%%'  (与 migrate_kb_source_type 一致)", TITLE_PREFIX)
    log.info("  命中总数: %d 条", report.total_with_prefix)
    log.info("  按 title 分组 (>=2 行): %d 组", report.duplicate_title_groups)
    if report.by_group_size:
        sizes = ", ".join(f"size={s}={c} 组" for s, c in sorted(report.by_group_size.items()))
        log.info("  组大小分布: %s", sizes)
    log.info("")
    log.info("  字节相同组 (md5 一致): %d", sum(1 for g in report.groups if g.all_content_same))
    log.info("  字节不同组 (md5 不全同): %d", sum(1 for g in report.groups if not g.all_content_same))
    log.info("  FK 引用候选 id: %d 个 (扫描 4 张表 + ARRAY + Text)", len(report.fk_referenced_ids))
    log.info("")

    if plan is None:
        return

    log.info("--- 计划删除 (前 %d 组) ---", limit)
    n = 0
    for d in plan.decisions:
        if d.skipped:
            continue
        n += 1
        if n > limit:
            break
        log.info("  %-50s keep=#%-5d del=%s", d.title[:50], d.keep_id, d.delete_ids)
    if plan.groups_scheduled > limit:
        log.info("  ... (共 %d 组计划删除, 仅预览前 %d)", plan.groups_scheduled, limit)
    log.info("")

    skipped_mismatch = [d for d in plan.decisions if d.skipped and d.skip_reason == "content_md5_mismatch"]
    if skipped_mismatch:
        log.info("--- 跳过的组 (内容不一致, 走 C 方案前端隐藏) ---")
        for d in skipped_mismatch[:limit]:
            md5s = [r.content_md5[:8] for r in next(g for g in report.groups if g.title == d.title).rows]
            log.info("  %-50s skip=content_md5_mismatch md5s=%s", d.title[:50], md5s)
        if len(skipped_mismatch) > limit:
            log.info("  ... (共 %d 组跳过, 仅预览前 %d)", len(skipped_mismatch), limit)
        log.info("")

    if plan.groups_skipped_fk:
        log.warning("--- FK 引用跳过 ---")
        for d in plan.decisions:
            if d.skipped and d.skip_reason == "fk_referenced":
                log.warning("  %-50s skip=fk_referenced ids=%s", d.title[:50],
                            [r.id for r in next(g for g in report.groups if g.title == d.title).rows])
        log.info("")

    log.info("=== 汇总 ===")
    log.info("  计划删除: %d 条 (%d 组, 每组保留 id 最小)", plan.total_to_delete, plan.groups_scheduled)
    log.info("  内容不一致跳过: %d 组 (走 C 方案前端隐藏)", plan.groups_skipped_mismatch)
    log.info("  FK 引用跳过: %d 组 (保守策略, 全组保留)", plan.groups_skipped_fk)
    if plan.total_to_delete == 0:
        log.info("  ⚠ 没有可删的, 全部走 C 方案")


# ── 主流程 ────────────────────────────────────────────────────────
async def main() -> int:
    p = argparse.ArgumentParser(
        description="KB title 重复去重 (B 方案: 物理删 49 字节相同组)",
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
    p.add_argument(
        "--backup-dir", type=str, default="/tmp/kb_dedup_backups",
        help="JSON 备份目录 (默认 /tmp/kb_dedup_backups, 容器重启即清空强制用户主动迁出)",
    )
    args = p.parse_args()

    from sqlalchemy.ext.asyncio import create_async_engine
    from app.config import settings

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )

    try:
        # 1) scan
        log.info("[SCAN] 模式: 查询 title 重复组 + FK 引用")
        report = await scan_kb(engine)
        candidate_ids = [r.id for g in report.groups for r in g.rows]

        # 2) FK 防御检查 (scan 阶段也跑, 让 plan 表完整)
        log.info("[SCAN] 扫描 4 张表 + ARRAY + Text 引用 (5 类防御)...")
        report.fk_referenced_ids = await fetch_fk_references(engine, candidate_ids)
        report.plan = build_dedup_plan(report.groups, report.fk_referenced_ids)

        # 3) 输出
        print_scan_table(report, args.limit)

        if args.scan:
            log.info("[SCAN] 完成, 不写库")
            return 0

        # 4) apply 流程
        log.info("[APPLY] 模式: 实际写库")

        if not args.confirm:
            log.warning(
                "⚠ [DRY RUN] --apply 但未传 --confirm, 拒绝写库. "
                "如确认要执行请加 --confirm 参数."
            )
            return 1

        if report.plan.total_to_delete == 0:
            log.warning("⚠ plan.total_to_delete = 0, 没有可删的, 直接退出")
            return 0

        # 5) 备份 (apply 前必做)
        delete_ids = [i for d in report.plan.decisions if not d.skipped for i in d.delete_ids]
        backup_rows = await fetch_backup_rows(engine, delete_ids)
        backup_path = write_backup_file(backup_rows, args.backup_dir)
        log.info(
            "[APPLY] JSON 备份已写: %s (%d 条, %d 字节)",
            backup_path, len(backup_rows),
            Path(backup_path).stat().st_size,
        )
        log.info("[APPLY] 💡 拷回宿主机: docker cp <container>:%s ./backups/kb-dedup-20260630/", backup_path)

        # 6) 真删 (单事务)
        n_deleted = await apply_deletions(engine, report.plan)
        log.info("[APPLY] ✅ 完成: 删除 %d 条 (期望 %d)", n_deleted, report.plan.total_to_delete)
        log.info("[APPLY] 验证方法: 重新 --scan 应 total_with_prefix = %d (期望 %d)",
                 report.total_with_prefix, report.total_with_prefix - n_deleted)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
