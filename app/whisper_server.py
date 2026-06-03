"""Whisper语音识别API服务"""

import tempfile
import subprocess
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from faster_whisper import WhisperModel
import os

# 后处理函数（内联，避免依赖 app 包）
def postprocess_result(result: dict) -> dict:
    """清理和规范化识别结果"""
    if result.get("text"):
        result["text"] = result["text"].strip()
    return result

app = FastAPI(title="Whisper ASR Service")

# 模型配置
MODEL_SIZE = os.getenv("MODEL_SIZE", "large-v3")
DEVICE = os.getenv("DEVICE", "cuda")
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# 领域提示词 - 帮助 Whisper 识别专业术语
INITIAL_PROMPT = "微纳米气泡，zeta电位，表面活性剂，空化效应，气液界面，传质效率，溶解氧，粒径分布，含气量，界面张力"

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
        # 2026-06-02 修复：whisper_server 之前漏了反幻觉参数，导致 YouTube/B站常见
        # 结束语（"明镜与点点""点赞订阅转发""打赏"等）作为 hallucination 输出
        segments, info = model.transcribe(
            audio_array,
            language=language,
            task=task,
            beam_size=3,
            # 2026-06-03 关闭 Whisper 内置 VAD：已有 silero-vad 做 VAD，
            # 双重 VAD 可能互相干扰导致丢语音段
            vad_filter=False,
            initial_prompt=INITIAL_PROMPT,
            # 反幻觉三件套：
            # - condition_on_previous_text=False：不基于上文生成，避免 hallucination chain
            # - no_speech_threshold=0.6：no_speech_prob 超过 0.6 视为静音段
            # - temperature=0：不采样，结果稳定
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=0,
        )

        # 收集结果
        # 2026-06-02 修复：segment 级 no_speech_prob 过滤（之前只读不写不过滤）
        # faster-whisper 的 no_speech_prob 是该 segment 实际是语音的概率
        # 静音/低能量片段即使 VAD 没拦住，no_speech_prob 也会 > 0.6
        # 配合 INITIAL_PROMPT 引导模型用领域术语，whisper 偶尔会从训练集臆造
        # "请不吝点赞订阅转发打赏支持明镜与点点栏目" 等 YouTube 结束语，必须过滤
        NO_SPEECH_PROB_THRESHOLD = 0.6
        segments_list = []
        full_text = ""
        for segment in segments:
            no_speech_prob = round(segment.no_speech_prob, 3)
            if no_speech_prob > NO_SPEECH_PROB_THRESHOLD:
                # 跳过 whisper 自己也认为"不是语音"的 segment（最强反幻觉信号）
                continue
            text = segment.text.strip()
            if not text:
                continue
            segments_list.append({
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": text,
                "no_speech_prob": no_speech_prob,
            })
            full_text += text

        result = {
            "text": full_text.strip(),
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 3),
            "segments": segments_list
        }

        # 后处理：过滤低置信度、去重
        return postprocess_result(result)

    except Exception as e:
        import traceback
        print(f"[WHISPER ERROR] 识别失败: {e}", flush=True)
        traceback.print_exc()
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
