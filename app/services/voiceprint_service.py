"""声纹识别服务 — 3D-Speaker ERes2Net 嵌入提取 + pgvector 匹配"""

import io
import logging
import struct
import wave
from typing import List, Optional, Tuple

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger("microbubble.voiceprint")

# 3D-Speaker ERes2Net 嵌入维度（ERes2Net 实际输出 192 维，不是 256）
EMBEDDING_DIM = 192
# 声纹匹配置信度阈值（余弦距离，越低越相似）
MATCH_THRESHOLD = 0.7


class VoiceprintService:
    """声纹录入与识别服务"""

    def __init__(self):
        self._pipeline = None

    def _load_pipeline(self):
        """延迟加载 3D-Speaker 模型"""
        if self._pipeline is not None:
            return
        try:
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks

            logger.info("正在加载 3D-Speaker ERes2Net 模型...")
            self._pipeline = pipeline(
                Tasks.speaker_verification,
                model="iic/speech_eres2net_sv_zh-cn_16k-common",
            )
            logger.info("3D-Speaker 模型加载完成")
        except Exception as e:
            logger.error(f"3D-Speaker 模型加载失败: {e}（声纹识别将不可用，所有发言人显示 unknown）")
            # 不抛异常，让 identify_speaker 返回 unknown 而不是崩溃 WS
            self._pipeline = None

    def _ensure_wav_format(self, audio_data: np.ndarray) -> bytes:
        """将 float32 numpy 数组转为 WAV bytes（16kHz, 16bit, mono）。"""
        # 确保值范围 [-1, 1]
        audio = np.clip(audio_data, -1.0, 1.0)
        # 转为 int16
        int_data = (audio * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(int_data.tobytes())
        buf.seek(0)
        return buf.read()

    def extract_embedding(self, audio: np.ndarray) -> np.ndarray:
        """从音频片段提取说话人嵌入向量。

        直接调用底层 ERes2Net model，绕过 pipeline（pipeline 只接受文件路径/numpy
        数组但 preprocessor 缺失，必然失败浪费日志）。
        """
        self._load_pipeline()
        if self._pipeline is None:
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

        if len(audio) < 16000:
            padding = np.zeros(16000 - len(audio), dtype=np.float32)
            audio = np.concatenate([audio, padding])

        return self._extract_via_model(audio)

    def _parse_pipeline_result(self, result) -> Optional[np.ndarray]:
        """从 pipeline 返回值中提取 embedding 数组"""
        if isinstance(result, dict):
            for key in ['outputs', 'embedding', 'feature', 'scores', 'text']:
                val = result.get(key)
                if val is None:
                    continue
                arr = np.array(val, dtype=np.float32).flatten()
                if len(arr) >= 64:
                    return arr[:EMBEDDING_DIM].astype(np.float32)
        elif isinstance(result, (list, np.ndarray)):
            arr = np.array(result, dtype=np.float32).flatten()
            if len(arr) >= 64:
                return arr[:EMBEDDING_DIM].astype(np.float32)
        return None

    def _extract_via_model(self, audio: np.ndarray) -> np.ndarray:
        """直接调底层 model.forward() 提取 embedding（绕过 pipeline 调度）

        适用场景：pipeline 内部 preprocessor 缺失或 buggy。
        3D-Speaker ERes2Net 输入是 (batch, samples) 的 float32 tensor，
        输出是 (batch, embed_dim) 的 embedding tensor。
        """
        import torch
        try:
            model = self._pipeline.model
        except AttributeError:
            logger.error("pipeline 没有 .model 属性，无法直接调底层")
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

        try:
            # 准备 tensor：1D float32（与 ERes2Net_Pipeline.preprocess 规范一致）
            audio_t = torch.from_numpy(audio).float()
            with torch.no_grad():
                outputs = model(audio_t)
            # ERes2Net 输出：(1, 192) tensor（模型内部已加 batch 维）
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            if hasattr(outputs, 'last_hidden_state'):
                emb_t = outputs.last_hidden_state
            elif isinstance(outputs, dict):
                emb_t = outputs.get('embeddings') or outputs.get('features') or list(outputs.values())[0]
            else:
                emb_t = outputs
            # 展平成 1D ndarray
            emb = emb_t.squeeze().cpu().numpy().astype(np.float32)
            if len(emb) >= EMBEDDING_DIM:
                return emb[:EMBEDDING_DIM]
            # embedding 维度不够，pad 零
            padded = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            padded[: len(emb)] = emb
            return padded
        except Exception as e:
            logger.error(f"底层 model 提取失败: {e}", exc_info=True)
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

    async def enroll_member(
        self, db: AsyncSession, member_id: int, audio: np.ndarray
    ) -> bool:
        """录入成员声纹。

        多次录入时取均值以提升准确度。
        """
        from app.models.member import Member

        embedding = self.extract_embedding(audio)

        result = await db.execute(select(Member).where(Member.id == member_id))
        member = result.scalar_one_or_none()
        if not member:
            return False

        if member.voice_embedding is not None and member.voice_sample_count > 0:
            # 多次采样取均值
            old = np.array(member.voice_embedding, dtype=np.float32)
            # 加权平均（已有的权重更大）
            weight = member.voice_sample_count / (member.voice_sample_count + 1)
            embedding = old * weight + embedding * (1 - weight)

        member.voice_embedding = embedding.tolist()
        member.voice_sample_count = (member.voice_sample_count or 0) + 1
        member.voice_enrolled_at = text("NOW()")
        await db.commit()

        logger.info(f"成员 {member.name} (id={member_id}) 声纹已录入 (第{member.voice_sample_count}次)")
        return True

    async def identify_speaker(
        self, db: AsyncSession, audio: np.ndarray
    ) -> Tuple[Optional[str], Optional[int], float]:
        """识别说话人身份。

        Args:
            db: 数据库会话
            audio: float32 numpy 数组，16kHz 单声道

        Returns:
            (name, member_id, confidence) — name 为 None 表示未识别
        """
        from app.models.member import Member

        embedding = self.extract_embedding(audio)

        # 检查 embedding 是否全零（模型加载失败）
        if np.all(embedding == 0):
            logger.warning("声纹 embedding 全零（模型可能未加载），跳过识别")
            return None, None, 0.0

        embedding_list = embedding.tolist()

        # 查询已录入声纹的成员，按余弦距离排序
        result = await db.execute(
            select(Member)
            .where(Member.voice_embedding.isnot(None))
            .order_by(Member.voice_embedding.cosine_distance(embedding_list))
            .limit(1)
        )
        member = result.scalar_one_or_none()

        if not member:
            logger.debug("声纹识别：无已录入成员，返回 unknown")
            return None, None, 0.0

        # 计算余弦距离
        db_emb = np.array(member.voice_embedding, dtype=np.float32)
        cosine_dist = float(1.0 - np.dot(embedding, db_emb) / (
            np.linalg.norm(embedding) * np.linalg.norm(db_emb) + 1e-8
        ))

        confidence = float(1.0 - min(cosine_dist, 1.0))

        if cosine_dist < MATCH_THRESHOLD:
            logger.debug(f"声纹识别成功：{member.name} (dist={cosine_dist:.3f}, conf={confidence:.3f})")
            return member.name, member.id, confidence
        else:
            logger.debug(f"声纹识别未匹配：最近={member.name} (dist={cosine_dist:.3f} > threshold={MATCH_THRESHOLD})")
            return None, None, confidence

    async def identify_speaker_by_embedding(
        self, db: AsyncSession, embedding: np.ndarray
    ) -> Tuple[Optional[str], Optional[int], float]:
        """直接用 embedding 识别说话人（无需音频）。

        Args:
            db: 数据库会话
            embedding: 192 维声纹 embedding

        Returns:
            (name, member_id, confidence) — name 为 None 表示未识别
        """
        from app.models.member import Member

        if np.all(embedding == 0):
            return None, None, 0.0

        embedding_list = embedding.tolist()

        result = await db.execute(
            select(Member)
            .where(Member.voice_embedding.isnot(None))
            .order_by(Member.voice_embedding.cosine_distance(embedding_list))
            .limit(1)
        )
        member = result.scalar_one_or_none()
        if not member:
            return None, None, 0.0

        db_emb = np.array(member.voice_embedding, dtype=np.float32)
        cosine_dist = float(1.0 - np.dot(embedding, db_emb) / (
            np.linalg.norm(embedding) * np.linalg.norm(db_emb) + 1e-8
        ))
        confidence = float(1.0 - min(cosine_dist, 1.0))

        if cosine_dist < MATCH_THRESHOLD:
            return member.name, member.id, confidence
        else:
            return None, None, confidence

    async def get_enrolled_members(self, db: AsyncSession) -> List[dict]:
        """获取已录入声纹的成员列表。"""
        from app.models.member import Member

        result = await db.execute(
            select(Member).where(Member.voice_embedding.isnot(None))
        )
        members = result.scalars().all()
        return [
            {
                "id": m.id,
                "name": m.name,
                "sample_count": m.voice_sample_count or 0,
                "enrolled_at": m.voice_enrolled_at.isoformat() if m.voice_enrolled_at else None,
            }
            for m in members
        ]


# 全局单例
voiceprint_service = VoiceprintService()


async def get_fingerprints(
    db: AsyncSession,
    member_ids: list[int] | None = None,
) -> list[dict]:
    """
    批量返回成员的 256 维 embedding + 元数据。
    用于声纹库页面一次性加载。
    """
    from sqlalchemy import select
    from app.models.member import Member
    stmt = select(Member)
    if member_ids is not None:
        stmt = stmt.where(Member.id.in_(member_ids))
    stmt = stmt.where(Member.voice_embedding.isnot(None), Member.is_active == True)
    result = await db.execute(stmt)
    members = result.scalars().all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "avatar": m.avatar,
            # 强制转 python float — list(numpy_array) 后元素仍是 numpy.float32，
            # FastAPI jsonable_encoder 不能序列化，会抛 ValueError。
            # 用 .tolist() 一键转成原生 python float 列表
            "embedding": (
                m.voice_embedding.tolist()
                if hasattr(m.voice_embedding, "tolist")
                else [float(x) for x in m.voice_embedding]
            ) if m.voice_embedding is not None else [],
            "enrolled_at": m.voice_enrolled_at.isoformat() if m.voice_enrolled_at else None,
            "sample_count": m.voice_sample_count or 0,
        }
        for m in members
    ]


