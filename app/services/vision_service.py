"""视觉识别服务 - 使用多模态模型处理图片消息"""

import base64
import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger("microbubble.vision")


class VisionService:
    """视觉识别服务"""

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
        """从企业微信下载语音"""
        return await self.download_image(media_id)

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
        使用多模态模型分析图片

        Args:
            image_data: 图片二进制数据
            question: 对图片的问题

        Returns:
            分析结果文本
        """
        import anthropic

        try:
            client = anthropic.AsyncAnthropic(
                api_key=settings.CLAUDE_API_KEY,
                base_url=settings.CLAUDE_BASE_URL or None,
            )
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
            media_type = self._detect_media_type(image_data)

            # 使用配置的模型，默认为 mimo-v2.5
            model = settings.CLAUDE_MODEL or "mimo-v2.5"
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
                # 处理不同的响应格式
                content_block = response.content[0]
                if hasattr(content_block, 'text'):
                    return content_block.text
                elif isinstance(content_block, dict) and 'text' in content_block:
                    return content_block['text']
                else:
                    # 尝试转换为字符串
                    return str(content_block)

            return "无法解析图片分析结果"

        except anthropic.APIError as e:
            logger.error(f"API 调用失败: {e}", exc_info=True)
            raise Exception(f"AI 服务调用失败: {str(e)}")
        except Exception as e:
            logger.error(f"图片分析失败: {e}", exc_info=True)
            raise Exception(f"图片分析失败: {str(e)}")

    async def analyze_task_screenshot(self, image_data: bytes) -> str:
        """分析任务相关截图"""
        return await self.analyze_image(
            image_data,
            "这张图片是课题组任务相关的截图。请分析图片内容，提取任务信息（标题、负责人、截止日期、状态等）。如果是任务完成截图，请总结完成情况。"
        )

    async def identify_person_from_image(self, image_data: bytes) -> str:
        """从图片中识别人物（用于身份确认）"""
        return await self.analyze_image(
            image_data,
            "这张图片中的人物是谁？请描述人物特征。如果是证件照或头像，请描述外貌特征。"
        )


# 全局实例
vision_service = VisionService()
