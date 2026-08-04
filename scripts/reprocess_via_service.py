#!/usr/bin/env python3
"""通过 service 化接口重跑会议 (CLI 入口)

2026-08-04 Batch C-3
"""
import argparse
import asyncio
import json
import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, ".")

from app.config import settings
from app.services.meeting_reprocessing_service import (
    MeetingReprocessingService,
    ReprocessRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reprocess_via_service")


async def run(args):
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        stages = [s.strip() for s in args.stages.split(",") if s.strip()]
        req = ReprocessRequest(
            meeting_id=args.meeting,
            requested_stages=stages,
            trigger=f"cli:{args.user or 'unknown'}",
            force=args.force,
        )
        svc = MeetingReprocessingService(db)
        result = await svc.execute(req)

    print(json.dumps({
        "meeting_id": result.meeting_id,
        "run_id": result.run_id,
        "reused": result.reused,
        "completed_stages": result.completed_stages,
        "skipped_stages": result.skipped_stages,
        "warnings": result.warnings,
        "errors": result.errors,
    }, ensure_ascii=False, indent=2))

    if result.errors:
        sys.exit(1)
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting", type=int, required=True)
    parser.add_argument("--stages", type=str, required=True,
                        help="逗号分隔: title,polish,analysis,speaker_assignment,quality")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--user", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()