"""会议 AI 分析服务

提供发言者检测、转录解析、结构化分析和发言人统计功能。
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.llm import (
    get_anthropic_client,
    get_default_model,
    parse_llm_json,
    extract_text_from_response,
)

logger = logging.getLogger("microbubble.meeting_analysis")

SPEAKER_DETECTION_PROMPT = """你是一个会议分析助手。请分析以下会议转录文本，识别出不同发言者。

转录文本：
{transcript_text}

分析要求：
1. 识别所有不同的发言者标识（如 "王老师"、"Speaker A"、"张三" 等）
2. 从上下文推测每位发言者的姓名或角色
3. 统计每位发言者的发言次数
4. 提取每位发言者的 1-2 句代表性发言

注意：
- 发言者标识可能以【】包裹，也可能是纯文本中的"XXX说："、"XXX："格式
- 如果没有明确发言者标识，标记为 "未区分发言者"
- 如果无法确定中文名，suggested_name 设为 null
- 中文输出

请输出严格 JSON 格式：
{{
  "detected_speakers": [
    {{
      "original_label": "王老师",
      "suggested_name": null,
      "turn_count": 12,
      "sample_lines": ["今天我们讨论气泡生成效率的实验方案"]
    }}
  ],
  "total_turns": 30,
  "confidence": "high",
  "format_type": "marked"
}}"""

ANALYSIS_PROMPT = """你是一个专业的会议纪要生成助手。请分析以下会议转录内容。

会议转录：
{transcript_text}

请完成以下分析，输出严格的 JSON 格式：

1. 会议摘要（3-5句话，概述会议主题、讨论过程、结论）
2. 讨论要点（逐条列出重要观点，每条标注发言人，格式：【发言人】内容）
3. 决议事项（会议中达成的共识和决定，每条标注来源发言人）
4. 待办任务（明确的行动项，包含负责人、截止日期、优先级）

输出格式：
{{
  "summary": "会议围绕...展开了讨论...",
  "key_points": [
    "【张三】提出了气泡稳定性实验的新方案，建议调整pH值参数",
    "【李四】汇报了上周实验进展，数据表明..."
  ],
  "decisions": [
    "【全组决定】下周三前确定实验方案",
    "【王老师】批准采购新的粒径分析仪"
  ],
  "action_items": [
    {{
      "title": "修改气泡稳定性实验方案",
      "assignee_name": "张三",
      "description": "根据讨论调整气泡稳定性实验的参数设置和测试流程",
      "due_date": "2026-06-04",
      "priority": "high",
      "confidence": "confirmed"
    }}
  ]
}}

