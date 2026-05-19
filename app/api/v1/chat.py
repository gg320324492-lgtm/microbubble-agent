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
    file_url: Optional[str] = None
    file_name: Optional[str] = None


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
        db=db,
        user_id=current_user.id
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
        image_media_type=media_type,
        user_id=current_user.id
    )
    return ChatResponse(
        content=result["content"],
        session_id=session_id
    )


@router.post("/chat/file", response_model=ChatResponse)
async def chat_with_file(
    message: str = Form(""),
    session_id: str = Form("default"),
    file: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """文件对话接口（支持图片/PDF/Word/Excel/TXT）"""
    file_data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    # 图片走多模态路径
    if content_type.startswith("image/"):
        media_type = content_type
        result = await agent.chat(
            message=message or "请描述这张图片",
            session_id=session_id, db=db,
            image_data=file_data, image_media_type=media_type
        )
        return ChatResponse(content=result["content"], session_id=session_id)

    # 文档：提取文本注入上下文
    from app.services.file_parser_service import file_parser_service
    try:
        extracted_text = await file_parser_service.extract_text(
            file_data, filename, content_type
        )
    except ValueError:
        raise HTTPException(400, f"不支持的文件类型: {filename}")
    except Exception as e:
        raise HTTPException(400, f"文件解析失败: {str(e)}")

    if not extracted_text.strip():
        raise HTTPException(400, "未能从文件中提取到文本内容")

    # 截断过长文本
    if len(extracted_text) > 50000:
        extracted_text = extracted_text[:50000] + "\n... (内容过长，已截断)"

    # 上传到 MinIO 供后续查看
    file_url = None
    try:
        from app.services.file_service import file_service
        upload_result = await file_service.upload_file(
            file_data=file_data, filename=filename,
            content_type=content_type, prefix=f"chat/{session_id}"
        )
        file_url = upload_result.get("url")
    except Exception:
        pass  # 存储失败不影响对话

    # 构建含文件上下文的消息
    file_context = f"[文件: {filename}]\n{extracted_text}"
    if message:
        full_message = f"{file_context}\n\n用户问题: {message}"
    else:
        full_message = f"请分析以下文件内容:\n{file_context}"

    result = await agent.chat(
        message=full_message, session_id=session_id, db=db,
        user_id=current_user.id
    )
    return ChatResponse(
        content=result["content"],
        session_id=session_id,
        file_url=file_url,
        file_name=filename
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
    # 从 token 中获取用户 ID（用于记忆系统）
    token_user_id = payload.get("sub")
    try:
        token_user_id = int(token_user_id) if token_user_id else None
    except (ValueError, TypeError):
        token_user_id = None

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
                        db=db,
                        user_id=token_user_id
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
                            image_media_type=image_media_type,
                            user_id=token_user_id
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
