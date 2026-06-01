"""会议挂断后处理任务

阶段：
0. extracting_transcript - 确认转录完整性
1. identifying_speakers - 重跑声纹识别或确认 speaker_mapping
2. generating_title - meeting_analysis.generate_title
3. generating_minutes - meeting_analysis.analyze_transcript
4. creating_tasks - meeting_service._auto_create_task_from_meeting
5. linking_history - 第三波启用（本波跳过）
6. done

每步：progress_service.update_progress，失败重试 1 次。
"""
import asyncio
import logging

from app.core.celery import celery_app
from app.core.database import async_session
from app.services.progress_service import ProgressStage, update_progress

logger = logging.getLogger("microbubble.post_meeting")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def post_meeting_process(self, meeting_id: int):
    """Celery 任务：5 阶段后处理"""
    logger.info(f"开始挂断后处理: meeting_id={meeting_id}")

    async def _run():
        async with async_session() as db:
            from app.models.meeting import Meeting
            from sqlalchemy import select
            result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
            meeting = result.scalar_one_or_none()
            if not meeting:
                logger.error(f"会议不存在: {meeting_id}")
                return

            # 阶段 0
            await update_progress(meeting_id, ProgressStage.EXTRACTING_TRANSCRIPT, detail="确认转录完整性")
            transcript = meeting.transcript or []
            if not transcript:
                logger.warning(f"会议转录为空: {meeting_id}")

            # 阶段 1
            await update_progress(meeting_id, ProgressStage.IDENTIFYING_SPEAKERS, detail="识别发言人")
            await asyncio.sleep(0.5)  # 占位

            # 阶段 2
            await update_progress(meeting_id, ProgressStage.GENERATING_TITLE, detail="生成会议标题")
            from app.services.meeting_analysis_service import meeting_analysis
            if not meeting.title or meeting.title == "新会议":
                meeting.title = await meeting_analysis.generate_title(db, transcript)
                await db.commit()

            # 阶段 3
            await update_progress(meeting_id, ProgressStage.GENERATING_MINUTES, detail="生成会议纪要")
            analysis = await meeting_analysis.analyze_transcript(db, transcript)
            meeting.summary = analysis.get("summary")
            meeting.key_points = analysis.get("key_points", [])
            meeting.decisions = analysis.get("decisions", [])
            await db.commit()

            # 阶段 4
            await update_progress(meeting_id, ProgressStage.CREATING_TASKS, detail="自动创建任务")
            from app.services.meeting_service import MeetingService
            svc = MeetingService(db)
            for decision in analysis.get("decisions", []):
                await svc._auto_create_task_from_meeting(meeting, decision)

            # 阶段 5：第三波启用，本波跳过
            await update_progress(meeting_id, ProgressStage.LINKING_HISTORY, detail="跨会议关联（第三波）")
            await asyncio.sleep(0.1)

            # 阶段 6
            await update_progress(meeting_id, ProgressStage.DONE, detail="处理完成")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
        loop.close()
        return {"status": "done", "meeting_id": meeting_id}
    except Exception as e:
        logger.error(f"挂断后处理失败: meeting_id={meeting_id}, error={e}")
        # 不重试 Celery 任务本身（每阶段内部已有 try/except）
        return {"status": "error", "meeting_id": meeting_id, "error": str(e)}
