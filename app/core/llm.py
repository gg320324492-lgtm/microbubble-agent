"""LLM 工具函数 — Anthropic 客户端工厂 + JSON 解析"""

import json
import logging
from typing import Optional

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
    for block in response.content:
        if hasattr(block, "text"):
            return block.text.strip()
    return ""
