"""2026-07-02 v2 PR6-P10 — backup_before_delete helper + restore_from_backup.py 单测

覆盖:
1. backup_rows_to_json: 备份文件生成 + SKIP_DB_SETUP 模式下 OK (mock db)
2. execute_backup_then_delete: SELECT → 备份 → DELETE 三段式
3. restore_from_backup CLI: --scan 无副作用 + --apply 需 --confirm 二次确认
4. BACKUP_BEFORE_DELETE_ENABLED=False 跳过备份

不依赖真实 DB (纯 mock, 与 chat_history_tasks / file_mention_tasks 范式一致)
"""
import json
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock, mock_open

import pytest

from app.services.cleanup_backup import (
    backup_rows_to_json,
    execute_backup_then_delete,
    _row_to_dict,
)
from app.config import settings
from sqlalchemy import true  # 用 true() 作占位 where clause (SQLAlchemy 真实表达式)


# ============================================================
# _row_to_dict 单元测试
# ============================================================

class TestRowToDict:
    """_row_to_dict: ORM row → JSON-serializable dict"""

    def test_basic_row(self):
        """普通 row → dict (datetime → ISO, 其他透传)"""
        class FakeRow:
            class __table__:
                class _Col:
                    def __init__(self, name):
                        self.name = name
                columns = [_Col("id"), _Col("title"), _Col("created_at")]
            id = 1
            title = "test"
            created_at = datetime(2026, 7, 2, 12, 0, 0)

        result = _row_to_dict(FakeRow())
        assert result["id"] == 1
        assert result["title"] == "test"
        assert result["created_at"] == "2026-07-02T12:00:00"

    def test_nullable_field(self):
        """nullable 字段 None → JSON null"""
        class FakeRow:
            class __table__:
                class _Col:
                    def __init__(self, name):
                        self.name = name
                columns = [_Col("id"), _Col("optional")]
            id = 1
            optional = None

        result = _row_to_dict(FakeRow())
        assert result["optional"] is None


# ============================================================
# backup_rows_to_json 测试
# ============================================================

