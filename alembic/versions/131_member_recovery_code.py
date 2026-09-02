"""members 加恢复码列 — 用户自助重置密码 (2026-09-02)

背景: agent 曾静默改掉用户密码, 用户被锁死只能找管理员。本迁移给 members 加
recovery_code_hash (SHA-256) + recovery_code_generated_at 两列, 支持两处自助流程:
- 登录页「忘记密码」: username + 恢复码 + 新密码, 一步重置, 零人工介入
- 设置页「账号安全」: 生成/轮换恢复码 (明文仅显示一次)

Revision ID: 131_member_recovery_code
Revises: 130_meeting_chunks
Create Date: 2026-09-02
"""
from alembic import op

revision = "131_member_recovery_code"
down_revision = "130_meeting_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='members' AND column_name='recovery_code_hash'
            ) THEN
                ALTER TABLE members ADD COLUMN recovery_code_hash VARCHAR(255);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='members' AND column_name='recovery_code_generated_at'
            ) THEN
                ALTER TABLE members ADD COLUMN recovery_code_generated_at TIMESTAMP;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE members DROP COLUMN IF EXISTS recovery_code_generated_at"
    )
    op.execute(
        "ALTER TABLE members DROP COLUMN IF EXISTS recovery_code_hash"
    )
