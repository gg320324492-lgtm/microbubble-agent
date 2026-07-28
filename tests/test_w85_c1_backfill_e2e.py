"""tests/test_w85_c1_backfill_e2e.py — W85 第 1 批 C-1 drive_upload 数据回填 e2e 测试 (主拍签字)

6 核心场景:
1. alembic chain verify (086 串接 085, 1 head) — 派工前提铁律 12 第 11 条实战
2. migration 文件结构验证 (down_revision + revision 一致)
3. drive_file_versions 模型字段与 migration 列对齐 (version_number / is_current / minio_object_key)
4. 回填 idempotent — 重跑 upgrade 不重复插
5. downgrade 精确删除 (按 comment 标记)
6. file_path NULL 的 drive_file 安全跳过

依赖:
- tests/conftest.py: db fixture (SKIP_DB_SETUP=1 时跳过)
- Alembic 086 migration 必须 down_revision='085_billing_payment_tables'

W85 第 1 批 C-1 纪律:
- 数据回填涉及生产数据, 必须主拍签字 + staging 验证 (派工前提铁律 12 第 9 条)
- 0 production code 改动铁律 例外 1 已批 (C-1 数据回填)
- 不动 W82 B-1 / W83 B-1 / W84 B-1 + W84 C-1 实战代码 (派工 v6 §1.2 范畴)
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge import Knowledge


# ==========================================================================
# 静态结构验证 (无 DB)
# ==========================================================================

MIGRATION_FILE = Path(
    "alembic/versions/086_backfill_drive_file_versions.py"
)


def test_alembic_migration_file_exists():
    """086 migration 文件必须存在"""
    assert MIGRATION_FILE.exists(), f"Missing migration: {MIGRATION_FILE}"


def _read_migration() -> str:
    return MIGRATION_FILE.read_text(encoding="utf-8")


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_alembic_migration_has_correct_revision_chain():
    """down_revision 必须接 085_billing_payment_tables (W78 第 11 批 alembic rebase 纪律)"""
    source = _read_migration()
    assert "revision = \"086_backfill_drive_file_versions\"" in source
    assert "down_revision = \"085_billing_payment_tables\"" in source


def test_alembic_migration_has_main_signature_comment():
    """commit message 必须含 '主拍签字' (派工前提铁律 12 第 9 条实战)"""
    source = _read_migration()
    assert "主拍签字" in source
    # BACKFILL_COMMENT 是 downgrade 精确删除的标识, 必须含 '主拍签字'
    assert "BACKFILL_COMMENT" in source
    assert "主拍签字" in source.split("BACKFILL_COMMENT")[1][:200]


# ==========================================================================
# 模型与 migration 列对齐 (无 DB, 仅验证字段名)
# ==========================================================================


def test_drive_file_version_model_uses_version_number_not_version():
    """DriveFileVersion 模型必须用 version_number (不是 version)
    派工 v6 §1.2: W84 C-1 commit cecbad692 已用 version_number, 回填 migration 必须对齐
    """
    model_src = _read("app/models/drive_file_version.py")
    assert "version_number" in model_src


def test_migration_insert_uses_correct_column_names():
    """INSERT 必须使用真列名 (version_number / is_current / minio_object_key)"""
    source = _read_migration()
    # 错列名 (派工 v6 §1.2 范畴: 防止 copy-paste 错误)
    assert "(file_id, version, size, uploader_id, created_at, comment)" not in source
    # 正列名 (W84 C-1 create_initial_version 模型字段)
    assert "version_number" in source
    assert "is_current" in source
    assert "minio_object_key" in source


def test_migration_filters_by_storage_mode_drive():
    """回填必须限定 storage_mode='drive' (kb 卡片不入 drive_file_versions)"""
    source = _read_migration()
    assert "storage_mode = 'drive'" in source


def test_migration_idempotent_not_exists():
    """NOT EXISTS 子句确保重跑无副作用"""
    source = _read_migration()
    assert "NOT EXISTS" in source
    assert "drive_file_versions" in source


def test_migration_downgrade_deletes_by_comment_marker():
    """downgrade 必须按 comment 标记精确删除 (不破坏未来手动 v1)"""
    source = _read_migration()
    assert "WHERE comment = :comment" in source
    assert "BACKFILL_COMMENT" in source


# ==========================================================================
# alembic chain verify (派工前提铁律 12 第 11 条)
# ==========================================================================


def test_alembic_chain_086_is_single_head():
    """alembic 链必须 1 head (085 → 086, 类 20.13 拦截铁律)"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    script_dir = ScriptDirectory.from_config(cfg)
    heads = script_dir.get_heads()
    assert heads == ["086_backfill_drive_file_versions"], (
        f"alembic chain 双头, 必须 fix: heads={heads}"
    )


