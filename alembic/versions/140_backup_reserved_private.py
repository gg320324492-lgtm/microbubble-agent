"""140: ZB-1 备份隐私隔离 — 保留区 (backups/ 根子树) 内存量 drive 行刷 visibility='private'

背景 (工单 ZB-1 / ZB 恢复演练发现 ①): 零感托管备份把加密容器与解密钥匙 key.json
一起传到用户网盘 backups/ 目录。2026-09「单一团队空间」改造后 create_file 硬置
is_team_shared=True 且列表恒不过滤, 导致全组成员可见他人备份钥匙 (真实安全缺陷)。

本迁移 (与 app/services/drive_service.py 的保留区判定同语义, 服务端代码 ZB-1 同步落地):
- 保留区定义: 顶层目录名归一 (去首尾空白 + lower) 后等于 'backups' 的 folders 根,
  及其全部存活子目录 (与桌面端 auto-provision.ts `CLOUD_BACKUP_ROOT = 'backups'` 对齐)
- 把该子树内 storage_mode='drive' 的 knowledge 行 visibility 刷为 'private'
  (容器 .mnbbak 与 key.json 同目录同命名, 一并覆盖)
- **只动保留区内的行**; 区外一行不碰 (区外 private 行不回填不新增)
- 含软删行 (deleted_at 非空也算——它们仍可被 restore, 泄露面一致)

影响面: 迁移后保留区文件在「团队共享盘」视图对非 owner 消失 (符合预期);
负责人本人是 owner (created_by), 不受影响。
downgrade 可逆: 把保留区内 visibility='private' 的行刷回 'team'
(注意: 若 upgrade 前保留区内本就存在 private 行, downgrade 后无法区分——
当前库内不存在该形态, 133 已把全部存量刷成 team; 此限制已在 docstring 声明)。

Revision ID: 140_backup_reserved_private
Revises: 139_drop_wechat_fields
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "140_backup_reserved_private"
down_revision: Union[str, None] = "139_drop_wechat_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 保留区根: 顶层目录名归一后等于 'backups' (与 drive_service.BACKUP_RESERVED_ROOT_NAME 对齐)
_RESERVED_ROOT_FILTER = "lower(btrim(name)) = 'backups'"

# 保留区子树 CTE (根 + 全部存活后代), 与 drive_service._is_backup_reserved_folder 同语义
_RESERVED_CTE = f"""
WITH RECURSIVE reserved_folders AS (
    SELECT id FROM folders
    WHERE parent_id IS NULL AND deleted_at IS NULL AND {_RESERVED_ROOT_FILTER}
    UNION ALL
    SELECT f.id FROM folders f
    JOIN reserved_folders rf ON f.parent_id = rf.id
    WHERE f.deleted_at IS NULL
)
SELECT id FROM reserved_folders
"""


def upgrade() -> None:
    # 保留区内全部 drive 行 (含软删) → private; 区外一行不碰
    op.execute(
        """
        UPDATE knowledge k
        SET visibility = 'private'
        WHERE k.storage_mode = 'drive'
          AND k.folder_id IN (""" + _RESERVED_CTE + """)
        """
    )


def downgrade() -> None:
    # 可逆: 保留区内 private 行刷回 'team' (单一团队空间的默认可见性)。
    # 局限: 无法区分「本迁移刷成 private」与「理论上 upgrade 前已是 private」的行;
    # 后者在当前库中不存在 (迁移 133 已把全部存量 drive 行刷成 team), 故可逆性成立。
    op.execute(
        """
        UPDATE knowledge k
        SET visibility = 'team'
        WHERE k.storage_mode = 'drive'
          AND k.visibility = 'private'
          AND k.folder_id IN (""" + _RESERVED_CTE + """)
        """
    )
