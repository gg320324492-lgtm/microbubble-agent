"""验证 alembic 010 迁移正确添加 voice_embedding 字段

Wave 2a critical fix: Member.voice_embedding/voice_enrolled_at/voice_sample_count
defined in ORM but missing from DB schema. Without this migration,
voiceprint_service.enroll_member() fails with "column does not exist".

注意：本测试连接 microbubble_test DB（conftest 用 Base.metadata.create_all 创建），
不连接 prod microbubble DB。要验证 prod DB 需手工 psql 检查。
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
async def test_voice_embedding_columns_exist(db: AsyncSession):
    """members 表应有 voice_embedding / voice_enrolled_at / voice_sample_count 3 列"""
    result = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'members'
        AND column_name IN ('voice_embedding', 'voice_enrolled_at', 'voice_sample_count')
    """))
    columns = {row[0] for row in result.fetchall()}
    assert columns == {'voice_embedding', 'voice_enrolled_at', 'voice_sample_count'}


@pytest.mark.asyncio
async def test_voice_embedding_column_type(db: AsyncSession):
    """voice_embedding 应是 vector(256) 类型"""
    result = await db.execute(text("""
        SELECT data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = 'members' AND column_name = 'voice_embedding'
    """))
    row = result.fetchone()
    assert row is not None, "voice_embedding 列不存在"
    # pgvector 在 information_schema 中 udt_name = 'vector'
    assert row[1] == 'vector', f"voice_embedding 应为 vector 类型，实际为 {row[1]}"


@pytest.mark.asyncio
async def test_voice_sample_count_default(db: AsyncSession):
    """voice_sample_count 列默认值应为 0"""
    result = await db.execute(text("""
        SELECT column_name, column_default
        FROM information_schema.columns
        WHERE table_name = 'members' AND column_name = 'voice_sample_count'
    """))
    row = result.fetchone()
    assert row is not None, "voice_sample_count 列不存在"
    # column_default 形如 '0' 或 '0::integer'
    assert row[1] is not None and '0' in str(row[1]), \
        f"voice_sample_count 应有默认值 0，实际为 {row[1]}"
