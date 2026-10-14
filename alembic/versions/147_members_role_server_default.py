"""147: members.role / is_active 加 server_default（2026-10-14）

**Revision ID**: 147_members_role_server_default
**Revises**: 146_speaker_adjudications
**Create Date**: 2026-10-14

为什么
----
`MemberResponse.role: str` 是**非 Optional**，而 `members.role` 列**没有 DB 层默认值**：
`app/models/member.py` 只有 SQLAlchemy 侧的 ``default="member"``。

⇒ **任何裸 SQL INSERT（绕过 ORM）都会把 role 落成 NULL**，
⇒ pydantic 拒绝 None ⇒ ``GET /api/v1/members`` **整个端点 500**。

2026-10-14 实测踩中：新建成员 `肖佐林` 时用裸 SQL INSERT 漏了 role 列，
整个成员列表 500（不是那一个人坏，是端点整体挂）。
排查陷阱：traceback 行号指向 `member.py:83`（`resp.avatar = ...` 那行），
但实际报错字段是 `role` ⇒ **只看行号会往头像方向查错**。

同文件第 52-53 行的 ``drive_quota_bytes`` / ``drive_used_bytes``
**早已有 server_default** ⇒ 本仓对这类列一贯下沉到 DB 层，``role``/``is_active``
是漏的。本迁移补齐，与既有约定一致。

同时给 ``is_active`` 补默认值（``Boolean`` 列同样是裸 SQL 插入会落 NULL，
而 ``MemberResponse.is_active: bool`` 也非 Optional）。

**兼容性**：``SET DEFAULT`` 只影响**将来**的 INSERT，不动既有行。
既有 NULL 行由 146 之前的临时修复与本迁移的回填段一并处理（幂等）。

⚠️ revision id 必须 **≤32 字符**（`alembic_version.version_num` 在 CI 是
VARCHAR(32)；类 20.227）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "147_members_role_server_default"
down_revision: Union[str, None] = "146_speaker_adjudications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 回填既有 NULL（幂等；生产当前 0 行，但保证迁移在任何环境都安全）
    op.execute("UPDATE members SET role = 'member' WHERE role IS NULL")
    op.execute("UPDATE members SET is_active = true WHERE is_active IS NULL")

    op.alter_column(
        "members",
        "role",
        existing_type=sa.String(length=20),
        server_default="member",
        existing_nullable=True,
    )
    op.alter_column(
        "members",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=sa.true(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "members",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=True,
    )
    op.alter_column(
        "members",
        "role",
        existing_type=sa.String(length=20),
        server_default=None,
        existing_nullable=True,
    )