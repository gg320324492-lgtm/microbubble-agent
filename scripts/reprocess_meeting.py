"""重处理会议发言人识别 (通用化版本)

适用场景：
  会议处理完后，发现某发言人当时没录入声纹 → 全部未识别 (例如 97% 显示"发言人?")
  → 后续录入了新声纹 → 重跑识别流程

新流程固定为模式（2026-06-19 沉淀）：
  1. load    — 读 DB transcript + 音频（m4a 或 MinIO chunks）
  2. extract — 每段提 embedding（ThreadPoolExecutor 并行 + 锁保护 pipeline.model）
  3. cluster — KMeans 自动选 K（silhouette 评估）
  4. vote    — 每聚类对所有已录入声纹成员投票决定名字
  5. assign  — 重新分配 transcript.speaker（按 new_speaker 数组）
  6. backup  — 8 字段全部备份到 *_old_v1 (幂等)
  7. update  — 写回 DB (transcript / transcript_polished / speaker_mapping / speaker_stats / meeting_participants)
  8. regen   — 调 LLM 重生成 summary / key_points / decisions
  9. verify  — 8 字段全 0 旧错标人 + API 抽查

CLI 用法：
  docker cp scripts/reprocess_meeting.py microbubble-agent-app-1:/tmp/
  docker exec -i microbubble-agent-app-1 python /tmp/reprocess_meeting.py --meeting 120 --audio /tmp/x.m4a
  docker exec -i microbubble-agent-app-1 python /tmp/reprocess_meeting.py --meeting 120 --steps verify

幂等：备份字段 *_old_v1 已存在则跳过该 step（不覆盖老备份）

输出：
  /tmp/reprocess_{meeting_id}_result.json — 中间结果（用于诊断）
  /tmp/reprocess_{meeting_id}_new_transcript.json — 重建的 transcript
  终端日志：每步进度 + 8 字段 verify 结果
"""
import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import wave
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reprocess_meeting")

SAMPLE_RATE = 16000
MIN_SEG_SEC = 0.6
MAX_SEG_SEC = 3.0
N_WORKERS = 8

# 并发保护（2026-06-19 修复 bug：pipeline.model 跨线程访问竞态）
_extract_lock = threading.Lock()


# ============================================================================
# Step 1: load
# ============================================================================
def load_audio(audio_path: str, max_duration_sec: int = 10800) -> np.ndarray:
    """m4a/wav → 16kHz mono float32 PCM"""
    if audio_path.endswith(".m4a"):
        out_path = audio_path.replace(".m4a", "_16k.wav")
        if not os.path.exists(out_path):
            logger.info(f"ffmpeg {audio_path} → {out_path} ...")
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "wav", out_path],
                check=True, capture_output=True, timeout=600,
            )
        wav_path = out_path
    else:
        wav_path = audio_path

    with wave.open(wav_path, "rb") as wf:
        nframes = wf.getnframes()
        pcm = np.frombuffer(wf.readframes(nframes), dtype=np.int16).astype(np.float32) / 32768.0
    if len(pcm) > max_duration_sec * SAMPLE_RATE:
        pcm = pcm[: max_duration_sec * SAMPLE_RATE]
    logger.info(f"加载音频: {len(pcm) / SAMPLE_RATE:.1f}s, {len(pcm)} 样本")
    return pcm


async def fetch_meeting(meeting_id: int) -> dict:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import settings
    from app.models.meeting import Meeting
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        m = await db.get(Meeting, meeting_id)
        if not m:
            raise ValueError(f"Meeting {meeting_id} 不存在")
        return {
            "id": m.id,
            "title": m.title,
            "transcript": list(m.transcript or []),
            "transcript_polished": list(m.transcript_polished or []),
            "speaker_mapping": dict(m.speaker_mapping or {}),
        }


