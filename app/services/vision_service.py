"""视觉识别服务 - 使用 Claude Vision 处理图片消息"""

import base64
import httpx
from typing import Optional
from app.config import settings


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
                if response.status_code == 200:
                    return response.content
                return None
        except Exception as e:
            print(f"下载图片失败: {e}")
            return None

    async def download_voice(self, media_id: str) -> Optional[bytes]:
        """从企业微信下载语音"""
        return await self.download_image(media_id)

    async def analyze_image(self, image_data: bytes, question: str = "描述这张图片的内容") -> str:
        """
        使用 Claude Vision 分析图片

        Args:
            image_data: 图片二进制数据
            question: 对图片的问题

        Returns:
            分析结果文本
        """
        import anthropic

        client = anthropic.AsyncAnthropic(
            api_key=settings.CLAUDE_API_KEY,
            base_url=settings.CLAUDE_BASE_URL or None,
        )
        image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
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

        return response.content[0].text

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
