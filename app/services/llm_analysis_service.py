"""LLM 内容分析服务 — 自动分类、标签、摘要生成"""

import json
import logging
import anthropic

from app.config import settings

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
            client = anthropic.AsyncAnthropic(
                api_key=settings.CLAUDE_API_KEY,
                base_url=settings.CLAUDE_BASE_URL or None,
            )
            prompt = ANALYSIS_PROMPT.format(
                title=title,
                content=content[:3000]
            )
            response = await client.messages.create(
                model=settings.CLAUDE_MODEL or "mimo-v2.5",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            # 提取文本内容
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    break
            # 解析 JSON
            text = text.strip()
            # 处理可能的 markdown 代码块包裹
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM 分析返回非 JSON 格式: {e}")
            return {}
        except Exception as e:
            logger.error(f"LLM 内容分析失败: {e}")
            return {}


llm_analysis_service = LLMAnalysisService()
