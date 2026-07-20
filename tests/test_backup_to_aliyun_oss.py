"""
test_backup_to_aliyun_oss.py — W15 T2 阿里云 OSS 备份脚本单测

覆盖 (5 case):
1. --scan: 列出本地备份 (mock _scan_local_backups)
2. --apply 无 --confirm: DRY RUN, 不调 OSS API
3. --apply --confirm: 调 _oss_put_object + 成功路径
4. --apply 部分失败: 部分文件上传失败时返回 False
5. --cleanup: 删 retention_days 前 OSS 对象

纪律 (4 条):
1. 用 mock 不连真实 OSS (跟 backup_minio_daily.py 单测一致)
2. 不动 production script
3. 不依赖真实 env (env mock via monkeypatch.setenv)
4. 单 commit defer: test(backup): backup_to_aliyun_oss 单测覆盖 5 case
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 让 scripts/ 可 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from scripts.backup_to_aliyun_oss import (  # noqa: E402
    _build_auth_header,
    _oss_put_object,
    _scan_local_backups,
    apply_upload,
    cleanup_oss,
    scan_backups,
)


# ============================================================================
# 测试 1: --scan 列出本地备份
# ============================================================================

def test_scan_lists_local_backups(tmp_path, capsys):
    """scan_backups() 扫描本地 *.sql.gz + minio-daily/**/*.tar.gz"""
    # 准备: 创建 mock 备份文件
    db_backup = tmp_path / "microbubble_20260720.sql.gz"
    db_backup.write_bytes(b"PGDUMP_MOCK")
    minio_dir = tmp_path / "minio-daily" / "2026-07-20"
    minio_dir.mkdir(parents=True)
    tarball = minio_dir / "bucket.tar.gz"
    tarball.write_bytes(b"TAR_MOCK")

    # 不调 OSS API
    with patch("scripts.backup_to_aliyun_oss._oss_put_object") as mock_put:
        files = scan_backups(tmp_path)
        assert len(files) == 2
        assert db_backup in files
        assert tarball in files

    captured = capsys.readouterr()
    assert "本地备份扫描" in captured.out
    assert "总大小:" in captured.out
    # 关键: scan 不应该调 OSS API
    mock_put.assert_not_called()


# ============================================================================
# 测试 2: --apply 无 --confirm (DRY RUN)
# ============================================================================

def test_apply_without_confirm_is_dry_run(tmp_path, capsys):
    """apply_upload(confirm=False) 不调 OSS API"""
    db_backup = tmp_path / "test.sql.gz"
    db_backup.write_bytes(b"PGDUMP_MOCK")

    with patch("scripts.backup_to_aliyun_oss._oss_put_object") as mock_put:
        result = apply_upload(
            tmp_path, "test-bucket", "oss-cn-hangzhou.aliyuncs.com",
            "test-id", "test-secret", "cn-hangzhou", None, confirm=False,
        )
        assert result is True
        mock_put.assert_not_called()

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "无 --confirm" in captured.out


# ============================================================================
# 测试 3: --apply --confirm 成功路径
# ============================================================================

def test_apply_with_confirm_uploads_files(tmp_path):
    """apply_upload(confirm=True) 调 _oss_put_object per file"""
    db_backup = tmp_path / "test.sql.gz"
    db_backup.write_bytes(b"PGDUMP_MOCK")

    with patch("scripts.backup_to_aliyun_oss._oss_put_object") as mock_put:
        mock_put.return_value = True
        result = apply_upload(
            tmp_path, "test-bucket", "oss-cn-hangzhou.aliyuncs.com",
            "test-id", "test-secret", "cn-hangzhou", None, confirm=True,
        )
        assert result is True
        assert mock_put.call_count == 1
        # 验证 call args
        call = mock_put.call_args
        assert call[0][0] == "test-bucket"  # bucket
        assert call[0][1].endswith("test.sql.gz")  # remote key
        assert call[0][2] == b"PGDUMP_MOCK"  # body


# ============================================================================
# 测试 4: --apply 部分失败
# ============================================================================

def test_apply_partial_failure_returns_false(tmp_path):
    """apply_upload 部分文件失败 → return False"""
    db1 = tmp_path / "a.sql.gz"
    db1.write_bytes(b"A")
    db2 = tmp_path / "b.sql.gz"
    db2.write_bytes(b"B")

    with patch("scripts.backup_to_aliyun_oss._oss_put_object") as mock_put:
        # 第一次成功, 第二次失败
        mock_put.side_effect = [True, False]
        result = apply_upload(
            tmp_path, "test-bucket", "oss-cn-hangzhou.aliyuncs.com",
            "test-id", "test-secret", "cn-hangzhou", None, confirm=True,
        )
        assert result is False
        assert mock_put.call_count == 2


# ============================================================================
# 测试 5: --cleanup 删过期 OSS 对象
# ============================================================================

def test_cleanup_deletes_old_oss_objects():
    """cleanup_oss 删 retention_days 前对象, 保留新对象"""
    mock_objects = [
        {"key": "backups/old.sql.gz", "last_modified": "2020-01-01T00:00:00Z", "size": 100},
        {"key": "backups/new.sql.gz", "last_modified": "2026-07-21T00:00:00Z", "size": 200},
    ]
    with patch("scripts.backup_to_aliyun_oss._oss_list_objects") as mock_list, \
         patch("scripts.backup_to_aliyun_oss._oss_delete_object") as mock_delete:
        mock_list.return_value = mock_objects
        mock_delete.return_value = True
        deleted = cleanup_oss(
            30, "test-bucket", "oss-cn-hangzhou.aliyuncs.com",
            "test-id", "test-secret", "cn-hangzhou",
        )
        # 仅删 2020 的旧对象
        assert deleted == 1
        mock_delete.assert_called_once()
        assert mock_delete.call_args[0][1] == "backups/old.sql.gz"


# ============================================================================
# 测试 6: _build_auth_header 签名格式正确
# ============================================================================

def test_build_auth_header_signature_format():
    """Authorization header 包含 AWS4-HMAC-SHA256 + Credential + SignedHeaders + Signature"""
    auth = _build_auth_header(
        "GET", "https://test-bucket.oss-cn-hangzhou.aliyuncs.com/",
        "UNSIGNED-PAYLOAD", "",
        {}, "test-id", "test-secret", "cn-hangzhou",
    )
    assert auth.startswith("AWS4-HMAC-SHA256 ")
    assert "Credential=test-id/" in auth
    assert "SignedHeaders=" in auth
    assert "Signature=" in auth
    assert len(auth.split("Signature=")[1]) == 64  # hex SHA256 = 64 chars


# ============================================================================
# 测试 7: --scan 空目录 (无备份)
# ============================================================================

def test_scan_empty_directory(tmp_path, capsys):
    """scan_backups 在空目录返回空 list"""
    files = scan_backups(tmp_path)
    assert files == []
    captured = capsys.readouterr()
    assert "待上传文件: 0" in captured.out