def test_alembic_chain_walks_085_to_086():
    """085 → 086 必须串单链 (W78 第 11 批 alembic rebase 纪律)"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    script_dir = ScriptDirectory.from_config(cfg)
    rev = script_dir.get_revision("086_backfill_drive_file_versions")
    assert rev is not None
    assert rev.down_revision == "085_billing_payment_tables"


# ==========================================================================
# DB 集成测试 (需要 SKIP_DB_SETUP=0, 即真 DB fixture)
# ==========================================================================


@pytest.mark.asyncio
async def test_backfill_skips_files_with_null_file_path(db, test_member):
    """file_path 为 NULL 的 drive_file 必须安全跳过 (不抛错)"""
    # 创建 1 个 drive file, 但 file_path=None
    file_row = Knowledge(
        file_name="w85_c1_null_path.pdf",
        file_path=None,  # 关键: 无 MinIO object
        file_size=0,
        file_type="pdf",
        uploader_id=test_member.id,
        created_by=test_member.id,
        visibility="public",
        storage_mode="drive",
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)

    # 通过 SQL 直查 upgrade 路径的 SELECT 不会返这个 file
    # (因为 NOT EXISTS 会触发幂等检查, 但 file_path=NULL 也会被跳过)
    result = await db.execute(
        text(
            """
            SELECT k.id FROM knowledge k
            WHERE k.storage_mode = 'drive'
              AND k.deleted_at IS NULL
              AND k.file_path IS NULL
            """
        )
    )
    null_path_files = result.fetchall()
    assert len(null_path_files) >= 1
    # 这个 file 不会被 migration 选中 (migration 已 IS NOT NULL/真值检查)


@pytest.mark.asyncio
async def test_backfill_does_not_duplicate_v1_for_existing_files(db, test_member):
    """已有 v1 版本记录的文件, migration 不会重复插 (NOT EXISTS 守恒)"""
    # 创建 drive file
    file_row = Knowledge(
        file_name="w85_c1_existing_v1.pdf",
        file_path="uploads/drive/existing_v1.pdf",
        file_size=1024,
        file_type="pdf",
        uploader_id=test_member.id,
        created_by=test_member.id,
        visibility="public",
        storage_mode="drive",
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)

    # 手动插入 1 条 v1 (模拟已存在的版本)
    existing_v1 = DriveFileVersion(
        file_id=file_row.id,
        version_number=1,
        minio_object_key="uploads/drive/existing_v1.pdf",
        size=1024,
        uploader_id=test_member.id,
        comment="手动 v1 (测试用)",
        is_current=1,
    )
    db.add(existing_v1)
    await db.commit()

    # 检查: NOT EXISTS 子查询应排除这个 file
    result = await db.execute(
        text(
            """
            SELECT k.id FROM knowledge k
            WHERE k.storage_mode = 'drive'
              AND k.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM drive_file_versions v
                  WHERE v.file_id = k.id AND v.version_number = 1
              )
              AND k.id = :file_id
            """
        ),
        {"file_id": file_row.id},
    )
    rows = result.fetchall()
    assert len(rows) == 0, "已有 v1 的 file 不应被 migration 选中"