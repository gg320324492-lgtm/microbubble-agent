"""Vision MCP 客户端 - 通过 stdio 传输与 MCP 服务器通信"""

import asyncio
import json
import logging
import subprocess
from typing import Optional

logger = logging.getLogger("microbubble.mcp")


class VisionMCPClient:
    """Vision MCP 客户端（stdio 传输）"""

    def __init__(
        self,
        server_cmd: Optional[str] = None,
        timeout: float = 60.0
    ):
        from app.config import settings
        self.server_cmd = server_cmd or getattr(settings, 'VISION_MCP_SERVER_CMD', 'python -m mcp_server.server')
        self.timeout = timeout
        self._process: Optional[subprocess.Process] = None
        self._write_lock: Optional[asyncio.Lock] = None
        self._connected = False

    async def connect(self) -> None:
        """连接到 MCP 服务器（通过 stdio）"""
        if self._connected:
            return

        logger.info(f"Connecting to MCP server: {self.server_cmd}")

        # 启动 MCP 服务器进程
        parts = self.server_cmd.split()
        self._process = await asyncio.create_subprocess_exec(
            *parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        self._write_lock = asyncio.Lock()
        self._connected = True

        # 初始化 MCP 协议
        await self._send_init()

        logger.info("MCP client connected")

    async def _send_init(self) -> None:
        """发送 MCP 初始化请求"""
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "microbubble-agent",
                    "version": "1.0.0"
                }
            }
        }

        response = await self._send_request(init_request)
        logger.info(f"MCP server initialized: {response}")

    async def _send_request(self, request: dict) -> dict:
        """发送 JSON-RPC 请求并等待响应"""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("MCP process not running")

        json_request = json.dumps(request) + "\n"

        async with self._write_lock:
            self._process.stdin.write(json_request.encode())
            await self._process.stdin.drain()

        # 读取响应
        line = await asyncio.wait_for(
            self._process.stdout.readline(),
            timeout=self.timeout
        )

        if not line:
            raise RuntimeError("MCP server closed connection")

        response = json.loads(line.decode())

        # 检查是否是错误响应
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        return response.get("result", {})

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict
    ) -> str:
        """
        调用 MCP 工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果的文本
        """
        if not self._connected:
            await self.connect()

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = await self._send_request(request)

        # 解析响应内容
        content = response.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            if isinstance(content[0], dict) and content[0].get("type") == "text":
                return content[0].get("text", "")
            elif isinstance(content[0], str):
                return content[0]

        return str(content)

    async def analyze_image(
        self,
        image_base64: str,
        media_type: str = "image/png",
        question: str = "描述这张图片的内容"
    ) -> str:
        """
        分析图片

        Args:
            image_base64: Base64 编码的图片
            media_type: 图片 MIME 类型
            question: 关于图片的问题

        Returns:
            图片分析结果
        """
        return await self.call_tool(
            "analyze_image",
            {
                "image_base64": image_base64,
                "image_media_type": media_type,
                "question": question
            }
        )

    async def analyze_task_screenshot(
        self,
        image_base64: str,
        media_type: str = "image/png"
    ) -> str:
        """
        分析任务截图

        Args:
            image_base64: Base64 编码的图片
            media_type: 图片 MIME 类型

        Returns:
            截图分析结果
        """
        return await self.call_tool(
            "analyze_task_screenshot",
            {
                "image_base64": image_base64,
                "image_media_type": media_type
            }
        )

    async def disconnect(self) -> None:
        """断开 MCP 服务器连接"""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

        self._connected = False
        logger.info("MCP client disconnected")


# 全局单例
vision_mcp_client = VisionMCPClient()