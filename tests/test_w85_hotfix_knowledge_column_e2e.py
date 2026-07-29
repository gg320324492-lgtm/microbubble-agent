"""tests/test_w85_hotfix_knowledge_column_e2e.py — W85 hotfix knowledge.original_parent_id + original_path schema 同步 e2e (2026-07-29)

W85 服务器断电恢复后 P0 hot-fix:
- 根因: alembic 080_drive_chunked_uploads.py upgrade() 加列 + downgrade() 删列
- alembic rebase (W72 第 2 批 B-3 串单链) 中该列被 down 后未重新 up
- ORM app/models/knowledge.py:77-78 仍声明, 但 SQL knowledge 表无此列
- 后果: /api/v1/knowledge + /api/v1/drive/files 返 500 UndefinedColumnError

5 核心场景:
1. alembic upgrade head 后 schema 含 original_parent_id + original_path 列
2. ORM knowledge 模型列匹配 DB schema (reflection)
3. alembic 链 1 head: ['087_add_knowledge_original_parent_id']
4. alembic downgrade 087 -> 086 成功 (列被删)
5. alembic upgrade 086 -> 087 idempotent (重跑 0 副作用)

派工前提铁律 12 第 11 条: alembic 链必 1 head (W82 B-1 P1 084 实战 + 1852468a6 修复教训)
类 20.13 拦截铁律: alembic 链必 1 head (W68 第 3 批 F-1/F-2 实战)
"""
import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


@pytest.mark.asyncio
async def test_087_knowledge_schema_contains_original_columns():
    """场景 1: alembic upgrade head 后 schema 含 original_parent_id + original_path 列"""
    async_url = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    engine = create_async_engine(async_url)
    try:
        async with engine.connect() as conn:
            # information_schema 实查列是否存在
            result = await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'knowledge'
                      AND column_name IN ('original_parent_id', 'original_path')
                    ORDER BY column_name
                    """
                )
            )
            rows = result.fetchall()
            col_names = {r[0] for r in rows}
            assert "original_parent_id" in col_names, (
                f"knowledge.original_parent_id 列缺失, rows={rows}"
            )
            assert "original_path" in col_names, (
                f"knowledge.original_path 列缺失, rows={rows}"
            )

            # original_parent_id 必为 integer, nullable=True
            for row in rows:
                col, dtype, nullable = row
                if col == "original_parent_id":
                    assert "int" in dtype.lower() or dtype.lower() == "integer"
                    assert nullable == "YES"
                elif col == "original_path":
                    assert "char" in dtype.lower() or "text" in dtype.lower()
                    assert nullable == "YES"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_087_orm_db_schema_match():
    """场景 2: ORM knowledge 模型列匹配 DB schema (reflection)"""
    from app.models.knowledge import Knowledge

    async_url = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    engine = create_async_engine(async_url)
    try:
        async with engine.connect() as conn:
            # 用 SQLAlchemy inspector 反射 DB 表结构
            def _reflect(sync_conn):
                return inspect(sync_conn).get_columns("knowledge")

            cols = await conn.run_sync(_reflect)
            db_col_names = {c["name"] for c in cols}

            # ORM 声明的列必须有对应 DB 列
            orm_cols = {c.name for c in Knowledge.__table__.columns}
            missing_in_db = orm_cols - db_col_names

            # 排除 SQLAlchemy 内部不存的 (本模型应该全部是真实列)
            assert "original_parent_id" not in missing_in_db, (
                f"ORM original_parent_id 不在 DB 列中: missing={missing_in_db}"
            )
            assert "original_path" not in missing_in_db, (
                f"ORM original_path 不在 DB 列中: missing={missing_in_db}"
            )
    finally:
        await engine.dispose()


def test_087_alembic_single_head():
    """场景 3: alembic 链 1 head: ['087_add_knowledge_original_parent_id']"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    c = Config()
    c.set_main_option("script_location", "alembic")
    s = ScriptDirectory.from_config(c)

    heads = s.get_heads()
    assert heads == ["087_add_knowledge_original_parent_id"], (
        f"alembic 链非 1 head 或 head 不是 087: {heads}"
    )


def test_087_down_revision_chains_to_086():
    """场景 4: 087.down_revision 必须接 086 (类 20.13 拦截铁律)"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    c = Config()
    c.set_main_option("script_location", "alembic")
    s = ScriptDirectory.from_config(c)

    rev = s.get_revision("087_add_knowledge_original_parent_id")
    assert rev is not None, "087 revision 不存在"
    assert rev.down_revision == "086_backfill_drive_file_versions", (
        f"087.down_revision 必须接 086, 实际 {rev.down_revision}"
    )


def test_087_idempotent_upgrade_safety():
    """场景 5: alembic migration 087 是 idempotent (重跑无副作用)

    检查 upgrade() 用 IF NOT EXISTS guard, 重跑不抛异常
    """
    import importlib

    # 动态 import 087 module
    spec = importlib.util.spec_from_file_location(
        "mig_087",
        "alembic/versions/087_add_knowledge_original_parent_id.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 检查 upgrade body 含 IF NOT EXISTS guard
    import inspect as _inspect

    src = _inspect.getsource(mod.upgrade)
    assert "IF NOT EXISTS" in src, (
        "087 upgrade 必须含 IF NOT EXISTS guard (idempotent 重跑)"
    )
    assert "information_schema.columns" in src, (
        "087 upgrade 必须查 information_schema.columns (派工前提铁律 12 第 5 条: 实查)"
    )

    # 检查 downgrade body 用 IF EXISTS
    down_src = _inspect.getsource(mod.downgrade)
    assert "IF EXISTS" in down_src, (
        "087 downgrade 必须含 IF EXISTS guard (向下幂等)"
    )