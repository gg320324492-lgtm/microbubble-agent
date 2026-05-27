"""AI 内容排版服务 — 将 PDF 提取的混乱文本整理为结构化 Markdown"""

import logging

from app.core.llm import get_anthropic_client, get_default_model, extract_text_from_response

logger = logging.getLogger("microbubble.content_formatter")

FORMAT_PROMPT = """你是学术文档排版助手。请将以下从 PDF 提取的混乱文本整理为结构清晰的 Markdown 格式。

排版规则：
1. **去除干扰**：删除页眉、页脚、页码、目录碎片等非正文内容
2. **合并段落**：将因换页而断开的句子和段落重新合并，保持语义完整
3. **识别层级**：按原文章节结构使用 # ## ### 标题层级
4. **化学式**：使用 HTML 标签格式化，如 MnO<sub>2</sub>、SO<sub>4</sub><sup>2−</sup>、•OH、<sup>1</sup>O<sub>2</sub>
5. **图表**：保留图表的编号和标题，用 > 引用块标注
6. **表格**：尽可能还原为 Markdown 表格格式
7. **完整保留**：不要删减或改写论文的实质性内容，只做排版整理
8. **参考文献**：保留完整，按原文格式

标题: {title}
原始文本:
{content}

请直接输出整理后的 Markdown 文档，不要加任何解释说明。"""


class ContentFormatterService:
    """使用 LLM 将 PDF 提取文本整理为结构化 Markdown"""

    async def format_content(self, title: str, content: str) -> str:
        """整理内容排版，返回 Markdown 格式文本"""
        try:
            client = get_anthropic_client()
            prompt = FORMAT_PROMPT.format(
                title=title,
                content=content[:50000]  # 全文排版，最多处理 5 万字符
            )
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=16384,
                timeout=300,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}]
            )
            formatted = extract_text_from_response(response)
            if formatted and len(formatted) > 50:
                logger.info(f"内容排版成功: {title}, 输出 {len(formatted)} 字符")
                return formatted
            else:
                logger.warning(f"内容排版输出过短: {title}")
                return ""
        except Exception as e:
            logger.error(f"内容排版失败: {title}, 错误: {e}")
            return ""


content_formatter_service = ContentFormatterService()
