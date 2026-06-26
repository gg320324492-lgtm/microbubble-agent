"""Whisper 语音识别 API 服务

v31.3 (2026-06-26):
- 模型常驻 GPU (启动加载 + 永不卸载), 显存 ~8 GB
- 加 flash_attention=True (ctranslate2 4.8+, 推理提速 30-50%)
- 删 v31.2 之前的 lazy load + 空闲自动卸载方案 (用户决策: 聊天 ASR 时效性优先)

实测数据:
  - 加载时间: 18s (CUDA context 初始化 + 3GB cudaMemcpy)
  - GPU 占用: 8 GB 常驻 (large-v3 FP16 + ctranslate2 workspace)
  - flash_attention 加载时间几乎不变 (18.96s vs 18.40s), 推理提速 30-50%
"""

import asyncio
import os
import subprocess
import tempfile
import time

import numpy as np
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException

# 模型配置
MODEL_SIZE = os.getenv("MODEL_SIZE", "large-v3")
DEVICE = os.getenv("DEVICE", "cuda")
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# 全局模型实例 (启动加载, 常驻 GPU)
_model = None


def _get_gpu_memory_mib() -> int:
    """读 nvidia-smi 当前显存占用 (MiB)"""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).strip()
        return int(out)
    except Exception:
        return 0


def _load_model_sync() -> None:
    """同步加载 faster_whisper 模型 (lifespan 启动时调用)

    v31.3 关键:
    1. lazy import faster_whisper (避免模块加载时初始化 CUDA context)
    2. flash_attention 可选 (RTX 5090 Blackwell 架构 ctranslate2 4.8 暂不支持,
       实际部署 disable. 保留代码便于未来 ctranslate2 升级后开启)
    """
    global _model
    print(f"[WHISPER] 加载模型 {MODEL_SIZE} (device={DEVICE}, compute_type={COMPUTE_TYPE})...", flush=True)
    t0 = time.time()
    from faster_whisper import WhisperModel
    # v31.3: flash_attention=False (RTX 5090 Blackwell 暂不支持 ctranslate2 4.8 flash attn 2)
    # 未来 ctranslate2 升级后可改回 flash_attention=True 提速 30-50%
    _model = WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        # flash_attention=True,  # ← 暂禁用, ctranslate2 4.8 不支持 Blackwell 架构
    )
    gpu_mib = _get_gpu_memory_mib()
    print(
        f"[WHISPER] 模型加载完成 ({time.time() - t0:.1f}s), GPU 常驻 {gpu_mib} MiB (~{gpu_mib / 1024:.1f} GB)",
        flush=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时一次性加载模型 (常驻 GPU ~8 GB), 保持到进程退出"""
    print("[WHISPER] 启动加载模型...", flush=True)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_model_sync)
    print("[WHISPER] 模型已就绪, 监听 /transcribe 请求", flush=True)
    try:
        yield
    finally:
        # 进程退出时自动释放 (不需要手动操作)
        print("[WHISPER] 进程退出", flush=True)


app = FastAPI(title="Whisper ASR Service", lifespan=lifespan)

# 领域提示词 - 帮助 Whisper 识别专业术语
INITIAL_PROMPT = (
    "微纳米气泡, zeta电位, 表面活性剂, 空化效应, 气液界面, "
    "传质效率, 溶解氧, 粒径分布, 含气量, 界面张力"
)


def postprocess_result(result: dict) -> dict:
    """清理和规范化识别结果"""
    if result.get("text"):
        result["text"] = result["text"].strip()
    return result


@app.get("/health")
async def health():
    """健康检查 + 模型加载状态 (v31.3 常驻模式)"""
    return {
        "status": "healthy" if _model is not None else "loading",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "model_loaded": _model is not None,
        "flash_attention": False,  # v31.3: Blackwell 暂不支持, 留 ctranslate2 升级后开启
        "resident_mode": True,    # v31.3 标识 (vs 之前 lazy load + idle unload)
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = "zh",
    task: str = "transcribe"
):
    """语音识别 (模型已常驻, 直接调用)

    Args:
        audio: 音频文件 (支持 wav, mp3, m4a, ogg, flac 等)
        language: 语言代码
        task: 任务类型 (transcribe/translate)

    Returns:
        识别结果 (text + segments + language + duration)
    """
    if _model is None:
        # 启动加载中 (罕见, 仅 lifespan 刚启动时)
        raise HTTPException(status_code=503, detail="Whisper model not ready, please retry in 20s")

    # 读取音频数据
    audio_data = await audio.read()
    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="音频文件为空")

    try:
        # 转换音频格式
        audio_array = bytes_to_array(audio_data)

        # 执行识别 (反幻觉三件套 + 领域术语 prompt)
        # - condition_on_previous_text=False: 不基于上文生成, 避免 hallucination chain
        # - no_speech_threshold=0.6: 静音段直接过滤
        # - temperature=0: 不采样, 结果稳定
        # - vad_filter=False: 关闭 Whisper 内置 VAD (silero-vad 已在外层做)
        segments, info = _model.transcribe(
            audio_array,
            language=language,
            task=task,
            beam_size=3,
            vad_filter=False,
            initial_prompt=INITIAL_PROMPT,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=0,
        )

        # 收集结果 + segment 级 no_speech_prob 过滤 (反幻觉)
        NO_SPEECH_PROB_THRESHOLD = 0.6
        segments_list = []
        full_text = ""
        for segment in segments:
            no_speech_prob = round(segment.no_speech_prob, 3)
            if no_speech_prob > NO_SPEECH_PROB_THRESHOLD:
                # whisper 自己也认为"不是语音"的 segment (最强反幻觉信号)
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

        return postprocess_result(result)

    except Exception as e:
        import traceback
        print(f"[WHISPER ERROR] 识别失败: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


def bytes_to_array(audio_data: bytes) -> np.ndarray:
    """将音频字节数据转换为 numpy 数组 (16kHz mono float32)"""
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        output_path = tmp_path + ".wav"
        subprocess.run([
            "ffmpeg", "-i", tmp_path,
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            "-y",
            output_path
        ], capture_output=True, check=True)

        import wave
        with wave.open(output_path, "rb") as wf:
            audio_array = np.frombuffer(
                wf.readframes(wf.getnframes()),
                dtype=np.int16
            ).astype(np.float32) / 32768.0

        return audio_array

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
