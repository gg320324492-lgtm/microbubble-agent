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


# ============================================================
# 2026-07-02 v2 PR6-P10 增量: --table 显式指定目标表
# ============================================================

class TestRestoreFromBackupTableFlag:
    """scripts/restore_from_backup.py 的 --table 覆盖逻辑 (PR6-P10 增量)"""

    def test_table_invalid_fails_fast(self, tmp_path):
        """--table 指定不存在的表 → 退出码 1 + 列出合法选项"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--table=invalid_table_name", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 1
        out = result.stdout
        assert "不在支持列表" in out
        # 必须列出全部合法选项
        for valid in ["chat_sessions", "file_mentions", "drive_files", "folders"]:
            assert valid in out, f"合法选项 {valid} 应在错误信息中"

    def test_table_same_as_json_no_warn(self, tmp_path):
        """--table 与 JSON 原始 table_name 一致 → 无 ⚠️ 警告"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "title": "test"}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--table=file_mentions", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # 显式 --table=file_mentions + JSON 原始=file_mentions → 一致, 无覆盖警告
        assert "覆盖自 JSON 原始" not in out
        assert "[WARN] --table=" not in out

    def test_table_diff_from_json_warns_and_overrides(self, tmp_path):
        """--table 与 JSON 原始不一致 → ⚠️ 警告 + 覆盖生效"""
        import subprocess
        backup = tmp_path / "backup.json"
        # JSON 标 file_mentions, --table 强制 folders
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 2,
            "items": [{"id": 1}, {"id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--table=folders", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # 警告: 覆盖
        assert "[WARN] --table=folders" in out
        assert "table_name=file_mentions" in out
        # scan summary 显示覆盖标记
        assert "覆盖自 JSON 原始 table_name=file_mentions" in out
        # 目标表显示为 folders (不是 file_mentions)
        assert "folders" in out

    def test_table_scan_no_side_effects(self, tmp_path):
        """--table + --scan 完全无 DB 副作用 (--apply 必传 --confirm, scan 一定不写)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--table=folders", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        # scan 模式永远退出码 0
        assert result.returncode == 0
        # 必须有 "dry-run 完成" 字样
        assert "dry-run 完成" in result.stdout
        # 不能出现 "✅ [RESTORE]"  (那是写库成功的标志)
        assert "✅ [RESTORE]" not in result.stdout

    def test_table_absent_uses_json_default(self, tmp_path):
        """不传 --table → 走 JSON 原始 table_name (向后兼容)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # 不传 --table → 无 [WARN] 警告
        assert "[WARN]" not in out
        # scan summary 也不显示 "覆盖自"
        assert "覆盖自" not in out

    def test_table_argparse_help_includes_choices(self):
        """--table --help 应包含 BACKUP_TABLE_TO_ORM 全部可选值, 帮用户记忆"""
        import subprocess
        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--help"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # help 文本里必须列出 4 个合法选项
        for valid in ["chat_sessions", "file_mentions", "drive_files", "folders"]:
            assert valid in out, f"--help 应包含 {valid}"

    def test_table_payload_override_unit(self):
        """load_backup 不会动 JSON, 覆盖必须在 main() 层做 (in-memory)"""
        # 验证 print_scan_summary 接受 original_table_name 参数
        from scripts.restore_from_backup import print_scan_summary, load_backup
        import inspect
        sig = inspect.signature(print_scan_summary)
        assert "original_table_name" in sig.parameters
        # 默认值是 None (向后兼容)
        assert sig.parameters["original_table_name"].default is None

    def test_table_payload_passthrough_to_restore(self):
        """restore_from_backup 接受 payload 参数 (--table override 时传入, 避免重新 load 丢覆盖)"""
        from scripts.restore_from_backup import restore_from_backup
        import inspect
        sig = inspect.signature(restore_from_backup)
        assert "payload" in sig.parameters
        # 默认值是 None (向后兼容, 内部 load)
        assert sig.parameters["payload"].default is None


class TestRestorePartialColumns:
    """scripts/restore_from_backup.py 的 --columns 部分字段模式 (PR6-P10+ 增量)"""

    def test_columns_invalid_fails_fast(self, tmp_path):
        """--columns 指定不存在的列 → 退出码 1 + 列出目标表合法列"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--columns=id,nonexistent_column,another_typo", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 1
        out = result.stdout
        # 必须列出无效列名 + 提示语
        assert "nonexistent_column" in out
        assert "another_typo" in out
        assert "不在表" in out
        # 必须列出 file_mentions 的合法列 (至少包含 id)
        assert "id" in out
        # 提示用户加 id (如果缺)
        # (此处 id 在 --columns 里, 不应触发 pk 缺失警告)

    def test_columns_missing_pk_fails_fast(self, tmp_path):
        """--columns 不包含主键 id → 退出码 1 + 提示加 id"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--columns=file_id,context", str(backup)],  # 故意缺 id
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 1
        out = result.stdout
        # 主键列名提示
        assert "主键列" in out
        assert "id" in out
        # 提示修复建议
        assert "id,file_id,context" in out or "id," in out

    def test_columns_valid_partial_scan_succeeds(self, tmp_path):
        """--columns=id,file_id + --scan → 退出码 0 + scan summary 显示 partial 模式"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 2,
            "items": [
                {"id": 100, "file_id": 1, "context": "msg1", "extra_col": "ignored"},
                {"id": 101, "file_id": 2, "context": "msg2", "extra_col": "ignored"},
            ],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--columns=id,file_id", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # partial 模式标识
        assert "partial" in out
        # 列出指定列
        assert "id" in out
        assert "file_id" in out
        # scan 模式无副作用
        assert "dry-run 完成" in out
        assert "✅ [RESTORE]" not in out

    def test_columns_absent_uses_full_row_mode(self, tmp_path):
        """不传 --columns → 全字段模式 (PR6-P10 默认行为, 向后兼容)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2, "context": "msg"}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # 全字段模式标识
        assert "全部列" in out
        # 不应出现 partial
        assert "partial" not in out

    def test_columns_dedup_duplicate_entries(self, tmp_path):
        """--columns=id,id,file_id → 去重保留 id,file_id (不报错)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--columns=id,id,file_id", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        # 去重后不重复列 → 退出码 0
        assert result.returncode == 0
        out = result.stdout
        # partial 模式标识
        assert "partial" in out

    def test_columns_whitespace_stripped(self, tmp_path):
        """--columns='id, file_id , context' → 空白自动 strip, 跟 id,file_id,context 等价"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2, "context": "msg"}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--columns=id, file_id , context", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # 空白被 strip, partial 模式生效
        assert "partial" in out
        assert "id" in out and "file_id" in out and "context" in out

    def test_columns_with_table_combined(self, tmp_path):
        """--table + --columns 组合: 跨表 + 部分字段同时生效"""
        import subprocess
        backup = tmp_path / "backup.json"
        # JSON 标 file_mentions, --table=folders 跨表, --columns=id,parent_id 走 folders 主键
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2, "context": "msg"}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--table=folders", "--columns=id,parent_id", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        # --table=folders 与 JSON=file_mentions 不一致 → 但 columns 必须按 folders 表验证
        assert result.returncode == 0
        out = result.stdout
        # --table 警告
        assert "[WARN] --table=folders" in out
        # partial 模式标识
        assert "partial" in out
        # 列名按 folders 验证 (parent_id 是 folders 的列)
        assert "id" in out and "parent_id" in out

    def test_columns_partial_inspect_signature(self):
        """restore_from_backup 接受 columns 参数 (--columns 透传)"""
        from scripts.restore_from_backup import restore_from_backup
        import inspect
        sig = inspect.signature(restore_from_backup)
        assert "columns" in sig.parameters
        # 默认值是 None (向后兼容, 全字段模式)
        assert sig.parameters["columns"].default is None

    def test_columns_print_scan_summary_signature(self):
        """print_scan_summary 接受 partial_columns 参数"""
        from scripts.restore_from_backup import print_scan_summary
        import inspect
        sig = inspect.signature(print_scan_summary)
        assert "partial_columns" in sig.parameters
        # 默认值是 None (向后兼容)
        assert sig.parameters["partial_columns"].default is None

    def test_columns_get_table_columns_returns_list(self):
        """get_table_columns 返回目标表所有 ORM 列名 (含 id)"""
        from scripts.restore_from_backup import get_table_columns, BACKUP_TABLE_TO_ORM
        for table_name in BACKUP_TABLE_TO_ORM.keys():
            cols = get_table_columns(table_name)
            assert isinstance(cols, list)
            assert "id" in cols, f"{table_name} 必须含主键 id"
            assert len(cols) > 1, f"{table_name} 应有 >1 列"

    def test_columns_invalid_table_raises(self):
        """get_table_columns 传不存在的 table_name → ValueError"""
        from scripts.restore_from_backup import get_table_columns
        with pytest.raises(ValueError) as exc_info:
            get_table_columns("nonexistent_table")
        assert "不支持的 table_name" in str(exc_info.value)


