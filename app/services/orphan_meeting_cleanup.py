"""孤儿会议清理任务（2026-06-12 防御机制, 2026-07-16 扩展 #207 完整修复）

解决问题：会议状态卡在 recording，但音频数据已物理丢失（前端刷新/断网），
且用户不再回来点 stop-recording。会议永久占着 ID，Celery 也不会触发后处理。

触发条件（每 10 分钟一次）：
- status = 'recording'
- recording_started_at < NOW() - ORPHAN_MEETING_TIMEOUT_MINUTES 分钟（默认 30, 原 60 改 30）
- **且** Redis 上无录音心跳（app/services/recording_heartbeat.py）← 2026-09-15 P0 新增

动作：
- 标 status='error', error_reason 含 user_agent + last_chunk_index + total_chunks
- 推 WS 进度通知（让前端能显示）
- 删 MinIO 上的相关 chunk 文件（如果有）

2026-07-16 改动:
  1. 删除 (last_chunk_index IS NULL OR last_chunk_index < 0) 条件, 扩展覆盖
     "录了 30 分钟突然刷新离开" 的孤儿 (last_chunk_index >= 0 但用户从不 stop)。
     原条件漏了这部分, 会议永远卡 recording 永不清理。
  2. error_reason 拼 user_agent 片段, 便于事后排查兼容性问题 (HarmonyOS ArkWeb 等)。
  3. 阈值改 60min → 30min (settings.ORPHAN_MEETING_TIMEOUT_MINUTES 可配置)。

2026-09-15 P0 改动（听会 09-14 事故）:
  4. 加录音心跳守卫。事故: 会议 250 录音 1h40m 被本任务在 20:14:58 误标 error,
     而用户 21:18 才停止录音 → 整场录音丢失。原判据只看时间不看前端存活。
     现在心跳仍在的会议会被跳过（skipped_alive），真孤儿仍照常清理。

2026-10-08 P0 改动（听会 10-08 会议 255 事故修复链 · 进一步保守）:
  5. **数据保护**（不再无条件删 MinIO）:
     原实现对每个判死的孤儿都调 delete_chunks 把 MinIO 上的 chunk 文件真删掉 ——
     09-14 事故里若用户桌面 Chrome 已传了 N 个分片后刷新离开，这批音频会被直接销毁，
     用户连 1 byte 都救不回来（只保护了"判定"，没保护"数据"）。现在:
       - `has_chunks` (last_chunk_index >= 0) → **保留分片**，
         error_reason 追加 `chunks_preserved=N`，前端可识别并提示"可尝试恢复"
       - `presence_recent` (recording_presence_at 在超时阈值内，即前端 pagehide
         刚发过 presence 信号, 见 web/src/composables/useRecordingHeartbeat.js)
         → **保留分片**（弱信号不豁免判死，页面已关内存 blob 早已销毁，
           再等只让真孤儿多占槽位；但万一有实时分片，那仍是唯一能救的东西，绝不能删），
         error_reason 追加 `presence_recent=True`
       - 两者都不成立（0 分片 + 从未上报 presence）→ 走原 delete_chunks（此时是 no-op）

  补救链路（配合 2026-10-08 P0-4 的 API 放宽）:
     PUT  /api/v1/meetings/{id}/audio-chunk        （已放宽接受 status='error'）
     POST /api/v1/meetings/{id}/chunks/reset       （已放宽接受 status='error'）
     POST /api/v1/meetings/{id}/merge-chunks       （mode=auto 或 raw）
     POST /api/v1/meetings/{id}/reprocess          （error → processing + 触发 Celery）
"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.core.celery_db import create_celery_engine_and_session
from app.core.celery import celery_app

logger = logging.getLogger("microbubble.orphan_cleanup")


@celery_app.task(name="app.services.orphan_meeting_cleanup.cleanup_orphan_meetings")
def cleanup_orphan_meetings():
    """
    Celery beat 调度：每 10 分钟扫一次
    """
    logger.info("开始扫描孤儿会议")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_scan_and_cleanup())
        logger.info(f"孤儿会议清理完成: {result}")
        return result
    finally:
        loop.close()


async def _scan_and_cleanup() -> dict:
    """异步执行清理逻辑"""
    from sqlalchemy import select
    from app.config import settings
    from app.models.meeting import Meeting
    from app.services.chunked_upload_service import chunked_upload_service
    from app.services.progress_service import update_progress, ProgressStage
    import redis.asyncio as aioredis
    engine, session_factory = create_celery_engine_and_session()
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    # 2026-07-16: 阈值改 60min → 30min, 由 settings.ORPHAN_MEETING_TIMEOUT_MINUTES 控制
    threshold = datetime.utcnow() - timedelta(minutes=settings.ORPHAN_MEETING_TIMEOUT_MINUTES)
    cleaned = []
    errors = []
    skipped_alive = []  # 2026-09-15: 心跳仍在, 主动跳过的会议

    try:
        async with session_factory() as db:
            # 2026-07-16 扩展: 删除 last_chunk_index 条件, 覆盖 "录了 N 分钟突然刷新离开" 的孤儿
            r = await db.execute(
                select(Meeting).where(
                    Meeting.status == "recording",
                    Meeting.recording_started_at < threshold
                )
            )
            orphans = r.scalars().all()

            for m in orphans:
                try:
                    # 2026-09-15 P0 修复 (听会 09-14 事故): 心跳守卫
                    # 事故: 会议 250 录音 1h40m, 20:14:58 被本任务误判为孤儿标记 error,
                    # 但用户 21:18 才停止录音 → 录音数据全丢。
                    # 原判据只看 recording_started_at, 完全不关心前端是否还活着,
                    # 于是任何超过 30 分钟的会议都会被误杀。
                    # 修法: 录音页面每 60s 写一次 Redis 心跳 (TTL 300s),
                    # 心跳仍在 → 前端还活着 → 跳过, 交给用户自己 stop。
                    from app.services.recording_heartbeat import is_recording_alive
                    if await is_recording_alive(m.id, redis_client=redis_client):
                        logger.info(
                            f"会议 {m.id} 录音超时但心跳仍在 (前端仍在录音), 跳过清理"
                        )
                        skipped_alive.append(m.id)
                        continue

                    # 标 error (2026-07-16: error_reason 拼 user_agent 片段)
                    m.status = "error"
                    ua_short = (m.user_agent or 'unknown')[:80]

                    # 2026-10-08 P0-4 + 主指挥复验修正: 判断是否有可保留的数据
                    #
                    # 判据 1 — has_chunks: 有 MinIO 分片 (last_chunk_index >= 0)
                    #   → 保留分片不删, 给用户补传 / reprocess 的补救机会
                    #
                    # 判据 2 — presence_recent: recording_presence_at 在超时阈值内
                    #   （前端 pagehide 刚发过 presence 信号, 说明"页面刚离开",
                    #     用户可能马上就切回来 —— 见 web/src/composables/useRecordingHeartbeat.js）
                    #   → 弱信号, **不豁免判死**（页面已关, 内存 blob 早已随导航销毁,
                    #     再等下去只是让真孤儿多占会议槽位）, 但**强制保留分片**:
                    #     万一有实时分片已上传, 那是用户唯一能救回来的东西, 绝不能删。
                    has_chunks = (m.last_chunk_index is not None and m.last_chunk_index >= 0)
                    chunks_count = (m.last_chunk_index + 1) if has_chunks else 0
                    presence_recent = bool(
                        m.recording_presence_at
                        and (threshold <= m.recording_presence_at)
                    )
                    # 保留分片的两个充分条件之一成立即保留
                    preserve_chunks = has_chunks or presence_recent

                    error_reason_parts = [
                        f"录音超过 {settings.ORPHAN_MEETING_TIMEOUT_MINUTES}min 未 stop",
                        f"(last_chunk_index={m.last_chunk_index}, total_chunks={m.total_chunks})",
                    ]
                    if has_chunks:
                        error_reason_parts.append(f"chunks_preserved={chunks_count}")
                    if presence_recent:
                        error_reason_parts.append("presence_recent=True")
                    error_reason_parts.append(f"[UA: {ua_short}]")
                    m.error_reason = ", ".join(error_reason_parts)
                    # 2026-09-13: 占位标题 (正在听会（ID N）) 改为明确状态,
                    # 避免列表里永远显示"正在听会"造成误解
                    from app.services.meeting_analysis_service import is_placeholder_meeting_title
                    if is_placeholder_meeting_title(m.title or ""):
                        m.title = f"听会记录（已清理 {m.created_at.strftime('%m-%d %H:%M')}）"
                    # 2026-10-08 P0-4: preserve_chunks → 保留 MinIO (delete_chunks 会真删
                    # MinIO 上的 chunk 文件, 而这些是用户已上传的音频字节。原版误杀路径会让
                    # 用户连 1 byte 都救不回来)。无分片且无 presence → 原 delete_chunks
                    # 走 no-op (MinIO 本来就空)
                    if not preserve_chunks:
                        try:
                            deleted = await chunked_upload_service.delete_chunks(m.id)
                            if deleted:
                                logger.info(f"会议 {m.id} 清理 {deleted} 个 chunk")
                        except Exception as e:
                            logger.warning(f"清理会议 {m.id} chunks 失败: {e}")
                    else:
                        logger.warning(
                            f"会议 {m.id} 保留 MinIO 供用户补救 "
                            f"(chunks={chunks_count}, presence_recent={presence_recent}); "
                            f"可用 POST /api/v1/meetings/{m.id}/reprocess 重启流水线"
                        )

                    # 推 WS 通知
                    try:
                        await update_progress(
                            m.id, ProgressStage.DONE,
                            detail=f"录音超时已清理: {m.error_reason[:80]}",
                            status="error",
                            redis_override=redis_client,
                        )
                    except Exception as e:
                        logger.warning(f"推 WS 失败: {e}")

                    cleaned.append(m.id)
                except Exception as e:
                    errors.append(f"{m.id}: {e}")

            if cleaned:
                await db.commit()
    finally:
        await redis_client.aclose()
        await engine.dispose()

    return {
        "cleaned": cleaned,
        "errors": errors,
        "count": len(cleaned),
        "skipped_alive": skipped_alive,
    }
