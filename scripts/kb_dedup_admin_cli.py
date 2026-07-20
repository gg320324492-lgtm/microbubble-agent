"""KB duplicate administration CLI.

This command provides a conservative three-step workflow for duplicate KB
records:

    python scripts/kb_dedup_admin_cli.py --scan
    python scripts/kb_dedup_admin_cli.py --validate
    python scripts/kb_dedup_admin_cli.py --apply --confirm

Only active, system-created KB records are candidates.  A duplicate is an
exact ``(title, SHA-256(content))`` match.  Apply soft-deletes all but the
best record (highest quality score, then newest id), and never hard-deletes
content.  ``--confirm`` is required for every write.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kb_dedup_admin_cli")


@dataclass(frozen=True)
class KbRecord:
    """The fields needed to make a safe duplicate decision."""

    id: int
    title: str
    content_hash: str
    quality_score: float = 0.0
    created_at: datetime | None = None
    created_by: int | None = None
    storage_mode: str = "kb"


@dataclass
class DuplicateGroup:
    """Records sharing both title and content hash."""

    title: str
    content_hash: str
    records: list[KbRecord] = field(default_factory=list)

    @property
    def keep(self) -> KbRecord:
        return max(self.records, key=lambda row: (row.quality_score, row.id))

    @property
    def delete_ids(self) -> list[int]:
        keep_id = self.keep.id
        return [row.id for row in self.records if row.id != keep_id]


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome for a cleanup plan."""

    valid: bool
    groups: int
    delete_ids: tuple[int, ...]
    errors: tuple[str, ...] = ()


@dataclass
class CleanupPlan:
    """A scan plus its validated, write-ready decisions."""

    groups: list[DuplicateGroup] = field(default_factory=list)
    validation: ValidationResult | None = None

    @property
    def delete_ids(self) -> list[int]:
        return [item for group in self.groups for item in group.delete_ids]


def content_hash(content: str | None) -> str:
    """Return a stable full-content SHA-256 hash."""

    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def group_duplicate_records(records: Iterable[KbRecord]) -> list[DuplicateGroup]:
    """Group active KB records by exact title and content hash.

    Records created by a user or belonging to another storage mode are not
    eligible for administrative cleanup.  They remain visible to the caller
    so this function is safe to use with a broad database query.
    """

    grouped: dict[tuple[str, str], list[KbRecord]] = {}
    for record in records:
        if record.storage_mode != "kb" or record.created_by is not None:
            continue
        key = (record.title.strip(), record.content_hash)
        grouped.setdefault(key, []).append(record)

    return [
        DuplicateGroup(title=title, content_hash=digest, records=sorted(rows, key=lambda r: r.id))
        for (title, digest), rows in sorted(grouped.items(), key=lambda item: item[0])
        if len(rows) > 1
    ]


def validate_cleanup_plan(plan: CleanupPlan | Sequence[DuplicateGroup]) -> ValidationResult:
    """Validate that every delete target is a non-keeper duplicate.

    Validation is intentionally pure so it can be run in CI and in a dry run
    without a database connection.
    """

    groups = list(plan.groups if isinstance(plan, CleanupPlan) else plan)
    errors: list[str] = []
    delete_ids: list[int] = []
    seen_ids: set[int] = set()

    for group in groups:
        if len(group.records) < 2:
            errors.append(f"title={group.title!r}: duplicate group has fewer than two records")
            continue
        if any(record.storage_mode != "kb" for record in group.records):
            errors.append(f"title={group.title!r}: non-KB record in cleanup group")
        if any(record.created_by is not None for record in group.records):
            errors.append(f"title={group.title!r}: user-created record in cleanup group")
        if len({record.content_hash for record in group.records}) != 1:
            errors.append(f"title={group.title!r}: content hash mismatch")
        keep_id = group.keep.id
        for record_id in group.delete_ids:
            if record_id == keep_id:
                errors.append(f"title={group.title!r}: keeper appears in delete targets")
            if record_id in seen_ids:
                errors.append(f"record id={record_id} appears in multiple cleanup groups")
            seen_ids.add(record_id)
            delete_ids.append(record_id)

    return ValidationResult(
        valid=not errors,
        groups=len(groups),
        delete_ids=tuple(sorted(delete_ids)),
        errors=tuple(errors),
    )


