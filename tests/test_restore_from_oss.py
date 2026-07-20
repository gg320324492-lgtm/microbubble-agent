"""
test_restore_from_oss.py — W16 T1 阿里云 OSS 恢复脚本单测

覆盖 (5 case):
1. --scan: 列出 OSS 最新备份 (mock _oss_list_objects, 验 dry-run)
2. --scan 无可用备份: 返 1 报错
3. --verify: RTO estimate < 1h (Phase 8.4 SLA)
4. --verify 超 1h: SLA fail 时返 1
5. --apply --confirm: 调 _oss_get_object + 写入本地 + SHA-256 校验

纪律 (4 条):
1. 用 mock 不连真实 OSS (跟 backup_to_aliyun_oss.py + backup_minio_daily.py 单测一致)
2. 不动 production script (只测 helper + main CLI)
3. 不依赖真实 env (env mock via monkeypatch.setenv)
4. 单 commit defer: test(restore): restore_from_oss 单测覆盖 5 case
"""
import gzip
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 让 scripts/ 可 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from scripts.restore_from_oss import (  # noqa: E402
    RTO_TARGET_SECONDS,
    _oss_get_object,
    _oss_list_objects,
    download_backup,
    main,
    select_latest_backup,
    verify_local_file,
)


# ============================================================================
# 测试 1: --scan 列出 OSS 最新备份 (dry-run)
# ============================================================================

def test_scan_returns_latest_backup(monkeypatch, capsys):
    """--scan 应列 OSS 上最新 DB 备份 + 打印 age + DRY RUN 警告."""
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "test-secret")
    monkeypatch.setenv("ALIYUN_OSS_BUCKET", "test-bucket")
    monkeypatch.setenv("ALIYUN_OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")

    # Mock OSS list: 返 2 个备份 (按 last_modified desc 排序, 取最新)
    fake_objects = [
        {
            "key": "backups/microbubble_20260721.sql.gz",
            "last_modified": "2026-07-21T10:00:00Z",
            "size": 1024 * 1024 * 100,  # 100 MB
            "etag": "fake-etag-1",
        },
        {
            "key": "backups/microbubble_20260720.sql.gz",
            "last_modified": "2026-07-20T10:00:00Z",
            "size": 1024 * 1024 * 80,  # 80 MB
            "etag": "fake-etag-2",
        },
    ]
    with patch("scripts.restore_from_oss._oss_list_objects", return_value=fake_objects):
        exit_code = main(["--scan"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "OSS DB 备份扫描" in captured.out
    assert "test-bucket" in captured.out
    assert "oss-cn-hangzhou.aliyuncs.com" in captured.out
    # 最新备份 (按 last_modified desc 排序)
    assert "microbubble_20260721.sql.gz" in captured.out
    assert "DRY RUN" in captured.out


def test_scan_no_backup_available(monkeypatch, capsys):
    """OSS 上无备份时 --scan 返 1."""
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "test-secret")

    with patch("scripts.restore_from_oss._oss_list_objects", return_value=[]):
        exit_code = main(["--scan"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "没有 DB 备份" in captured.out


# ============================================================================
# 测试 2: --verify RTO estimate < 1h (Phase 8.4 SLA)
# ============================================================================

def test_verify_rto_meets_sla(monkeypatch, capsys):
    """--verify 验 RTO SLA: < 1h (Phase 8.4 SLA)."""
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "test-secret")

    # Mock: 1 GB 备份 (size_mb = 1024)
    fake_objects = [
        {
            "key": "backups/backup_1GB.sql.gz",
            "last_modified": "2026-07-21T10:00:00Z",
            "size": 1024 * 1024 * 1024,
            "etag": "fake",
        },
    ]
    with patch("scripts.restore_from_oss._oss_list_objects", return_value=fake_objects):
        exit_code = main(["--verify"])

    # 1 GB / 50 MB/s + 1 GB × 0.5 s/MB ≈ 20s + 512s ≈ 532s < 3600s SLA
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "RTO Estimate" in captured.out
    assert "RTO SLA: < 3600s (1h)" in captured.out
    assert "✅" in captured.out  # SLA met


def test_verify_rto_fails_sla_for_huge_backup(monkeypatch, capsys):
    """--verify 100 GB 备份 RTO 远超 1h SLA → 返 1."""
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "test-secret")

    # 100 GB 备份 (size_mb = 102400)
    # Download: 102400 / 50 = 2048s + Restore: 102400 * 0.5 = 51200s
    # 总 RTO ≈ 53248s (14.8h) > 1h SLA
    fake_objects = [
        {
            "key": "backups/backup_huge.sql.gz",
            "last_modified": "2026-07-21T10:00:00Z",
            "size": 100 * 1024 * 1024 * 1024,
            "etag": "fake",
        },
    ]
    with patch("scripts.restore_from_oss._oss_list_objects", return_value=fake_objects):
        exit_code = main(["--verify"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "✗" in captured.out  # SLA not met
    assert "RTO SLA: < 3600s (1h)" in captured.out


# ============================================================================
# 测试 3: --apply --confirm 调 _oss_get_object + 写本地 + 校验
# ============================================================================

def test_apply_with_confirm_downloads_and_writes_local_file(monkeypatch, tmp_path, capsys):
    """--apply --confirm 应调 _oss_get_object + 写入 dest-dir + 校验 SHA-256."""
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "test-secret")
    monkeypatch.setenv("ALIYUN_OSS_BUCKET", "test-bucket")
    monkeypatch.setenv("ALIYUN_OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")

    fake_body = b"PGDUMP_BINARY_CONTENT_X" * 100
    fake_objects = [
        {
            "key": "backups/backup_test.sql.gz",
            "last_modified": "2026-07-21T10:00:00Z",
            "size": len(fake_body),
            "etag": "fake",
        },
    ]

    with patch("scripts.restore_from_oss._oss_list_objects", return_value=fake_objects), \
         patch("scripts.restore_from_oss._oss_get_object", return_value=fake_body):
        exit_code = main(["--apply", "--confirm", "--dest-dir", str(tmp_path)])

    assert exit_code == 0
    captured = capsys.readouterr()

    # 本地文件应被创建 + 校验通过
    local_file = tmp_path / "backup_test.sql.gz"
    assert local_file.exists()
    assert local_file.read_bytes() == fake_body
    assert "下载完成" in captured.out
    assert "SHA-256:" in captured.out


def test_apply_without_confirm_returns_dry_run(monkeypatch, capsys):
    """--apply 无 --confirm 应 DRY RUN (返 1, 不下载)."""
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "test-secret")

    with patch("scripts.restore_from_oss._oss_list_objects", return_value=[]):
        exit_code = main(["--apply"])  # 无 --confirm

    # DRY RUN 默认返 1 (跟 backup_to_aliyun_oss.py 一致)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "--confirm" in captured.out


# ============================================================================
# 测试 4: helper unit tests (download_backup / verify_local_file)
# ============================================================================

def test_download_backup_writes_to_local(tmp_path, monkeypatch):
    """download_backup 应写本地文件 + 返回 Path."""
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "test-secret")

    fake_body = b"OSS_DOWNLOAD_BODY"
    with patch("scripts.restore_from_oss._oss_get_object", return_value=fake_body):
        result = download_backup(
            bucket="test-bucket",
            key="backups/test.sql.gz",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            access_key_id="test-id",
            access_key_secret="test-secret",
            region="cn-hangzhou",
            dest_dir=tmp_path,
        )

    assert result is not None
    assert result.exists()
    assert result.read_bytes() == fake_body