注意事项：
- 每条关键点和决议都要标注来源发言人
- 截止日期根据会议时间和事务紧急性合理推断
- 优先级参考：high=本周完成，medium=两周内，low=一月内
- 如果没有明确负责人，assignee_name 设为 null
- confidence 标注：confirmed=明确指派，tentative=建议性
- 只提取明确的行动项，不要过度推断
- 中文输出"""


class MeetingAnalysisService:
    """会议 AI 分析服务"""

    def __init__(self):
        self.client = get_anthropic_client()
        self.model = get_default_model()

    # === 发言者检测 ===

    def _quick_parse_speakers(self, text: str) -> Optional[Dict[str, Any]]:
        """本地快速解析发言者（不调用 AI），处理明确的【发言人】格式。

        成功检测到多位发言者时返回结果，否则返回 None 交由 AI 处理。
        """
        # 匹配 【名称】: ... 或 【名称】：... 格式
        pattern = re.compile(r'【(.+?)】[:：]')
        matches = pattern.findall(text)

        if not matches:
            # 尝试匹配 "名称说：" "名称：" 格式
            pattern2 = re.compile(r'(?:(?:^|\n)([^\s【】]{2,6})(?:说|：|:))')
            matches = pattern2.findall(text)

        if not matches:
            return None

        speaker_counts: Dict[str, int] = {}
        speaker_lines: Dict[str, List[str]] = {}
        lines = text.split("\n")

        for label in matches:
            speaker_counts[label] = speaker_counts.get(label, 0) + 1

        for label in set(matches):
            sample = []
            for line in lines:
                if label in line and len(sample) < 2:
                    clean = line.strip()[:120]
                    if clean not in sample:
                        sample.append(clean)
            speaker_lines[label] = sample

        unique_speakers = list(speaker_counts.keys())
        if len(unique_speakers) < 2:
            return None

        detected = []
        for label in unique_speakers:
            detected.append({
                "original_label": label,
                "suggested_name": None,
                "turn_count": speaker_counts[label],
                "sample_lines": speaker_lines.get(label, [])[:2],
            })

        return {
            "detected_speakers": detected,
            "total_turns": sum(speaker_counts.values()),
            "confidence": "high" if len(unique_speakers) <= 5 else "medium",
            "format_type": "marked",
        }

    async def detect_speakers(self, transcript_text: str) -> Dict[str, Any]:
        """自动识别转录文本中的发言者。

        先用本地正则快速解析【发言人】格式，失败时回退到 Claude AI。
        """
        local = self._quick_parse_speakers(transcript_text)
        if local:
            return local

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="你是会议分析助手。只输出 JSON，不要其他内容。",
                messages=[{
                    "role": "user",
                    "content": SPEAKER_DETECTION_PROMPT.format(
                        transcript_text=transcript_text[:12000]
                    ),
                }],
            )
            text = extract_text_from_response(response)
            return parse_llm_json(text)
        except Exception as e:
            logger.error(f"发言者检测失败: {e}")
            return {
                "detected_speakers": [
                    {"original_label": "未区分发言者", "suggested_name": None,
                     "turn_count": 1, "sample_lines": [transcript_text[:100]]}
                ],
                "total_turns": 1,
                "confidence": "low",
                "format_type": "unknown",
            }

    # === 转录解析 ===

    def parse_with_mapping(
        self, transcript_text: str, speaker_mapping: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """将原始文本 + 发言者映射转换为结构化转录 JSON。

        输出格式与 Meeting.transcript JSON 兼容：
        [{"speaker": "张三", "text": "..."}, ...]
        """
        entries: List[Dict[str, str]] = []

        # 尝试按【发言人】: 格式切分
        pattern = re.compile(r'【(.+?)】[:：]\s*(.+?)(?=【|$)', re.DOTALL)
        matches = pattern.findall(transcript_text)

        if matches:
            for label, text in matches:
                text = text.strip()
                if not text:
                    continue
                real_name = speaker_mapping.get(label, label)
                entries.append({"speaker": real_name, "text": text})
        else:
            # 按换行切分，尝试匹配 "名称说/：" 格式
            lines = transcript_text.split("\n")
            current_speaker = "参会者"
            current_text: List[str] = []

            for line in lines:
                line = line.strip()
                if not line:
                    if current_text:
                        entries.append({
                            "speaker": speaker_mapping.get(current_speaker, current_speaker),
                            "text": " ".join(current_text),
                        })
                        current_text = []
                    continue

                # 检测说话人切换
                speaker_match = re.match(r'^(.{2,6})(?:说|：|:)\s*(.+)', line)
                if speaker_match:
                    if current_text:
                        entries.append({
                            "speaker": speaker_mapping.get(current_speaker, current_speaker),
                            "text": " ".join(current_text),
                        })
                        current_text = []
                    current_speaker = speaker_match.group(1)
                    text_part = speaker_match.group(2).strip()
                    if text_part:
                        current_text.append(text_part)
                else:
                    current_text.append(line)

            if current_text:
                entries.append({
                    "speaker": speaker_mapping.get(current_speaker, current_speaker),
                    "text": " ".join(current_text),
                })

        return entries

    # === 结构化分析 ===

    async def analyze_transcript(
        self,
        transcript_text: str,
        speaker_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """对转录文本进行完整 AI 分析：摘要 + 要点 + 决策 + 行动项。

        Args:
            transcript_text: 原始转录文本
            speaker_mapping: 可选的发言者映射，用于标注发言人归属
        """
        # 如果有映射，先重写转录文本使发言人标签一致
        text_to_analyze = transcript_text
        if speaker_mapping:
            applied = []
            for issue, resolved in speaker_mapping.items():
                applied.append(f"【{issue}】→ {resolved}")
            text_to_analyze = (
                f"发言者映射：{', '.join(applied)}\n\n{transcript_text}"
            )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system="你是课题组会议分析专家。只输出 JSON，不要其他内容。",
                messages=[{
                    "role": "user",
                    "content": ANALYSIS_PROMPT.format(
                        transcript_text=text_to_analyze[:12000]
                    ),
                }],
            )
            text = extract_text_from_response(response)
            return parse_llm_json(text)
        except Exception as e:
            logger.error(f"转录分析失败: {e}")
            return {
                "summary": "",
                "key_points": [],
                "decisions": [],
                "action_items": [],
            }

    # === 标题自动生成 ===

    async def generate_title(self, transcript_text: str) -> str:
        """根据转录内容自动生成会议标题（15 字以内）。"""
        prompt = (
            "请根据以下会议转录内容，生成一个简洁的会议标题（15字以内）。"
            "标题应概括会议的核心主题。只输出标题文本，不要引号或额外说明。\n\n"
            f"{transcript_text[:3000]}"
        )
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=64,
                system="你是一个专业的会议记录员。只输出会议标题，不要其他内容。",
                messages=[{"role": "user", "content": prompt}],
            )
            title = extract_text_from_response(response).strip().strip('"').strip("'").strip("《》")
            return title[:30] if title else "未命名会议"
        except Exception as e:
            logger.error(f"标题生成失败: {e}")
            return "未命名会议"

    # === 发言人统计（纯本地计算） ===

    def compute_speaker_stats(
        self, transcript_entries: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """计算每位发言者的统计数据。

        Args:
            transcript_entries: 结构化转录条目
                [{"speaker": "张三", "text": "..."}, ...]
        """
        speaker_data: Dict[str, Dict[str, Any]] = {}
        total_words = 0

        for entry in transcript_entries:
            name = entry.get("speaker", "未知")
            text = entry.get("text", "")
            words = len(text.replace(" ", ""))

            if name not in speaker_data:
                speaker_data[name] = {
                    "name": name,
                    "turn_count": 0,
                    "word_count": 0,
                }
            speaker_data[name]["turn_count"] += 1
            speaker_data[name]["word_count"] += words
            total_words += words

        stats = []
        for name, data in speaker_data.items():
            ratio = round(data["word_count"] / total_words, 3) if total_words > 0 else 0
            stats.append({
                "name": name,
                "turn_count": data["turn_count"],
                "word_count": data["word_count"],
                "speaking_ratio": ratio,
                "avg_turn_length": round(data["word_count"] / data["turn_count"]) if data["turn_count"] else 0,
                "topics": [],
            })

        stats.sort(key=lambda x: x["word_count"], reverse=True)
        return stats


# 全局单例
meeting_analysis = MeetingAnalysisService()
