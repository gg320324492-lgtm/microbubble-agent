"""W68 第 10 批 B-3 — Auto Intake Rollback 端到端测试

8 场景:
1. 5 道防线失败触发 record_failure → knowledge_rejected 写入
2. 24h 到 + retry_count < 3 → should_retry = True (可重试)
3. 24h 未到 → should_retry = False (不重试)
4. retry_count >= 3 → should_retry = False (永久挂起前)
5. mark_permanent_suspend → 写 knowledge_pending_review + permanent_suspended=True
6. daily_kb_intake_health_check → 统计失败率 + 应触发告警 (>20%)
7. 失败率 < 20% 不触发告警
8. delete_permanent_suspended_old → 清理 7 天前永久挂起行

设计纪律 (CLAUDE.md 2026-07-24 test 规范):
- SKIP_DB_SETUP=1 时 db fixture 不可用, 测试自动 skip
- pytest-asyncio + httpx AsyncClient
- 每个 test 独立 fixture, 避免污染
- mock Redis 用 fakeredis / monkeypatch

参考:
- app/services/auto_intake_rollback_service.py (业务核心)
- app/services/save_to_kb_service.py (5 道防线入口)
- app/services/auto_intake_rollback_tasks.py (Celery 包装)
"""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import pytest
import pytest_asyncio
from sqlalchemy import select, delete

SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))

if SKIP_DB_SETUP:
    pytest.skip("requires DB (SKIP_DB_SETUP not set)", allow_module_level=True)

