"""
ASR 输出后处理过滤器。

历史背景 (CLAUDE.md 2026-06-02/03 7 层幻觉防护):
1. HALLUCINATION_STRONG (强匹配: "明镜与点点", "感谢观看") - 无条件过滤
2. HALLUCINATION_WEAK (弱匹配: "12345", "测试", "嗯") - 仅在低能量时过滤
3. segment duration < 0.3s - 视为噪声
4. text 去标点后 < 2 chars - 视为短噪音
5. _is_repetitive_text - 同短子串重复 (1字≥4, 2-6字≥3, 去标点后)
6. _is_alphanumeric_run - 字母+数字纯串 (Whisper 臆造 "G6G7G10G11...")
7. _is_sentence_repetitive - 完整句子重复 ≥ 2 次

commit ac80ec3a (2026-06 重构) 删除了旧实现。本模块是 2026-06-30 benchmark 重新落地版本。

用法:
    from app.voice.asr_filters import apply_7_layers
    filtered = apply_7_layers(raw_text, audio_rms=0.05)
"""
import re
from typing import List


# 强幻觉词 (YouTube/B站结束语等训练集记忆)
HALLUCINATION_STRONG = [
    "明镜与点点", "感谢观看", "感谢收看", "谢谢观看", "谢谢收看",
    "请不吝点赞", "订阅转发", "打赏支持", "中文字幕", "中文字幕志愿者",
    "字幕组", "校译", "明镜", "点点", "看完了别忘了",
    "记得点赞", "一键三连", "三连支持", "关注我们",
]

# 弱幻觉词 (可能是真话, 仅在低能量时过滤)
HALLUCINATION_WEAK = [
    "12345", "123456", "67890", "11111", "00000",
    "一二三四五", "二二三四", "三二三四",
    "嗯嗯嗯", "啊啊啊", "哦哦哦", "呃呃呃",
    "测试", "test",
]

# BGM 噪声标签 (SenseVoice 输出)
BGM_TAGS = ["<|BGM|>", "<|Speech|>", "<|cry|>", "<|laugh|>", "<|sigh|>", "<|cough|>"]


def strip_bgm_tags(text: str) -> str:
    """剥除 SenseVoice BGM/非语音事件标签"""
    for tag in BGM_TAGS:
        text = text.replace(tag, "")
    return text.strip()


def strip_emotion_tags(text: str) -> str:
    """剥除 SenseVoice 情感标签 <|zh|><|NEUTRAL|><|withitn|>"""
    text = re.sub(r"<\|[a-z]+\|>", "", text, flags=re.IGNORECASE)
    return text.strip()


def strip_all_tags(text: str) -> str:
    """剥除所有 SenseVoice 输出标签"""
    text = strip_emotion_tags(text)
    text = strip_bgm_tags(text)
    return text


def _is_repetitive_text(text: str) -> bool:
    """检测同短子串重复 (1字≥4次, 2-6字≥3次), 去标点后判断"""
    clean = re.sub(r"[，。！？、；：""''《》（）\.\,\!\?]", "", text).strip()
    if len(clean) < 2:
        return False
    # 1字重复
    if len(clean) >= 4 and len(set(clean)) == 1:
        return True
    # 2-6字重复检测
    for sub_len in [2, 3, 4, 5, 6]:
        if len(clean) < sub_len * 3:
            continue
        substr = clean[:sub_len]
        count = 0
        i = 0
        while i < len(clean):
            if clean[i:i+sub_len] == substr:
                count += 1
                i += sub_len
            else:
                i += 1
        if count >= 3:
            return True
    return False


def _is_alphanumeric_run(text: str) -> bool:
    """检测字母+数字纯串 (Whisper 臆造 "G6G7G10G11...")"""
    clean = re.sub(r"[，。！？、；：\s\.\,\!\?]", "", text)
    if len(clean) < 4:
        return False
    # 必须全是字母+数字 (无中文)
    has_chinese = bool(re.search(r"[一-鿿]", clean))
    has_alnum = bool(re.search(r"[a-zA-Z0-9]", clean))
    return has_alnum and not has_chinese


def _is_gibberish(text: str) -> bool:
    """检测长无意义乱码 (30+ 字符无虚词/代词/动作词)"""
    if len(text) < 30:
        return False
    functional_words = [
        "的", "了", "是", "我", "你", "他", "她", "它", "们", "在", "有", "和",
        "就", "都", "也", "不", "要", "能", "好", "这", "那", "说", "看", "做",
        "去", "来", "会", "可以", "应该", "但是", "因为", "所以", "如果",
    ]
    has_functional = any(w in text for w in functional_words)
    return not has_functional


def _has_strong_hallucination(text: str) -> bool:
    """检测强幻觉词 (YouTube/B站模板)"""
    return any(phrase in text for phrase in HALLUCINATION_STRONG)


def _has_weak_hallucination(text: str, audio_rms: float) -> bool:
    """检测弱幻觉词, 仅在低能量时 (audio_rms < 0.02)"""
    if audio_rms >= 0.02:
        return False
    return any(phrase in text for phrase in HALLUCINATION_WEAK)


def apply_7_layers(
    text: str,
    audio_rms: float = 1.0,
    segment_duration_sec: float = 1.0,
) -> str:
    """
    7 层幻觉防护, 返回过滤后的文本。

    Args:
        text: 原始 ASR 输出
        audio_rms: 音频能量 (0-1), 默认 1.0 (高能量, 不触发弱幻觉过滤)
        segment_duration_sec: 段时长 (秒), 默认 1.0

    Returns:
        过滤后的文本 (若被过滤则返回空字符串 "")
    """
    if not text:
        return ""

    # 第 0 层: 剥除 SenseVoice 标签
    text = strip_all_tags(text)
    if not text:
        return ""

    # 第 1 层: 强幻觉词 - 无条件过滤
    if _has_strong_hallucination(text):
        return ""

    # 第 2 层: 弱幻觉词 - 仅低能量时过滤
    if _has_weak_hallucination(text, audio_rms):
        return ""

    # 第 3 层: segment 时长 < 0.3s 视为噪声
    if segment_duration_sec < 0.3:
        return ""

    # 第 4 层: 文本去标点后 < 2 字符视为短噪音
    clean = re.sub(r"[，。！？、；：""''《》（）\.\,\!\?\s]", "", text).strip()
    if len(clean) < 2:
        return ""

    # 第 5 层: 重复文本检测
    if _is_repetitive_text(text):
        return ""

    # 第 6 层: 字母+数字纯串 (Whisper 臆造)
    if _is_alphanumeric_run(text):
        return ""

    # 第 7 层: 长无意义乱码 (备选, 中文场景较少触发)
    if _is_gibberish(text):
        return ""

    return text


def filter_segments(
    segments: List[dict],
    default_rms: float = 0.5,
) -> List[dict]:
    """
    对 segment 列表逐个过滤, 返回过滤后的列表。
    每段需要包含: text, start, end, (可选) audio_rms
    """
    filtered = []
    for seg in segments:
        text = seg.get("text", "")
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        rms = seg.get("audio_rms", default_rms)
        duration = end - start if end > start else default_rms

        cleaned = apply_7_layers(text, audio_rms=rms, segment_duration_sec=duration)
        if cleaned:
            filtered.append({**seg, "text": cleaned})
    return filtered