def test_verify_local_file_size_and_sha256(tmp_path):
    """verify_local_file 校验 size + 算 SHA-256."""
    fake_body = b"VERIFY_THIS_CONTENT" * 50
    test_file = tmp_path / "verify_test.sql.gz"
    test_file.write_bytes(fake_body)

    expected_size = len(fake_body)
    result = verify_local_file(test_file, expected_size)

    assert result["ok"] is True
    assert result["size"] == expected_size
    import hashlib
    expected_sha256 = hashlib.sha256(fake_body).hexdigest()
    assert result["sha256"] == expected_sha256


def test_verify_local_file_size_mismatch(tmp_path):
    """verify_local_file 大小不符应返 ok=False."""
    test_file = tmp_path / "mismatch.sql.gz"
    test_file.write_bytes(b"short")

    result = verify_local_file(test_file, 999)  # 期望大小不符

    assert result["ok"] is False
    assert "size mismatch" in result["error"]


# ============================================================================
# 测试 5: 缺 env var 应报错
# ============================================================================

def test_missing_env_returns_error(monkeypatch, capsys):
    """缺 ALIYUN_OSS_ACCESS_KEY_ID 应返 1."""
    monkeypatch.delenv("ALIYUN_OSS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("ALIYUN_OSS_ACCESS_KEY_SECRET", raising=False)

    exit_code = main(["--scan"])

    assert exit_code == 1
    captured = capsys.readouterr()
    # 错误信息走 stderr (跟 backup_to_aliyun_oss.py 范式一致)
    assert "缺 ALIYUN_OSS_ACCESS_KEY_ID" in captured.err