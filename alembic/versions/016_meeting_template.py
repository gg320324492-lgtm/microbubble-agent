"""Create meeting_templates table + seed 4 builtin templates

Wave 3b: 会议模板（组会/一对一/立项会/自由 + 用户自建）
"""
import json

from alembic import op
import sqlalchemy as sa


revision = "016_meeting_template"
down_revision = "015_reminder_task_id_nullable"


def upgrade():
    op.create_table(
        "meeting_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, index=True),
        sa.Column("title_template", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agenda", sa.JSON, nullable=True),
        sa.Column("default_duration_minutes", sa.Integer, nullable=True, server_default="60"),
        sa.Column("default_participant_ids", sa.JSON, nullable=True),
        sa.Column("default_location", sa.String(200), nullable=True),
        sa.Column("is_builtin", sa.Boolean, nullable=True, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=True, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    op.create_index("idx_meeting_template_active", "meeting_templates", ["is_active"])

    # Seed 4 builtin templates（幂等：先查再插）
    bind = op.get_bind()
    builtin = [
        {
            "name": "组会",
            "title_template": "组会 - {date}",
            "description": "项目组例行周会",
            "agenda": ["上周进展回顾", "本周计划", "问题与风险讨论", "下一步行动项"],
            "default_duration_minutes": 60,
            "is_builtin": True,
        },
        {
            "name": "一对一",
            "title_template": "1-on-1 沟通",
            "description": "导师与学生或同事间的一对一沟通",
            "agenda": ["上周工作总结", "遇到的困难", "本周重点", "需要的支持"],
            "default_duration_minutes": 30,
            "is_builtin": True,
        },
        {
            "name": "立项会",
            "title_template": "立项评审 - {project_name}",
            "description": "新项目立项评审",
            "agenda": ["项目背景", "目标与范围", "技术方案", "资源需求", "风险评估", "决策"],
            "default_duration_minutes": 90,
            "is_builtin": True,
        },
        {
            "name": "自由会议",
            "title_template": "临时讨论",
            "description": "无固定议程的自由讨论",
            "agenda": [],
            "default_duration_minutes": 30,
            "is_builtin": True,
        },
    ]
    for tpl in builtin:
        exists = bind.execute(
            sa.text("SELECT 1 FROM meeting_templates WHERE name = :name AND is_builtin = true"),
            {"name": tpl["name"]},
        ).first()
        if not exists:
            bind.execute(sa.text(
                "INSERT INTO meeting_templates (name, title_template, description, agenda, "
                "default_duration_minutes, is_builtin, is_active) "
                "VALUES (:name, :title_template, :description, CAST(:agenda AS json), "
                ":dur, :builtin, true)"
            ), {
                "name": tpl["name"],
                "title_template": tpl["title_template"],
                "description": tpl["description"],
                "agenda": json.dumps(tpl["agenda"], ensure_ascii=False),
                "dur": tpl["default_duration_minutes"],
                "builtin": tpl["is_builtin"],
            })


def downgrade():
    op.drop_index("idx_meeting_template_active", "meeting_templates")
    op.drop_table("meeting_templates")
