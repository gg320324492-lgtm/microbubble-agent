"""用本地录音文件恢复一场"听会"会议，并重跑完整后处理流水线。

适用场景
--------
用户在手机上点了"开始听会"，但录音因为兼容性/体积/网络问题没能上传成功
（典型：iOS Safari 不触发 MediaRecorder timeslice → 停止时一次性 162MB 上传
被反代体积上限拒绝 → 前端只显示 "Network Error"），事后只保留了手机自带
录音机里的原始音频文件。

本脚本把这段本地音频作为该会议的正式录音入库，并把会议重置到
"processing" 状态，然后派发 Celery `post_meeting_process` 走完整流水线：

    下载音频 → VAD 分段 → ASR(GPU 7B / SenseVoice) → 声纹识别 →
    AI 润色 → 纪要分析(摘要/要点/决议) → 标题生成 → 入库

跑完后前端会议详情页即可正常查看转录、发言人、纪要与录音回放。

用法
----
    # 1) 把脚本和音频拷进 app 容器（项目既有约定，见 scripts/reprocess_meeting.py）
    docker cp scripts/recover_meeting_audio.py microbubble-agent-app-1:/tmp/
    docker cp "C:/Users/pc/Desktop/2026.9.14 组会.m4a" microbubble-agent-app-1:/tmp/recover_audio.m4a

    # 2) 入库 + 触发流水线（时间为北京时间）
    docker exec -i microbubble-agent-app-1 python /tmp/recover_meeting_audio.py \
        --meeting 250 --audio /tmp/recover_audio.m4a \
        --start "2026-09-14 20:14:57" --end "2026-09-14 21:51:24"

    # 只看不改（dry-run）
    docker exec -i microbubble-agent-app-1 python /tmp/recover_meeting_audio.py \
        --meeting 250 --audio /tmp/recover_audio.m4a --start "..." --end "..." --dry-run

设计要点
--------
- **不改原始音频**：只把文件传进 MinIO，会议记录里保存 object_name。
- **可审计**：执行前把会议原有字段快照写到 /tmp/recover_meeting_{id}_before.json。
- **清理干净**：清掉该会议遗留的 chunks / merged 产物 / Redis 录音心跳，
  避免旧分片在后续 merge 时混进来，或心跳残留挡住孤儿清理。
- **幂等**：重复执行只是重新入音频 + 重新触发流水线（会新建一个 processing run）。
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recover_meeting_audio")

BEIJING = timezone(timedelta(hours=8))


def parse_bj(s: str) -> datetime:
    """"2026-09-14 20:14:57"(北京时间) → naive UTC datetime(与 DB 一致)"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"无法解析时间: {s!r} (期望 'YYYY-MM-DD HH:MM:SS')")
    return dt.replace(tzinfo=BEIJING).astimezone(timezone.utc).replace(tzinfo=None)


