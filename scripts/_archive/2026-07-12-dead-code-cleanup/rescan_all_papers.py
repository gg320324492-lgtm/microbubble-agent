"""v28 step 105: 批量重新扫描所有有文件的论文，用 vision model 输出 page_layout

用法：
    # 本地
    python scripts/rescan_all_papers.py

    # 容器内
    docker cp scripts/rescan_all_papers.py microbubble-agent-app-1:/tmp/
    docker exec -i microbubble-agent-app-1 bash -c "cd /app && python /tmp/rescan_all_papers.py"

功能：
- 找出所有 file_path 不为空 + quality_score 较高的 knowledge
- 触发 scan_paper_layout Celery task（异步）
- 报告处理进度
"""

import asyncio
import sys
from pathlib import Path

# 让脚本能 import app 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_, or_, not_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.knowledge import Knowledge
from app.models.knowledge_layout import KnowledgeLayout


async def main(batch_size: int = 50, force: bool = False):
    """主流程

    Args:
        batch_size: 每批提交的任务数
        force: 是否强制重扫（已有 layout 的也重扫）
    """
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 延迟 import celery 任务
    from app.services.paper_layout_service import scan_paper_layout_task

    async with factory() as db:
        # 找所有有文件路径的论文
        # knowledge_type='paper' 且 file_path 不为空
        q = select(Knowledge).where(
            and_(
                Knowledge.file_path.isnot(None),
                Knowledge.file_path != "",
            )
        )
        result = await db.execute(q)
        all_papers = result.scalars().all()

        # 过滤掉已经有 layout 的（除非 force=True）
        existing_layout_ids = set()
        if not force:
            layout_q = select(KnowledgeLayout.knowledge_id)
            layout_result = await db.execute(layout_q)
            existing_layout_ids = {row[0] for row in layout_result.all()}

        to_scan = []
        for kb in all_papers:
            if kb.id in existing_layout_ids:
                continue
            to_scan.append(kb)

        print(f"[rescan] 总论文: {len(all_papers)}")
        print(f"[rescan] 已有 layout: {len(existing_layout_ids)}")
        print(f"[rescan] 待扫描: {len(to_scan)}")
        print()

        if not to_scan:
            print("[rescan] 没有需要扫描的论文，退出")
            await engine.dispose()
            return

        # 分批提交 Celery task
        queued = 0
        for i, kb in enumerate(to_scan):
            try:
                task = scan_paper_layout_task.delay(kb.id)
                queued += 1
                if (i + 1) % 10 == 0:
                    print(f"[rescan] 已提交 {i + 1}/{len(to_scan)} 个任务")
            except Exception as e:
                print(f"[rescan] 提交 task 失败 knowledge_id={kb.id}: {e}")

        print(f"\n[rescan] 总共提交 {queued} 个 Celery task 到 worker")
        print(f"[rescan] 任务名: app.services.paper_layout_service.scan_paper_layout_task")
        print(f"[rescan] 监控日志: docker logs -f microbubble-agent-celery-worker-1 | grep scan_layout")
        print(f"[rescan] 查询进度: GET /api/v1/knowledge/{id}/layout")

    await engine.dispose()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量重新扫描论文生成 vision layout")
    parser.add_argument("--batch-size", type=int, default=50, help="每批提交数")
    parser.add_argument("--force", action="store_true", help="强制重扫已有 layout 的论文")
    args = parser.parse_args()

    asyncio.run(main(batch_size=args.batch_size, force=args.force))