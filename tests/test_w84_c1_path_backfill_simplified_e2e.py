from pathlib import Path


def test_path_backfill_task_uses_unified_service_entrypoint():
    service = Path("app/services/drive_comments_path_backfill_service.py").read_text()
    task = Path("app/services/drive_comments_path_backfill_tasks.py").read_text()
    assert "async def backfill_comments_path(" in service
    assert "backfill_comments_path(" in task