class TestBackupRowsToJson:
    """backup_rows_to_json: SELECT → JSON 写盘 (纯 mock)"""

    @pytest.mark.asyncio
    async def test_disabled_setting_skips_backup(self, tmp_path, monkeypatch):
        """BACKUP_BEFORE_DELETE_ENABLED=False → 仍 SELECT (给 caller count) 但不写备份"""
        monkeypatch.setattr(settings, "BACKUP_BEFORE_DELETE_ENABLED", False)

        db = MagicMock()

        # mock SELECT 返回 3 行
        class FakeRow:
            class __table__:
                class _Col:
                    def __init__(self, name): self.name = name
                columns = [_Col("id")]
            id = 1
        row1, row2, row3 = FakeRow(), FakeRow(), FakeRow()
        row2.id = 2
        row3.id = 3

        mock_select_result = MagicMock()
        mock_select_result.scalars.return_value.all.return_value = [row1, row2, row3]
        db.execute = AsyncMock(return_value=mock_select_result)

        from app.models.knowledge import FileMention
        count, backup_path = await backup_rows_to_json(
            db,
            model=FileMention,
            where_clause=true(),
            table_name="file_mentions",
        )
        assert count == 3
        assert backup_path is None  # disabled → 无备份文件

    @pytest.mark.asyncio
    async def test_enabled_writes_json(self, tmp_path, monkeypatch):
        """BACKUP_BEFORE_DELETE_ENABLED=True (默认) → 写 /tmp/<prefix>_<table>_<ts>.json"""
        monkeypatch.setattr(settings, "BACKUP_BEFORE_DELETE_ENABLED", True)
        monkeypatch.setattr(settings, "CLEANUP_BACKUP_PREFIX", "celery_cleanup")

        db = MagicMock()

        class FakeRow:
            class __table__:
                class _Col:
                    def __init__(self, name): self.name = name
                columns = [_Col("id"), _Col("title")]
            id = 100
            title = "test mention"
        row = FakeRow()

        mock_select_result = MagicMock()
        mock_select_result.scalars.return_value.all.return_value = [row]
        db.execute = AsyncMock(return_value=mock_select_result)

        # 把 /tmp 重定向到 tmp_path (pytest fixture)
        with patch("builtins.open", mock_open()) as m_open:
            with patch("app.services.cleanup_backup.open", mock_open(), create=True):
                with patch("json.dump") as m_json_dump:
                    from app.models.knowledge import FileMention
                    count, backup_path = await backup_rows_to_json(
                        db,
                        model=FileMention,
                        where_clause=true(),
                        table_name="file_mentions",
                        extra_metadata={"cutoff": "2026-07-02"},
                    )
                    assert count == 1
                    assert backup_path is not None
                    assert "/tmp/celery_cleanup_file_mentions_" in backup_path
                    assert backup_path.endswith(".json")
                    # json.dump 被调
                    assert m_json_dump.called

    @pytest.mark.asyncio
    async def test_zero_rows_no_backup(self, monkeypatch):
        """0 行 → 返回 (0, None) 不写备份"""
        monkeypatch.setattr(settings, "BACKUP_BEFORE_DELETE_ENABLED", True)

        db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_select_result)

        with patch("builtins.open") as m_open:
            with patch("json.dump") as m_json_dump:
                from app.models.knowledge import FileMention
                count, backup_path = await backup_rows_to_json(
                    db,
                    model=FileMention,
                    where_clause=true(),
                    table_name="file_mentions",
                )
                assert count == 0
                assert backup_path is None
                # 0 行 → 不应调 open/json.dump
                assert not m_open.called

    @pytest.mark.asyncio
    async def test_backup_write_failure_raises(self, monkeypatch):
        """写备份失败 → 抛异常 (让 caller 决定是否中止 DELETE, 保守策略)"""
        monkeypatch.setattr(settings, "BACKUP_BEFORE_DELETE_ENABLED", True)

        db = MagicMock()

        class FakeRow:
            class __table__:
                class _Col:
                    def __init__(self, name): self.name = name
                columns = [_Col("id")]
            id = 1

        mock_select_result = MagicMock()
        mock_select_result.scalars.return_value.all.return_value = [FakeRow()]
        db.execute = AsyncMock(return_value=mock_select_result)

        # 模拟 open() 抛 IOError
        with patch("builtins.open", side_effect=IOError("disk full")):
            with patch("json.dump"):
                from app.models.knowledge import FileMention
                with pytest.raises(IOError):
                    await backup_rows_to_json(
                        db,
                        model=FileMention,
                        where_clause=true(),
                        table_name="file_mentions",
                    )


# ============================================================
# execute_backup_then_delete 测试
# ============================================================

class TestExecuteBackupThenDelete:
    """execute_backup_then_delete: SELECT + 备份 + DELETE 三段式"""

    @pytest.mark.asyncio
    async def test_three_step_flow(self, monkeypatch):
        """完整流程: SELECT → 备份 → DELETE → commit"""
        monkeypatch.setattr(settings, "BACKUP_BEFORE_DELETE_ENABLED", True)
        monkeypatch.setattr(settings, "CLEANUP_BACKUP_PREFIX", "celery_cleanup")

        db = MagicMock()
        db.commit = AsyncMock()  # commit 需 await

        # 第一次 db.execute: SELECT
        class FakeRow:
            class __table__:
                class _Col:
                    def __init__(self, name): self.name = name
                columns = [_Col("id"), _Col("title")]
            id = 1
            title = "test"

        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [FakeRow()]

        # 第二次 db.execute: DELETE 返回 rowcount
        delete_result = MagicMock()
        delete_result.rowcount = 1

        db.execute = AsyncMock(side_effect=[select_result, delete_result])

        with patch("builtins.open", mock_open()):
            with patch("json.dump"):
                from app.models.knowledge import FileMention
                count, backup_path = await execute_backup_then_delete(
                    db,
                    model=FileMention,
                    where_clause=true(),
                    table_name="file_mentions",
                )
                assert count == 1
                assert backup_path is not None
                # commit 被调
                db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disabled_setting_passes_through(self, monkeypatch):
        """BACKUP_BEFORE_DELETE_ENABLED=False → 仍走 SELECT + DELETE (但无备份文件)"""
        monkeypatch.setattr(settings, "BACKUP_BEFORE_DELETE_ENABLED", False)

        db = MagicMock()
        db.commit = AsyncMock()

        class FakeRow:
            class __table__:
                class _Col:
                    def __init__(self, name): self.name = name
                columns = [_Col("id")]
            id = 1

        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [FakeRow()]
        delete_result = MagicMock()
        delete_result.rowcount = 1
        db.execute = AsyncMock(side_effect=[select_result, delete_result])

        from app.models.knowledge import FileMention
        with patch("builtins.open") as m_open:
            with patch("json.dump"):
                count, backup_path = await execute_backup_then_delete(
                    db,
                    model=FileMention,
                    where_clause=true(),
                    table_name="file_mentions",
                )
                assert count == 1
                assert backup_path is None  # disabled → 无备份
                assert not m_open.called


