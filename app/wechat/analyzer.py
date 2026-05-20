"""对话智能分析模块

从自然对话中提取：
- 任务分配（谁做什么、什么时候截止）
- 会议安排（时间、地点、参与者）
- 决定/结论
- 待办事项
"""

import json
import logging

logger = logging.getLogger("microbubble.wechat.analyzer")
from typing import List, Dict
from app.config import settings
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

ANALYSIS_PROMPT = """你是课题组的AI助手，负责从对话中提取任务和行动项。

请分析以下对话内容，提取结构化信息。输出 JSON 格式：

{
  "tasks": [
    {
      "assignee_name": "负责人姓名",
      "title": "任务标题",
      "description": "任务描述",
      "due_date": "截止日期（YYYY-MM-DD格式，如果没有明确日期则为null）",
      "priority": "high/medium/low"
    }
  ],
  "meetings": [
    {
      "title": "会议主题",
      "time": "会议时间",
      "location": "会议地点",
      "participants": ["参与者姓名"]
    }
  ],
  "decisions": ["决定/结论1", "决定/结论2"],
  "reminders": [
    {
      "person": "需要提醒的人",
      "content": "提醒内容",
      "time": "提醒时间"
    }
  ],
  "is_actionable": true
}

注意：
- 只提取明确的指令和安排，不要过度推测
- 如果对话中没有任务、会议、决定等可操作内容，is_actionable 设为 false，其他字段为空数组
- 姓名尽量与课题组成员匹配
- 日期如果没有明确提到则设为 null
- 只输出 JSON，不要其他内容"""


class ConversationAnalyzer:
    """对话智能分析器"""

    def __init__(self):
        self.client = get_anthropic_client()
        self.model = get_default_model()

    async def analyze(self, messages: List[Dict[str, str]]) -> Dict:
        """
        分析对话内容，提取任务和行动项

        Args:
            messages: 对话消息列表，格式 [{"speaker": "姓名", "content": "内容"}, ...]

        Returns:
            分析结果字典
        """
        if not messages:
            return {"is_actionable": False, "tasks": [], "meetings": [], "decisions": [], "reminders": []}

        # 格式化对话
        conversation = "\n".join(
            f"【{m['speaker']}】: {m['content']}" for m in messages
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=ANALYSIS_PROMPT,
                messages=[{"role": "user", "content": f"请分析以下对话：\n\n{conversation}"}]
            )

            # 兼容 ThinkingBlock + TextBlock 响应（如 mimo-v2.5）
            text = extract_text_from_response(response)
            result = parse_llm_json(text)
            return result

        except Exception as e:
            logger.error(f"对话分析失败: {e}", exc_info=True)
            return {"is_actionable": False, "tasks": [], "meetings": [], "decisions": [], "reminders": []}

    async def analyze_single_message(self, speaker: str, content: str,
                                      context: List[Dict] = None) -> Dict:
        """
        分析单条消息（结合上下文）

        Args:
            speaker: 发言人
            content: 消息内容
            context: 最近的上下文消息

        Returns:
            分析结果
        """
        messages = []
        if context:
            messages.extend(context)
        messages.append({"speaker": speaker, "content": content})
        return await self.analyze(messages)

    async def extract_action_items(self, meeting_notes: str) -> Dict:
        """
        从会议纪要中提取行动项

        Args:
            meeting_notes: 会议纪要文本

        Returns:
            行动项列表
        """
        return await self.analyze([{"speaker": "会议纪要", "content": meeting_notes}])


# 全局实例
analyzer = ConversationAnalyzer()
