"""重新生成会议 #83 的 summary（用 polished 内容）"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.llm import get_anthropic_client, get_default_model, extract_text_from_response
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models.meeting import Meeting


async def main():
    engine = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with sf() as db:
            m = await db.get(Meeting, 83)
            polished = m.transcript_polished or []
            text_sample = "\n".join(
                "[{}] {}".format(seg.get("speaker", ""), seg.get("text", ""))
                for seg in polished[:30]
            )
            client = get_anthropic_client()
            model = get_default_model()
            response = await client.messages.create(
                model=model,
                max_tokens=600,
                system="你是会议秘书，请用 3-5 句中文总结会议的核心内容。",
                messages=[
                    {"role": "user", "content": "会议转录片段：\n" + text_sample + "\n\n请输出会议总结（3-5 句中文）。"}
                ],
            )
            txt = extract_text_from_response(response)
            print("NEW SUMMARY:", txt)
            m.summary = txt
            await db.commit()
            print("✅ summary 已更新")
    finally:
        await engine.dispose()


asyncio.run(main())