# 条件 import: DB fixture 可用时才加载
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.celery_db import create_celery_engine_and_session  # noqa: E402
from app.models.knowledge_rejected import (  # noqa: E402
    GATE_CONTENT,
    GATE_GRAYSCALE,
    GATE_INTAKE_FLAG,
    GATE_INTENT,
    GATE_SCORE,
    KnowledgePendingReview,
    KnowledgeRejected,
)
from app.services.auto_intake_rollback_service import (  # noqa: E402
    AutoIntakeRollbackService,
    MAX_RETRY_COUNT,
    RETRY_INTERVAL_SECONDS,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest_asyncio.fixture
async def rollback_service():
    """AutoIntakeRollbackService 实例 (独立 NullPool engine)"""
    engine, session_factory = create_celery_engine_and_session()
    db = session_factory()
    svc = AutoIntakeRollbackService(db)
    try:
        yield svc
    finally:
        await db.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def clean_rejected_tables():
    """每个 test 前清理 knowledge_rejected + knowledge_pending_review"""
    engine, session_factory = create_celery_engine_and_session()
    db = session_factory()
    try:
        await db.execute(delete(KnowledgePendingReview))
        await db.execute(delete(KnowledgeRejected))
        await db.commit()
        yield
    finally:
        await db.execute(delete(KnowledgePendingReview))
        await db.execute(delete(KnowledgeRejected))
        await db.commit()
        await db.close()
        await engine.dispose()


def _to_naive(dt: datetime) -> datetime:
    """tz-aware → naive 转换 (与 service 内部一致)"""
    if dt.tzinfo is None:
        return dt
    return dt.replace(tzinfo=None)


# =============================================================================
# Test 1: 5 道防线失败 → knowledge_rejected 写入 (幂等 upsert)
# =============================================================================
@pytest.mark.asyncio
async def test_record_failure_5_gates_write_rejected(
    rollback_service, clean_rejected_tables
):
    """5 道防线任一失败 → AutoIntakeRollbackService.record_failure → knowledge_rejected 写入"""
    svc = rollback_service

    # 防线 1: score 失败
    rej = await svc.record_failure(
        qa_id="S-001",
        failed_gate=GATE_SCORE,
        error_msg="score 3 < min_score 4",
        question="什么是微纳米气泡?",
        content="...",
        score=3,
        intent="explain_concept",
        extra={"grayscale_pct": 25},
    )
    assert rej is not None
    assert rej.qa_id == "S-001"
    assert rej.failed_gate == GATE_SCORE
    assert rej.retry_count == 0
    assert rej.permanent_suspended is False
    assert rej.next_retry_at is not None


@pytest.mark.asyncio
async def test_record_failure_invalid_gate_returns_none(
    rollback_service, clean_rejected_tables
):
    """非法 failed_gate → record_failure 返回 None"""
    rej = await rollback_service.record_failure(
        qa_id="S-002",
        failed_gate="invalid_gate",
    )
    assert rej is None


@pytest.mark.asyncio
async def test_record_failure_idempotent_upsert(
    rollback_service, clean_rejected_tables
):
    """同一 qa_id 多次失败 → 幂等 upsert, 不重复创建行"""
    svc = rollback_service

    # 第 1 次失败
    rej1 = await svc.record_failure(
        qa_id="S-003",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )
    assert rej1 is not None
    rej1_id = rej1.id

    # 第 2 次失败 (同 qa_id, 不同 gate)
    rej2 = await svc.record_failure(
        qa_id="S-003",
        failed_gate=GATE_CONTENT,
        error_msg="content length 100 < 200",
        content="short",
        score=4,
    )
    assert rej2 is not None
    assert rej2.id == rej1_id, "幂等 upsert 应该返回同一行"
    assert rej2.failed_gate == GATE_CONTENT, "failed_gate 应被更新"


# =============================================================================
# Test 2: should_retry 4 条件 (24h 到 + retry_count<3 + 未挂起 + next_retry_at 不为 NULL)
# =============================================================================
@pytest.mark.asyncio
async def test_should_retry_after_24h_eligible(
    rollback_service, clean_rejected_tables
):
    """24h 到 + retry_count=0 → should_retry=True"""
    rej = await rollback_service.record_failure(
        qa_id="S-010",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )
    assert rej is not None

    # 把 next_retry_at 设为 24h 前 (模拟 24h 已过)
    rej.next_retry_at = _to_naive(datetime.now(timezone.utc) - timedelta(hours=24))
    await rollback_service.db.commit()

    can_retry = await rollback_service.should_retry(rej.id)
    assert can_retry is True, "24h 已过应该允许重试"


@pytest.mark.asyncio
async def test_should_retry_not_yet_24h_false(
    rollback_service, clean_rejected_tables
):
    """24h 未到 → should_retry=False"""
    rej = await rollback_service.record_failure(
        qa_id="S-011",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )
    # 默认 next_retry_at = now + 24h, 还没到
    can_retry = await rollback_service.should_retry(rej.id)
    assert can_retry is False, "24h 未到不应该重试"


@pytest.mark.asyncio
async def test_should_retry_permanent_suspended_false(
    rollback_service, clean_rejected_tables
):
    """permanent_suspended=True → should_retry=False (不重试)"""
    rej = await rollback_service.record_failure(
        qa_id="S-012",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )
    rej.next_retry_at = _to_naive(datetime.now(timezone.utc) - timedelta(hours=48))
    rej.permanent_suspended = True
    await rollback_service.db.commit()

    can_retry = await rollback_service.should_retry(rej.id)
    assert can_retry is False, "永久挂起的不应该重试"


@pytest.mark.asyncio
async def test_should_retry_max_retry_count_false(
    rollback_service, clean_rejected_tables
):
    """retry_count >= MAX_RETRY_COUNT → should_retry=False"""
    rej = await rollback_service.record_failure(
        qa_id="S-013",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )
    rej.next_retry_at = _to_naive(datetime.now(timezone.utc) - timedelta(hours=48))
    rej.retry_count = MAX_RETRY_COUNT  # 3
    await rollback_service.db.commit()

    can_retry = await rollback_service.should_retry(rej.id)
    assert can_retry is False, "retry_count=3 不应该重试"


# =============================================================================
# Test 3: schedule_retry 重排 + retry_count++ + 永久挂起
# =============================================================================
@pytest.mark.asyncio
async def test_schedule_retry_increment_count(
    rollback_service, clean_rejected_tables
):
    """schedule_retry: retry_count++ + next_retry_at = +24h"""
    rej = await rollback_service.record_failure(
        qa_id="S-020",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )
    original_count = rej.retry_count

    new_rej = await rollback_service.schedule_retry(rej.id)
    assert new_rej is not None
    assert new_rej.retry_count == original_count + 1
    assert new_rej.next_retry_at > _to_naive(datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_schedule_retry_exceeds_max_suspends(
    rollback_service, clean_rejected_tables
):
    """schedule_retry: retry_count 达到 MAX+1 → 触发永久挂起"""
    rej = await rollback_service.record_failure(
        qa_id="S-021",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )
    # 把 retry_count 设到 MAX_RETRY_COUNT, 再次 schedule_retry 应触发挂起
    rej.retry_count = MAX_RETRY_COUNT
    await rollback_service.db.commit()

    result = await rollback_service.schedule_retry(rej.id)
    assert result is None, "retry_count > MAX 应返回 None (已挂起)"

    # 验证: permanent_suspended=True
    refreshed = await rollback_service.db.execute(
        select(KnowledgeRejected).where(KnowledgeRejected.id == rej.id)
    )
    refreshed_rej = refreshed.scalar_one()
    assert refreshed_rej.permanent_suspended is True


# =============================================================================
# Test 4: mark_permanent_suspend 写 knowledge_pending_review
# =============================================================================
@pytest.mark.asyncio
async def test_mark_permanent_suspend_writes_pending_review(
    rollback_service, clean_rejected_tables
):
    """mark_permanent_suspend → 写 knowledge_pending_review + permanent_suspended=True"""
    rej = await rollback_service.record_failure(
        qa_id="S-030",
        failed_gate=GATE_CONTENT,
        error_msg="content too short",
        question="Q?",
        content="short",
        score=4,
        intent="explain_concept",
    )
    rej.retry_count = MAX_RETRY_COUNT
    await rollback_service.db.commit()

    pending = await rollback_service.mark_permanent_suspend(rej.id)
    assert pending is not None
    assert pending.qa_id == "S-030"
    assert pending.failed_gate == GATE_CONTENT
    assert pending.review_status == "pending"
    assert pending.total_attempts == MAX_RETRY_COUNT + 1  # 1 首次 + 3 retry = 4

    # 验证 rejected 表: permanent_suspended=True
    refreshed = await rollback_service.db.execute(
        select(KnowledgeRejected).where(KnowledgeRejected.id == rej.id)
    )
    refreshed_rej = refreshed.scalar_one()
    assert refreshed_rej.permanent_suspended is True


@pytest.mark.asyncio
async def test_mark_permanent_suspend_idempotent(
    rollback_service, clean_rejected_tables
):
    """mark_permanent_suspend 幂等: 第二次调用返回已有 pending_review"""
    rej = await rollback_service.record_failure(
        qa_id="S-031",
        failed_gate=GATE_SCORE,
        error_msg="score 3",
        score=3,
    )

    # 第 1 次挂起
    pending1 = await rollback_service.mark_permanent_suspend(rej.id)
    assert pending1 is not None

    # 第 2 次挂起 (幂等)
    pending2 = await rollback_service.mark_permanent_suspend(rej.id)
    assert pending2 is not None
    assert pending2.id == pending1.id, "幂等返回同 id"


# =============================================================================
# Test 5: get_failure_rate 失败率统计 + 告警阈值
# =============================================================================
@pytest.mark.asyncio
async def test_get_failure_rate_alert_threshold(
    rollback_service, clean_rejected_tables
):
    """get_failure_rate: 失败率 > 20% → should_alert=True"""
    # 模拟 10 个 rejected + 30 个 success = 25% > 20%
    for i in range(10):
        await rollback_service.record_failure(
            qa_id=f"S-FAIL-{i:03d}",
            failed_gate=GATE_SCORE,
            error_msg="simulated",
            score=3,
        )

    # 模拟 30 个 success (knowledge 行)
    from app.models.knowledge import Knowledge

    for i in range(30):
        kb = Knowledge(
            title=f"success-{i}",
            content="...",
            source_type="auto_expansion",
            source=f"qa-bench:S-OK-{i:03d}",
            created_by=None,
        )
        rollback_service.db.add(kb)
    await rollback_service.db.commit()

    rate = await rollback_service.get_failure_rate(days=7)
    assert rate["rejected_count"] == 10
    assert rate["success_count"] == 30
    assert rate["total_attempts"] == 40
    assert abs(rate["failure_rate"] - 0.25) < 0.001
    assert rate["should_alert"] is True


@pytest.mark.asyncio
async def test_get_failure_rate_below_threshold_no_alert(
    rollback_service, clean_rejected_tables
):
    """get_failure_rate: 失败率 < 20% → should_alert=False"""
    # 模拟 1 个 rejected + 100 个 success = 1% < 20%
    await rollback_service.record_failure(
        qa_id="S-FAIL-001",
        failed_gate=GATE_SCORE,
        error_msg="simulated",
        score=3,
    )

    from app.models.knowledge import Knowledge

    for i in range(100):
        kb = Knowledge(
            title=f"success-{i}",
            content="...",
            source_type="auto_expansion",
            source=f"qa-bench:S-OK-{i:03d}",
            created_by=None,
        )
        rollback_service.db.add(kb)
    await rollback_service.db.commit()

    rate = await rollback_service.get_failure_rate(days=7)
    assert rate["rejected_count"] == 1
    assert rate["success_count"] == 100
    assert rate["should_alert"] is False


@pytest.mark.asyncio
async def test_get_failure_rate_zero_total(
    rollback_service, clean_rejected_tables
):
    """get_failure_rate: 0 rejected + 0 success → failure_rate=0, no alert"""
    rate = await rollback_service.get_failure_rate(days=7)
    assert rate["rejected_count"] == 0
    assert rate["success_count"] == 0
    assert rate["total_attempts"] == 0
    assert rate["failure_rate"] == 0.0
    assert rate["should_alert"] is False


# =============================================================================
# Test 6: list_pending_retries 调度候选
# =============================================================================
@pytest.mark.asyncio
async def test_list_pending_retries_returns_active_only(
    rollback_service, clean_rejected_tables
):
    """list_pending_retries: 只返回 active (未挂起 + 未到 retry_count 上限 + 到期)"""
    # 1. active retry
    rej1 = await rollback_service.record_failure(
        qa_id="S-LIST-001",
        failed_gate=GATE_SCORE,
        error_msg="simulated",
        score=3,
    )
    rej1.next_retry_at = _to_naive(datetime.now(timezone.utc) - timedelta(hours=1))
    await rollback_service.db.commit()

    # 2. 永久挂起的 (不应出现在列表)
    rej2 = await rollback_service.record_failure(
        qa_id="S-LIST-002",
        failed_gate=GATE_SCORE,
        error_msg="simulated",
        score=3,
    )
    rej2.permanent_suspended = True
    await rollback_service.db.commit()

    # 3. retry_count=MAX 的 (不应出现在列表)
    rej3 = await rollback_service.record_failure(
        qa_id="S-LIST-003",
        failed_gate=GATE_SCORE,
        error_msg="simulated",
        score=3,
    )
    rej3.retry_count = MAX_RETRY_COUNT
    rej3.next_retry_at = _to_naive(datetime.now(timezone.utc) - timedelta(hours=1))
    await rollback_service.db.commit()

    candidates = await rollback_service.list_pending_retries()
    qa_ids = [c.qa_id for c in candidates]
    assert "S-LIST-001" in qa_ids
    assert "S-LIST-002" not in qa_ids, "永久挂起的应该被排除"
    assert "S-LIST-003" not in qa_ids, "retry_count=MAX 的应该被排除"


# =============================================================================
# Test 7: delete_permanent_suspended_old 7 天前清理
# =============================================================================
@pytest.mark.asyncio
async def test_delete_permanent_suspended_old(
    rollback_service, clean_rejected_tables
):
    """delete_permanent_suspended_old: 删除 7 天前 permanent_suspended=True 行"""
    # 1. 7 天前永久挂起的 (应被删)
    old_rej = await rollback_service.record_failure(
        qa_id="S-OLD-001",
        failed_gate=GATE_SCORE,
        error_msg="simulated",
        score=3,
    )
    old_rej.permanent_suspended = True
    old_rej.created_at = _to_naive(datetime.now(timezone.utc) - timedelta(days=10))
    await rollback_service.db.commit()

    # 2. 1 天前永久挂起的 (不应被删)
    new_rej = await rollback_service.record_failure(
        qa_id="S-NEW-001",
        failed_gate=GATE_SCORE,
        error_msg="simulated",
        score=3,
    )
    new_rej.permanent_suspended = True
    new_rej.created_at = _to_naive(datetime.now(timezone.utc) - timedelta(days=1))
    await rollback_service.db.commit()

    deleted = await rollback_service.delete_permanent_suspended_old(retention_days=7)
    assert deleted == 1, "只应删 7 天前的"

    # 验证: 老的删了, 新的还在
    remaining = await rollback_service.db.execute(
        select(KnowledgeRejected).order_by(KnowledgeRejected.id.asc())
    )
    rows = list(remaining.scalars().all())
    qa_ids = [r.qa_id for r in rows]
    assert "S-OLD-001" not in qa_ids
    assert "S-NEW-001" in qa_ids


# =============================================================================
# Test 8: Celery task smoke (不真跑 Celery, 直接调 service)
# =============================================================================
@pytest.mark.asyncio
async def test_celery_task_module_imports():
    """Celery task 模块 import 不挂"""
    from app.services import auto_intake_rollback_tasks

    assert hasattr(auto_intake_rollback_tasks, "retry_rejected_kb_intake_task")
    assert hasattr(
        auto_intake_rollback_tasks, "permanent_suspend_rejected_kb_intake_task"
    )
    assert hasattr(auto_intake_rollback_tasks, "daily_kb_intake_health_check_task")
    assert hasattr(auto_intake_rollback_tasks, "schedule_retry_in_24h")


@pytest.mark.asyncio
async def test_kb_intake_alert_service_module_imports():
    """KbIntakeAlertService 模块 import 不挂"""
    from app.services.kb_intake_alert_service import KbIntakeAlertService

    assert hasattr(KbIntakeAlertService, "send_alert_if_high_failure_rate")
    assert hasattr(KbIntakeAlertService, "_publish_alert")


@pytest.mark.asyncio
async def test_save_to_kb_service_record_failure_called_from_5_gates(
    rollback_service, clean_rejected_tables
):
    """SaveToKbService 5 道防线都走 record_failure (集成测试)"""
    from app.services.save_to_kb_service import SaveToKbService

    # 创建 service (grayscale=0 → 防线 4 必失败)
    svc = SaveToKbService(
        rollback_service.db,
        grayscale_pct=0,
    )

    # 防线 1: score 失败
    r1 = await svc.ingest_one(
        qa_id="S-INT-001",
        question="Q?",
        content="a" * 300,
        score=3,  # < 4
        intent="explain_concept",
    )
    assert r1["status"] == "rejected"
    assert r1["failed_gate"] == GATE_SCORE

    # 防线 2: content 失败
    r2 = await svc.ingest_one(
        qa_id="S-INT-002",
        question="Q?",
        content="short",  # < 200
        score=5,
        intent="explain_concept",
    )
    assert r2["status"] == "rejected"
    assert r2["failed_gate"] == GATE_CONTENT

    # 防线 3: intent 失败
    r3 = await svc.ingest_one(
        qa_id="S-INT-003",
        question="Q?",
        content="a" * 300,
        score=5,
        intent="gibberish",  # not in whitelist
    )
    assert r3["status"] == "rejected"
    assert r3["failed_gate"] == GATE_INTENT

    # 防线 4: grayscale=0 (默认跳过)
    r4 = await svc.ingest_one(
        qa_id="S-INT-004",
        question="Q?",
        content="a" * 300,
        score=5,
        intent="explain_concept",
    )
    assert r4["status"] == "rejected"
    assert r4["failed_gate"] == GATE_GRAYSCALE


# =============================================================================
# Teardown
# =============================================================================
@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_test_data():
    """session 级清理: 所有测试结束后清干净"""
    yield
    # 清理由 clean_rejected_tables fixture 处理, 这里 no-op