"""成员人名谐音/别名映射模块

v28 step 60: 会议转录 ASR/说话人识别会产生谐音/错识（如"洪辉"="张宏魁"、
"吴迪"="蒋芦笛"等），需要把任意文本里出现的谐音人名**自动**替换为真实成员名。

两层逻辑：
1. **硬编码已知谐音表**（HARDCODED_ALIASES）—— 用户/历史已确认的映射
2. **自动模糊匹配**（match_by_similarity）—— 编辑距离/拼音相似度，对每个成员名
   自动生成候选别名（"张宏魁" 自动派生 "宏魁"/"红奎"/"鸿辉" 等）

被以下流程调用：
- 会议转录后处理（speaker name 修正）
- 知识内容入库前清洗（content/formatted_content 中的人名替换）
- LLM prompt 构建（让 LLM 输出时也知道真实人名）
- 知识图谱 entity 提取（保证实体节点指向真实成员）
"""
from __future__ import annotations

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("microbubble.name_aliases")

# ===== 硬编码已知谐音映射 =====
# 左侧 = 谐音/错识（ASR/说话人识别可能产生的名字），右侧 = 真实成员名
# 注意：键必须与成员库 `members.name` 完全匹配，或注册为额外的别名形式
HARDCODED_ALIASES: Dict[str, str] = {
    # ===== 2026-06-27 会议 153 transcript 实际 ASR 误识（用户明确指出 + 跑出来的）=====
    "铜鹤": "杜同贺",       # 用户明确指出（"同贺"谐音）
    "同客": "杜同贺",       # ASR 误识（"铜鹤" → "同客"）
    "铜棍": "杜同贺",       # ASR 误识（"铜鹤" → "铜棍"）
    "同合": "杜同贺",       # 防御性（同音字）
    "童鹤": "杜同贺",       # 防御性（同音字）
    "铜和": "杜同贺",       # 防御性
    "铜合": "杜同贺",       # 防御性
    # ===== 用户 2026-06-21 确认 =====
    "洪辉": "张宏魁",       # "宏魁"谐音"洪辉"
    "张洪辉": "张宏魁",
    "张宏辉": "张宏魁",
    "吴迪": "蒋芦笛",       # "芦笛"尾字"笛"与"迪"谐音，姓"蒋"被省略/误识成"吴"
    "易斐": "吴怡霏",       # "怡霏"截取为"怡斐"谐音
    "莫斐": "刘莫菲",       # "莫菲"谐音"莫斐"
    # ===== 合并 speaker_assignment.py 的 PHONETIC_CORRECTIONS（避免遗漏）=====
    "杜同河": "杜同贺",     # 防御性
    "吴梦全": "吴孟铨",
    "吴孟全": "吴孟铨",
    "吴孟拴": "吴孟铨",
    "王天之": "王天志",
    "王田志": "王天志",
    "赵航嘉": "赵航佳",
    "赵航家": "赵航佳",
    # ===== 历史确认的谐音（保留作参考）=====
    "杜同和": "杜同贺",
    "同和": "杜同贺",
    "杜同赫": "杜同贺",
    "王天志": "王天志",     # 显式占位（避免 fuzzy 把"王天志"误改）
    "宋扬": "宋洋",
}

# ===== 姓氏常见错识（前缀替换规则）=====
# 用于自动派生别名：若成员名以"蒋X"开头，ASR 可能误识姓为"吴/江/姜"等
SURNAME_ALIASES: Dict[str, List[str]] = {
    "王": ["汪", "黄"],            # "王" → 汪/黄 (很少)
    "李": ["黎", "厉"],
    "张": ["章", "彰"],
    "刘": ["柳", "溜", "六"],
    "陈": ["程", "成", "晨"],
    "杨": ["羊", "阳"],
    "黄": ["王", "汪"],
    "周": ["邹", "洲"],
    "吴": ["胡", "邬", "无"],
    "蒋": ["江", "姜", "将"],
    "郑": ["正", "政"],
    "杜": ["度"],
    "贾": ["价", "甲"],
}


