"""语音识别结果后处理 — 过滤噪音、去重"""


def postprocess_result(result: dict) -> dict:
    """后处理识别结果：过滤低置信度 segment，去重

    Args:
        result: Whisper 识别结果，包含 text 和 segments 字段

    Returns:
        处理后的结果
    """
    segments = result.get("segments", [])
    if not segments:
        return result

    # 过滤 no_speech_prob > 0.8 的 segment（噪音段）
    filtered = [s for s in segments if s.get("no_speech_prob", 0) < 0.8]

    # 去重：连续重复文本只保留一次
    deduped = []
    for seg in filtered:
        text = seg["text"].strip()
        if text and (not deduped or text != deduped[-1]["text"].strip()):
            deduped.append(seg)

    # 重新拼接
    final_text = "".join(s["text"] for s in deduped).strip()
    result["text"] = final_text
    result["segments"] = deduped
    return result
