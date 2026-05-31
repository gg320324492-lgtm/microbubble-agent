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

# 3D-Speaker 嵌入维度
EMBEDDING_DIM = 256
# 声纹匹配置信度阈值（余弦距离，越低越相似）
MATCH_THRESHOLD = 0.55


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
            # 使用 speaker_embedding 任务提取声纹嵌入向量（非 verification 比对）
            self._pipeline = pipeline(
                Tasks.speaker_embedding,
                model="iic/speech_eres2net_sv_zh-cn_3dspeaker_16k",
            )
            # 标记是否成功加载
            self._pipeline_loaded = True
            logger.info("3D-Speaker 模型加载完成")
        except Exception as e:
            logger.error(f"3D-Speaker 模型加载失败: {e}")
            raise

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

        Args:
            audio: float32 numpy 数组，16kHz 单声道，值范围 [-1, 1]

        Returns:
            256 维 float32 numpy embedding 向量
        """
        self._load_pipeline()

        # 确保足够的语音长度（至少 1 秒）
        if len(audio) < 16000:
            # 静音填充
            padding = np.zeros(16000 - len(audio), dtype=np.float32)
            audio = np.concatenate([audio, padding])

        wav_bytes = self._ensure_wav_format(audio)
        result = self._pipeline(wav_bytes)

        # speaker_embedding 返回 embedding 向量 (可能是 list, numpy array, 或 dict)
        if isinstance(result, dict):
            embedding = result.get("outputs") or result.get("embedding") or result.get("feature")
            if embedding is not None:
                return np.array(embedding, dtype=np.float32).flatten()
        elif isinstance(result, (list, np.ndarray)):
            emb = np.array(result, dtype=np.float32).flatten()
            if len(emb) >= EMBEDDING_DIM:
                return emb[:EMBEDDING_DIM]
            return emb

        logger.error(f"3D-Speaker 返回未知格式: {type(result)}, keys={result.keys() if isinstance(result, dict) else 'N/A'}")
        raise ValueError(f"无法从结果中提取 embedding: {result}")

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
            return None, None, 0.0

        # 计算余弦距离
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
