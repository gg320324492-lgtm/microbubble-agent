"""LLM 工具函数 — Anthropic 客户端工厂 + JSON 解析"""

import json
import logging

import anthropic

from app.config import settings

logger = logging.getLogger("microbubble.llm")


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """创建异步 Anthropic 客户端（单例模式由调用方管理）"""
    return anthropic.AsyncAnthropic(
        api_key=settings.CLAUDE_API_KEY,
        base_url=settings.CLAUDE_BASE_URL or None,
    )


def get_default_model() -> str:
    """获取默认 LLM 模型名称"""
    return settings.CLAUDE_MODEL or "mimo-v2.5"


def parse_llm_json(text: str) -> dict:
    """解析 LLM 返回的 JSON 文本，自动处理 markdown 代码块包裹"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # 移除首行 ```json 和末尾 ```
        if lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
        else:
            text = "\n".join(lines[1:])
        text = text.strip()
    return json.loads(text)


def extract_text_from_response(response) -> str:
    """从 Claude API 响应中提取文本内容（兼容 ThinkingBlock）"""
    text_content = ""
    thinking_content = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            text_content = block.text.strip()
        elif hasattr(block, "thinking") and block.thinking:
            thinking_content = block.thinking.strip()
    # 优先返回 text；如果只有 thinking 则返回 thinking（模型有时只返回 thinking）
    if not text_content and thinking_content:
        logger.debug("响应只有 ThinkingBlock，使用 thinking 内容")
    return text_content or thinking_content