# ============================================================================
# Step 2: extract (声纹提取 — 修复 batch bug)
# ============================================================================
def _extract_one(vp_service, audio: np.ndarray) -> np.ndarray:
    """单条声纹提取（带锁保护 self._pipeline.model 并发访问）"""
    if audio is None or len(audio) == 0:
        return np.zeros(192, dtype=np.float32)
    try:
        with _extract_lock:
            return vp_service._extract_via_model(audio)
    except Exception as e:
        logger.error(f"chunk 提取失败: {e}")
        from app.services.voiceprint_service import EMBEDDING_DIM
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)


def extract_embeddings_parallel(vp_service, chunks: list) -> list:
    """ThreadPoolExecutor 并行单条声纹提取

    Bug 修复 (2026-06-19):
      modelscope ERes2Net_aug.py 的 __extract_feature 强制 batch=1，
      即便输入是 (4, 32000) feature 也是 (1, ?, ?)。
      旧 batch_extract_embeddings 把 32 段一次性塞给模型 → 实际只处理第 1 段。
      修法：单条调用 + ThreadPoolExecutor(8) 并行。
    """
    results = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futures = {ex.submit(_extract_one, vp_service, c): i for i, c in enumerate(chunks) if c is not None}
        done = 0
        for fut in futures:
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as e:
                logger.error(f"chunk {i} 失败: {e}")
                from app.services.voiceprint_service import EMBEDDING_DIM
                results[i] = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            done += 1
            if done % 200 == 0:
                logger.info(f"  进度: {done}/{len(futures)}")
    return results


def prepare_chunks(pcm: np.ndarray, transcript: list) -> tuple:
    """按 transcript 切分音频 chunks"""
    chunks = []
    valid_idx = []
    skipped = 0
    for i, seg in enumerate(transcript):
        s = float(seg.get("start", 0))
        e = float(seg.get("end", 0))
        if e <= s:
            chunks.append(None)
            skipped += 1
            continue
        a = int(s * SAMPLE_RATE)
        b = int(e * SAMPLE_RATE)
        chunk = pcm[a:b]
        if len(chunk) < int(MIN_SEG_SEC * SAMPLE_RATE):
            chunks.append(None)
            skipped += 1
            continue
        if len(chunk) > MAX_SEG_SEC * SAMPLE_RATE:
            mid = len(chunk) // 2
            chunk = chunk[mid - int(1.5 * SAMPLE_RATE): mid + int(1.5 * SAMPLE_RATE)]
        chunks.append(chunk)
        valid_idx.append(i)
    logger.info(f"分块: {len(transcript)} 段, {len(valid_idx)} 段有效, {skipped} 段过短")
    return chunks, valid_idx


# ============================================================================
# Step 3: cluster
# ============================================================================
def cluster_embeddings(seg_embs: list, n_expected: int = 3) -> tuple:
    """KMeans 自动选 K（silhouette 评估）"""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    valid = np.array([e for e in seg_embs if e is not None])
    if len(valid) < 2:
        return [0] * len(seg_embs), 1, -1.0
    k_options = list(range(2, min(n_expected + 3, len(valid))))
    best_k, best_score = 2, -1
    for k in k_options:
        try:
            km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(valid)
            s = silhouette_score(valid, km.labels_)
            logger.info(f"  K={k} silhouette={s:.3f}")
            if s > best_score:
                best_k, best_score = k, s
        except Exception as e:
            logger.warning(f"K={k}: {e}")
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit(valid)
    labels = [-1] * len(seg_embs)
    j = 0
    for i, e in enumerate(seg_embs):
        if e is not None:
            labels[i] = int(km.labels_[j])
            j += 1
    return labels, best_k, best_score