async def main() -> int:
    ap = argparse.ArgumentParser(description="用本地录音恢复会议并重跑流水线")
    ap.add_argument("--meeting", type=int, required=True, help="会议 ID")
    ap.add_argument("--audio", required=True, help="容器内音频文件路径")
    ap.add_argument("--start", required=True, help="会议真实开始时间(北京时间)")
    ap.add_argument("--end", required=True, help="会议真实结束时间(北京时间)")
    ap.add_argument("--title", default=None, help="标题; 省略则保留原占位标题让流水线自动生成")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做的变更, 不写库不触发")
    ap.add_argument("--no-trigger", action="store_true", help="入库但不派发 Celery 后处理")
    args = ap.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        logger.error(f"音频文件不存在: {audio_path}")
        return 2

    start_utc = parse_bj(args.start)
    end_utc = parse_bj(args.end)
    wall_seconds = int((end_utc - start_utc).total_seconds())

    # ---- 延迟导入(必须在 sys.path 调整之后) ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.file_service import file_service
    from app.services.chunked_upload_service import chunked_upload_service
    from app.services.audio_metadata import ffprobe_duration_async
    from app.services.recording_heartbeat import clear_recording_heartbeat

    audio_bytes = audio_path.read_bytes()
    probe = audio_path.suffix.lstrip(".")
    ext, content_type = chunked_upload_service.sniff_audio_container(audio_bytes)
    if not probe:
        probe = ext

    media_seconds = None
    try:
        media_seconds = await ffprobe_duration_async(audio_bytes)
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning(f"ffprobe 探测时长失败: {e}")

    logger.info(
        f"音频就绪: {audio_path.name} | {len(audio_bytes)} bytes | "
        f"容器={content_type} | ffprobe 时长={media_seconds}s | 墙钟={wall_seconds}s"
    )

    engine, session_factory = create_celery_engine_and_session()
    try:
        async with session_factory() as db:
            meeting = (
                await db.execute(select(Meeting).where(Meeting.id == args.meeting))
            ).scalar_one_or_none()
            if meeting is None:
                logger.error(f"会议 {args.meeting} 不存在")
                return 3

            snapshot = {
                "id": meeting.id,
                "title": meeting.title,
                "status": meeting.status,
                "upload_status": meeting.upload_status,
                "audio_url": meeting.audio_url,
                "error_reason": meeting.error_reason,
                "start_time": str(meeting.start_time),
                "end_time": str(meeting.end_time),
                "recording_started_at": str(meeting.recording_started_at),
                "recording_ended_at": str(meeting.recording_ended_at),
                "audio_duration": meeting.audio_duration,
                "media_duration_seconds": meeting.media_duration_seconds,
                "last_chunk_index": meeting.last_chunk_index,
                "total_chunks": meeting.total_chunks,
                "has_transcript": bool(meeting.transcript),
                "has_summary": bool(meeting.summary),
            }
            snap_path = Path(f"/tmp/recover_meeting_{args.meeting}_before.json")
            snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"变更前快照已写入 {snap_path}")
            logger.info(f"变更前: status={snapshot['status']} audio_url={snapshot['audio_url']}")

            if args.dry_run:
                logger.info("[dry-run] 跳过写入与派发")
                return 0

            # ---- 1) 上传音频到 MinIO ----
            timestamp = start_utc.strftime("%Y%m%d_%H%M%S")
            upload = await file_service.upload_file(
                file_data=audio_bytes,
                filename=f"recovered_{args.meeting}_{timestamp}.{probe}",
                content_type=content_type,
                prefix="recordings",
            )
            audio_url = upload["object_name"]
            logger.info(f"音频已入库 MinIO: {audio_url}")

            # ---- 2) 清掉可能残留的分片/合并产物/录音心跳 ----
            try:
                deleted = await chunked_upload_service.delete_chunks(args.meeting)
                logger.info(f"清理遗留 chunks: {deleted} 个")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"清理 chunks 失败(忽略): {e}")
            try:
                await chunked_upload_service.delete_merged(args.meeting)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"清理旧 merged 失败(忽略): {e}")
            try:
                await clear_recording_heartbeat(args.meeting)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"清理录音心跳失败(忽略): {e}")

            # ---- 3) 重置会议到"待后处理"状态 ----
            meeting.audio_url = audio_url
            meeting.upload_status = "completed"
            meeting.status = "processing"
            meeting.error_reason = None
            meeting.last_chunk_index = 0
            meeting.total_chunks = 1
            meeting.start_time = start_utc
            meeting.end_time = end_utc
            meeting.recording_started_at = start_utc
            meeting.recording_ended_at = end_utc
            meeting.audio_duration = wall_seconds
            meeting.media_duration_seconds = int(media_seconds) if media_seconds else wall_seconds
            if args.title:
                meeting.title = args.title
            # 派生字段清空，避免旧数据混进新一次流水线的结果
            meeting.transcript = None
            meeting.transcript_polished = None
            meeting.summary = None
            meeting.key_points = None
            meeting.decisions = None
            meeting.speaker_mapping = None
            meeting.speaker_stats = None
            meeting.processing_status = None

            await db.commit()
            await db.refresh(meeting)
            logger.info(
                f"会议 {meeting.id} 已重置: status=processing, audio_url={meeting.audio_url}, "
                f"duration={meeting.media_duration_seconds}s, 窗口={start_utc}~{end_utc} (UTC)"
            )

            # ---- 4) 派发 Celery 后处理 ----
            if args.no_trigger:
                logger.info("--no-trigger: 未派发 Celery 后处理")
                return 0

            from app.services.post_meeting_tasks import post_meeting_process
            async_result = post_meeting_process.delay(meeting.id)
            logger.info(f"已派发 post_meeting_process 任务: task_id={async_result.id}")
            logger.info(
                "后续用以下命令观察进度:\n"
                f"  docker logs -f --tail 200 microbubble-agent-celery-meeting-worker-1 | grep -i 'meeting_id={meeting.id}'"
            )
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
