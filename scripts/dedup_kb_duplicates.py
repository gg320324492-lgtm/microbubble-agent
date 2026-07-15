"""KB 重复记录清理脚本 (2026-07-15 follow-up)

背景:
- 2026-07-15 用户截图: "知识引用" 渲染 3 张一模一样的卡
- 根因排查: DB 真实有 3 条记录 (id=38/86/135), title 完全一致
- 历史脏数据: source 列全 NULL + source_type='auto_expansion'
- 旧 dedup 逻辑依赖 source='qa-bench:qa_id' 查重, NULL 时失效 → 重复入库
- 修复 (commit 4f03e9c7 + 后续):
  1. create_from_auto_expansion 加 content_hash 兜底 (sha256(question|content[:500])[:32])
  2. search_semantic + _search_keyword_fallback 按 title 去重 (防御性兜底)
  3. ★ 本脚本: 清理历史已入库的重复记录

目标:
- 找出 title 完全一致的重复 KB 条目
- 保留一条 (quality_score 最高 + id 最大兜底), 软删除其他 (deleted_at=now())
- 同步: BM25 索引 + embedding 索引 (不影响 pgvector 因为软删除 filter 已加)

设计 (3 步范式, 与 fill_wechat_id_placeholders.py 一致):
  1. --scan: 列出所有 title 重复的 KB 记录 (按 title 分组 + 每组条数)
  2. --apply --confirm: 实际合并 (保留 best, 软删除其他)
  3. (无 --validate 步骤, 因为合并规则固定: best = max(quality_score) + tie-break max(id))

安全:
- 默认软删除 (deleted_at=now()) — 不真删, 可恢复
- 不修 content/tags/embedding — 物理删除影响 embedding 索引一致性
- 单事务包裹 (失败回滚)
- --confirm 二次确认门 (无此 flag DRY RUN)
- 排除: created_by IS NOT NULL (用户手动创建的不能合并, 哪怕 title 重)
- 排除: storage_mode != 'kb' (drive/private 文件不入 KB, 不参与合并)
- 排除: deleted_at IS NOT NULL (已软删除的不参与合并)

不做的事 (本次范围外):
- 不真删 (hard delete) — 软删除足够, 业务上 KB 30 天后会被 Celery 清
- 不合并 content/tags — 物理删除影响 embedding 一致性, 不值得冒险
- 不改 source/source_type — 即使是脏数据, 也是入库时的真实状态, 不动

用法:
  # 1. 先 scan 看清单 (无副作用)
  python scripts/dedup_kb_duplicates.py --scan

  # 2. 实际合并 (DRY RUN 默认, 必须 --confirm 才写库)
  python scripts/dedup_kb_duplicates.py --apply             # DRY RUN, 打印将做什么
  python scripts/dedup_kb_duplicates.py --apply --confirm   # 真合并
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))
# 容器内 app 包路径
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("dedup_kb_duplicates")


# ── 数据结构 ──────────────────────────────────────────────────────
@dataclass
class DuplicateGroup:
    """同 title 重复组 (按 title 分组, 含所有成员 id)"""
    title: str
    group: List["KbRecord"] = field(default_factory=list)


@dataclass
class KbRecord:
    """KB 记录 (用于 dedup 决策)"""
    id: int
    title: str
    quality_score: float
    created_at: datetime
    source: str
    source_type: str
    created_by: int | None  # None = 系统自动创建
    storage_mode: str


@dataclass
class MergePlan:
    """合并计划: 保留 1 条 + 软删除 N-1 条"""
    group_title: str
    keep_id: int  # best = max(quality_score), 平局 id 最大
    delete_ids: List[int] = field(default_factory=list)


# ── 扫描 ──────────────────────────────────────────────────────────
async def scan_duplicates(session_factory) -> List[DuplicateGroup]:
    """扫描所有 title 重复的 KB 记录 (排除用户手动 + drive/private + 已软删)"""
    async with session_factory() as db:
        stmt = text("""
            SELECT id, title, quality_score, created_at, source, source_type,
                   created_by, storage_mode
            FROM knowledge
            WHERE deleted_at IS NULL
              AND storage_mode = 'kb'
              AND created_by IS NULL
              AND title IN (
                SELECT title FROM knowledge
                WHERE deleted_at IS NULL
                  AND storage_mode = 'kb'
                  AND created_by IS NULL
                GROUP BY title
                HAVING COUNT(*) > 1
              )
            ORDER BY title, id
        """)
        rows = (await db.execute(stmt)).fetchall()

    groups: dict[str, DuplicateGroup] = {}
    for row in rows:
        rec = KbRecord(
            id=row.id,
            title=row.title,
            quality_score=row.quality_score or 0.0,
            created_at=row.created_at,
            source=row.source or "",
            source_type=row.source_type or "",
            created_by=row.created_by,
            storage_mode=row.storage_mode,
        )
        if rec.title not in groups:
            groups[rec.title] = DuplicateGroup(title=rec.title)
        groups[rec.title].group.append(rec)

    return list(groups.values())


def make_merge_plan(group: DuplicateGroup) -> MergePlan:
    """生成合并计划: keep = max(quality_score), 平局 max(id)"""
    sorted_recs = sorted(
        group.group,
        key=lambda r: (r.quality_score, r.id),
        reverse=True,
    )
    best = sorted_recs[0]
    return MergePlan(
        group_title=group.title,
        keep_id=best.id,
        delete_ids=[r.id for r in sorted_recs[1:]],
    )


# ── 应用 ──────────────────────────────────────────────────────────
async def apply_merge_plans(
    session_factory,
    plans: List[MergePlan],
    dry_run: bool,
) -> tuple[int, int]:
    """应用合并计划: 软删除 (deleted_at=now()) non-best 记录

    Returns: (deleted_count, kept_count)
    """
    if not plans:
        return 0, 0

    deleted_count = 0
    kept_count = 0
    async with session_factory() as db:
        try:
            for plan in plans:
                kept_count += 1
                if not plan.delete_ids:
                    continue
                if dry_run:
                    log.info(
                        f"[DRY RUN] title='{plan.group_title[:60]}' "
                        f"keep_id={plan.keep_id} delete_ids={plan.delete_ids}"
                    )
                    deleted_count += len(plan.delete_ids)
                    continue
                # 真合并: 软删除
                stmt = text("""
                    UPDATE knowledge
                    SET deleted_at = NOW()
                    WHERE id = ANY(:ids)
                      AND deleted_at IS NULL
                """).bindparams(
                    ids=[int(i) for i in plan.delete_ids],
                )
                result = await db.execute(stmt)
                deleted_count += result.rowcount or 0
                log.info(
                    f"[APPLY] title='{plan.group_title[:60]}' "
                    f"keep_id={plan.keep_id} 软删除 {result.rowcount} 条"
                )
            if not dry_run:
                await db.commit()
                log.info(f"[APPLY] 提交事务: 软删除 {deleted_count} 条, 保留 {kept_count} 条")
            else:
                log.info(f"[DRY RUN] 未提交事务 (缺 --confirm flag)")
        except Exception:
            await db.rollback()
            log.exception("[APPLY] 失败, 已回滚")
            raise
    return deleted_count, kept_count


# ── 入口 ──────────────────────────────────────────────────────────
async def main() -> int:
    p = argparse.ArgumentParser(
        description="KB 重复记录清理 (软删除历史重复入库, 保留 best)",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--scan",
        action="store_true",
        help="列出所有 title 重复的 KB 记录 (无副作用)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="实际合并 (默认 DRY RUN, 必须 --confirm 才写库)",
    )
    p.add_argument(
        "--confirm",
        action="store_true",
        help="apply 时必填: 二次确认确实要写库 (无此 flag DRY RUN)",
    )

    args = p.parse_args()

    # lazy import DB (避免 SKIP_DB_SETUP=1 时失败)
    from app.core.database import async_session as default_async_session

    if args.scan:
        groups = await scan_duplicates(default_async_session)
        if not groups:
            log.info("[SCAN] ✅ 没有发现 title 重复的 KB 记录")
            return 0
        log.info(f"[SCAN] 发现 {len(groups)} 组 title 重复:")
        total_dupes = 0
        for g in groups:
            ids = [r.id for r in g.group]
            total_dupes += len(g.group) - 1
            log.info(
                f"  - title='{g.title[:60]}' (id={ids}, "
                f"count={len(g.group)}, "
                f"source='{g.group[0].source or '(空)'}')"
            )
        log.info(
            f"[SCAN] 汇总: {len(groups)} 组重复, 涉及 {total_dupes} 条冗余记录\n"
            f"       实际合并: python scripts/dedup_kb_duplicates.py --apply --confirm"
        )
        return 0

    if args.apply:
        dry_run = not args.confirm
        if dry_run:
            log.warning(
                "[APPLY] ⚠️  DRY RUN 模式 (无 --confirm), 不会写库. "
                "实际合并请加 --confirm."
            )
        groups = await scan_duplicates(default_async_session)
        if not groups:
            log.info("[APPLY] ✅ 没有发现重复记录, 无需合并")
            return 0
        plans = [make_merge_plan(g) for g in groups]
        log.info(
            f"[APPLY] 准备合并 {len(plans)} 组: 保留 {len(plans)} 条, "
            f"软删除 {sum(len(p.delete_ids) for p in plans)} 条"
        )
        deleted, kept = await apply_merge_plans(
            default_async_session, plans, dry_run=dry_run,
        )
        if dry_run:
            log.info(
                f"[DRY RUN] 完成: 将软删除 {deleted} 条, 保留 {kept} 条\n"
                f"         实际执行: python scripts/dedup_kb_duplicates.py --apply --confirm"
            )
        else:
            log.info(
                f"[APPLY] ✅ 完成: 软删除 {deleted} 条, 保留 {kept} 条\n"
                f"        验证方法: 重新 --scan 期望 0 组重复"
            )
        return 0

    return 1  # 不应到达 (mutually_exclusive_group required)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))