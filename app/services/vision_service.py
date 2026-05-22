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

    async def download_image(self, media_id: str) -> Optional[bytes]:
        """
        从企业微信下载图片

        Args:
            media_id: 企业微信媒体文件ID

        Returns:
            图片二进制数据
        """
        try:
            from app.wechat.bot import wechat_bot
            token = await wechat_bot._get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.WECHAT_API_BASE_URL.rstrip('/')}/cgi-bin/media/get",
                    params={"access_token": token, "media_id": media_id}
                )
                logger.info(f"下载图片响应: status={response.status_code}, content-type={response.headers.get('content-type')}, size={len(response.content)}")

                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    # 企业微信返回 JSON 表示错误
                    if "json" in content_type or "text" in content_type:
                        logger.error(f"下载图片返回错误: {response.text[:500]}")
                        return None
                    return response.content
                logger.error(f"下载图片失败: HTTP {response.status_code}, body={response.text[:500]}")
                return None
        except Exception as e:
            logger.error(f"下载图片失败: {e}", exc_info=True)
            return None

    async def download_voice(self, media_id: str) -> Optional[bytes]:
        """从企业微信下载语音（自动检测格式：SILK/AMR/WAV）"""
        data = await self.download_image(media_id)
        if data:
            # 检测音频格式
            if data[:4] == b'RIFF':
                fmt = "WAV"
            elif data[:4] == b'#!AM':
                fmt = "AMR"
            elif data[:4] == b'\x02#!':
                fmt = "SILK"
            else:
                fmt = f"unknown({data[:4].hex()})"
            logger.info(f"下载语音: media_id={media_id}, format={fmt}, size={len(data)} bytes")
        return data

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
            if response.content and len(response.content) > 0:
                content_block = response.content[0]
                if hasattr(content_block, 'text'):
                    return content_block.text
                elif isinstance(content_block, dict) and 'text' in content_block:
                    return content_block['text']
                else:
                    return str(content_block)

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