from datetime import datetime, timezone


async def record_confidence(
    db: AsyncSession,
    meeting_id: int,
    member_id: int,
    confidence: float,
) -> None:
    """记录一次声纹识别置信度（用于历史曲线）"""
    from app.models.voiceprint_history import VoiceprintHistory
    history = VoiceprintHistory(
        meeting_id=meeting_id,
        member_id=member_id,
        confidence=confidence,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(history)
    await db.commit()


async def search_speaker_history(
    db: AsyncSession,
    member_id: int,
    limit: int = 20,
) -> list[dict]:
    """
    跨会议反查"该成员说过的内容"。
    """
    from sqlalchemy import select, desc
    from app.models.meeting import Meeting
    stmt = (
        select(Meeting)
        .where(Meeting.transcript.isnot(None))
        .order_by(desc(Meeting.start_time))
        .limit(limit * 3)
    )
    result = await db.execute(stmt)
    meetings = list(result.scalars().all())

    matches = []
    for meeting in meetings:
        transcript = meeting.transcript or []
        for entry in transcript:
            if entry.get("member_id") == member_id:
                matches.append({
                    "meeting_id": meeting.id,
                    "meeting_title": meeting.title,
                    "text": entry.get("text", ""),
                    "speaker": entry.get("speaker", ""),
                    "ts": entry.get("ts") or entry.get("start"),
                    "confidence": entry.get("confidence", 0),
                })
                if len(matches) >= limit:
                    return matches
    return matches
