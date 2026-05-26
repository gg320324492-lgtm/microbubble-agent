"""add knowledge brain models: dynamic fields, knowledge_relations

Adds:
- Knowledge: key_concepts, related_topics, knowledge_type, analysis_status,
  auto_researched, quality_score columns
- knowledge_relations table for knowledge graph

Revision ID: 007
Revises: 006
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Knowledge 表新增字段
    op.add_column('knowledge', sa.Column('key_concepts', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('knowledge', sa.Column('related_topics', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('knowledge', sa.Column('knowledge_type', sa.String(50), nullable=True))
    op.add_column('knowledge', sa.Column('analysis_status', sa.String(20), server_default='pending'))
    op.add_column('knowledge', sa.Column('auto_researched', sa.Boolean(), server_default='false'))
    op.add_column('knowledge', sa.Column('quality_score', sa.Float(), nullable=True))

    # category 扩宽以支持动态分类
    op.alter_column('knowledge', 'category',
                    existing_type=sa.String(50),
                    type_=sa.String(100),
                    existing_nullable=True)

    # 创建知识关联表
    op.create_table('knowledge_relations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('knowledge.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_id', sa.Integer(), sa.ForeignKey('knowledge.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relation_type', sa.String(30)),
        sa.Column('score', sa.Float(), server_default='0.5'),
        sa.Column('reason', sa.String(500)),
        sa.Column('created_by', sa.String(20), server_default='auto'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # 创建索引
    op.create_index('ix_knowledge_relations_source', 'knowledge_relations', ['source_id'])
    op.create_index('ix_knowledge_relations_target', 'knowledge_relations', ['target_id'])
    op.create_index('ix_knowledge_relations_type', 'knowledge_relations', ['relation_type'])


def downgrade() -> None:
    op.drop_table('knowledge_relations')
    op.drop_column('knowledge', 'quality_score')
    op.drop_column('knowledge', 'auto_researched')
    op.drop_column('knowledge', 'analysis_status')
    op.drop_column('knowledge', 'knowledge_type')
    op.drop_column('knowledge', 'related_topics')
    op.drop_column('knowledge', 'key_concepts')
    op.alter_column('knowledge', 'category',
                    existing_type=sa.String(100),
                    type_=sa.String(50),
                    existing_nullable=True)
