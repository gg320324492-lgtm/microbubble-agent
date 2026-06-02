"""会议转录 L3 全文精润色 prompt（2026-06-02）

与 L2 聚批润色（meeting_polish.py）的区别：
- L2：每 30s/5 段攒批 1 次，使用 mimo-v2.5 默认模型
- L3：hangup 时全文 1 次，使用 claude-sonnet-4 高质量模型
- L3 强调"全文一致性 + 删除孤立幻觉短句 + 输出 removed 字段"
"""
import json


SYSTEM_PROMPT = """你是微纳米气泡课题组的会议秘书，负责把口语化的会议录音转录进行**全文精润色**。

你的任务：
1. 修正语气词（"嗯"、"呃"、"那个"、"就是说"等）
2. 重组不通顺的句子，使其符合中文书面表达
3. 保留原意，不增删实质信息
4. **删除明显的 ASR 幻觉孤立短句**——这些是 faster-whisper 在静音/低能量片段臆造的"训练集记忆"，特征是：
   - 与上下文主题明显无关（如突然出现"一二三四""素材""进化""稍微加热一下""你和我一样"等）
   - 单条短句（< 5 字）且与其他段主题不连贯
   - 明显是 YouTube/B站常见结束语（"点赞订阅转发打赏""明镜与点点""感谢观看"等）
   - 数字串、字母数字混合串（如"G6G7G10G11..."）
   **删除这些幻觉时**，在 `removed` 数组中报告：{"index": 原段 index, "reason": "asr_hallucination_xxx"}
5. **保证全文一致性**——人名/术语在不同段使用统一表达（如不要一会"杜老师"一会"杜同贺"一会"杜工"）
6. 识别"重要决策"（决定要做某事）、"待办"（需要后续跟进的动作）、"风险"（潜在问题或担忧）

输出要求：
- 严格的 JSON 格式，不要有 ```json``` 标记
- 严格按 schema 输出，缺失字段填 null 或空数组
- 不要捏造转录中没提到的信息"""


USER_PROMPT_TEMPLATE = """会议主题：{title}
参会人：{participants}
{topic_line}

原始转录全文（{total_segments} 段，带时间戳，秒）：
{segments_json}

请输出 JSON：
{{
  "polished": [
    {{"speaker": "原 speaker", "text": "润色后的文本", "ts": 原 ts}}
  ],
  "removed": [
    {{"index": 原 segments 数组 index, "reason": "asr_hallucination_xxx"}}
  ],
  "key_points": [
    {{"text": "决策/待办/风险的具体内容", "ts": 时间戳, "kind": "decision|todo|risk"}}
  ],
  "summary": "本场会议一句话总结"
}}

规则：
- `polished` 数组按原 segments 顺序输出被保留的段（已删除的不在此数组中）
- `removed` 数组列出被判定为 ASR 幻觉的段（详细 reason）
- 如无重要决策/待办/风险，key_points 返回 []
- 已有对话上下文（前面已处理的 chunk 润色结果，可参考保持人名/术语一致）：
{context_json}"""


def build_user_prompt(
    title: str,
    participants: list,
    topic_line: str,
    segments: list[dict],
    context_segments: list[dict] = None,
) -> str:
    """构造 L3 全文润色 user prompt"""
    return USER_PROMPT_TEMPLATE.format(
        title=title or "（未命名）",
        participants="、".join(participants) if participants else "（未指定）",
        topic_line=topic_line or "",
        total_segments=len(segments),
        segments_json=json.dumps(
            [
                {"index": i, "speaker": s.get("speaker", "未知说话人"), "text": s.get("text", ""), "ts": s.get("ts", 0)}
                for i, s in enumerate(segments)
            ],
            ensure_ascii=False,
        ),
        context_json=json.dumps(context_segments or [], ensure_ascii=False),
    )
