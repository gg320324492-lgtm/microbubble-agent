"""v28 step 105: 批量重新排版所有无文件的论文（只走 LLM 文本重排版）

用法：
    docker cp scripts/reformat_text_only.py microbubble-agent-app-1:/tmp/
    docker exec -i microbubble-agent-app-1 bash -c "cd /app && python /tmp/reformat_text_only.py"

功能：
- 找出所有 file_path 为空 + 已有 content 但无 formatted_content 的 knowledge
- 触发 reformat_knowledge_task Celery task（异步）
- 报告处理进度
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.knowledge import Knowledge


async def main(batch_size: int = 50, force: bool = False):
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from app.services.content_formatter_service import reformat_knowledge_task

    async with factory() as db:
        # 找所有无文件路径但有 content 的 knowledge
        q = select(Knowledge).where(
            and_(
                or_(Knowledge.file_path.is_(None), Knowledge.file_path == ""),
                Knowledge.content.isnot(None),
                Knowledge.content != "",
            )
        )
        result = await db.execute(q)
        all_no_file = result.scalars().all()

        # 过滤：已有 formatted_content 且不强制
        to_reformat = []
        if not force:
            for kb in all_no_file:
                if kb.formatted_content and len(kb.formatted_content) > 100:
                    continue
                to_reformat.append(kb)
        else:
            to_reformat = all_no_file

        print(f"[reformat_no_file] 总无文件: {len(all_no_file)}")
        print(f"[reformat_no_file] 待重排版: {len(to_reformat)}")
        print()

        if not to_reformat:
            print("[reformat_no_file] 没有需要重排版的，退出")
            await engine.dispose()
            return

        queued = 0
        for i, kb in enumerate(to_reformat):
            try:
                task = reformat_knowledge_task.delay(kb.id)
                queued += 1
                if (i + 1) % 10 == 0:
                    print(f"[reformat_no_file] 已提交 {i + 1}/{len(to_reformat)} 个任务")
            except Exception as e:
                print(f"[reformat_no_file] 提交失败 knowledge_id={kb.id}: {e}")

        print(f"\n[reformat_no_file] 总共提交 {queued} 个 Celery task")
        print(f"[reformat_no_file] 任务名: app.services.content_formatter_service.reformat_knowledge_task")

    await engine.dispose()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量重新排版无文件论文")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--force", action="store_true", help="强制重排已有 formatted_content 的")
    args = parser.parse_args()

    asyncio.run(main(batch_size=args.batch_size, force=args.force))