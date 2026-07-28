"""W82 第 1 批 B-1 P0: celery safety 三防线 regression coverage.

Lock in the 3 safety guards added to app/core/celery.py so future refactors
cannot silently disable them:
- task_reject_on_worker_lost=True
- task_time_limit=600 + task_soft_time_limit=540
- worker_max_tasks_per_child=1000
"""
from __future__ import annotations

from app.core.celery import celery_app


def test_task_rejects_on_worker_lost() -> None:
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_task_time_limits_defined() -> None:
    assert celery_app.conf.task_time_limit == 600
    assert celery_app.conf.task_soft_time_limit == 540


def test_worker_max_tasks_per_child_defined() -> None:
    assert celery_app.conf.worker_max_tasks_per_child == 1000
