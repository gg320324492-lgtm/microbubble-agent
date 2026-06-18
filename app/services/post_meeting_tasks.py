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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def post_meeting_process(self, meeting_id: int):
    """
    Celery 任务：6 阶段离线后处理

    阶段 4 修复（2026-06-12）：阶段 0/1-5 失败时真实调用 self.retry()
    让 Celery 真正重试（之前 max_retries 形同虚设，失败直接落 error）。
    """
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

                # ===== 阶段 1.3: 语义断句（基于规则的对话切换检测） =====
                import re

                # 检测对话切换的模式：
                # 1. 问答模式：第一个问号/感叹号后可能是不同人
                # 2. 转折词："不过"、"但是"、"可"、"那"等开头可能是不同人
                # 3. 回应词："嗯嗯"、"好的"、"行"开头可能是不同人
                SPEAKER_CUT_PATTERNS = [
                    (r'(?<=[？?!！。])\s*(?!.*[？?!！。])(.+$)', '问答切分'),
                    (r'(?<=[。])\s*(?=那[你我他她])', '转折切分'),
                    (r'(?<=[。])\s*(?=好的|嗯|行|对|是的)', '回应切分'),
                    (r'(?<=[。])\s*(?=不过|但是|可|所以|那)', '转折切分'),
                ]

                def _split_by_semantics(text: str, segment_start: float, segment_end: float, seg_index: int) -> list:
                    """基于规则的语义断句：检测对话切换点"""
                    # 模式1：问答 - 最后一个？或！后拆开
                    # 找最后一个问号（"怎么了？"）
                    last_q = max(text.rfind('？'), text.rfind('?'))
                    last_excl = max(text.rfind('！'), text.rfind('!'))

                    # 如果有问号且有后续内容，在问号后切分
                    cut_positions = []
                    if last_q >= 0 and last_q < len(text) - 3:
                        # 问号后面有内容，可能是回答
                        after_q = text[last_q + 1:].strip()
                        if after_q and len(after_q) >= 3:
                            cut_positions.append(last_q + 1)
                    if last_excl >= 0 and last_excl < len(text) - 3:
                        after_ex = text[last_excl + 1:].strip()
                        if after_ex and len(after_ex) >= 3:
                            cut_positions.append(last_excl + 1)

                    # 模式2：检测"好的"、"那"、"嗯"等开头的切换
                    for m in re.finditer(r'[。]?(好的|嗯嗯|行吧|那[你我他她]|不过|但是|可问题是|所以)', text):
                        pos = m.start() + (1 if text[m.start()] == '。' else 0)
                        if pos > 3 and pos not in cut_positions:  # 不在开头
                            cut_positions.append(pos)

                    if not cut_positions:
                        return [{"text": text, "start": segment_start, "end": segment_end,
                                 "speaker_label": f"speaker_{seg_index}"}]

                    # 排序切分点
                    cut_positions = sorted(set(cut_positions))
                    # 过滤太近的切分点（< 5 字间隔）
                    filtered = []
                    prev = -100
                    for pos in cut_positions:
                        if pos - prev >= 5:
                            filtered.append(pos)
                            prev = pos

                    if not filtered:
                        return [{"text": text, "start": segment_start, "end": segment_end,
                                 "speaker_label": f"speaker_{seg_index}"}]

                    # 按切分点拆分
                    parts = []
                    last_cut = 0
                    for cut in filtered:
                        part_text = text[last_cut:cut].strip()
                        if part_text:
                            parts.append(part_text)
                        last_cut = cut
                    part_text = text[last_cut:].strip()
                    if part_text:
                        parts.append(part_text)

                    if len(parts) <= 1:
                        return [{"text": text, "start": segment_start, "end": segment_end,
                                 "speaker_label": f"speaker_{seg_index}"}]

                    total_len = sum(len(p) for p in parts)
                    result = []
                    current_start = segment_start
                    for i, part in enumerate(parts):
                        ratio = len(part) / total_len if total_len > 0 else 0
                        dur = (segment_end - segment_start) * ratio
                        result.append({
                            "text": part,
                            "start": round(current_start, 2),
                            "end": round(current_start + dur, 2),
                            "speaker_label": f"speaker_{seg_index}_{i}",
                        })
                        current_start += dur
                    return result

                semantic_split_segments = []
                for i, seg in enumerate(transcript_segments):
                    text = seg["text"]
                    if len(text) <= 15:
                        semantic_split_segments.append(seg)
                        continue
                    parts = _split_by_semantics(text, seg["start"], seg["end"], i)
                    if len(parts) > 1:
                        logger.debug(f"语义断句: [{seg['start']:.1f}-{seg['end']:.1f}s] {len(text)}字→{len(parts)}段")
                    semantic_split_segments.extend(parts)

                if len(semantic_split_segments) > len(transcript_segments):
                    logger.info(f"语义断句: {len(transcript_segments)}→{len(semantic_split_segments)} 段")
                    transcript_segments = semantic_split_segments

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
                    "纬纳米气泡": "微纳米气泡",
                    "臭氧纬纳米": "臭氧微纳米",
                }
                for ck, cv in TEXT_CORRECTIONS.items():
                    for seg in transcript_segments:
                        if ck in seg["text"]:
                            seg["text"] = seg["text"].replace(ck, cv)

                # ===== 阶段 2: 发言人分离（声纹 + 停顿 + 内容） =====
                await update_progress(meeting_id, ProgressStage.IDENTIFYING_SPEAKERS, detail="识别发言人", redis_override=redis_client)
                from app.services.voiceprint_service import VoiceprintService
                from app.services.speaker_assignment import (
                    SpeakerMatch,
                    correct_speaker_name,
                    cosine_similarity,
                    finalize_cluster_speakers,
                    should_force_split,
                )
                import torch

                vp_service = VoiceprintService()
                speaker_mapping = {}
                speaker_assignment_result = None

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

                # 2.2 对所有转录段提取声纹 embedding（GPU batch 加速）
                # 2026-06-18 优化：3368 段 CPU 串行要 84 分钟，GPU batch=32 几秒搞定
                seg_audios = []  # 与 transcript_segments 等长，None 表示跳过
                for seg in transcript_segments:
                    start_sample = int(seg["start"] * sample_rate)
                    end_sample = int(seg["end"] * sample_rate)
                    seg_audio = audio_pcm[start_sample:end_sample]
                    if len(seg_audio) < sample_rate * 0.5:
                        seg_audios.append(None)
                    else:
                        seg_audios.append(seg_audio)

                # 一次性 batch 推理
                logger.info(f"开始批量声纹提取：{len(seg_audios)} 段")
                seg_embeddings = vp_service.batch_extract_embeddings(
                    seg_audios, batch_size=32
                )
                logger.info(f"批量声纹提取完成：{sum(1 for e in seg_embeddings if e is not None)} 段有效")

                # 2.3 统一聚类所有段的声纹
                from collections import Counter

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
                        sim = cosine_similarity(emb, center)
                        if sim > best_sim:
                            best_sim = sim
                            best_cluster = ci

                    # 相似度 >= 0.40 归为已有聚类
                    if best_sim >= 0.40:
                        clusters.append(best_cluster)
                    else:
                        clusters.append(len(cluster_centers))
                        cluster_centers.append(emb)
                        cluster_representatives.append(emb)

                # 2.4 识别每个段落的发言人（用声纹查询，不依赖聚类）
                unique_clusters = set(c for c in clusters if c >= 0)
                seg_names = []
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
                    if name and conf > 0.35:
                        seg_names.append(name)
                    else:
                        seg_names.append(None)  # 暂时留空，后面统一处理

                # 2.4.5 兜底：聚类数=1 但有多个明显不同的说话模式时强制分裂
                if len(unique_clusters) == 1 and len(seg_embeddings) >= 3:
                    # 计算段间声纹相似度统计
                    sims = []
                    for i in range(len(seg_embeddings)):
                        for j in range(i+1, len(seg_embeddings)):
                            if seg_embeddings[i] is not None and seg_embeddings[j] is not None:
                                sims.append(cosine_similarity(seg_embeddings[i], seg_embeddings[j]))
                    if sims:
                        import statistics
                        mean_sim = statistics.mean(sims)
                        std_sim = statistics.stdev(sims) if len(sims) > 1 else 0
                        max_sim = max(sims)
                        min_sim = min(sims)
                        logger.info(f"聚类统计: 平均={mean_sim:.3f}, 标准差={std_sim:.3f}, max={max_sim:.3f}, min={min_sim:.3f}")

                        # 标准差大说明确实有不同说话人
                        if should_force_split(seg_embeddings):
                            logger.info(f"检测到声纹分布发散（标准差={std_sim:.3f}），强制分裂聚类")
                            # 用 KMeans 硬分 2 聚类
                            from sklearn.cluster import KMeans
                            valid_embs = np.array([e for e in seg_embeddings if e is not None])
                            if len(valid_embs) >= 2:
                                km = KMeans(n_clusters=2, random_state=42, n_init=10).fit(valid_embs)
                                # 重新赋值 clusters
                                idx = 0
                                new_clusters = list(clusters)
                                for i in range(len(seg_embeddings)):
                                    if seg_embeddings[i] is not None:
                                        new_clusters[i] = int(km.labels_[idx])
                                        idx += 1
                                clusters = new_clusters
                                # 重置聚类中心和代表
                                valid_cids = sorted(cid for cid in set(clusters) if cid >= 0)
                                cluster_centers = [None] * (max(valid_cids) + 1)
                                cluster_representatives = [None] * (max(valid_cids) + 1)
                                for cid in valid_cids:
                                    members = [seg_embeddings[i] for i in range(len(seg_embeddings)) if clusters[i] == cid]
                                    if members:
                                        cluster_centers[cid] = members[0]
                                        cluster_representatives[cid] = members[0]
                                logger.info(f"强制分裂后: 聚类数={len(valid_cids)}")
                                # 同步重新识别（用更新后的聚类数）
                                seg_names = []
                                for i, seg in enumerate(transcript_segments):
                                    if clusters[i] < 0:
                                        seg_names.append("发言人?")
                                        continue
                                    start_sample = int(seg["start"] * sample_rate)
                                    end_sample = int(seg["end"] * sample_rate)
                                    seg_audio = audio_pcm[start_sample:end_sample]
                                    if len(seg_audio) < sample_rate * 0.5:
                                        seg_names.append(None)
                                        continue
                                    name, member_id, conf = await vp_service.identify_speaker(db, seg_audio)
                                    if name and conf > 0.35:
                                        seg_names.append(name)
                                    else:
                                        seg_names.append(None)

                                # 2.4.6 立即把 seg["speaker"] 也更新到分裂后聚类
                                for i, seg in enumerate(transcript_segments):
                                    if clusters[i] >= 0 and i < len(seg_names) and seg_names[i]:
                                        seg["speaker"] = seg_names[i]

                # 2.5 聚类 + 声纹结果协调
                unique_clusters = sorted(set(c for c in clusters if c >= 0))
                cluster_votes = {
                    cid: [
                        seg_names[i] for i in range(len(transcript_segments))
                        if clusters[i] == cid and seg_names[i] is not None
                    ]
                    for cid in unique_clusters
                }
                representative_matches = {}
                for cid in unique_clusters:
                    if cid >= len(cluster_representatives) or cluster_representatives[cid] is None:
                        continue
                    name, member_id, conf = await vp_service.identify_speaker_by_embedding(
                        db, cluster_representatives[cid]
                    )
                    representative_matches[cid] = SpeakerMatch(name=name, member_id=member_id, confidence=conf)

                speaker_assignment_result = finalize_cluster_speakers(
                    cluster_ids=unique_clusters,
                    cluster_votes=cluster_votes,
                    representative_matches=representative_matches,
                )
                cluster_to_name = speaker_assignment_result.cluster_to_name
                known_names_set = {
                    name for name in cluster_to_name.values()
                    if name and not name.startswith("发言人")
                }

                logger.info(f"聚类调试: 聚类数={len(unique_clusters)}, 标签={cluster_to_name}")
                if speaker_assignment_result.ambiguous_clusters:
                    logger.warning(
                        "声纹存在歧义聚类: %s",
                        speaker_assignment_result.ambiguous_clusters,
                    )

                # 2.9 分配发言人到每个段
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

                name_corrections = {}
                all_speakers = set(seg.get("speaker", "") for seg in transcript_segments)
                for sp in all_speakers:
                    if sp.startswith("发言人") or not sp:
                        continue

                    corrected = correct_speaker_name(sp, all_members)
                    if corrected != sp:
                        name_corrections[sp] = corrected
                        logger.info(f"名字校对: '{sp}' → '{corrected}'")

                # 应用名字修正
                if name_corrections:
                    for seg in transcript_segments:
                        sp = seg.get("speaker", "")
                        if sp in name_corrections:
                            seg["speaker"] = name_corrections[sp]
                    # 同步更新 cluster_to_name
                    for cid in cluster_to_name:
                        if cluster_to_name[cid] in name_corrections:
                            cluster_to_name[cid] = name_corrections[cluster_to_name[cid]]
                    logger.info(f"名字校对完成: 纠正了 {len(name_corrections)} 个名字")

                # 更新 speaker_mapping
                for seg in transcript_segments:
                    sp = seg.get("speaker", "")
                    if not sp.startswith("发言人") and seg.get("speaker_label"):
                        speaker_mapping[seg["speaker_label"]] = sp

                logger.info(f"声纹识别完成: {len(set(seg.get('speaker','') for seg in transcript_segments))} 位发言人")

                # ===== 阶段 1.8: 规则标点补充（兜底 AI 润色失败的情况） =====
                def _add_punctuation(text: str) -> str:
                    """给中文文本添加基本标点符号"""
                    import re
                    # 已有标点的不处理
                    if re.search(r'[，。？！、；：]', text):
                        return text
                    # 按空格/中文分词边界处加逗号
                    # 问句特征词后加问号
                    text = re.sub(r'([吗呢吧啊])\s*$', r'\1？', text)
                    text = re.sub(r'([吗呢吧啊])\s+', r'\1？', text)
                    # 句末加句号
                    if not re.search(r'[。？！]$', text):
                        text += '。'
                    # 中间长连串加逗号（每隔约 10-15 字加一个）
                    if len(text) > 15 and '，' not in text and '？' not in text:
                        # 在常见连接词后加逗号
                        text = re.sub(r'(然后|所以|但是|不过|而且|因为|或者)', r'，\1', text)
                    return text

                for seg in transcript_segments:
                    seg["text"] = _add_punctuation(seg["text"])

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
                identified_member_ids = set(
                    speaker_assignment_result.known_member_ids
                    if speaker_assignment_result is not None else []
                )
                for seg in transcript_segments:
                    if seg.get("speaker") and not seg["speaker"].startswith("发言人"):
                        member_id = all_members.get(seg["speaker"])
                        if member_id:
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

                # ===== 阶段 2.8: 声纹持续学习（用本次识别结果强化已有声纹） =====
                from datetime import datetime, timezone
                learned_count = 0
                for cid in unique_clusters:
                    if cid < 0 or cid >= len(cluster_representatives):
                        continue
                    sp_name = cluster_to_name.get(cid, "")
                    if not sp_name or sp_name.startswith("发言人"):
                        continue
                    # 找到对应成员
                    member_id = all_members.get(sp_name)
                    if not member_id:
                        continue
                    # 加权平均更新声纹
                    try:
                        emb_new = cluster_representatives[cid]
                        from app.models.member import Member as MemberModel2
                        from sqlalchemy import select as sa_select3
                        member_row = await db.execute(sa_select3(MemberModel2).where(MemberModel2.id == member_id))
                        member = member_row.scalar_one_or_none()
                        if not member:
                            continue
                        if member.voice_embedding is not None and member.voice_sample_count > 0:
                            old = np.array(member.voice_embedding, dtype=np.float32)
                            wt = member.voice_sample_count / (member.voice_sample_count + 1)
                            emb_new = old * wt + emb_new * (1 - wt)
                        member.voice_embedding = emb_new.tolist()
                        member.voice_sample_count = (member.voice_sample_count or 0) + 1
                        member.voice_enrolled_at = datetime.now(timezone.utc).replace(tzinfo=None)
                        learned_count += 1
                        logger.info(f"声纹学习: {sp_name}(id={member_id}) 第{member.voice_sample_count}次更新")
                    except Exception as e:
                        logger.warning(f"声纹学习失败 {sp_name}: {e}")
                if learned_count > 0:
                    await db.commit()
                    logger.info(f"声纹持续学习完成: {learned_count} 人已更新")

                # ===== 阶段 3: AI 分析 =====
                await update_progress(meeting_id, ProgressStage.GENERATING_ANALYSIS, detail="AI 分析会议内容", redis_override=redis_client)
                from app.services.meeting_analysis_service import meeting_analysis

                # 优先使用润色后的文本进行分析
                transcript_text = "\n".join(
                    f"{seg.get('speaker', '未知')}: {seg.get('text_polished', seg['text'])}"
                    for seg in transcript_segments
                )

                # 生成标题
                need_title = not meeting.title or meeting.title.startswith("听会") or meeting.title == "未命名会议"
                if need_title:
                    logger.info(f"开始生成标题，当前标题: '{meeting.title}'")
                    new_title = await meeting_analysis.generate_title(transcript_text)
                    logger.info(f"标题生成结果: '{new_title}'")
                    if new_title and new_title != "未命名会议":
                        meeting.title = new_title
                    else:
                        logger.warning(f"标题生成返回无效: '{new_title}'，保留原标题")

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

                # ===== 阶段 4: 自动创建任务（2026-06-19 默认关闭，决策不再自动变任务） =====
                from app.config import settings
                if settings.ENABLE_AUTO_TASK_FROM_MEETING:
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
                else:
                    logger.info(
                        f"会议 {meeting_id} 后处理: 跳过自动建任务"
                        f"（{len(analysis.get('decisions', []))} 个 decisions 未创建任务；"
                        f"ENABLE_AUTO_TASK_FROM_MEETING=False）"
                    )

                # ===== 阶段 5: 存储结果 =====
                await update_progress(meeting_id, ProgressStage.STORING_RESULTS, detail="保存结果", redis_override=redis_client)
                meeting.status = "completed"
                await db.commit()

                # ===== 阶段 6: 完成 =====
                await update_progress(meeting_id, ProgressStage.DONE, detail="处理完成", redis_override=redis_client)
                logger.info(f"后处理完成: meeting_id={meeting_id}, 转写{len(transcript_segments)}段, 标题={meeting.title}")

            except Exception as e:
                # ★ 阶段 4 修复：瞬时错误（ValueError/IOError/ConnectionError）→ self.retry
                # 永久错误（KeyError/AttributeError）→ 落 error
                import redis as _redis_sync
                try:
                    await redis_client.aclose()
                except Exception:
                    pass
                try:
                    await engine.dispose()
                except Exception:
                    pass

                transient_errors = (ValueError, IOError, OSError, ConnectionError, TimeoutError)
                if isinstance(e, transient_errors):
                    logger.warning(
                        f"后处理瞬时错误: meeting_id={meeting_id}, retry_count={self.request.retries}, error={e}"
                    )
                    try:
                        # 让 Celery 重新调度本任务（max_retries=3, default_retry_delay=60）
                        raise self.retry(exc=e, countdown=60)
                    except self.MaxRetriesExceededError:
                        logger.error(f"会议 {meeting_id} 重试耗尽, 落 error")
                        # 重新 raise 走外层 except 推 error 状态
                        raise

                # 非瞬时错误：标记 error + 推 WS 通知
                logger.error(f"后处理阶段失败（永久错误）: meeting_id={meeting_id}, error={e}", exc_info=True)
                try:
                    # 重新打开 db/redis 推 error 状态（_run 的 db 已关闭，需新建）
                    err_engine = create_async_engine(
                        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                        poolclass=NullPool,
                    )
                    err_session = async_sessionmaker(err_engine, class_=AsyncSession, expire_on_commit=False)
                    err_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                    async with err_session() as db2:
                        r = await db2.execute(select(Meeting).where(Meeting.id == meeting_id))
                        m2 = r.scalar_one_or_none()
                        if m2:
                            m2.status = "error"
                            m2.error_reason = str(e)[:500]
                            await db2.commit()
                    await update_progress(
                        meeting_id, ProgressStage.DONE,
                        detail=f"处理失败: {str(e)[:80]}",
                        status="error",
                        redis_override=err_redis,
                    )
                    await err_redis.aclose()
                    await err_engine.dispose()
                except Exception as push_err:
                    logger.error(f"推送 error 状态也失败: {push_err}")
                return  # 永久错误：return 不 raise（Celery 视为 success）

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
