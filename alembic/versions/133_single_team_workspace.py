"""单一团队工作区 — 网盘去私有化数据迁移 (2026-09-05)

背景: 主拍决策「网盘只有一个团队空间, 不再有个人盘」。owner 列降级为纯溯源,
private 概念无报错退役。本迁移为纯数据迁移 (0 schema 变更), 配套服务层门禁放宽:

1. 软删 8 个 private 测试垃圾夹 (实测生产数据: 7×'diag_%' + 'alice_private_folder')
   及其下 drive 类 knowledge 条目;
2. 其余 folders visibility 归一 'team';
3. 所有在世顶级夹 is_team_default = true;
4. drive 类 knowledge visibility 归一 'team' + is_team_shared 回填 true。

Revision ID: 133_single_team_workspace
Revises: 132_flatten_member_role
Create Date: 2026-09-05
"""
from alembic import op

revision = "133_single_team_workspace"
down_revision = "132_flatten_member_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Step 1a: 先按名字软删已核实的 8 个测试垃圾夹 (7×diag_% + alice_private_folder)。
    # 生产数据可能略有出入, 故后续 Step 1c 再兜底清一遍全部 private 夹。
    op.execute(
        """
        UPDATE folders SET deleted_at = now(), updated_at = now()
        WHERE visibility = 'private' AND deleted_at IS NULL
          AND (name LIKE 'diag_%' OR name = 'alice_private_folder')
        """
    )

    # ── Step 1b: 软删上述刚被标记的 private 夹下的 drive 类 knowledge 条目。
    # 必须在 Step 2 归一 visibility='team' 之前跑, 子查询靠 visibility='private'
    # 才能圈定刚软删的那批夹 (夹本身 deleted_at IS NOT NULL)。
    op.execute(
        """
        UPDATE knowledge SET deleted_at = now(), updated_at = now()
        WHERE folder_id IN (
            SELECT id FROM folders
            WHERE visibility = 'private' AND deleted_at IS NOT NULL
        )
        AND deleted_at IS NULL
        """
    )

    # ── Step 1c: 兜底软删其余仍存活的 private 夹 (意图显式: 个人盘概念退役,
    # 生产上若还有名字不在核实清单里的 private 夹, 一并进垃圾桶)。
    op.execute(
        """
        UPDATE folders SET deleted_at = now(), updated_at = now()
        WHERE visibility = 'private' AND deleted_at IS NULL
        """
    )

    # ── Step 1d: 兜底软删上一步新圈出的 private 夹下的 drive 条目。
    op.execute(
        """
        UPDATE knowledge SET deleted_at = now(), updated_at = now()
        WHERE folder_id IN (
            SELECT id FROM folders
            WHERE visibility = 'private' AND deleted_at IS NOT NULL
        )
        AND deleted_at IS NULL
        """
    )

    # ── Step 2: 剩余非 team 夹 (含刚软删的 private 夹, 一致性归一) 全部 visibility='team'。
    op.execute(
        """
        UPDATE folders SET visibility = 'team', updated_at = now()
        WHERE visibility != 'team'
        """
    )

    # ── Step 3: 所有在世顶级夹置 is_team_default = true。
    # 列声明 NOT NULL server_default 'false', IS NOT true 同时兜住 NULL/False 两种脏值。
    op.execute(
        """
        UPDATE folders SET is_team_default = true, updated_at = now()
        WHERE parent_id IS NULL AND deleted_at IS NULL
          AND is_team_default IS NOT true
        """
    )

    # ── Step 4: drive 类 knowledge visibility 归一 'team' (kb 卡片不动)。
    op.execute(
        """
        UPDATE knowledge SET visibility = 'team'
        WHERE storage_mode = 'drive' AND visibility != 'team'
        """
    )

    # ── Step 5: drive 类 knowledge is_team_shared 回填 true (字段随本轮退役, 服务端恒置)。
    op.execute(
        """
        UPDATE knowledge SET is_team_shared = true
        WHERE storage_mode = 'drive' AND is_team_shared IS NOT true
        """
    )


def downgrade() -> None:
    # 纯数据翻转不可机械还原 (软删清单/原 visibility 归属未记录),
    # 如需回滚请从迁移前备份恢复 (scripts/backup_db.sh 每日快照)。
    pass
