"""
app/utils/text_sanitize.py — 文本清洗工具集

提供项目描述 / 短文本清洗函数,防止 LLM 工具或用户输入脏 markdown / 套路开场白
直接写入数据库导致卡片显示错乱。

触发场景 (2026-07-15):
  - 用户反馈 /workspace?tab=projects 第 1/2 张卡 description 含 #/**/## markdown + LLM 套路开场白
  - 根因: app/agent/tools/project_tools.py generate_project_plan 把整段 LLM 计划塞 description
  - 修复: create_project / update_project 入库前 sanitize,前端 ProjectsPanel.vue 显示再 sanitize 兜底

本模块被以下地方依赖:
  - app/services/project_service.py (入库前 sanitize)
  - web/src/views/workspace/ProjectsPanel.vue (前端兜底, 等价 JS 实现见前端 utils)
  - scripts/clean_project_descriptions.py (历史数据清洗)
"""
from __future__ import annotations

import re


# 长度上限: 前端 <p class="project-desc"> 适配容器 + 1 行可读
DEFAULT_MAX_LEN = 280

# 粗暴剔除 inline markdown 字符 (在 sub() 时用)
INLINE_MD_CHARS = re.compile(r"[*_`#>]+|\[.+?\]\(.+?\)")
# 多空白收尾
TRAILING_WHITESPACE = re.compile(r"[ \t]+")

# LLM 套路开场白 (在 stripped text 开头匹配)
PREAMBLE_PATTERNS = [
    re.compile(r"^好的[，,。\s].{0,80}(计划|安排|为您|开始).{0,40}[。\n]"),
    re.compile(r"^非常荣幸[，,。\s].{0,80}[。\n]"),
    re.compile(r"^以下是.{0,30}计划[：:，,。\s].{0,40}[。\n]"),
    re.compile(r"^下面为?您.{0,30}规划[。\n]"),
    re.compile(r"^根据.{0,40}要求[，,。\s].{0,40}[。\n]"),
    re.compile(r"^感谢.{0,40}提问[。\n]"),
]

# LLM 计划字段 (贪婪 + 行末锚 + min 6 字避开 [^*\n]+? 非贪婪 bug)
FIELD_PATTERNS = [
    re.compile(r"项目名称\s*[:：]\s*([^\n\r]{6,280})"),
    re.compile(r"研究方向\s*[:：]\s*([^\n\r]{6,280})"),
    re.compile(r"核心目标\s*[:：]\s*([^\n\r]{6,280})"),
]

# 字段值剔除关键词 (含这些说明是 LLM 元信息不是真描述)
FIELD_STOP_WORDS = ("6个月", "本计划", "团队人数", "团队角色", "3人",
                     "项目周期", "团队构成", "团队配置")

# 主题关键词 (Step C 用于挑选首句含主题的目标句)
TOPIC_KEYWORDS = ("微纳米气泡", "微气泡", "气泡成核", "纳米气泡",
                  "抗生素", "臭氧", "过氧化氢", "羟基自由基",
                  "水处理", "降解", "高级氧化", "黑臭水体",
                  "水产养殖", "饮用水", "稳定性", "消毒",
                  "污染物", "底泥", "去除", "抑制", "效率", "机理", "效能")

# 研究动词 (Step C 用于挑选首句)
RESEARCH_VERBS = ("研究", "探索", "调查", "探讨", "开展", "开发", "提出", "构建",
                  "建立", "分析", "设计", "研发", "实现", "优化", "验证")

# LLM 字段标签前缀 (步骤 D 跳过)
FIELD_LABEL_PREFIXES = ("项目名称", "项目周期", "团队构成",
                         "团队配置", "核心目标", "具体任务",
                         "阶段划分", "分阶段", "阶段产出",
                         "第一阶段", "第二阶段", "第三阶段",
                         "第四阶段", "第五阶段", "沟通与调整",
                         "风险管控", "成果最大化", "祝您的",
                         "项目总览")

# LLM 句首语气词 (Step C/D 跳过) — 含 "祝您/感谢" 等 LLM 元信息
# 注意: 不要包含 "本计划/本项目" — 它们后面常跟有意义的研究句 (含研究动词 + 主题关键词)
# Step C-1 的研究动词 + 主题关键词判定会捕获它们
LLM_TONE_STARTS = ("祝您", "感谢", "下面是", "以下为", "接下来",
                    "后续我们", "我们希望", "我们建议",
                    "请注意", "请参考",
                    "重要提示", "风险评估")


