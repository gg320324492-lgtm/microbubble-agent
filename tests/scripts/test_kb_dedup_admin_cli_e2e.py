"""KB dedup admin CLI E2E 测试 — 9ca41623 收官后补

覆盖 scripts/kb_dedup_admin_cli.py 的 3 段式流程:
- --scan: 读 DB 不写库
- --validate: 校验清理计划合法性, 不写库
- --apply (无 --confirm): DRY RUN, 不写库
- --apply --confirm: 真写库 (软删除)
- 幂等性: 重复 --apply --confirm 不重复删

E2E 真写库 (PR6-P18 范式), 用 tests/conftest.py 提供的 TestSession。
SKIP_DB_SETUP=1 时整体 skip (依赖真实 DB)。

跑法:
    docker exec -e TEST_DATABASE_URL=... microbubble-agent-app-1 bash -c 'cd /app && python -m pytest tests/scripts/test_kb_dedup_admin_cli_e2e.py -v --tb=short'

注意: 任务描述里给的 `docker exec -e SKIP_DB_SETUP=1` 命令无法跑 E2E 测试
(SKIP 模式下 db fixture 会 pytest.skip)。本测试必须非 SKIP 模式。
"""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# 让 scripts/ 可 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from scripts.kb_dedup_admin_cli import (  # noqa: E402
    CleanupPlan,
    DuplicateGroup,
    KbRecord,
    apply_cleanup,
    content_hash,
    group_duplicate_records,
    main,
    scan_duplicates,
    validate_cleanup_plan,
)

SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))

# E2E 测试必须用真 DB (PR6-P18 admin CLI 范式)
pytestmark = pytest.mark.skipif(
    SKIP_DB_SETUP,
    reason="E2E 测试需要真 DB (非 SKIP 模式)",
)


# ============================================================================
# E2E fixture helpers
# ============================================================================

