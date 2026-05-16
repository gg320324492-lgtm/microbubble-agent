"""Whisper语音识别API服务"""

import io
import tempfile
import subprocess
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import os

app = FastAPI(title="Whisper ASR Service")

# 模型配置
MODEL_SIZE = os.getenv("MODEL_SIZE", "large-v3")
DEVICE = os.getenv("DEVICE", "cuda")
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# 加载模型
print(f"正在加载Whisper模型: {MODEL_SIZE}")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("模型加载完成")


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy", "model": MODEL_SIZE, "device": DEVICE}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = "zh",
    task: str = "transcribe"
):
    """
    语音识别

    Args:
        audio: 音频文件（支持wav, mp3, m4a, ogg, flac等）
        language: 语言代码
        task: 任务类型（transcribe/translate）

    Returns:
        识别结果
    """
    # 读取音频数据
    audio_data = await audio.read()

    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="音频文件为空")

    try:
        # 转换音频格式
        audio_array = bytes_to_array(audio_data)

        # 执行识别
        segments, info = model.transcribe(
            audio_array,
            language=language,
            task=task,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        # 收集结果
        segments_list = []
        full_text = ""

        for segment in segments:
            segments_list.append({
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text.strip()
            })
            full_text += segment.text

        return {
            "text": full_text.strip(),
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 3),
            "segments": segments_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


def bytes_to_array(audio_data: bytes) -> np.ndarray:
    """将音频字节数据转换为numpy数组"""
    # 写入临时文件
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        # 使用ffmpeg转换为wav格式
        output_path = tmp_path + ".wav"
        subprocess.run([
            "ffmpeg", "-i", tmp_path,
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            "-y",
            output_path
        ], capture_output=True, check=True)

        # 读取wav文件
        import wave
        with wave.open(output_path, "rb") as wf:
            audio_array = np.frombuffer(
                wf.readframes(wf.getnframes()),
                dtype=np.int16
            ).astype(np.float32) / 32768.0

        return audio_array

    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
