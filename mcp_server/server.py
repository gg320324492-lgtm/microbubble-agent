"""MCP Vision Server - 视觉分析 MCP 服务器（stdio 传输）"""

import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities

from app.config import settings
from app.services.vision_service import VisionService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_vision")

# 创建 MCP 服务器
app = Server(
    name="vision-mcp-server",
    version="1.0.0",
    capabilities=ServerCapabilities(
        tools={"listChanged": True}
    )
)

# 注册视觉工具
from .tools.vision import create_vision_tools
create_vision_tools(app)


async def main():
    """主入口"""
    logger.info("Starting Vision MCP Server...")
    logger.info(f"Vision model: {getattr(settings, 'VISION_MODEL', 'mimo-v2.5')}")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())