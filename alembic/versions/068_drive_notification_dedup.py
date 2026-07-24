"""Persistent de-duplication for combined @mention/reaction notifications."""
from alembic import op
import sqlalchemy as sa

revision = "068_drive_notification_dedup"
down_revision = "067_drive_reactions"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "drive_notification_dedup",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("actions_hash", sa.String(64), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "comment_id", "actions_hash", name="uq_drive_notification_dedup"),
    )
    op.create_index("ix_drive_notification_dedup_user_id", "drive_notification_dedup", ["user_id"])
    op.create_index("ix_drive_notification_dedup_comment_id", "drive_notification_dedup", ["comment_id"])

def downgrade() -> None:
    op.drop_index("ix_drive_notification_dedup_comment_id", table_name="drive_notification_dedup")
    op.drop_index("ix_drive_notification_dedup_user_id", table_name="drive_notification_dedup")
    op.drop_table("drive_notification_dedup")
