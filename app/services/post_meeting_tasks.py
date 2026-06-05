"""会议后处理任务 — 6 阶段离线处理

阶段：
0. downloading_audio — 下载音频 + ffmpeg 转 16kHz WAV + VAD 分段
1. transcribing — faster-whisper ASR 转写
2. identifying_speakers — 3D-Speaker 声纹识别 + 发言人标注
3. generating_analysis — Claude Sonnet 分析（标题+摘要+要点+决议）
4. creating_tasks — 从决议/要点自动创建任务
5. storing_results — 存储结果到 DB
6. done — 完成通知

每步：progress_service.update_progress，失败重试 1 次。
"""

import asyncio
import logging
import io
import wave

import numpy as np

from app.core.celery import celery_app
from app.services.progress_service import ProgressStage, update_progress

logger = logging.getLogger("microbubble.post_meeting")


def _numpy_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    """float32 PCM numpy → WAV bytes"""
    pcm_int16 = (audio * 32768).clip(-32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16.tobytes())
    return buf.getvalue()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def post_meeting_process(self, meeting_id: int):
    """Celery 任务：6 阶段离线后处理"""
    logger.info(f"开始后处理: meeting_id={meeting_id}")

    async def _run():
        import redis.asyncio as aioredis
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy.pool import NullPool
        from app.config import settings

        engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            poolclass=NullPool,
        )
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as db:
            from app.models.meeting import Meeting
            from sqlalchemy import select
            result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
            meeting = result.scalar_one_or_none()
            if not meeting:
                logger.error(f"会议不存在: {meeting_id}")
                return

            try:
                # ===== 阶段 0: 下载音频 + VAD 分段 =====
                await update_progress(meeting_id, ProgressStage.DOWNLOADING_AUDIO, detail="下载音频并转码", redis_override=redis_client)
                from app.services.audio_processor import audio_processor
                from app.services.file_service import file_service

                audio_data = await file_service.download_file(meeting.audio_url)
                if not audio_data:
                    raise ValueError("音频文件下载失败")

                audio_pcm, segments, sample_rate = await audio_processor.convert_and_segment(audio_data)
                logger.info(f"音频转码+VAD 分段完成: {len(segments)} 段, 总时长 {len(audio_pcm)/sample_rate:.1f}s")

                # ===== 阶段 1: ASR 转写 =====
                await update_progress(meeting_id, ProgressStage.TRANSCRIBING, detail=f"转写 {len(segments)} 个语音段", redis_override=redis_client)
                from app.voice.asr import asr_service

                transcript_segments = []
                for i, seg in enumerate(segments):
                    wav_bytes = _numpy_to_wav_bytes(seg.audio, sample_rate)
                    result = await asr_service.transcribe(wav_bytes, language="zh", skip_convert=True)
                    text = result.get("text", "").strip()
                    if text:
                        transcript_segments.append({
                            "text": text,
                            "start": round(seg.start_time, 2),
                            "end": round(seg.end_time, 2),
                            "speaker_label": f"speaker_{i}",
                        })
                    logger.debug(f"  段 {i+1}/{len(segments)}: [{seg.start_time:.1f}-{seg.end_time:.1f}s] {text[:50]}")

                logger.info(f"ASR 转写完成: {len(transcript_segments)}/{len(segments)} 段有文本")

                # ===== 阶段 2: 声纹识别 =====
                await update_progress(meeting_id, ProgressStage.IDENTIFYING_SPEAKERS, detail="识别发言人", redis_override=redis_client)
                from app.services.voiceprint_service import VoiceprintService

                vp_service = VoiceprintService()
                speaker_mapping = {}

                for seg in transcript_segments:
                    start_sample = int(seg["start"] * sample_rate)
                    end_sample = int(seg["end"] * sample_rate)
                    seg_audio = audio_pcm[start_sample:end_sample]

                    if len(seg_audio) < sample_rate * 0.5:
                        continue

                    name, member_id, confidence = await vp_service.identify_speaker(db, seg_audio)
                    if name and confidence > 0.55:
                        seg["speaker"] = name
                        speaker_mapping[seg["speaker_label"]] = name
                    else:
                        seg["speaker"] = f"发言人{seg['speaker_label'].split('_')[-1]}"

                # 统一未识别的发言人标签
                unknown_labels = sorted(set(
                    seg["speaker"] for seg in transcript_segments
                    if seg["speaker"].startswith("发言人")
                ))
                label_map = {old: f"发言人{chr(65+i)}" for i, old in enumerate(unknown_labels)}
                for seg in transcript_segments:
                    if seg["speaker"] in label_map:
                        seg["speaker"] = label_map[seg["speaker"]]

                logger.info(f"声纹识别完成: {len(speaker_mapping)} 人已识别, {len(label_map)} 人未知")

                # 将识别出的发言人添加为会议参与者
                from app.models.meeting import MeetingParticipant
                from sqlalchemy import select as sa_select
                identified_member_ids = set()
                for seg in transcript_segments:
                    if seg.get("speaker") and not seg["speaker"].startswith("发言人"):
                        # 通过声纹识别找到 member_id
                        start_sample = int(seg["start"] * sample_rate)
                        end_sample = int(seg["end"] * sample_rate)
                        seg_audio = audio_pcm[start_sample:end_sample]
                        if len(seg_audio) >= sample_rate * 0.5:
                            _, member_id, conf = await vp_service.identify_speaker(db, seg_audio)
                            if member_id and conf > 0.55:
                                identified_member_ids.add(member_id)

                # 去重：检查已有参与者
                existing = await db.execute(
                    sa_select(MeetingParticipant.member_id).where(MeetingParticipant.meeting_id == meeting_id)
                )
                existing_ids = {row[0] for row in existing.fetchall()}

                for mid in identified_member_ids:
                    if mid not in existing_ids:
                        db.add(MeetingParticipant(meeting_id=meeting_id, member_id=mid, role="participant"))
                        logger.info(f"自动添加参与者: member_id={mid}")

                # ===== 阶段 3: AI 分析 =====
                await update_progress(meeting_id, ProgressStage.GENERATING_ANALYSIS, detail="AI 分析会议内容", redis_override=redis_client)
                from app.services.meeting_analysis_service import meeting_analysis

                transcript_text = "\n".join(
                    f"{seg.get('speaker', '未知')}: {seg['text']}"
                    for seg in transcript_segments
                )

                # 生成标题
                if not meeting.title or meeting.title.startswith("听会"):
                    meeting.title = await meeting_analysis.generate_title(transcript_text)

                # 分析摘要/要点/决议
                analysis = await meeting_analysis.analyze_transcript(
                    transcript_text, speaker_mapping=speaker_mapping
                )
                meeting.summary = analysis.get("summary")
                meeting.key_points = analysis.get("key_points", [])
                meeting.decisions = analysis.get("decisions", [])

                # 保存转写结果
                meeting.transcript = transcript_segments
                meeting.speaker_mapping = speaker_mapping

                # ===== 阶段 4: 自动创建任务 =====
                await update_progress(meeting_id, ProgressStage.CREATING_TASKS, detail="自动创建任务", redis_override=redis_client)
                from app.services.meeting_service import MeetingService
                svc = MeetingService(db)

                for decision in analysis.get("decisions", []):
                    await svc._auto_create_task_from_meeting(meeting, decision)

                # ===== 阶段 5: 存储结果 =====
                await update_progress(meeting_id, ProgressStage.STORING_RESULTS, detail="保存结果", redis_override=redis_client)
                meeting.status = "completed"
                await db.commit()

                # ===== 阶段 6: 完成 =====
                await update_progress(meeting_id, ProgressStage.DONE, detail="处理完成", redis_override=redis_client)
                logger.info(f"后处理完成: meeting_id={meeting_id}, 转写{len(transcript_segments)}段, 标题={meeting.title}")

            except Exception as e:
                logger.error(f"后处理阶段失败: meeting_id={meeting_id}, error={e}", exc_info=True)
                meeting.status = "error"
                await db.commit()
                await update_progress(
                    meeting_id, ProgressStage.DONE,
                    detail=f"处理失败: {str(e)[:80]}",
                    status="error",
                    redis_override=redis_client,
                )

        await redis_client.aclose()
        await engine.dispose()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"后处理失败: meeting_id={meeting_id}, error={e}", exc_info=True)
        try:
            err_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(err_loop)
            try:
                err_loop.run_until_complete(update_progress(
                    meeting_id, ProgressStage.DONE,
                    detail=f"处理失败: {str(e)[:80]}",
                    status="error",
                ))
            finally:
                err_loop.close()
        except Exception as push_err:
            logger.error(f"推送 error 状态也失败: {push_err}")
        return {"status": "error", "meeting_id": meeting_id, "error": str(e)}
