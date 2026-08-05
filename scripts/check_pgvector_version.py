"""验证 pgvector >= 0.7.0 支持 halfvec (W-N-B 阶段 B.1)

用法:
    docker exec microbubble-agent-app-1 python scripts/check_pgvector_version.py

预期输出:
    pgvector version: 0.7.0
    halfvec type registered: True
    ✅ pgvector + halfvec ready
"""
import asyncio

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


async def main() -> int:
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    )
    try:
        async with engine.connect() as conn:
            # 1. pgvector extension version
            result = await conn.execute(sql_text(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
            ))
            version = result.scalar()
            if version is None:
                print("❌ pgvector extension not installed")
                return 1
            print(f"pgvector version: {version}")
            if version < "0.7.0":
                print(f"❌ need pgvector >= 0.7.0, got {version}")
                return 1

            # 2. halfvec type registered in pg_type
            result = await conn.execute(sql_text(
                "SELECT typname FROM pg_type WHERE typname = 'halfvec';"
            ))
            halfvec_typname = result.scalar()
            print(f"halfvec type registered: {halfvec_typname == 'halfvec'}")
            if halfvec_typname != "halfvec":
                print("❌ halfvec type not found in pg_type")
                return 1

            # 3. halfvec_cosine_ops operator class
            result = await conn.execute(sql_text("""
                SELECT 1 FROM pg_opclass
                WHERE opcname = 'halfvec_cosine_ops'
                LIMIT 1;
            """))
            if result.scalar() is None:
                print("❌ halfvec_cosine_ops operator class not found")
                return 1
            print("halfvec_cosine_ops: available")
    finally:
        await engine.dispose()

    print("✅ pgvector + halfvec ready")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