# ============================================================================
# Step 4: vote
# ============================================================================
def _vp_identify_sync(embedding, enrolled_list, match_threshold: float = 0.7):
    if np.all(embedding == 0):
        return None, None, 0.0
    emb = np.array(embedding, dtype=np.float32)
    best_name, best_mid, best_dist = None, None, 999.0
    for mid, name, db_emb in enrolled_list:
        if db_emb is None:
            continue
        db_emb = np.array(db_emb, dtype=np.float32)
        if np.all(db_emb == 0):
            continue
        dist = float(1.0 - np.dot(emb, db_emb) / (np.linalg.norm(emb) * np.linalg.norm(db_emb) + 1e-8))
        if dist < best_dist:
            best_dist = dist
            best_name = name
            best_mid = mid
    if best_dist < match_threshold:
        return best_name, best_mid, 1.0 - best_dist
    return None, None, 1.0 - best_dist


def vote_names_by_cluster(seg_embs: list, labels: list, enrolled: list) -> dict:
    """每聚类对所有已录入成员投票决定名字"""
    cluster_names = {}
    for cid in sorted(set(l for l in labels if l >= 0)):
        idxs = [i for i, l in enumerate(labels) if l == cid]
        names_with_conf = []
        for i in idxs:
            if seg_embs[i] is None:
                continue
            n, mid, conf = _vp_identify_sync(seg_embs[i], enrolled)
            if n:
                names_with_conf.append((n, conf))
        if not names_with_conf:
            cluster_names[cid] = (None, 0.0, 0, 0)
            continue
        ctr = Counter([n for n, _ in names_with_conf])
        best_name, votes = ctr.most_common(1)[0]
        confs = [c for n, c in names_with_conf if n == best_name]
        cluster_names[cid] = (best_name, float(np.mean(confs)), votes, len(idxs))
        logger.info(
            f"  聚类 {cid} ({len(idxs)} 段, 有效 {len(names_with_conf)}): "
            f"{best_name} votes={votes} avg_conf={cluster_names[cid][1]:.3f}"
        )
    return cluster_names


# ============================================================================
# Step 5: assign
# ============================================================================
def assign_speakers(transcript: list, labels: list, seg_embs: list, cluster_names: dict) -> tuple:
    """重新分配 transcript.speaker，返回 (new_speaker, speaker_label_to_name)"""
    new_speaker = [""] * len(transcript)
    speaker_label_to_name = {}
    unknown_idx = 0
    for i, seg in enumerate(transcript):
        if labels[i] < 0 or seg_embs[i] is None:
            new_speaker[i] = "发言人?"
            continue
        cid = labels[i]
        name, conf, votes, _ = cluster_names.get(cid, (None, 0.0, 0, 0))
        if name and votes >= 1 and conf > 0.30:
            new_speaker[i] = name
            old_label = seg.get("speaker_label", f"speaker_{i}")
            speaker_label_to_name[old_label] = name
        else:
            new_speaker[i] = f"发言人{chr(65 + unknown_idx) if unknown_idx < 26 else unknown_idx - 25}"
            unknown_idx += 1
    ctr = Counter(new_speaker)
    logger.info(f"新 speaker 分布: {dict(ctr)}")
    return new_speaker, speaker_label_to_name