class TestRestoreUpsert:
    """scripts/restore_from_backup.py 的 --upsert ON CONFLICT DO UPDATE 模式 (PR6-P11+ 增量)"""

    def test_upsert_absent_uses_do_nothing_mode(self, tmp_path):
        """不传 --upsert → DO NOTHING 模式 (PR6-P10+ 默认行为, 向后兼容)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # DO NOTHING 模式标识
        assert "DO NOTHING" in out
        # 不应出现 UPSERT 标识
        assert "DO UPDATE" not in out
        # 不应出现 --upsert 缺 --columns 警告
        assert "建议配合 --columns" not in out

    def test_upsert_flag_enables_do_update_mode(self, tmp_path):
        """传 --upsert → DO UPDATE 模式标识 + ⚠️ 警告 (缺 --columns)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", "--upsert", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # UPSERT 模式标识
        assert "UPSERT" in out
        assert "DO UPDATE" in out
        # ⚠️ 警告 (缺 --columns)
        assert "建议配合 --columns" in out
        # scan 模式无副作用
        assert "dry-run 完成" in out

    def test_upsert_with_columns_partial_silent(self, tmp_path):
        """--upsert + --columns = 完美打补丁 (无覆盖全部列警告)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--upsert", "--columns=id,is_read,read_at", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # UPSERT 模式 + partial 列同时显示
        assert "UPSERT" in out
        assert "partial" in out
        # 列出指定列 (Python list repr 格式)
        assert "['id', 'is_read', 'read_at']" in out
        # 无覆盖全部列警告 (因为有 --columns)
        assert "建议配合 --columns" not in out

    def test_upsert_with_table_combined(self, tmp_path):
        """--upsert + --table=folders 跨表 + UPSERT"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",  # JSON 标 file_mentions
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--upsert", "--table=folders", "--columns=id,name", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # --table 警告 + UPSERT 标识 + partial 同时显示
        assert "[WARN] --table=folders" in out
        assert "UPSERT" in out
        assert "partial" in out
        # 目标表显示为 folders
        assert "folders" in out

    def test_upsert_scan_no_side_effects(self, tmp_path):
        """--upsert + --scan 永远不写库 (与 PR6-P10+ 一致)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", "--upsert", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        assert "dry-run 完成" in result.stdout
        # 不能出现 UPSERT 完成 (那是写库成功的标志)
        assert "UPSERT 完成" not in result.stdout

    def test_upsert_argparse_help_includes_flag(self):
        """--help 应包含 --upsert flag"""
        import subprocess
        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--help"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        assert "--upsert" in result.stdout

    def test_upsert_inspect_signature(self):
        """restore_from_backup 接受 upsert 参数"""
        from scripts.restore_from_backup import restore_from_backup
        import inspect
        sig = inspect.signature(restore_from_backup)
        assert "upsert" in sig.parameters
        # 默认值是 False (向后兼容, PR6-P10+ 行为)
        assert sig.parameters["upsert"].default is False

    def test_upsert_print_scan_summary_signature(self):
        """print_scan_summary 接受 upsert_mode 参数"""
        from scripts.restore_from_backup import print_scan_summary
        import inspect
        sig = inspect.signature(print_scan_summary)
        assert "upsert_mode" in sig.parameters
        # 默认值是 False (向后兼容)
        assert sig.parameters["upsert_mode"].default is False

    def test_upsert_with_missing_pk_columns_fails_fast(self, tmp_path):
        """--upsert + --columns 缺主键 id → fail fast (与 PR6-P10+ 一致)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1, "file_id": 2}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--upsert", "--columns=file_id,context", str(backup)],  # 故意缺 id
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 1
        out = result.stdout
        # 主键列名提示
        assert "主键列" in out
        # 修复建议
        assert "id,file_id,context" in out

    def test_upsert_with_invalid_columns_fails_fast(self, tmp_path):
        """--upsert + --columns 含无效列 → fail fast (与 PR6-P10+ 一致)"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan",
             "--upsert", "--columns=id,typo_col", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 1
        out = result.stdout
        assert "typo_col" in out
        assert "不在表" in out

    def test_upsert_final_summary_line(self, tmp_path):
        """--upsert 时 scan summary 最终行应显示 '即将 UPSERT'"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", "--upsert", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # scan summary 最终行应区分 INSERT/UPSERT
        assert "即将 UPSERT" in out
        assert "即将恢复" not in out  # 默认模式才是 "即将恢复"

    def test_upsert_default_mode_final_summary_line(self, tmp_path):
        """默认模式 (无 --upsert) scan summary 最终行应显示 '即将恢复'"""
        import subprocess
        backup = tmp_path / "backup.json"
        backup.write_text(json.dumps({
            "backup_at": "2026-07-02T12:00:00",
            "table_name": "file_mentions",
            "row_count": 1,
            "items": [{"id": 1}],
        }), encoding="utf-8")

        result = subprocess.run(
            ["python", "scripts/restore_from_backup.py", "--scan", str(backup)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0
        out = result.stdout
        # 默认模式最终行
        assert "即将恢复" in out
        assert "即将 UPSERT" not in out