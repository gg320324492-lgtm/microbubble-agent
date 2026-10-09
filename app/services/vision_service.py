"""视觉识别服务 - 支持多种后端（直接 API / MCP）"""

import base64
import httpx
import logging
from typing import Optional
from app.config import settings
from app.core.llm import get_anthropic_client, get_default_model

logger = logging.getLogger("microbubble.vision")


class VisionService:
    """视觉识别服务 - 支持直接 API 调用或 MCP 模式"""

    def __init__(self):
        self._use_mcp = getattr(settings, 'VISION_USE_MCP', False)
        self._mcp_client = None

    async def _get_mcp_client(self):
        """懒加载 MCP 客户端"""
        if self._mcp_client is None:
            from app.mcp.client import vision_mcp_client
            await vision_mcp_client.connect()
            self._mcp_client = vision_mcp_client
        return self._mcp_client

    def _detect_media_type(self, image_data: bytes) -> str:
        """根据图片魔数检测媒体类型"""
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif image_data[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif image_data[:4] == b'GIF8':
            return "image/gif"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return "image/webp"
        return "image/png"  # 默认

    async def analyze_image(self, image_data: bytes, question: str = "描述这张图片的内容") -> str:
        """
        使用多模态模型分析图片（直接 API 或 MCP 模式）

        Args:
            image_data: 图片二进制数据
            question: 对图片的问题

        Returns:
            分析结果文本
        """
        image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
        media_type = self._detect_media_type(image_data)

        if self._use_mcp:
            return await self._analyze_via_mcp(image_b64, media_type, question)
        else:
            return await self._analyze_direct(image_data, image_b64, media_type, question)

    async def _analyze_via_mcp(self, image_b64: str, media_type: str, question: str) -> str:
        """通过 MCP 调用视觉服务"""
        try:
            client = await self._get_mcp_client()
            return await client.analyze_image(image_b64, media_type, question)
        except Exception as e:
            logger.error(f"MCP 调用失败，回退到直接 API: {e}")
            # MCP 失败时回退到直接 API
            image_data = base64.standard_b64decode(image_b64)
            return await self._analyze_direct(image_data, image_b64, media_type, question)

    async def _analyze_direct(self, image_data: bytes, image_b64: str, media_type: str, question: str) -> str:
        """直接调用视觉 API（Anthropic/GPT-4V 等）"""
        try:
            client = get_anthropic_client()
            model = getattr(settings, 'VISION_MODEL', None) or get_default_model()
            logger.info(f"使用模型 {model} 分析图片, media_type={media_type}")

            response = await client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": question
                        }
                    ]
                }]
            )

            # 提取响应文本
            #
            # 【2026-10-09 修复 · agent19】这里**不能**取 content[0]。
            # 带思维链的模型（mimo-v2.5 → MiniMax-M3、MiniMax-M3.1-Flash-Preview 等）
            # 在 Anthropic 端点返回的是**多块** content：
            #     content[0] = ThinkingBlock(thinking="We need inspect image...", signature="...")
            #     content[1] = TextBlock(text="绿色")
            # 旧写法 `response.content[0]` 会命中 thinking 块，既没有 `.text`
            # 又不是 dict，于是走 `str(content_block)` 分支把 ThinkingBlock 的
            # repr（ThinkingBlock(thinking='We need inspect image...', signature='...')）
            # 当成图片描述返回 → **思维链直接污染 ocr_text / visual_summary**。
            #
            # 正确语义与 app/core/llm.py::extract_text_from_response 对齐：
            # 遍历全部块，优先拼接 text 块；一个 text 块都没有才回退 thinking。
            if response.content and len(response.content) > 0:
                text_content = ""
                thinking_content = ""
                for block in response.content:
                    # 兼容两种形态：Anthropic SDK 对象（有 .text/.thinking 属性）
                    # 与代理端点常见的裸 dict（{"type": "text", "text": "..."}）
                    if isinstance(block, dict):
                        block_text = block.get("text")
                        block_thinking = block.get("thinking")
                    else:
                        block_text = getattr(block, "text", None)
                        block_thinking = getattr(block, "thinking", None)
                    if block_text:
                        text_content += block_text
                    if block_thinking:
                        thinking_content += block_thinking

                if text_content.strip():
                    return text_content
                if thinking_content.strip():
                    # 没有任何 text 块：回退 thinking（对齐 extract_text_from_response 语义），
                    # 总比把整块 repr 写进 ocr_text 好；下游 _clean_ocr_text 还会再剥一遍。
                    logger.warning("视觉响应无 text 块，回退使用 thinking 内容作为分析结果")
                    return thinking_content
                return str(response.content[0])

            return "无法解析图片分析结果"

        except Exception as e:
            logger.error(f"图片分析失败: {e}", exc_info=True)
            raise Exception(f"图片分析失败: {str(e)}")

    async def analyze_task_screenshot(self, image_data: bytes) -> str:
        """分析任务相关截图"""
        return await self.analyze_image(
            image_data,
            "这张图片是课题组任务相关的截图。请分析图片内容，提取任务信息（标题、负责人、截止日期、状态等）。如果是任务完成截图，请总结完成情况。"
        )



# 全局实例
vision_service = VisionService()
