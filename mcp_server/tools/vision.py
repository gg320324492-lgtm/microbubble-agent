"""视觉分析 MCP 工具实现"""

import base64
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult

from app.config import settings

logger = logging.getLogger("mcp_vision.tools")


def create_vision_tools(server: Server):
    """注册视觉分析工具"""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """列出可用工具"""
        return [
            Tool(
                name="analyze_image",
                description="分析图片内容，返回图片的详细描述。支持 PNG/JPEG/GIF/WEBP 格式。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "image_base64": {
                            "type": "string",
                            "description": "Base64 编码的图片数据"
                        },
                        "image_media_type": {
                            "type": "string",
                            "description": "图片 MIME 类型，如 image/png、image/jpeg",
                            "default": "image/png"
                        },
                        "question": {
                            "type": "string",
                            "description": "关于图片的问题",
                            "default": "描述这张图片的内容"
                        }
                    },
                    "required": ["image_base64"]
                }
            ),
            Tool(
                name="analyze_task_screenshot",
                description="分析任务相关截图，提取任务信息（标题、负责人、截止日期、状态等）。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "image_base64": {
                            "type": "string",
                            "description": "Base64 编码的图片数据"
                        },
                        "image_media_type": {
                            "type": "string",
                            "description": "图片 MIME 类型",
                            "default": "image/png"
                        }
                    },
                    "required": ["image_base64"]
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        """处理工具调用"""
        try:
            if name == "analyze_image":
                result = await _analyze_image(
                    image_base64=arguments["image_base64"],
                    media_type=arguments.get("image_media_type", "image/png"),
                    question=arguments.get("question", "描述这张图片的内容")
                )
                return CallToolResult(content=[TextContent(type="text", text=result)])

            elif name == "analyze_task_screenshot":
                result = await _analyze_task_screenshot(
                    image_base64=arguments["image_base64"],
                    media_type=arguments.get("image_media_type", "image/png")
                )
                return CallToolResult(content=[TextContent(type="text", text=result)])

            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                    isError=True
                )
        except Exception as e:
            logger.error(f"Tool error: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True
            )


async def _analyze_image(image_base64: str, media_type: str, question: str) -> str:
    """分析图片"""
    from app.services.vision_service import VisionService

    image_data = base64.standard_b64decode(image_base64)
    service = VisionService()
    return await service.analyze_image(image_data, question)


async def _analyze_task_screenshot(image_base64: str, media_type: str) -> str:
    """分析任务截图"""
    from app.services.vision_service import VisionService

    image_data = base64.standard_b64decode(image_base64)
    service = VisionService()
    return await service.analyze_task_screenshot(image_data)