"""Drive v2 PR16 — workspace 回收站 file_versions 保留期清理 (2026-07-24, W68 第 13 批 C-3)

背景 (W68 第 4 批 #2 agent 调研发现):
- 当前 drive_file_versions 表: file 软删 (Knowledge.deleted_at) 后, 关联 file_versions 行
  没有自动清理机制 (Knowledge.file_id FK ON DELETE CASCADE 不会触发, 因 Knowledge 是软删).
- 后果: admin 删文件 → file_versions 变孤儿, minio_object_key 永久指向已删对象 (浪费磁盘)
- file_versions 表持续膨胀 (长期积累后查询性能下降 + MinIO 配额压力)

设计:
- 加 2 列:
  * drive_file_versions.purged_at: TIMESTAMP NULL
    - NULL = 活跃版本 (正常业务可见)
    - 非 NULL = 已软删 (Celery 30 天保留后物理删除, 但 audit window 内可恢复)
  * drive_file_versions.purged_by: INT NULL FK members.id
    - 谁触发的删除 (Celery auto / admin manual / service), audit 追溯
- 加 GIN trgm 索引? 不需要 (deleted_at/purged_at 都是精确时间查询, B-tree 索引足够)
- 加 (purged_at) B-tree 索引: 高频 `WHERE purged_at IS NULL` 过滤

策略 (与 chat_history 30 天保留对齐):
1. workspace admin 软删 file → Knowledge.deleted_at = now()
2. drive_file_versions 行立即可见 (purged_at = NULL), 但 list_versions API 应过滤 (本 PR 范围外)
3. Celery 每日 04:00 跑: 找 file_versions JOIN Knowledge
   WHERE Knowledge.deleted_at < (now - 30 days) AND v.purged_at IS NULL
   → set v.purged_at = now (软删)
4. 下次再跑 (30 天后): 找 v.purged_at < (now - 30 days)
   → hard DELETE (物理删 MinIO 对象 + DB 行)

依赖:
- 063_drive_file_versions: drive_file_versions 表必须存在
- 069_drive_comments_recursive_func: 当前 main HEAD, 串单链接续 (CLAUDE.md W68 第 4 批纪律)

下接: PR17+ 继续 (mention dedup / soft delete batch / 跨 PR CI)

实施纪律:
- 0 production code 改动铁律 (W68 第 13 批): 纯新功能, 不动 PR9/PR10/PR11/PR12 老逻辑
- W68 第 4 批 串单链纪律: down_revision 接 069_drive_comments_recursive_func
  merge 后 verify ScriptDirectory.get_heads() == ['070_drive_version_retention']
  期望只 1 个 head (CLAUDE.md W68 第 4 批纪律 + memory/w68-alembic-chain-discipline-2026-07-24.md)
- 不破坏老 file_versions 行 (NULL 默认值兼容)
- purged_by 用 RESTRICT FK (保留 member 行可审计, 不被 member 删除级联)
- settings 新增 DRIVE_VERSION_RETENTION_DAYS = 30 (本迁移不加, 留 app/config.py 单独提交)
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "070_drive_version_retention"
down_revision: Union[str, None] = "069_drive_comments_recursive_func"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # === 1. drive_file_versions.purged_at 列 ===
    # NULL = 活跃, 非 NULL = 已软删 (Celery 30 天后物理删除)
    # 兼容老行 (已有 file_versions 行的 purged_at 默认 NULL)
    op.add_column(
        "drive_file_versions",
        sa.Column(
            "purged_at",
            sa.TIMESTAMP(),
            nullable=True,
            comment="软删时间 (NULL=活跃, 非 NULL=Celery 已标记待清理)",
        ),
    )

    # === 2. drive_file_versions.purged_by 列 ===
    # INT FK members.id, 谁触发删除 (admin manual / Celery auto / service)
    # RESTRICT FK: 删 member 行前必须先清 file_versions.purged_by (审计完整性)
    op.add_column(
        "drive_file_versions",
        sa.Column(
            "purged_by",
            sa.Integer(),
            nullable=True,
            comment="触发软删的 member.id (Celery auto-purge 写系统用户 / admin manual 写真实用户)",
        ),
    )
    op.create_foreign_key(
        "fk_drive_file_versions_purged_by",
        "drive_file_versions",
        "members",
        ["purged_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    # === 3. (purged_at) B-tree 索引 ===
    # 高频: Celery task 跑 `WHERE purged_at IS NULL` + JOIN Knowledge
    # B-tree 索引对精确时间查询足够, 不需要 GIN trgm
    op.create_index(
        "ix_drive_file_versions_purged_at",
        "drive_file_versions",
        ["purged_at"],
        unique=False,
    )

    # === 4. (purged_at, file_id) 复合索引 ===
    # 用途: Celery 30 天后物理删除 step 2: `WHERE purged_at < cutoff AND purged_at IS NOT NULL`
    #       + admin endpoint stats: GROUP BY file_id 算每个文件剩余版本数
    op.create_index(
        "ix_drive_file_versions_purged_at_file_id",
        "drive_file_versions",
        ["purged_at", "file_id"],
        unique=False,
    )


def downgrade() -> None:
    # 顺序: 先 drop 复合索引 → 单列索引 → FK → 列
    op.drop_index(
        "ix_drive_file_versions_purged_at_file_id",
        table_name="drive_file_versions",
    )
    op.drop_index(
        "ix_drive_file_versions_purged_at",
        table_name="drive_file_versions",
    )
    op.drop_constraint(
        "fk_drive_file_versions_purged_by",
        "drive_file_versions",
        type_="foreignkey",
    )
    op.drop_column("drive_file_versions", "purged_by")
    op.drop_column("drive_file_versions", "purged_at")