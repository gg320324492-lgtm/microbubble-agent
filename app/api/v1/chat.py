from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import json

from app.agent.core import agent
from app.core.database import get_db
from app.core.security import get_current_user, decode_token
from app.models.member import Member

router = APIRouter()


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    """对话响应"""
    content: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """文字对话接口"""
    result = await agent.chat(
        message=request.message,
        session_id=request.session_id,
        db=db
    )
    return ChatResponse(
        content=result["content"],
        session_id=request.session_id
    )


@router.websocket("/ws/chat/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: str, token: str = ""):
    """WebSocket实时对话"""
    # 认证：从query参数获取token
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    session_id = f"user_{user_id}"

    from app.core.database import async_session
    async with async_session() as db:
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                message = message_data.get("content", "")
                msg_type = message_data.get("type", "text")

                if msg_type == "text":
                    result = await agent.chat(
                        message=message,
                        session_id=session_id,
                        db=db
                    )
                    await websocket.send_json({
                        "type": "text",
                        "content": result["content"]
                    })
                elif msg_type == "voice":
                    await websocket.send_json({
                        "type": "text",
                        "content": "语音功能开发中..."
                    })

        except WebSocketDisconnect:
            await agent.clear_session(session_id)
