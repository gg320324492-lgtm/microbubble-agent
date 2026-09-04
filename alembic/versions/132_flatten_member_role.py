"""成员角色扁平化 — 废除管理员/组长等级 (2026-09-05)

背景: 课题组决定所有成员一律等权，不再区分 admin/leader/member 权限等级。
成员对外只带年级身份称谓 (导师/博士/硕士/本科生/校友, 由 members.grade 派生,
代码层 app/core/member_identity.member_status 统一计算)。

本迁移把所有非 'member' 的 role 值归一为 'member' (users/meetings/projects 等其他
表的 role 字段与账号权限无关, 不动)。role 列本身保留 (历史数据 + 回滚成本),
代码中不再据其做任何权限判断。

Revision ID: 132_flatten_member_role
Revises: 131_member_recovery_code
Create Date: 2026-09-05
"""
from alembic import op

revision = "132_flatten_member_role"
down_revision = "131_member_recovery_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 归一所有账号角色; downgrade 无法还原历史 admin/leader 归属, 故为单向数据迁移
    op.execute("UPDATE members SET role = 'member' WHERE role IS DISTINCT FROM 'member'")


def downgrade() -> None:
    # 数据不可逆 (原 admin/leader 归属未记录), 结构无变化 → no-op
    pass
