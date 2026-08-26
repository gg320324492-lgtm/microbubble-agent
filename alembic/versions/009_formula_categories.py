"""add formula_categories table, enhance knowledge_formulas

Adds:
- formula_categories table for structured formula categories
- source_type, category_id, is_active columns to knowledge_formulas
- Make knowledge_formulas.knowledge_id nullable (for built-in formulas)

Revision ID: 009
Revises: 008
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '009'
down_revision: Union[str, None] = '008_fix_embedding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create formula_categories table
    op.create_table(
        'formula_categories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_foreign_key(
        'fk_formula_categories_parent',
        'formula_categories', 'formula_categories',
        ['parent_id'], ['id'],
    )

    # Phase 14 (2026-08-26 sandbox): 009 之前 ALTER knowledge_formulas 但 CREATE 缺失.
    # 若 knowledge_formulas 不存在, ALTER 失败. 显式 IF NOT EXISTS 兜底.
    # 不在 CREATE 中列 source_type/category_id/is_active (这些列由后面 ALTER 加).
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_formulas (
            id INTEGER PRIMARY KEY,
            knowledge_id INTEGER,
            name VARCHAR(200) NOT NULL,
            formula_latex TEXT,
            formula_python TEXT NOT NULL,
            variables JSONB DEFAULT '{}'::jsonb,
            result_unit VARCHAR(50),
            conditions TEXT,
            domain VARCHAR(100),
            confidence FLOAT DEFAULT 0.5,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (knowledge_id) REFERENCES knowledge(id) ON DELETE CASCADE
        )
    """)

    # Add columns to knowledge_formulas (ALTER TABLE 在 IF NOT EXISTS 之后安全)
    op.add_column('knowledge_formulas', sa.Column('source_type', sa.String(20),
                   server_default='extracted'))
    op.add_column('knowledge_formulas', sa.Column('category_id', sa.Integer(), nullable=True))
    op.add_column('knowledge_formulas', sa.Column('is_active', sa.Boolean(),
                   server_default='true'))

    # Make knowledge_id nullable (for built-in formulas without parent document)
    op.alter_column('knowledge_formulas', 'knowledge_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    # Add foreign key and indexes
    op.create_foreign_key(
        'fk_knowledge_formulas_category',
        'knowledge_formulas', 'formula_categories',
        ['category_id'], ['id'],
    )
    op.create_index('ix_knowledge_formulas_source_type', 'knowledge_formulas', ['source_type'])
    op.create_index('ix_knowledge_formulas_category_id', 'knowledge_formulas', ['category_id'])
    op.create_index('ix_knowledge_formulas_is_active', 'knowledge_formulas', ['is_active'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_knowledge_formulas_source_type', table_name='knowledge_formulas')
    op.drop_index('ix_knowledge_formulas_category_id', table_name='knowledge_formulas')
    op.drop_index('ix_knowledge_formulas_is_active', table_name='knowledge_formulas')

    # Drop foreign keys
    op.drop_constraint('fk_knowledge_formulas_category', 'knowledge_formulas', type_='foreignkey')
    op.drop_constraint('fk_formula_categories_parent', 'formula_categories', type_='foreignkey')

    # Remove columns from knowledge_formulas
    op.drop_column('knowledge_formulas', 'is_active')
    op.drop_column('knowledge_formulas', 'category_id')
    op.drop_column('knowledge_formulas', 'source_type')

    # Restore knowledge_id to NOT NULL
    op.alter_column('knowledge_formulas', 'knowledge_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    # Drop formula_categories table
    op.drop_table('formula_categories')