# ============================================================
# Settings 验证
# ============================================================

class TestSettingsConstants:
    """PR6-P10 新增 settings 验证"""

    def test_backup_before_delete_enabled_default_true(self):
        """BACKUP_BEFORE_DELETE_ENABLED 默认 True (事故防复发)"""
        assert settings.BACKUP_BEFORE_DELETE_ENABLED is True

    def test_cleanup_backup_prefix_default(self):
        """CLEANUP_BACKUP_PREFIX 默认 celery_cleanup"""
        assert settings.CLEANUP_BACKUP_PREFIX == "celery_cleanup"

    def test_mention_retention_days_unchanged(self):
        """MENTION_RETENTION_DAYS 仍为 30 (PR6-P9 已设置, 不能破坏)"""
        assert settings.MENTION_RETENTION_DAYS == 30


# ============================================================
# restore_from_backup.py CLI 测试
# ============================================================

class TestRestoreFromBackupCLI:
    """scripts/restore_from_backup.py 的 --scan / --apply 模式"""

    def test_load_backup_file_not_found(self, tmp_path):
        """不存在的备份文件 → FileNotFoundError"""
        from scripts.restore_from_backup import load_backup
        with pytest.raises(FileNotFoundError):
            load_backup(str(tmp_path / "nonexistent.json"))

    def test_load_backup_missing_required_keys(self, tmp_path):
        """备份 JSON 缺必需字段 → ValueError"""
        from scripts.restore_from_backup import load_backup
        bad_backup = tmp_path / "bad.json"
        bad_backup.write_text(json.dumps({"backup_at": "2026-07-02"}), encoding="utf-8")
        with pytest.raises(ValueError, match="缺必需字段"):
            load_backup(str(bad_backup))

    def test_load_backup_items_not_list(self, tmp_path):
        """items 字段不是 list → ValueError"""
        from scripts.restore_from_backup import load_backup
        bad_backup = tmp_path / "bad2.json"
        bad_backup.write_text(json.dumps({
            "backup_at": "2026-07-02",
            "table_name": "file_mentions",
            "row_count": 0,
            "items": "not a list",
        }), encoding="utf-8")
        with pytest.raises(ValueError, match="items 字段不是 list"):
            load_backup(str(bad_backup))

    def test_load_backup_valid(self, tmp_path):
        """合法备份 JSON → 返回 payload"""
        from scripts.restore_from_backup import load_backup
        backup = tmp_path / "good.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "title": "test"}],
            "meta": {"strategy": "test"},
        }), encoding="utf-8")
        payload = load_backup(str(backup))
        assert payload["table_name"] == "file_mentions"
        assert payload["row_count"] == 1
        assert len(payload["items"]) == 1

    def test_print_scan_summary_runs(self, tmp_path, capsys):
        """--scan 模式打印摘要无副作用"""
        from scripts.restore_from_backup import load_backup, print_scan_summary
        backup = tmp_path / "scan.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 2,
            "items": [{"id": 1, "title": "test1"}, {"id": 2, "title": "test2"}],
            "meta": {"strategy": "test", "cutoff_date": "2026-07-01"},
        }), encoding="utf-8")
        payload = load_backup(str(backup))
        print_scan_summary(payload, str(backup))
        captured = capsys.readouterr()
        assert "file_mentions" in captured.out
        assert "test1" in captured.out
        assert "INSERT" in captured.out

    def test_apply_without_confirm_dry_run(self, tmp_path):
        """--apply 但没 --confirm → DRY RUN 退出码 1"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--apply", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 1
        assert "DRY RUN" in result.stdout or "DRY RUN" in result.stderr

    def test_scan_mode_exits_zero(self, tmp_path):
        """--scan 模式无副作用退出码 0"""
        import subprocess
        backup = tmp_path / "scan.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 0,
            "items": [],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        assert "dry-run 完成" in result.stdout