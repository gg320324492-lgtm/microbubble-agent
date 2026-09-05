"""批次⑩.2 人名文件夹内容归属修正 (2026-09-05, 用户拍板)

背景: 组会PPT 下的人名文件夹及其中历史文件当初由王天志批量上传/创建,
created_by 全挂在王天志名下; 135 已把文件夹 owner 改为同名成员。

本迁移:
1. 无同名成员的人名文件夹 (冯懿鑫/艾琳朔) → owner 改为杜同贺 (dutonghe)。
2. 文件归属跟随文件夹: 每个团队盘一级人名文件夹 (含其全部子孙层) 里的
   未删文件 created_by → 该文件夹的 owner_id。即 "胡小琪文件夹里的文件,
   上传人就是胡小琪"; 冯懿鑫/艾琳朔的文件上传人为杜同贺。
   只调整团队盘一级人名文件夹层, 组会PPT 根直属文件不动。

幂等: 重复执行时 created_by 已等于目标值, UPDATE 命中 0 行。

Revision ID: 136_member_folder_file_attribution
Revises: 135_drive_folder_stars
Create Date: 2026-09-05
"""
from alembic import op

revision = "136_member_folder_file_attribution"
down_revision = "135_drive_folder_stars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 无同名成员的人名文件夹 → 杜同贺 ──
    op.execute(
        """
        UPDATE folders f
        SET owner_id = (SELECT id FROM members WHERE username = 'dutonghe' LIMIT 1)
        WHERE f.deleted_at IS NULL
          AND f.parent_id IN (SELECT id FROM folders WHERE is_team_default)
          AND NOT EXISTS (SELECT 1 FROM members m WHERE m.name = f.name)
        """
    )

    # ── 2. 文件归属跟随文件夹 (人名文件夹 + 其子孙层, path 前缀递归) ──
    op.execute(
        """
        UPDATE knowledge k
        SET created_by = fa.owner_id
        FROM (
            SELECT f.id AS folder_id, f.owner_id, f.path
            FROM folders f
            WHERE f.deleted_at IS NULL
              AND f.parent_id IN (SELECT id FROM folders WHERE is_team_default)
        ) fa
        JOIN folders f2 ON f2.path LIKE fa.path || '%'
        WHERE k.folder_id = f2.id
          AND k.deleted_at IS NULL
          AND k.created_by IS DISTINCT FROM fa.owner_id
        """
    )


def downgrade() -> None:
    # 数据修正不可逆 (原始 created_by 已被覆盖), downgrade 为空操作
    pass
