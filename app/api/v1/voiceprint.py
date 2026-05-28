"""声纹录入 API"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.services.voiceprint_service import voiceprint_service

router = APIRouter()


@router.post("/voiceprint/enroll/{member_id}")
async def enroll_voiceprint(
    member_id: int,
    audio: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """录入成员声纹 — 上传 3-5 秒语音"""
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="请上传音频文件")

    try:
        audio_data = await audio.read()
        if len(audio_data) < 1000:
            raise HTTPException(status_code=400, detail="音频太短，请录制至少 3 秒语音")

        # 转为 float32 numpy 数组
        import numpy as np
        import subprocess
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            output_path = tmp_path + ".wav"
            subprocess.run([
                "ffmpeg", "-y", "-i", tmp_path,
                "-ar", "16000", "-ac", "1",
                "-f", "s16le", "-v", "error",
                output_path,
            ], check=True, timeout=10)

            with open(output_path, "rb") as f:
                raw = f.read()
            audio_array = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        finally:
            for p in [tmp_path, output_path]:
                if os.path.exists(p):
                    os.unlink(p)

        success = await voiceprint_service.enroll_member(db, member_id, audio_array)
        if not success:
            raise HTTPException(status_code=404, detail="成员不存在")

        return {"message": "声纹录入成功", "member_id": member_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"声纹录入失败: {str(e)}")


@router.get("/voiceprint/enrolled")
async def list_enrolled_members(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取已录入声纹的成员列表"""
    members = await voiceprint_service.get_enrolled_members(db)
    return {"members": members}
