from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, UploadFile, File, Form
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


@router.post("/chat/image", response_model=ChatResponse)
async def chat_with_image(
    message: str = Form(...),
    session_id: str = Form("default"),
    image: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """图片对话接口"""
    # 读取图片数据
    image_data = await image.read()

    # 获取图片媒体类型
    content_type = image.content_type or "image/png"
    if content_type == "image/jpeg":
        media_type = "image/jpeg"
    elif content_type == "image/gif":
        media_type = "image/gif"
    elif content_type == "image/webp":
        media_type = "image/webp"
    else:
        media_type = "image/png"

    result = await agent.chat(
        message=message,
        session_id=session_id,
        db=db,
        image_data=image_data,
        image_media_type=media_type
    )
    return ChatResponse(
        content=result["content"],
        session_id=session_id
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
                elif msg_type == "image":
                    # 处理图片消息
                    import base64
                    image_b64 = message_data.get("image", "")
                    image_media_type = message_data.get("media_type", "image/png")

                    if image_b64:
                        image_data = base64.b64decode(image_b64)
                        result = await agent.chat(
                            message=message,
                            session_id=session_id,
                            db=db,
                            image_data=image_data,
                            image_media_type=image_media_type
                        )
                        await websocket.send_json({
                            "type": "text",
                            "content": result["content"]
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "content": "图片数据为空"
                        })
                elif msg_type == "voice":
                    await websocket.send_json({
                        "type": "text",
                        "content": "语音功能开发中..."
                    })

        except WebSocketDisconnect:
            await agent.clear_session(session_id)