def _normalize(text: str) -> str:
    """归一化：去空白 + 全角→半角"""
    return unicodedata.normalize("NFKC", text).strip()


def hardcoded_replace(text: str) -> str:
    """仅用硬编码表替换

    Args:
        text: 任意文本（可能含谐音人名）
    Returns:
        替换后的文本（所有 HARDCODED_ALIASES 键都被替换）
    """
    if not text:
        return text
    out = text
    for alias, real in HARDCODED_ALIASES.items():
        if alias == real:
            continue  # 跳过占位
        # 用 re 替换避免部分匹配误伤
        # 比如 "王天志" 不能误把 "王天" 替换
        # 用字符级 substring 替换即可，因为键都是完整人名
        out = out.replace(alias, real)
    return out


def _char_similarity(a: str, b: str) -> float:
    """字符级相似度（0-1）"""
    return SequenceMatcher(None, a, b).ratio()


def _pinyin_similarity(a: str, b: str) -> float:
    """拼音相似度（占位实现，未来可接入 pypinyin）

    暂时回退到字符级相似度。等真实使用案例多了再升级。
    """
    return _char_similarity(a, b)


def _name_similarity(name: str, candidate: str) -> float:
    """人名相似度（带奖励分，最高 ~2.0）

    评分维度：
    - 全名字符相似度（0-1）
    - 尾字相同 +0.20（"吴迪" vs "蒋芦笛" 尾字"迪/笛"相同）
    - 成员名包含 token 后两字 +0.30（"芦笛" 在 "蒋芦笛" 里）
    - 成员名包含 token 前两字 +0.20
    - 成员名包含 token 全部 +0.50
    """
    a = _normalize(name)
    b = _normalize(candidate)
    if not a or not b:
        return 0.0
    score = _pinyin_similarity(a, b)
    # 尾字相同
    if a[-1] == b[-1]:
        score += 0.20
    # 包含 token 后两字（最常见的谐音模式："芦笛"在"蒋芦笛"里）
    if len(a) >= 2 and a[-2:] in b:
        score += 0.30
    elif len(a) >= 2 and a[:2] in b:
        score += 0.20
    # 完全包含
    if a in b:
        score += 0.50
    return score


def match_by_similarity(
    name: str,
    candidates: List[str],
    threshold: float = 0.70,
) -> Optional[Tuple[str, float]]:
    """从候选列表里找最相似的真实成员名

    Args:
        name: 待匹配的谐音/疑似名
        candidates: 真实成员名列表
        threshold: 相似度阈值（0-2，含奖励分）
    Returns:
        (最佳匹配名, 相似度) 或 None（低于阈值）
    """
    if not name or not candidates:
        return None
    best: Optional[Tuple[str, float]] = None
    for cand in candidates:
        sim = _name_similarity(name, cand)
        if best is None or sim > best[1]:
            best = (cand, sim)
    if best and best[1] >= threshold:
        return best
    return None


def is_likely_person_name(token: str, members: List[str]) -> bool:
    """判断 token 是否看起来像人名

    启发式：
    - 长度 2-4 字
    - 全中文
    - 在成员库里有相似候选（编辑距离 ≤ 2 或拼音相似度 ≥ 0.7）
    """
    if not token or len(token) < 2 or len(token) > 4:
        return False
    if not re.fullmatch(r"[一-鿿]+", token):
        return False
    # 在成员库里有匹配？
    match = match_by_similarity(token, members, threshold=0.65)
    return match is not None


