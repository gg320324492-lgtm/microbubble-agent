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
            # speaker_verification 任务可以提取嵌入特征
            self._pipeline = pipeline(
                Tasks.speaker_verification,
                model="iic/speech_eres2net_sv_zh-cn_3dspeaker_16k",
            )
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
            padding = np.zeros(16000 - len(audio), dtype=np.float32)
            audio = np.concatenate([audio, padding])

        wav_bytes = self._ensure_wav_format(audio)

        # 尝试通过 pipeline 的底层模型直接提取 embedding
        try:
            # 方式1: 使用 pipeline 的预处理+模型前向传播
            if hasattr(self._pipeline, 'preprocessor') and hasattr(self._pipeline, 'model'):
                import torch
                inputs = self._pipeline.preprocessor(wav_bytes)
                with torch.no_grad():
                    outputs = self._pipeline.model(inputs)
                # ERes2Net 输出通常是 embedding tensor
                if isinstance(outputs, torch.Tensor):
                    emb = outputs.cpu().numpy().flatten()
                    if len(emb) >= EMBEDDING_DIM:
                        return emb[:EMBEDDING_DIM].astype(np.float32)
                    return emb.astype(np.float32)
                if isinstance(outputs, dict):
                    for key in ['embedding', 'feature', 'output', 'last_hidden_state']:
                        if key in outputs:
                            return outputs[key].cpu().numpy().flatten()[:EMBEDDING_DIM].astype(np.float32)
        except Exception as e:
            logger.warning(f"底层模型提取失败, 回退 pipeline 方式: {e}")

        # 方式2: 直接用 pipeline 调用（speaker_verification 任务）
        result = self._pipeline(wav_bytes)
        if isinstance(result, dict):
            # verification pipeline 返回 scores, 尝试从模型内部获取 embedding
            for key in ['outputs', 'embedding', 'feature', 'scores']:
                val = result.get(key)
                if val is not None:
                    arr = np.array(val, dtype=np.float32).flatten()
                    if len(arr) >= 64:
                        return arr[:EMBEDDING_DIM]
        elif isinstance(result, (list, np.ndarray)):
            arr = np.array(result, dtype=np.float32).flatten()
            if len(arr) >= 64:
                return arr[:EMBEDDING_DIM]

        logger.error(f"3D-Speaker 无法提取 embedding, 返回类型: {type(result)}")
        # 返回零向量作为回退
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
            "embedding": list(m.voice_embedding) if m.voice_embedding is not None else [],
            "enrolled_at": m.voice_enrolled_at.isoformat() if m.voice_enrolled_at else None,
            "sample_count": m.voice_sample_count or 0,
        }
        for m in members
    ]
