"""用修复后的分析链路重新生成某会议的摘要/要点/决议（2026-09-15 P0 修复的回填工具）。

背景：会议 250 的摘要由旧代码生成 —— 发言者映射（1328 条，27,015 字）被拼进
分析正文，占掉 8 个分块里的前 4 块，LLM 只能回"本次提供的会议转录材料（第1/6部分）
仅包含说话人识别映射表…未包含任何实际对话文本"，这句元话又被原样拼进最终摘要。
分析链路修好后（映射压缩进 system prompt + 元话语清洗 + 二次 LLM 归并），
用本脚本把历史会议的摘要重新生成一遍。

用法：
  docker cp scripts/regen_meeting_summary.py microbubble-agent-app-1:/tmp/
  docker exec -i microbubble-agent-app-1 python /tmp/regen_meeting_summary.py --meeting 250
  # 只重算摘要，不动标题：
  ... --meeting 250 --stages analysis
"""
import argparse
import asyncio
import sys

sys.path.insert(0, "/app")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--stages", default="analysis,title",
                    help="逗号分隔，可选 analysis / title / speaker_assignment / polish")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from app.core.celery_db import create_celery_engine_and_session
    from app.services.meeting_reprocessing_service import (
        MeetingReprocessingService, ReprocessRequest)

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    if args.dry_run:
        print(f"[dry-run] 将对会议 {args.meeting} 重跑阶段: {stages}")
        return 0

    engine, sf = create_celery_engine_and_session()
    try:
        async with sf() as db:
            svc = MeetingReprocessingService(db)
            res = await svc.execute(ReprocessRequest(
                meeting_id=args.meeting, requested_stages=stages,
                trigger="p0_summary_fix_regen", force=True))
            print("completed:", res.completed_stages)
            print("errors   :", res.errors)
            print("warnings :", res.warnings)
            return 0 if not res.errors else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