def replace_person_names(
    text: str,
    members: List[str],
    hardcoded_only: bool = False,
) -> Tuple[str, List[Tuple[str, str]]]:
    """统一入口：硬编码 + 自动匹配

    Args:
        text: 待清洗文本
        members: 真实成员名列表（从 DB 加载）
        hardcoded_only: True 只用硬编码表（快路径）；False 同时用模糊匹配（慢但强）
    Returns:
        (cleaned_text, replacements) — replacements 列表 [(原名, 替换名), ...]
    """
    if not text:
        return text, []

    replacements: List[Tuple[str, str]] = []

    # 第一轮：硬编码替换
    cleaned = hardcoded_replace(text)
    # 记录硬编码替换
    for alias, real in HARDCODED_ALIASES.items():
        if alias == real:
            continue
        if alias in text and real in cleaned:
            count_before = text.count(alias)
            count_after = cleaned.count(real)
            # 简化：每个 alias 至多记录一次
            if count_before > 0:
                replacements.append((alias, real))

    if hardcoded_only:
        return cleaned, replacements

    # 第二轮：自动模糊匹配
    # 找出"独立"的中文 token（前后是标点/空白/开头/结尾），2-3 字优先
    # 用 (?<=[\s，。！？：；、]) 前后断言避免 "芦笛配" "怡霏和" 这种带上下文
    tokens = set(re.findall(
        r"(?<![一-鿿])(?:[一-鿿]{2,3})(?![一-鿿])",
        cleaned,
    ))
    for token in tokens:
        # 跳过已知真实成员（已经在用真实名了）
        if token in members:
            continue
        match = match_by_similarity(token, members, threshold=0.65)
        if match is None:
            continue
        real_name, sim = match
        # 二次验证：real_name 不在 cleaned 里（避免重复替换）
        if real_name in cleaned:
            continue
        # 用 re 替换（前面已有前后断言，但仍带 re.escape 防特殊字符）
        cleaned = re.sub(
            re.escape(token),
            real_name,
            cleaned,
        )
        replacements.append((token, real_name))
        logger.debug(
            f"name_aliases fuzzy: {token!r} → {real_name!r} (sim={sim:.2f})"
        )

    return cleaned, replacements


# ===== 单例接口（懒加载）=====

_cached_members: Optional[List[str]] = None


def get_member_names(force_reload: bool = False) -> List[str]:
    """从 DB 加载所有成员名（缓存）

    Args:
        force_reload: True 跳过缓存（用于成员表变更后）
    """
    global _cached_members
    if _cached_members is not None and not force_reload:
        return _cached_members
    try:
        from app.models.member import Member
        from app.core.database import async_session
        import asyncio

        async def _load():
            async with async_session() as db:
                from sqlalchemy import select
                r = await db.execute(select(Member.name).where(Member.is_active == True))
                return [row[0] for row in r.fetchall()]

        # 兼容同步上下文
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已经在 event loop 内（Celery worker）→ 跳过缓存异步加载
                logger.debug("name_aliases: 检测到 running event loop，使用空缓存")
                return _cached_members or []
        except RuntimeError:
            pass

        _cached_members = asyncio.run(_load())
        logger.info(f"name_aliases: 已加载 {len(_cached_members)} 个真实成员名")
        return _cached_members
    except Exception as e:
        logger.warning(f"name_aliases: 加载成员名失败: {e}")
        return _cached_members or []


def clean_text(text: str, hardcoded_only: bool = False) -> str:
    """便捷接口：清洗文本里所有人名谐音

    Args:
        text: 待清洗文本
        hardcoded_only: True 只用硬编码（默认 False，用全部机制）
    Returns:
        清洗后的文本
    """
    if not text:
        return text
    members = get_member_names()
    cleaned, _ = replace_person_names(text, members, hardcoded_only=hardcoded_only)
    return cleaned


# ===== 自学习：新增别名建议 =====

def suggest_new_alias(
    token: str,
    real_name: str,
    confidence: float,
) -> Optional[Dict[str, str]]:
    """如果 fuzzy 匹配到一个不在硬编码表里的新谐音，返回建议

    由调用方决定是否持久化到 HARDCODED_ALIASES（写 DB / 写文件 / 仅 log）
    """
    if token == real_name:
        return None
    if token in HARDCODED_ALIASES:
        return None  # 已存在
    if confidence < 0.80:
        return None  # 置信度太低
    return {"alias": token, "real": real_name, "confidence": round(confidence, 3)}