async def scan_duplicates(session_factory) -> CleanupPlan:
    """Read active system KB rows and build a duplicate cleanup plan."""

    from sqlalchemy import select
    from app.models.knowledge import Knowledge

    async with session_factory() as db:
        result = await db.execute(
            select(
                Knowledge.id,
                Knowledge.title,
                Knowledge.content,
                Knowledge.quality_score,
                Knowledge.created_at,
                Knowledge.created_by,
                Knowledge.storage_mode,
            ).where(Knowledge.deleted_at.is_(None))
        )
        records = [
            KbRecord(
                id=row.id,
                title=row.title or "",
                content_hash=content_hash(row.content),
                quality_score=row.quality_score or 0.0,
                created_at=row.created_at,
                created_by=row.created_by,
                storage_mode=row.storage_mode or "kb",
            )
            for row in result.all()
        ]

    plan = CleanupPlan(groups=group_duplicate_records(records))
    plan.validation = validate_cleanup_plan(plan)
    return plan


async def apply_cleanup(session_factory, plan: CleanupPlan, *, dry_run: bool) -> int:
    """Soft-delete duplicate rows in one transaction, or report a dry run."""

    validation = plan.validation or validate_cleanup_plan(plan)
    if not validation.valid:
        raise ValueError("cleanup plan validation failed: " + "; ".join(validation.errors))
    if not validation.delete_ids:
        return 0

    from sqlalchemy import text

    async with session_factory() as db:
        if dry_run:
            log.info("[DRY RUN] 将软删除 knowledge ids=%s", list(validation.delete_ids))
            return len(validation.delete_ids)
        try:
            result = await db.execute(
                text("""
                    UPDATE knowledge
                    SET deleted_at = NOW()
                    WHERE id = ANY(:ids)
                      AND deleted_at IS NULL
                      AND storage_mode = 'kb'
                      AND created_by IS NULL
                """).bindparams(ids=list(validation.delete_ids))
            )
            await db.commit()
            return result.rowcount or 0
        except Exception:
            await db.rollback()
            raise


def print_plan(plan: CleanupPlan, *, mode: str) -> None:
    validation = plan.validation or validate_cleanup_plan(plan)
    log.info("[%s] 重复组: %d, 计划软删除: %d", mode, len(plan.groups), len(validation.delete_ids))
    for group in plan.groups:
        log.info(
            "  title=%r hash=%s records=%s keep=%d delete=%s",
            group.title[:80],
            group.content_hash[:12],
            [row.id for row in group.records],
            group.keep.id,
            group.delete_ids,
        )
    if validation.errors:
        for error in validation.errors:
            log.error("  [INVALID] %s", error)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KB duplicate cleanup (scan/validate/apply)")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--scan", action="store_true", help="scan only; never writes")
    modes.add_argument("--validate", action="store_true", help="scan and validate cleanup targets")
    modes.add_argument("--apply", action="store_true", help="soft-delete validated duplicates")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="required with --apply; without it no database write is allowed",
    )
    return parser


async def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    from app.core.database import async_session

    plan = await scan_duplicates(async_session)
    mode = "SCAN" if args.scan else "VALIDATE" if args.validate else "APPLY"
    print_plan(plan, mode=mode)

    if args.scan:
        log.info("[SCAN] 完成, 未写库")
        return 0

    validation = plan.validation or validate_cleanup_plan(plan)
    if args.validate:
        if validation.valid:
            log.info("[VALIDATE] ✅ 清理目标合法, 未写库")
            return 0
        log.error("[VALIDATE] ❌ 清理目标不合法, 未写库")
        return 1

    if not args.confirm:
        log.warning("[APPLY] ⚠️ 缺少 --confirm, DRY RUN 且拒绝写库")
        await apply_cleanup(async_session, plan, dry_run=True)
        return 1
    if not validation.valid:
        log.error("[APPLY] ❌ 验证失败, 拒绝写库")
        return 1

    deleted = await apply_cleanup(async_session, plan, dry_run=False)
    log.info("[APPLY] ✅ 完成, 软删除 %d 条", deleted)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