# ============================================================================
# Step 6+7: backup + update
# ============================================================================
async def apply_to_db(meeting_id: int, new_speaker: list, backup: bool = True, workdir: str = "/tmp") -> dict:
    """把 new_speaker 应用到 DB 8 字段

    备份策略 (2026-06-19 修复):
      用文件备份而非 DB 列 — Meeting model 没 *_old_v1 列，
      SQLAlchemy 会静默忽略未映射属性，让"已备份"成为谎言。
      文件备份路径: {workdir}/meeting_{id}_backup_{timestamp}.json
      幂等: 同一 workdir 下的备份文件不会被覆盖（timestamp 唯一）

    更新字段:
      transcript[*].speaker, transcript_polished[*].speaker,
      speaker_mapping, speaker_stats, meeting_participants
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, delete
    from app.config import settings
    from app.models.meeting import Meeting, MeetingParticipant
    from app.models.member import Member
    from datetime import datetime

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    result = {"backup_file": None, "updated_fields": [], "added_participants": []}
    async with sf() as db:
        m = await db.get(Meeting, meeting_id)
        old_transcript = list(m.transcript or [])
        old_polished = list(m.transcript_polished or [])

        # 备份到文件（幂等：含时间戳，不覆盖）
        if backup:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = Path(workdir) / f"meeting_{meeting_id}_backup_{ts}.json"
            backup_data = {
                "meeting_id": meeting_id,
                "title": m.title,
                "backup_at": ts,
                "transcript": old_transcript,
                "transcript_polished": old_polished,
                "speaker_mapping": dict(m.speaker_mapping or {}),
                "speaker_stats": list(m.speaker_stats or []),
                "summary": m.summary,
                "key_points": list(m.key_points or []),
                "decisions": list(m.decisions or []),
            }
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            result["backup_file"] = str(backup_path)
            logger.info(f"备份写入 {backup_path} ({len(old_transcript)} 段, "
                        f"{len(old_polished)} polished, summary={len(m.summary or '')} chars)")

        # 1. transcript
        new_t_list = []
        for i, seg in enumerate(old_transcript):
            ns = dict(seg)
            ns["speaker"] = new_speaker[i] if i < len(new_speaker) else "发言人?"
            new_t_list.append(ns)
        m.transcript = new_t_list
        result["updated_fields"].append(f"transcript ({len(new_t_list)} 段)")

        # 2. transcript_polished
        new_p_list = []
        for i, pseg in enumerate(old_polished):
            np_ = dict(pseg)
            np_["speaker"] = new_speaker[i] if i < len(new_speaker) else "发言人?"
            new_p_list.append(np_)
        m.transcript_polished = new_p_list
        result["updated_fields"].append(f"transcript_polished ({len(new_p_list)} 段)")

        # 3. speaker_mapping
        new_mapping = {}
        for i, seg in enumerate(old_transcript):
            old_label = seg.get("speaker_label", f"speaker_{i}")
            new_name = new_speaker[i] if i < len(new_speaker) else "发言人?"
            if new_name and not new_name.startswith("发言人"):
                new_mapping[old_label] = new_name
        m.speaker_mapping = new_mapping
        result["updated_fields"].append(f"speaker_mapping ({len(new_mapping)} 条)")

        # 4. speaker_stats
        ctr = Counter()
        dur = Counter()
        chars = Counter()
        for i, seg in enumerate(new_t_list):
            name = new_speaker[i] if i < len(new_speaker) else "发言人?"
            if not name.startswith("发言人") and name != "?":
                ctr[name] += 1
                dur[name] += float(seg.get("end", 0)) - float(seg.get("start", 0))
                chars[name] += len(seg.get("text", ""))
        new_stats = [
            {"name": name, "segments": ctr[name], "duration_sec": round(dur[name], 1), "chars": chars[name]}
            for name in ctr
        ]
        new_stats.sort(key=lambda x: -x["segments"])
        m.speaker_stats = new_stats
        result["updated_fields"].append(f"speaker_stats ({len(new_stats)} 条)")

        # 5. meeting_participants
        real_speakers = list({n for n in new_speaker if n and not n.startswith("发言人")})
        result2 = await db.execute(
            select(Member).where(Member.name.in_(real_speakers))
        )
        name_to_member = {m_.name: m_ for m_ in result2.scalars().all()}
        await db.execute(
            delete(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id)
        )
        for name in real_speakers:
            member = name_to_member.get(name)
            if not member:
                logger.warning(f"未找到成员: {name}")
                continue
            db.add(MeetingParticipant(meeting_id=meeting_id, member_id=member.id, role="participant"))
            result["added_participants"].append(f"{name} (id={member.id})")

        await db.commit()
        result["real_speakers"] = real_speakers

    await engine.dispose()
    return result


# ============================================================================
# Step 8: regen
# ============================================================================
def build_transcript_text(transcript: list, max_chars: int = 80000) -> str:
    lines = []
    cur_speaker = None
    cur_texts = []
    for seg in transcript:
        sp = seg.get("speaker", "发言人?")
        text = seg.get("text", "").strip()
        if not text or len(text) < 2 or text in ("嗯", "啊", "哦", "哎", "好", "的", "了"):
            continue
        if sp != cur_speaker:
            if cur_speaker and cur_texts:
                lines.append(f"【{cur_speaker}】{''.join(cur_texts)}")
            cur_speaker = sp
            cur_texts = [text]
        else:
            cur_texts.append(text)
    if cur_speaker and cur_texts:
        lines.append(f"【{cur_speaker}】{''.join(cur_texts)}")
    full = "\n".join(lines)
    if len(full) > max_chars:
        half = max_chars // 2
        full = full[:half] + "\n... [省略] ...\n" + full[-half:]
    return full


async def regen_summary(meeting_id: int, real_speakers: list, workdir: str = "/tmp") -> dict:
    """重新生成 summary / key_points / decisions（调 LLM）"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import settings
    from app.models.meeting import Meeting
    from app.core.llm import (
        get_anthropic_client,
        get_default_model,
        parse_llm_json,
        extract_text_from_response,
    )
    from app.services.meeting_analysis_service import ANALYSIS_PROMPT
    from datetime import datetime

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        m = await db.get(Meeting, meeting_id)
        transcript_text = build_transcript_text(m.transcript or [])

        # 备份 summary/key_points/decisions 到文件（不依赖 DB 列）
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(workdir) / f"meeting_{meeting_id}_summary_backup_{ts}.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump({
                "meeting_id": meeting_id,
                "backup_at": ts,
                "summary": m.summary,
                "key_points": list(m.key_points or []),
                "decisions": list(m.decisions or []),
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"summary/key_points/decisions 备份写入 {backup_path}")

        client = get_anthropic_client()
        model = get_default_model()
        user_prompt = ANALYSIS_PROMPT.format(transcript_text=transcript_text)
        logger.info(f"调 LLM ({model}), transcript {len(transcript_text)} 字符 ...")
        response = await client.messages.create(
            model=model,
            max_tokens=16000,
            system="你是微纳米气泡课题组的会议纪要生成助手，按要求输出严格 JSON。",
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = extract_text_from_response(response)
        if not text:
            raise RuntimeError("LLM 返回空")
        result = parse_llm_json(text)

        m.summary = (result.get("summary", "") or "").strip()
        m.key_points = result.get("key_points", [])
        m.decisions = result.get("decisions", [])
        await db.commit()
        backup_file = str(backup_path)

    await engine.dispose()
    return {
        "summary_len": len(m.summary or ""),
        "key_points": len(m.key_points or []),
        "decisions": len(m.decisions or []),
        "backup_file": backup_file,
    }


# ============================================================================
# Step 9: verify
# ============================================================================
async def verify_eight_fields(meeting_id: int) -> dict:
    """8 字段全 0 旧错标人（参考 CLAUDE.md 2026-06-15 教训）

    关键：speaker 字段名要严格匹配，【】括号内才算 speaker，
    正文里出现 "洪辉"（人名提及）不算错标。
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text as sa_text
    from app.config import settings

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        result = await db.execute(sa_text("""
            -- 字段值是 speaker 字段（直接匹配）
            SELECT 'transcript' AS f, COUNT(*) FROM meetings, jsonb_array_elements(transcript::jsonb) e
              WHERE id = :mid AND (e->>'speaker' IN ('洪辉','赵航佳') OR e->>'speaker' ~ '^test_' OR e->>'speaker' ~ '^发言人[ABCDE]$')
            UNION ALL SELECT 'transcript_polished', COUNT(*) FROM meetings, jsonb_array_elements(transcript_polished::jsonb) e
              WHERE id = :mid AND (e->>'speaker' IN ('洪辉','赵航佳') OR e->>'speaker' ~ '^test_' OR e->>'speaker' ~ '^发言人[ABCDE]$')
            UNION ALL SELECT 'speaker_mapping', COUNT(*) FROM meetings, jsonb_each_text(speaker_mapping::jsonb)
              WHERE id = :mid AND (value IN ('洪辉','赵航佳') OR value ~ '^test_' OR value ~ '^发言人[ABCDE]$')
            UNION ALL SELECT 'speaker_stats', COUNT(*) FROM meetings, jsonb_array_elements(speaker_stats::jsonb) s
              WHERE id = :mid AND (s->>'name' IN ('洪辉','赵航佳') OR s->>'name' ~ '^test_' OR s->>'name' ~ '^发言人[ABCDE]$')
            UNION ALL SELECT 'meeting_participants', COUNT(*) FROM meeting_participants mp JOIN members m ON m.id = mp.member_id
              WHERE mp.meeting_id = :mid AND (m.name IN ('洪辉','赵航佳') OR m.name ~ '^test_')
            -- 文本字段只看【】括号内的 speaker 前缀
            UNION ALL SELECT 'key_points', COUNT(*) FROM meetings, unnest(key_points) kp
              WHERE id = :mid AND kp ~ '^【(洪辉|赵航佳|test_\\w+|发言人[ABCDE])】'
            UNION ALL SELECT 'decisions', COUNT(*) FROM meetings, unnest(decisions) d
              WHERE id = :mid AND d ~ '^【(洪辉|赵航佳|test_\\w+|发言人[ABCDE])】'
            UNION ALL SELECT 'summary', COUNT(*) FROM meetings
              WHERE id = :mid AND summary ~ '^【(洪辉|赵航佳|test_\\w+|发言人[ABCDE])】'
        """), {"mid": meeting_id})
        rows = result.fetchall()
    await engine.dispose()
    return {f: n for f, n in rows}


# ============================================================================
# Main pipeline
# ============================================================================
async def main():
    parser = argparse.ArgumentParser(description="重处理会议发言人识别")
    parser.add_argument("--meeting", type=int, required=True, help="会议 ID")
    parser.add_argument("--audio", type=str, default=None, help="音频文件路径（m4a/wav），不传则跳过 extract")
    parser.add_argument("--steps", type=str, default="load,extract,cluster,vote,assign,apply,regen,verify",
                        help="逗号分隔的步骤，默认全跑")
    parser.add_argument("--n-expected", type=int, default=3, help="应到会人数（用于 KMeans K 搜索范围）")
    parser.add_argument("--skip-backup", action="store_true", help="不备份旧字段（用于调试）")
    parser.add_argument("--workdir", type=str, default="/tmp", help="中间结果输出目录")
    parser.add_argument("--learn", action="store_true",
                        help="apply 后自动调 learn_from_verified_segments, 把 verified 段累积到 member.voice_embedding (下次识别率提升)")
    args = parser.parse_args()

    steps = set(args.steps.split(","))
    meeting_id = args.meeting
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    result_path = workdir / f"reprocess_{meeting_id}_result.json"
    new_t_path = workdir / f"reprocess_{meeting_id}_new_transcript.json"

    # 自动加前置依赖
    if "extract" in steps: steps.add("load")
    if "cluster" in steps: steps.update({"load", "extract"})
    if "vote" in steps: steps.update({"load", "extract", "cluster"})
    if "assign" in steps: steps.update({"load", "extract", "cluster", "vote"})
    if "apply" in steps: steps.update({"load", "extract", "cluster", "vote", "assign"})
    # regen 不依赖 extract/cluster — 直接复用 /tmp/reprocess_{id}_result.json 里的 new_speaker
    if "regen" in steps: steps.add("load")

    logger.info(f"=== 重处理会议 #{meeting_id} ===")
    logger.info(f"Steps: {sorted(steps)}")

    # Step 1: load
    if "load" in steps:
        meeting = await fetch_meeting(meeting_id)
        transcript = meeting["transcript"]
        logger.info(f"[1/load] 标题: {meeting['title']} | 段数: {len(transcript)}")
    else:
        logger.info("[1/load] skip")

    if "extract" in steps:
        from app.services.voiceprint_service import voiceprint_service
        voiceprint_service._load_pipeline()
        pcm = load_audio(args.audio)
        chunks, valid_idx = prepare_chunks(pcm, transcript)
        logger.info(f"[2/extract] ThreadPoolExecutor(N_WORKERS={N_WORKERS}) 并行 ...")
        embs = extract_embeddings_parallel(voiceprint_service, [chunks[i] for i in valid_idx])
        seg_embs = [None] * len(transcript)
        for j, i in enumerate(valid_idx):
            seg_embs[i] = embs[j]
        n_valid = sum(1 for e in seg_embs if e is not None and not np.all(e == 0))
        logger.info(f"[2/extract] {n_valid}/{len(transcript)} 段有效")

    if "cluster" in steps:
        # 2026-06-26 优化: 用 smart_select_k 综合 silhouette + 平衡度 + n_expected 评分
        from app.services.voiceprint_voting import smart_select_k
        labels, n_clusters, silhouette, _all_scores = smart_select_k(seg_embs, n_expected=args.n_expected)
        logger.info(f"[3/cluster] smart_select_k K={n_clusters}, composite={silhouette:.3f}")

    if "vote" in steps:
        from app.config import settings as _s
        from app.models.member import Member
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import select
        engine = create_async_engine(
            _s.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        )
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        # 加载 enrolled (4-tuple 含 sample_count)
        async with sf() as db:
            r = await db.execute(
                select(Member).where(Member.voice_embedding.isnot(None))
            )
            enrolled = [
                (m.id, m.name, np.array(m.voice_embedding, dtype=np.float32), m.voice_sample_count or 1)
                for m in r.scalars().all()
                if m.voice_embedding is not None
            ]
            # 2026-06-26 优化: 用 meeting context (summary / description / history) 过滤 enrolled
            from app.models.meeting import Meeting
            from app.services.voiceprint_voting import (
                extract_context_speakers, resolve_context_to_names,
                get_recent_meeting_speakers,
            )
            meeting_obj = await db.get(Meeting, meeting_id)
            ctx_raw = extract_context_speakers(meeting_obj)
            ctx = await resolve_context_to_names(ctx_raw, db) if ctx_raw else set()
            history_ctx = await get_recent_meeting_speakers(meeting_id, db, lookback_count=10, lookback_days=90)
            if history_ctx:
                ctx = ctx | history_ctx
            logger.info(f"[4/vote] 已录入声纹成员: {len(enrolled)} 人, context={ctx if ctx else '(无)'}")
        await engine.dispose()

        # 2026-06-26 优化: 用 vote_with_quality_gates (Hungarian + sample_count penalty + 4 质量门)
        from app.services.voiceprint_voting import vote_with_quality_gates
        cluster_names = vote_with_quality_gates(
            seg_embs, labels, enrolled, context_names=ctx if ctx else None,
            center_dist_threshold=0.75, min_votes=3, votes_ratio_threshold=0.30,
        )

    if "assign" in steps:
        # 2026-06-26 优化: 用 assign_with_strict_threshold (conf > 0.50 + votes_ratio >= 0.5)
        from app.services.voiceprint_voting import assign_with_strict_threshold
        new_speaker, speaker_label_to_name = assign_with_strict_threshold(
            transcript, labels, cluster_names,
            conf_threshold=0.50, votes_ratio_threshold=0.5,
        )
        # 保存中间结果
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "meeting_id": meeting_id,
                "n_segments": len(transcript),
                "n_valid_embs": sum(1 for e in seg_embs if e is not None),
                "n_clusters": n_clusters,
                "silhouette": silhouette,
                "cluster_names": {cid: {"name": n, "avg_conf": c, "votes": v, "total_segments": t}
                                  for cid, (n, c, v, t) in cluster_names.items()},
                "speaker_label_to_name": speaker_label_to_name,
                "new_speaker": new_speaker,
                "enrolled_members": [{"id": item[0], "name": item[1]} for item in enrolled],
            }, f, ensure_ascii=False, indent=2)
        new_t_list = [
            {**seg, "speaker": new_speaker[i]}
            for i, seg in enumerate(transcript)
        ]
        with open(new_t_path, "w", encoding="utf-8") as f:
            json.dump(new_t_list, f, ensure_ascii=False, indent=2)
        logger.info(f"[5/assign] 中间结果 → {result_path}")

    if "apply" in steps:
        apply_result = await apply_to_db(meeting_id, new_speaker, backup=not args.skip_backup, workdir=str(workdir))
        logger.info(f"[6,7/apply] 备份文件: {apply_result['backup_file']}")
        logger.info(f"[6,7/apply] 更新: {apply_result['updated_fields']}")
        logger.info(f"[6,7/apply] 参与者: {apply_result['added_participants']}")

        # 2026-06-26 新增: --learn 自动累积 verified 段到 member.voice_embedding
        if args.learn and seg_embs is not None:
            from app.services.voiceprint_voting import learn_from_verified_segments
            from app.models.member import Member
            from sqlalchemy import select
            from collections import defaultdict
            engine_l = create_async_engine(
                settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            )
            sf_l = async_sessionmaker(engine_l, class_=AsyncSession, expire_on_commit=False)
            # 构造 member_id → [seg_emb] 从 cluster_names 映射
            member_to_segs = defaultdict(list)
            for cid, (name, conf, votes, total) in cluster_names.items():
                if not name:
                    continue
                # 拿 member_id
                # 用现有的 enrolled 列表
                for item in enrolled:
                    if item[1] == name:
                        mid = item[0]
                        for i, lab in enumerate(labels):
                            if lab == cid and seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0):
                                member_to_segs[mid].append(seg_embs[i])
                        break
            async with sf_l() as db:
                learned = await learn_from_verified_segments(dict(member_to_segs), db, max_segments_per_member=15)
            await engine_l.dispose()
            if learned:
                logger.info(f"[6.5/learn] 累积 {sum(learned.values())} 段到 {len(learned)} 个 member, 下次会议识别率提升")
            else:
                logger.warning("[6.5/learn] 未累积任何段 (cluster_names 全是 None)")

    if "regen" in steps:
        # regen 优先复用已有 result.json（避免重跑声纹提取）
        if "new_speaker" not in dir() or not new_speaker:
            if result_path.exists():
                logger.info(f"[8/regen] 复用 {result_path} 的 new_speaker")
                with open(result_path) as f:
                    saved = json.load(f)
                new_speaker = saved["new_speaker"]
            else:
                logger.error(f"[8/regen] 需要 new_speaker 但 {result_path} 不存在；先跑 extract+assign")
                return
        real_speakers = list({n for n in new_speaker if n and not n.startswith("发言人")})
        regen_result = await regen_summary(meeting_id, real_speakers, workdir=str(workdir))
        logger.info(f"[8/regen] 备份: {regen_result['backup_file']}")
        logger.info(f"[8/regen] summary={regen_result['summary_len']} chars, "
                    f"key_points={regen_result['key_points']}, decisions={regen_result['decisions']}")

    if "verify" in steps:
        verify_result = await verify_eight_fields(meeting_id)
        total = sum(verify_result.values())
        if total == 0:
            logger.info("✅ [9/verify] 8 字段全 0 旧错标人")
        else:
            logger.warning(f"❌ [9/verify] 仍有 {total} 个旧错标人: {verify_result}")
        for f, n in verify_result.items():
            status = "✅" if n == 0 else "❌"
            logger.info(f"  {status} {f}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