def sanitize_project_description(raw: str | None, max_len: int = DEFAULT_MAX_LEN) -> str:
    """
    把 LLM 原始计划输出压成 ≤ max_len 字符的人类可读 description.

    策略 (优先级 high → low):
      A. 抓 "项目名称:" / "研究方向:" / "核心目标:" 后的值
      B. 删 LLM 套路开场白
      C. 找首句含研究动词 + 主题关键词的目标句
      D. fallback: 取第一个非 LLM 元数据的短句
      E. cap max_len + 优雅截断 + 收尾句号

    Args:
        raw: LLM/用户输入的原文 (可能含 markdown + 套路开场白 + 阶段计划)
        max_len: 最大字符数 (默认 280)

    Returns:
        清洗后的 ≤ max_len 字符串 (空输入返空字符串)
    """
    if not raw or not raw.strip():
        return ""

    text = raw

    # Step 0: 剥离 markdown + 行首标题符
    text = INLINE_MD_CHARS.sub("", text)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]+\s+", "", text, flags=re.MULTILINE)

    # Step A: 抓 LLM 字段值 (finditer 允许多个 "项目名称:" 时回退到下一个)
    for pat in FIELD_PATTERNS:
        for m in pat.finditer(text):
            value = m.group(1).strip()
            value = INLINE_MD_CHARS.sub("", value).strip()
            if any(stop in value for stop in FIELD_STOP_WORDS):
                continue
            # 6 ≤ len ≤ max_len 限制
            if 6 <= len(value) <= max_len:
                if value[-1] not in "。.!?！？…":
                    value += "。"
                return value
            # 字段超 max_len 时, 截到第一个句号/逗号
            if len(value) > max_len:
                truncated = value[:max_len]
                for sep in ["。", "；", ";", "—"]:
                    idx = truncated.rfind(sep)
                    if idx > max_len // 2:
                        truncated = truncated[: idx + len(sep)]
                        break
                else:
                    truncated = truncated.rstrip() + "..."
                if 6 <= len(truncated) <= max_len and not any(stop in truncated for stop in FIELD_STOP_WORDS):
                    if truncated[-1] not in "。.!?！？…":
                        truncated += "。"
                    return truncated

    # Step B: 删 LLM 套路开场白 (按句子切, 只在首句 + delimiter 范围检测, 避免 .{0,80} 贪婪吃掉后续句)
    stripped = text.strip()
    # 先按第一个 。\n切, 只对首句(含尾标点)做 preamble 匹配
    first_sent_break = re.search(r"[。\n]", stripped)
    if first_sent_break:
        # 含 delimiter 的首句, 让 PREAMBLE_PATTERN 的 [。\n] 末尾锚能匹配
        first_sent_with_delim = stripped[: first_sent_break.end()]
    else:
        first_sent_with_delim = stripped
    # 首句匹配任一 PREAMBLE_PATTERN → 丢弃首句
    preamble_matched = False
    for pat in PREAMBLE_PATTERNS:
        if pat.match(first_sent_with_delim):
            preamble_matched = True
            break
    if preamble_matched and first_sent_break:
        stripped = stripped[first_sent_break.end():].lstrip()
    elif preamble_matched and not first_sent_break:
        # 整段就一句且匹配 preamble → 整段清空
        stripped = ""

    # Step C/D: 找首句
    final_text = None
    for sent in re.split(r"[。\n]", stripped):
        sent = sent.strip()
        if not sent or len(sent) < 8:
            continue
        if any(sent.startswith(label) for label in FIELD_LABEL_PREFIXES):
            continue
        # 跳 LLM 句首语气词 (本计划旨在/根据/请/祝您/...)
        if any(sent.startswith(t) for t in LLM_TONE_STARTS):
            continue
        # 命中: 研究动词 + 主题关键词
        if any(sent.startswith(v) for v in RESEARCH_VERBS) and any(k in sent for k in TOPIC_KEYWORDS):
            final_text = sent
            break
        # 备选: 多主题关键词
        kw_count = sum(1 for k in TOPIC_KEYWORDS if k in sent)
        if kw_count >= 2 and len(sent) <= max_len:
            final_text = sent
            break

    if final_text is None:
        for sent in re.split(r"[。\n]", stripped):
            sent = sent.strip()
            if not sent or len(sent) < 8:
                continue
            if any(sent.startswith(label) for label in FIELD_LABEL_PREFIXES):
                continue
            if any(sent.startswith(t) for t in LLM_TONE_STARTS):
                continue
            final_text = sent
            break

    if not final_text:
        return ""

    # Step E: cap + 优雅截断 (保证最终 ≤ max_len)
    while len(final_text) > max_len:
        truncated = final_text[:max_len]
        for sep in ["。", "；", ";", "—"]:
            last_idx = truncated.rfind(sep)
            if last_idx > max_len // 2:
                truncated = truncated[: last_idx + len(sep)]
                break
        else:
            # 截但不加 "..." 在外 → 改为截到 max_len - 3 留 3 字符给 "..."
            truncated = final_text[: max_len - 3].rstrip() + "..."
        final_text = truncated
        # 避免死循环: 如果 truncated 仍是 > max_len, 硬截
        if len(final_text) > max_len:
            final_text = final_text[:max_len].rstrip()
            break

    final_text = TRAILING_WHITESPACE.sub(" ", final_text).strip()
    if final_text and final_text[-1] not in "。.!?！？…":
        final_text += "。"

    return final_text
