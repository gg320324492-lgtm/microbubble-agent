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


def _apply_text_corrections(text: str, corrections: dict) -> str:
    """对文本应用纠错映射"""
    for ck, cv in corrections.items():
        if ck in text:
            text = text.replace(ck, cv)
    return text


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein 编辑距离（用于名字模糊匹配）"""
    la, lb = len(a), len(b)
    dp = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, lb + 1):
            temp = dp[j]
            dp[j] = min(
                prev + (0 if a[i - 1] == b[j - 1] else 1),
                dp[j] + 1,
                dp[j - 1] + 1,
            )
            prev = temp
    return dp[lb]


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

                # ===== 阶段 1.5: ASR 文本纠错 =====
                TEXT_CORRECTIONS = {
                    "小七助手": "小气助手",
                    "小西助手": "小气助手",
                    "小汽助手": "小气助手",
                    "小器助手": "小气助手",
                    "小气驻守": "小气助手",
                    "小七驻守": "小气助手",
                    "约纳米气泡": "微纳米气泡",
                    "拆GPT": "ChatGPT",
                    "多通科": "杜同贺",
                    "宋阳": "宋洋",
                }
                for ck, cv in TEXT_CORRECTIONS.items():
                    for seg in transcript_segments:
                        if ck in seg["text"]:
                            seg["text"] = seg["text"].replace(ck, cv)

                # ===== 阶段 2: 发言人分离（声纹 + 停顿 + 内容） =====
                await update_progress(meeting_id, ProgressStage.IDENTIFYING_SPEAKERS, detail="识别发言人", redis_override=redis_client)
                from app.services.voiceprint_service import VoiceprintService
                import torch

                vp_service = VoiceprintService()
                speaker_mapping = {}

                # 2.1 对长段音频做细粒度 VAD，检测发言人切换点
                def _detect_speaker_changes(audio: np.ndarray, sr: int, min_gap_sec: float = 0.4) -> list[tuple[int, int]]:
                    """检测音频中的发言人切换点（基于停顿）
                    返回 [(start_sample, end_sample), ...] 的语音片段列表"""
                    audio_tensor = torch.from_numpy(audio.copy())
                    try:
                        vad_model, vad_utils = torch.hub.load(
                            repo_or_dir="snakers4/silero-vad", model="silero_vad",
                            source="local", force_reload=False, trust_repo=True,
                        )
                        get_timestamps = vad_utils[0]
                        speeches = get_timestamps(
                            audio_tensor, vad_model, threshold=0.5,
                            min_speech_duration_ms=300, min_silence_duration_ms=200,
                            return_seconds=False, sampling_rate=sr,
                        )
                    except Exception:
                        # VAD 失败时回退：整段作为一个片段
                        return [(0, len(audio))]

                    if not speeches:
                        return [(0, len(audio))]

                    # 基于停顿切分（间隔 >= min_gap_sec 视为发言人可能切换）
                    result = []
                    for seg in speeches:
                        start, end = seg["start"], seg["end"]
                        if result and (start - result[-1][1]) >= sr * min_gap_sec:
                            # 停顿足够长，可能是发言人切换
                            result.append((start, end))
                        elif result:
                            # 停顿短，合并到上一段
                            result[-1] = (result[-1][0], end)
                        else:
                            result.append((start, end))
                    return result

                # 2.2 对所有转录段提取声纹 embedding
                seg_embeddings = []
                for seg in transcript_segments:
                    start_sample = int(seg["start"] * sample_rate)
                    end_sample = int(seg["end"] * sample_rate)
                    seg_audio = audio_pcm[start_sample:end_sample]

                    if len(seg_audio) < sample_rate * 0.5:
                        seg_embeddings.append(None)
                        continue

                    emb = vp_service.extract_embedding(seg_audio)
                    seg_embeddings.append(emb)

                # 2.3 统一聚类所有段的声纹
                from numpy.linalg import norm
                from collections import Counter

                def cosine_sim(a, b):
                    return np.dot(a, b) / (norm(a) * norm(b) + 1e-8)

                # 贪心聚类（不限人数）
                cluster_centers = []
                cluster_representatives = []
                clusters = []

                for i, emb in enumerate(seg_embeddings):
                    if emb is None:
                        clusters.append(-1)
                        continue

                    if not cluster_centers:
                        cluster_centers.append(emb)
                        cluster_representatives.append(emb)
                        clusters.append(0)
                        continue

                    best_cluster = -1
                    best_sim = -1
                    for ci, center in enumerate(cluster_centers):
                        sim = cosine_sim(emb, center)
                        if sim > best_sim:
                            best_sim = sim
                            best_cluster = ci

                    # 相似度 >= 0.45 归为已有聚类
                    if best_sim >= 0.45:
                        clusters.append(best_cluster)
                        cluster_centers[best_cluster] = (
                            cluster_centers[best_cluster] * 0.7 + emb * 0.3
                        )
                    else:
                        clusters.append(len(cluster_centers))
                        cluster_centers.append(emb)
                        cluster_representatives.append(emb)

                # 2.4 识别每个段落的发言人（用声纹查询，不依赖聚类）
                # 先为每个段单独识别
                seg_names = []
                for i, seg in enumerate(transcript_segments):
                    if clusters[i] < 0:
                        seg_names.append("发言人?")
                        continue
                    # 用原始音频段做识别（不是 embedding）
                    start_sample = int(seg["start"] * sample_rate)
                    end_sample = int(seg["end"] * sample_rate)
                    seg_audio = audio_pcm[start_sample:end_sample]
                    if len(seg_audio) < sample_rate * 0.5:
                        seg_names.append(None)
                        continue
                    name, member_id, conf = await vp_service.identify_speaker(db, seg_audio)
                    if name and conf > 0.35:  # 更宽松的阈值
                        seg_names.append(name)
                    else:
                        seg_names.append(None)  # 暂时留空，后面统一处理

                # 2.5 聚类 + 声纹结果协调
                # 统计每个聚类中出现的已知名字
                from collections import Counter
                unique_clusters = set(c for c in clusters if c >= 0)
                cluster_to_name = {}
                known_names_set = set()  # 记录所有已知名字

                for cid in unique_clusters:
                    # 收集该聚类中所有已知名字
                    cluster_names = [
                        seg_names[i] for i in range(len(transcript_segments))
                        if clusters[i] == cid and seg_names[i] is not None
                    ]
                    if cluster_names:
                        # 取出现最多的已知名字
                        best_name = Counter(cluster_names).most_common(1)[0][0]
                        cluster_to_name[cid] = best_name
                        known_names_set.add(best_name)
                    else:
                        cluster_to_name[cid] = None

                # 如果所有聚类都没有已知名字 → 使用编号
                if not known_names_set:
                    for cid in unique_clusters:
                        cluster_to_name[cid] = f"发言人{chr(65 + cid) if cid < 26 else str(cid - 25)}"
                else:
                    # 确保每个聚类都有名字：未知聚类分配新名字
                    unknown_count = 0
                    for cid in unique_clusters:
                        if cluster_to_name[cid] is None:
                            # 分配发言人标签
                            label = f"发言人{chr(65 + unknown_count) if unknown_count < 26 else str(unknown_count - 25)}"
                            while label in known_names_set:
                                unknown_count += 1
                                label = f"发言人{chr(65 + unknown_count) if unknown_count < 26 else str(unknown_count - 25)}"
                            cluster_to_name[cid] = label
                            known_names_set.add(label)
                            unknown_count += 1

                # 2.6 分配发言人到每个段
                for i, seg in enumerate(transcript_segments):
                    if clusters[i] >= 0:
                        seg["speaker"] = cluster_to_name[clusters[i]]
                        if not seg["speaker"].startswith("发言人"):
                            speaker_mapping[seg.get("speaker_label", f"speaker_{i}")] = seg["speaker"]
                    else:
                        seg["speaker"] = "发言人?"

                logger.info(f"声纹聚类完成: {len(known_names_set)} 位发言人, 已知={[n for n in known_names_set if not n.startswith('发言人')]}")

                # 后处理：统计确认
                speaker_set = set(seg.get("speaker", "?") for seg in transcript_segments)
                speaker_counts = Counter(seg.get("speaker", "?") for seg in transcript_segments)
                known = [s for s in speaker_set if not s.startswith("发言人") and s != "?"]
                unknown = [s for s in speaker_set if s.startswith("发言人")]
                logger.info(f"发言人确认: {len(known)} 位已知({', '.join(known)}), {len(unknown)} 位未知({', '.join(unknown)}), 共{len(speaker_set)}位")

                # 2.7 校对发言人名字（与成员管理中的真实姓名比对）
                from app.models.member import Member as MemberModel
                from sqlalchemy import select as sa_select2

                member_list = await db.execute(
                    sa_select2(MemberModel.id, MemberModel.name).where(MemberModel.is_active == True)
                )
                all_members = {row[1]: row[0] for row in member_list.fetchall()}  # name → id

                # 谐音/形近字映射表（常见 ASR 识别错误 → 正确姓名）
                PHONETIC_CORRECTIONS = {
                    "杜同和": "杜同贺",
                    "杜同河": "杜同贺",
                    "吴梦全": "吴孟铨",
                    "吴孟全": "吴孟铨",
                    "吴孟栓": "吴孟铨",
                    "王天之": "王天志",
                    "王田志": "王天志",
                    "赵航嘉": "赵航佳",
                    "赵航家": "赵航佳",
                }

                name_corrections = {}
                all_speakers = set(seg.get("speaker", "") for seg in transcript_segments)
                for sp in all_speakers:
                    if sp.startswith("发言人") or not sp:
                        continue

                    # 1) 精确匹配成员列表
                    if sp in all_members:
                        continue  # 无需纠正

                    # 2) 谐音/形近字映射
                    if sp in PHONETIC_CORRECTIONS:
                        corrected = PHONETIC_CORRECTIONS[sp]
                        name_corrections[sp] = corrected
                        logger.info(f"名字校对（谐音）: '{sp}' → '{corrected}'")
                        continue

                    # 3) 模糊匹配：编辑距离 ≤ 1 且不在成员列表中
                    best_match = None
                    best_dist = 99
                    for member_name in all_members:
                        dist = _edit_distance(sp, member_name)
                        if dist < best_dist:
                            best_dist = dist
                            best_match = member_name
                    # 编辑距离 ≤ 1 且名字长度相近，视为同一人
                    if best_dist <= 1 and abs(len(sp) - len(best_match)) <= 1:
                        name_corrections[sp] = best_match
                        logger.info(f"名字校对（模糊匹配）: '{sp}' → '{best_match}' (dist={best_dist})")

                # 应用名字修正
                if name_corrections:
                    for seg in transcript_segments:
                        sp = seg.get("speaker", "")
                        if sp in name_corrections:
                            seg["speaker"] = name_corrections[sp]
                    # 同步更新 cluster_speakers
                    for cid in cluster_speakers:
                        if cluster_speakers[cid] in name_corrections:
                            cluster_speakers[cid] = name_corrections[cluster_speakers[cid]]
                    logger.info(f"名字校对完成: 纠正了 {len(name_corrections)} 个名字")

                # 更新 speaker_mapping
                for seg in transcript_segments:
                    sp = seg.get("speaker", "")
                    if not sp.startswith("发言人") and seg.get("speaker_label"):
                        speaker_mapping[seg["speaker_label"]] = sp

                logger.info(f"声纹识别完成: {len(set(seg.get('speaker','') for seg in transcript_segments))} 位发言人")

                # ===== 阶段 2.5: AI 润色转录 =====
                await update_progress(meeting_id, ProgressStage.IDENTIFYING_SPEAKERS, detail="AI 润色转录文本", redis_override=redis_client)
                from app.services.meeting_ai_polish import polish_segments_with_lock

                # 准备润色上下文
                participant_names = list(speaker_mapping.values())
                polish_context = {
                    "title": meeting.title or "未命名会议",
                    "participants": participant_names,
                    "topic": None,
                    "context": [],
                }

                # 为润色添加 ts 字段（从 start 时间戳）
                segments_for_polish = []
                for seg in transcript_segments:
                    segments_for_polish.append({
                        "speaker": seg.get("speaker", "未知"),
                        "text": seg["text"],
                        "ts": seg.get("start", 0),
                    })

                try:
                    polish_result = await polish_segments_with_lock(
                        meeting_id, segments_for_polish, polish_context
                    )
                    polished_segments = polish_result.get("polished", [])
                    if polished_segments:
                        # 将润色后的文本回写到 transcript_segments
                        for i, polished in enumerate(polished_segments):
                            if i < len(transcript_segments):
                                transcript_segments[i]["text_polished"] = polished.get("text", transcript_segments[i]["text"])
                        logger.info(f"AI 润色完成: {len(polished_segments)} 段")
                    else:
                        logger.warning("AI 润色返回空结果，使用原文")
                except Exception as e:
                    logger.warning(f"AI 润色失败（降级为原文）: {e}")

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

                # 优先使用润色后的文本进行分析
                transcript_text = "\n".join(
                    f"{seg.get('speaker', '未知')}: {seg.get('text_polished', seg['text'])}"
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
                # 对 AI 输出也做文本纠错（"小七助手"→"小气助手" 等）
                meeting.summary = _apply_text_corrections(meeting.summary or "", TEXT_CORRECTIONS)
                meeting.key_points = [_apply_text_corrections(kp, TEXT_CORRECTIONS) for kp in (meeting.key_points or [])]
                meeting.decisions = [_apply_text_corrections(d, TEXT_CORRECTIONS) for d in (meeting.decisions or [])]

                # 保存转写结果（原始 + 润色版）
                meeting.transcript = transcript_segments
                meeting.speaker_mapping = speaker_mapping

                # 构建润色版转录（用于前端显示）
                transcript_polished = []
                for seg in transcript_segments:
                    transcript_polished.append({
                        "speaker": seg.get("speaker", "未知"),
                        "text": seg.get("text_polished", seg["text"]),
                        "ts": seg.get("start", 0),
                    })
                meeting.transcript_polished = transcript_polished
                logger.info(f"保存转录: {len(transcript_segments)} 段原始 + {len(transcript_polished)} 段润色")

                # 计算发言统计
                try:
                    speaker_stats = meeting_analysis.compute_speaker_stats(transcript_polished)
                    meeting.speaker_stats = speaker_stats
                    logger.info(f"发言统计完成: {len(speaker_stats)} 人")
                except Exception as e:
                    logger.warning(f"发言统计计算失败: {e}")

                # ===== 阶段 4: 自动创建任务 =====
                await update_progress(meeting_id, ProgressStage.CREATING_TASKS, detail="自动创建任务", redis_override=redis_client)
                from app.services.meeting_service import MeetingService
                svc = MeetingService(db)

                for decision in analysis.get("decisions", []):
                    # decisions 可能是字符串或字典，统一转为字典格式
                    if isinstance(decision, str):
                        task_info = {"title": decision}
                    elif isinstance(decision, dict):
                        task_info = decision
                    else:
                        continue
                    await svc._auto_create_task_from_meeting(meeting, task_info)

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
