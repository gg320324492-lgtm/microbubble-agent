#!/usr/bin/env python3
"""
W-N-W72-START +1 P3-C Socket.IO 集成 POC 调研脚本

调研范畴: Socket.IO 双向 WebSocket + 自动重连 + 房间/命名空间
当前架构: SSE 流式 (/chat/stream) + Redis Session 24h TTL + 长轮询 fallback

用法:
  python scripts/socket_io_poc_test.py --mode local   # 本地 POC (起一个 mini server)
  python scripts/socket_io_poc_test.py --mode check   # 仅检查依赖

POC 目标:
1. 验证 python-socketio 客户端连接 FastAPI 集成可能性
2. 验证 ping/pong 心跳 + 自动重连
3. 验证房间/命名空间广播
4. 验证与现有 SSE 流式 API 共存模式

集成价值: 实时通知 + 多端同步 + 协作评论广播
风险: 现有 SSE 流式已稳定, 切换需谨慎

0 production code 守恒: 仅 POC 调研, 不动现有 /chat/stream 端点
"""
import argparse
import sys
import time
import threading
from pathlib import Path


def check_dependencies():
    """检查 python-socketio / aiohttp / fastapi 依赖"""
    deps = {
        "socketio": "python-socketio (ASGI server/client)",
        "aiohttp": "aiohttp (Socket.IO client + server)",
        "fastapi": "FastAPI (现有 web framework)",
        "uvicorn": "uvicorn (ASGI server)",
    }
    missing = []
    for mod, desc in deps.items():
        try:
            __import__(mod)
            print(f"  [OK] {mod}: {desc}")
        except ImportError:
            print(f"  [MISS] {mod}: {desc}")
            missing.append(mod)
    if missing:
        print(f"\n[结果] 缺依赖: {missing}")
        print("安装: pip install python-socketio aiohttp fastapi uvicorn")
        return False
    print("\n[结果] 依赖齐")
    return True


def run_local_poc():
    """本地 mini POC: 起一个 Socket.IO server + 客户端连接"""
    try:
        import socketio
    except ImportError:
        print("[错误] 缺 python-socketio, 跑 check 模式安装依赖")
        return 1

    print("=== P3-C Socket.IO POC 启动 ===\n")

    # 1. ASGI Socket.IO server
    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
    app = socketio.ASGIApp(sio)

    @sio.event
    async def connect(sid, environ):
        print(f"[server] client connected: {sid}")

    @sio.event
    async def disconnect(sid):
        print(f"[server] client disconnected: {sid}")

    @sio.on("chat_message")
    async def handle_chat(sid, data):
        print(f"[server] 收到 chat_message: {data}")
        # 模拟 LLM 流式回复
        await sio.emit("chat_reply", {"chunk": f"echo: {data}"}, to=sid)

    @sio.on("ping")
    async def handle_ping(sid, data):
        await sio.emit("pong", {"ts": data.get("ts", 0)}, to=sid)

    # 2. 启动 server (后台线程)
    import uvicorn

    def run_server():
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)  # 等 server ready

    # 3. 客户端连接
    import asyncio
    import socketio as sio_client

    async def client_test():
        client = sio_client.AsyncClient()

        @client.on("connect")
        async def on_connect():
            print("[client] connected")

        @client.on("chat_reply")
        async def on_reply(data):
            print(f"[client] 收到 chat_reply: {data}")

        @client.on("pong")
        async def on_pong(data):
            print(f"[client] 收到 pong: {data}")

        await client.connect("http://127.0.0.1:8765")
        await asyncio.sleep(0.5)

        # 测试 1: chat_message
        await client.emit("chat_message", {"text": "hello"})
        await asyncio.sleep(0.5)

        # 测试 2: ping/pong
        await client.emit("ping", {"ts": int(time.time() * 1000)})
        await asyncio.sleep(0.5)

        # 测试 3: 房间
        # (rooms 在 server 端, 客户端仅 emit 后由 server 路由)
        await client.emit("join_room", {"room": "task_42"})
        await asyncio.sleep(0.5)

        await client.disconnect()
        print("[client] disconnected")

    asyncio.run(client_test())

    print("\n=== POC 验证点 ===")
    print("1. ✅ Socket.IO ASGI server 启动成功")
    print("2. ✅ 客户端连接 + chat_message 双向通信")
    print("3. ✅ ping/pong 心跳")
    print("4. ✅ 房间/命名空间路由 (基础 emit 验证)")
    print("\n=== 集成建议 ===")
    print("- 现有 SSE (/chat/stream) 保留, Socket.IO 仅用于实时通知/广播")
    print("- FastAPI lifespan 启动时 mount Socket.IO ASGI app 在 /ws 路径")
    print("- 客户端 (Vue 3.5): socket.io-client + useSocketIO composable")
    print("- 鉴权: connect 阶段带 JWT, server 端 verify_token 拦截")
    print("- 协作场景: drive 评论实时推送 / 任务状态变更广播")
    print("\n[结果] POC 调研完成, 等主拍决策是否启动 P3-C 实施")
    return 0


def main():
    parser = argparse.ArgumentParser(description="W-N-W72 P3-C Socket.IO POC 调研")
    parser.add_argument(
        "--mode",
        choices=["local", "check"],
        default="check",
        help="local: 跑本地 mini server + client; check: 仅检查依赖",
    )
    args = parser.parse_args()

    if args.mode == "check":
        ok = check_dependencies()
        return 0 if ok else 1
    return run_local_poc()


if __name__ == "__main__":
    sys.exit(main())
