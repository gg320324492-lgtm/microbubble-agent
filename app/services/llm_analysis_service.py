"""LLM 内容分析服务 — 自动分类、标签、摘要生成"""

import json
import logging

from app.config import settings
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

logger = logging.getLogger("microbubble.llm_analysis")

ANALYSIS_PROMPT = """分析以下知识库文档，返回严格的JSON格式（不要包含其他文字）：
{{
  "summary": "100字以内的中文摘要",
  "category": "从以下选项中选择一个: 基础/方法/文献/FAQ",
  "tags": ["标签1", "标签2", "标签3"]
}}

标题: {title}
内容: {content}"""


class LLMAnalysisService:
    """基于 LLM 的内容分析：自动分类、标签、摘要"""

    async def analyze_content(self, title: str, content: str) -> dict:
        """分析内容，返回 {summary, category, tags}"""
        try:
            client = get_anthropic_client()
            prompt = ANALYSIS_PROMPT.format(
                title=title,
                content=content[:3000]
            )
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            # 提取文本内容
            text = extract_text_from_response(response)
            # 解析 JSON
            return parse_llm_json(text)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM 分析返回非 JSON 格式: {e}")
            return {}
        except Exception as e:
            logger.error(f"LLM 内容分析失败: {e}")
            return {}


llm_analysis_service = LLMAnalysisService()