async def _create_dup_record(db, *, title: str, content: str, quality: float = 0.5,
                              storage_mode: str = "kb", created_by=None) -> int:
    """插入一条 knowledge 记录, 返回 id"""
    from app.models.knowledge import Knowledge
    row = Knowledge(
        title=title,
        content=content,
        quality_score=quality,
        storage_mode=storage_mode,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row.id


async def _count_active_by_title(db, title: str) -> int:
    """统计 title=X 且 deleted_at IS NULL 的行数"""
    from sqlalchemy import select, func
    from app.models.knowledge import Knowledge
    stmt = select(func.count(Knowledge.id)).where(
        Knowledge.title == title,
        Knowledge.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def _count_soft_deleted_by_title(db, title: str) -> int:
    """统计 title=X 且 deleted_at IS NOT NULL 的行数"""
    from sqlalchemy import select, func
    from app.models.knowledge import Knowledge
    stmt = select(func.count(Knowledge.id)).where(
        Knowledge.title == title,
        Knowledge.deleted_at.is_not(None),
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


# ============================================================================
# Case 1: --scan 不写库 (验证 DB count 不变)
# ============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_scan_does_not_write_db(db):
    """scan_duplicates 只读 DB, 不修改 deleted_at"""
    # 准备: 创建 3 条相同 title+content 的 kb 记录 (凑成 1 个重复组)
    title = "E2E-scan-test-001"
    content = "scan 不写库测试内容"
    await _create_dup_record(db, title=title, content=content, quality=0.3)
    await _create_dup_record(db, title=title, content=content, quality=0.7)
    await _create_dup_record(db, title=title, content=content, quality=0.5)
    await db.commit()

    # 拍快照: 3 条都未软删
    active_before = await _count_active_by_title(db, title)
    deleted_before = await _count_soft_deleted_by_title(db, title)
    assert active_before == 3
    assert deleted_before == 0

    # 通过 main() 跑 --scan
    exit_code = await main(["--scan"])
    assert exit_code == 0

    # 再次校验: count 不变, 没被软删
    active_after = await _count_active_by_title(db, title)
    deleted_after = await _count_soft_deleted_by_title(db, title)
    assert active_after == 3, "scan 不应修改任何行 (active count 必须不变)"
    assert deleted_after == 0, "scan 不应软删任何行"


# ============================================================================
# Case 2: --validate 拒绝不合法输入 (空 group / < 2 records)
# 注: 纯函数 case, 不需要 DB. E2E 文件标记 skip 在 SKIP 模式下也跳过,
#     但 E2E 隔离 — 纯函数测试在 tests/test_kb_dedup_admin_cli.py
# ============================================================================


# ============================================================================
# Case 3: --apply 缺 --confirm 进 DRY RUN (不写库)
# ============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_apply_without_confirm_does_not_write_db(db):
    """--apply 不带 --confirm → 拒绝写库 (DRY RUN 模式 + exit 1)"""
    title = "E2E-dryrun-test-001"
    content = "dry run 不应写库"
    await _create_dup_record(db, title=title, content=content, quality=0.3)
    await _create_dup_record(db, title=title, content=content, quality=0.7)
    await db.commit()

    active_before = await _count_active_by_title(db, title)
    deleted_before = await _count_soft_deleted_by_title(db, title)
    assert active_before == 2
    assert deleted_before == 0

    # --apply 无 --confirm → exit 1 + DRY RUN (不写库)
    exit_code = await main(["--apply"])
    assert exit_code == 1, "无 --confirm 必须 exit 1 (拒绝写库)"

    active_after = await _count_active_by_title(db, title)
    deleted_after = await _count_soft_deleted_by_title(db, title)
    assert active_after == 2, "DRY RUN 不应修改 active count"
    assert deleted_after == 0, "DRY RUN 不应软删任何行"


# ============================================================================
# Case 4: --apply --confirm 真写库 (3 段式完整流程)
# ============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_apply_with_confirm_writes_db(db):
    """--apply --confirm → 软删除 (keep best, delete rest)"""
    title = "E2E-apply-test-001"
    content = "apply --confirm 应真写库"
    # 3 条同 title+content, quality 不同 → keep quality=0.7 那条
    id1 = await _create_dup_record(db, title=title, content=content, quality=0.3)
    id2 = await _create_dup_record(db, title=title, content=content, quality=0.7)  # ← keep
    id3 = await _create_dup_record(db, title=title, content=content, quality=0.5)
    await db.commit()

    active_before = await _count_active_by_title(db, title)
    assert active_before == 3

    # 3 段式完整流程: scan → validate → apply --confirm
    plan = await scan_duplicates(lambda: db)  # 注意: scan_duplicates 接受 session_factory
    assert plan.validation is not None
    assert plan.validation.valid is True

    # 真 apply
    deleted_count = await apply_cleanup(lambda: db, plan, dry_run=False)
    assert deleted_count == 2, "应软删 2 条 (3 - 1 keep)"

    # 验证: 1 active (keep), 2 deleted
    active_after = await _count_active_by_title(db, title)
    deleted_after = await _count_soft_deleted_by_title(db, title)
    assert active_after == 1, f"应剩 1 条 active, 实得 {active_after}"
    assert deleted_after == 2, f"应软删 2 条, 实得 {deleted_after}"

    # keep 的是 quality=0.7 那条 (id2)
    from sqlalchemy import select
    from app.models.knowledge import Knowledge
    kept = (await db.execute(
        select(Knowledge).where(Knowledge.title == title, Knowledge.deleted_at.is_(None))
    )).scalar_one()
    assert kept.id == id2, f"keep 必须是 quality=0.7 (id={id2}), 实得 id={kept.id}"
    assert kept.quality_score == 0.7


# ============================================================================
# Case 5: 重复 --apply --confirm 幂等
# ============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_apply_is_idempotent(db):
    """第二次 apply --confirm 应扫不到重复组 (因为已软删), deleted_count = 0"""
    title = "E2E-idem-test-001"
    content = "幂等性测试内容"
    await _create_dup_record(db, title=title, content=content, quality=0.3)
    await _create_dup_record(db, title=title, content=content, quality=0.7)
    await db.commit()

    # 第一次 apply: 删 1 条
    plan1 = await scan_duplicates(lambda: db)
    deleted1 = await apply_cleanup(lambda: db, plan1, dry_run=False)
    assert deleted1 == 1

    # 第二次 apply: 已软删的不在 scan 范围, 0 删
    plan2 = await scan_duplicates(lambda: db)
    # 第二轮 plan 应该是空的 (active 行只剩 1 条, 不构成重复组)
    assert len(plan2.groups) == 0, f"第二次 scan 应无重复组, 实得 {len(plan2.groups)} 个"

    deleted2 = await apply_cleanup(lambda: db, plan2, dry_run=False)
    assert deleted2 == 0, "幂等: 第二次 apply 应 0 删除"

    # 终态: 1 active (keep), 1 deleted
    active_final = await _count_active_by_title(db, title)
    deleted_final = await _count_soft_deleted_by_title(db, title)
    assert active_final == 1
    assert deleted_final == 1


# ============================================================================
# Case 6 (bonus): --validate 在 DB 状态下扫描后立即校验, 不写库
# ============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_validate_mode_does_not_write_db(db):
    """--validate 走完整 scan+validate 但不 apply, DB count 不变"""
    title = "E2E-validate-test-001"
    content = "validate 模式不写库"
    await _create_dup_record(db, title=title, content=content, quality=0.3)
    await _create_dup_record(db, title=title, content=content, quality=0.7)
    await db.commit()

    active_before = await _count_active_by_title(db, title)
    deleted_before = await _count_soft_deleted_by_title(db, title)
    assert active_before == 2
    assert deleted_before == 0

    # --validate 完整跑 scan+validate 但不 apply
    exit_code = await main(["--validate"])
    assert exit_code == 0, "validate 模式若合法应 exit 0"

    active_after = await _count_active_by_title(db, title)
    deleted_after = await _count_soft_deleted_by_title(db, title)
    assert active_after == 2, "validate 不应修改 active count"
    assert deleted_after == 0, "validate 不应软删任何行"


# ============================================================================
# Case 7 (bonus): main() argparse 互斥组 (--scan/--validate/--apply 不能同时)
# ============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_main_argparse_mutually_exclusive(db):
    """--scan 与 --validate 互斥, 同时传应 SystemExit(2)"""
    with pytest.raises(SystemExit) as exc_info:
        await main(["--scan", "--validate"])
    assert exc_info.value.code == 2, "argparse 互斥组冲突应 exit 2"


# ============================================================================
# Case 8 (bonus): apply_cleanup 直接 dry_run=True 也不写库
# ============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_apply_cleanup_dry_run_flag_does_not_write_db(db):
    """apply_cleanup(dry_run=True) 只 log 不写库"""
    title = "E2E-dryrun-helper-test-001"
    content = "apply_cleanup dry_run 测试"
    await _create_dup_record(db, title=title, content=content, quality=0.3)
    await _create_dup_record(db, title=title, content=content, quality=0.7)
    await db.commit()

    plan = await scan_duplicates(lambda: db)
    deleted = await apply_cleanup(lambda: db, plan, dry_run=True)
    # dry_run 返 delete_ids 数量, 但实际不写
    assert deleted == 1  # 应返"如果真删会删 1 条"

    # 但 DB 没动
    active_after = await _count_active_by_title(db, title)
    deleted_after = await _count_soft_deleted_by_title(db, title)
    assert active_after == 2
    assert deleted_after == 0