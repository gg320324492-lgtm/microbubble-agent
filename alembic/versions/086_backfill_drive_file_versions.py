"""backfill drive_file_versions for W84 C-1 historical files (W85 第 1 批 C-1 数据回填 主拍签字)

锚点范式: W84 第 1 批 C-1 313 → W85 第 1 批 C-1 320 守恒 (+1, 数据回填不计 0 例外之外)

背景:
- W84 第 1 批 C-1 commit `cecbad6925` (2026-07-28 23:07:48+08:00) 在 DriveService.create_file()
  + DriveService.create_instant_upload() 注入 create_initial_version() 调用
- W84 C-1 之前上传的历史 drive_files (storage_mode='drive') 无 drive_file_versions 记录
- 本次 alembic data migration 回填 W84 C-1 之前所有历史 drive_files 的 v1 版本记录

串单链: down_revision = '085_billing_payment_tables' (W74 第 1 批 B-2 085 接续, 当前 HEAD)

派工前提铁律 12 第 11 条实战 (W82 B-1 P1 084 实战 + 类 20.13 拦截铁律):
- 部署前必跑 alembic chain verify, 必须 1 head
- merge 后立即 verify (1852468a6 commit 修复教训)

派工前提铁律 12 第 9 条实战:
- 数据回填涉及生产数据, 必须主拍签字 + staging 验证 + production 备份
- comment 字段填 "Backfilled by W85 C-1 (主拍签字)" → 未来可识别+可回滚

派工 v6 §1.2 范畴:
- 仅新增 alembic data migration (不破坏 schema 也不动老路径)
- W82 B-1 / W83 B-1 / W84 B-1 + W84 C-1 实战代码不动

0 production code 改动铁律: 例外 1 已批 (C-1 数据回填, 主拍决策)
"""
from alembic import op
from sqlalchemy import text


# revision identifiers
revision = "086_backfill_drive_file_versions"
down_revision = "085_billing_payment_tables"
branch_labels = None
depends_on = None


# W84 第 1 批 C-1 commit 时间戳 (commit `cecbad6925`)
# 早于该时间戳的 drive_files 均无 v1 版本记录, 需回填
W84_C1_COMMIT_TS = "2026-07-28 23:07:48+08:00"

BACKFILL_COMMENT = "Backfilled by W85 C-1 (主拍签字)"


def upgrade() -> None:
    """回填 W84 C-1 之前所有 drive_files 的初始 v1 版本记录"""
    conn = op.get_bind()

    # 1. 找 W84 C-1 之前的所有 drive_files (storage_mode='drive' 且 created_at < commit ts)
    #    同时排除已有 v1 版本记录的文件 (幂等: 重跑无副作用)
    result = conn.execute(
        text(
            """
            SELECT k.id, k.created_at, k.created_by, k.file_path, COALESCE(k.file_size, 0)
            FROM knowledge k
            WHERE k.storage_mode = 'drive'
              AND k.deleted_at IS NULL
              AND k.created_at < :w84_ts
              AND NOT EXISTS (
                  SELECT 1 FROM drive_file_versions v
                  WHERE v.file_id = k.id AND v.version_number = 1
              )
            ORDER BY k.id
            """
        ),
        {"w84_ts": W84_C1_COMMIT_TS},
    )
    historical_files = result.fetchall()

    # 2. 对每个文件插入 1 条 drive_file_versions v1 记录
    inserted = 0
    skipped_no_path = 0
    for row in historical_files:
        file_id, created_at, created_by, file_path, file_size = row

        # 边界保护: file_path 为 NULL 的 drive_file 没有 MinIO object, 无法回填
        if not file_path:
            skipped_no_path += 1
            continue

        # created_by 可能为 NULL (历史数据); fallback 'system' 注释, 但 uploader_id NOT NULL
        # 这里 created_by 为 Integer FK to members.id — 找一个真实存在的 member 作 fallback
        # 实在没有就用 1 (admin 种子, 必存在)
        uploader_id = created_by if created_by is not None else 1

        conn.execute(
            text(
                """
                INSERT INTO drive_file_versions
                    (file_id, version_number, minio_object_key, size,
                     uploader_id, comment, is_current)
                VALUES
                    (:file_id, 1, :minio_object_key, :size,
                     :uploader_id, :comment, 1)
                """
            ),
            {
                "file_id": file_id,
                "minio_object_key": file_path,
                "size": file_size,
                "uploader_id": uploader_id,
                "comment": BACKFILL_COMMENT,
            },
        )
        inserted += 1

    print(
        f"[086_backfill_drive_file_versions] inserted={inserted} "
        f"skipped_no_path={skipped_no_path}"
    )


def downgrade() -> None:
    """删除 W85 C-1 回填的版本记录 (按 comment 标记精确删除, 不影响未来手动 v1)"""
    conn = op.get_bind()
    conn.execute(
        text(
            """
            DELETE FROM drive_file_versions
            WHERE comment = :comment
            """
        ),
        {"comment": BACKFILL_COMMENT},
    )