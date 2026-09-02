"""Chat API 路由（v2 — 增强 SSE + Rich Blocks）

端点：
- POST /chat           非流式（兼容旧接口 + 扩展字段）
- POST /chat/image     多模态（图片对话）
- POST /chat/file      文档对话（PDF/Word/Excel/TXT）
- POST /chat/stream    新 — SSE 流式端点（前端主推）
- WS  /ws/chat/{user_id}  WebSocket（兼容旧）
- GET  /chat/history/{session_id}  会话历史（轮询用，向后兼容）

变化（v2 架构）：
- ChatResponse 新增 rich_blocks / tool_trace / usage / duration_ms
- /chat/stream 返回 text/event-stream，前端用 fetch + reader 接收
- WS 断连改为 mark_dirty（保留历史）
- chat 路由内部走 agent.micro_bubble_agent v2（与 v1 core 共存）
"""

import json
import logging
from typing import Any, AsyncIterator, Literal, Optional, List

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select  # #P5: 查 chat_session_attached_documents
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.micro_bubble_agent import agent as v2_agent
from app.agent.protocol import StreamEvent
from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.core.redis import session_store
from app.core.security import decode_token, get_current_user
from app.models.member import Member

logger = logging.getLogger("microbubble.api.chat")
router = APIRouter()


# ============================================================================
# Schema
# ============================================================================


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: str = "default"
    model: Optional[str] = None  # 覆盖 settings.AGENT_SYNTHESIS_MODEL
    # 2026-07-13 #P1 三档推理模式 (fast / balanced / deep), 前端 useChatStream 透传
    thinking_mode: Optional[Literal["fast", "balanced", "deep"]] = None  # None 走 settings.AGENT_THINKING_MODE_DEFAULT
    # 2026-08-15 #P4: 用户从知识库手动附加的文档 ID 列表
    # 附加后, 这些文档的完整内容会注入本轮对话的 system prompt 作为优先参考来源
    # 约束: 最多 8 个, 顺序保持, 后端静默跳过不存在/已删除的 ID (best-effort)
    attached_knowledge_ids: Optional[List[int]] = None
    # 2026-09-03 用户消息重复修复: 前端幂等键透传 (stream 持久化与
    # chat_history append 共用, 防止同一句用户消息落两行)
    client_msg_id: Optional[str] = None


class ChatResponse(BaseModel):
    """对话响应（v2 扩展 + 方案 C）

    字段说明：
    - content: 完整综合答案（方案 C 取消 brief/detail 双层，content 即最终答案）
    - is_brief: DEPRECATED 永远 False，仅保留为 v1 客户端兼容；v2+ 客户端请用 rich_blocks 判断
    - intent / critique: 方案 C Stage 2 新增，agent 自我意识元数据
    """
    content: str
    session_id: str
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    knowledge_content: Optional[str] = None
    is_brief: bool = False  # deprecated 永远 False（v1 客户端兼容）
    # === v2 新增字段 ===
    rich_blocks: list[dict[str, Any]] = []
    tool_trace: list[dict[str, Any]] = []
    usage: Optional[dict[str, int]] = None
    duration_ms: Optional[int] = None
    # === 2026-06-14 方案 C 新增 ===
    intent: Optional[dict[str, Any]] = None
    critique: Optional[dict[str, Any]] = None


# ============================================================================
# 端点：非流式 /chat
# ============================================================================


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """文字对话接口（v2）

    返回 v2 字段：rich_blocks（结构化富文本块）+ tool_trace（工具调用链）
    """
    # #P5: 自动从 DB 读用户全局附加文档 (与 /chat/stream 对齐)
    effective_attached_ids = request.attached_knowledge_ids
    if effective_attached_ids is None and current_user.id:
        from app.models.chat_session_attached_document import ChatSessionAttachedDocument
        stmt = (
            select(ChatSessionAttachedDocument.knowledge_id)
            .where(ChatSessionAttachedDocument.user_id == current_user.id)
            .limit(8)
        )
        effective_attached_ids = [r[0] for r in (await db.execute(stmt)).all()]

    result = await v2_agent.chat(
        message=request.message,
        session_id=request.session_id,
        db=db,
        user_id=current_user.id,
        model=request.model,
        # 2026-07-13 #P1 三档推理模式透传
        thinking_mode=request.thinking_mode,
        # #P5: 透传附加文档 → 屏蔽 RAG 工具
        attached_knowledge_ids=effective_attached_ids,
    )
    return ChatResponse(
        content=result["content"],
        session_id=request.session_id,
        is_brief=False,  # 2026-06-14 方案 C：永远 False（v1 客户端兼容）
        rich_blocks=result.get("rich_blocks", []),
        tool_trace=result.get("tool_trace", []),
        usage=result.get("usage"),
        duration_ms=result.get("duration_ms"),
        intent=result.get("intent"),
        critique=result.get("critique"),
    )


@router.post("/chat/image", response_model=ChatResponse)
async def chat_with_image(
    message: str = Form(...),
    session_id: str = Form("default"),
    image: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    # 2026-07-13 #P1 三档推理模式 (fast/balanced/deep)
    thinking_mode: Optional[str] = Form(None),
    # #P5: 用户从知识库附加的文档 ID 列表 (JSON 字符串, 逗号分隔)
    # Form 不支持 list[int], 用 str + 手动 split
    attached_knowledge_ids: Optional[str] = Form(None),
):
    """图片对话接口"""
    # #P5: 解析附加文档 ID (与 /chat/stream 自动从 DB 读对齐: 没传时查 DB)
    effective_attached_ids: Optional[List[int]] = None
    if attached_knowledge_ids is None or attached_knowledge_ids.strip() == "":
        from app.models.chat_session_attached_document import ChatSessionAttachedDocument
        stmt = (
            select(ChatSessionAttachedDocument.knowledge_id)
            .where(ChatSessionAttachedDocument.user_id == current_user.id)
            .limit(8)
        )
        effective_attached_ids = [r[0] for r in (await db.execute(stmt)).all()]
    else:
        # 解析 "12,47,89" → [12, 47, 89]
        try:
            effective_attached_ids = [int(x.strip()) for x in attached_knowledge_ids.split(",") if x.strip()]
        except (ValueError, TypeError):
            effective_attached_ids = None

    image_data = await image.read()
    content_type = image.content_type or "image/png"
    media_type_map = {
        "image/jpeg": "image/jpeg",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
        "image/png": "image/png",
    }
    media_type = media_type_map.get(content_type, "image/png")

    result = await v2_agent.chat(
        message=message,
        session_id=session_id,
        db=db,
        image_data=image_data,
        image_media_type=media_type,
        user_id=current_user.id,
        thinking_mode=thinking_mode,  # 2026-07-13 #P1 透传
        attached_knowledge_ids=effective_attached_ids,  # #P5 透传附加文档
    )
    return ChatResponse(
        content=result["content"],
        session_id=session_id,
        is_brief=True,
        rich_blocks=result.get("rich_blocks", []),
        tool_trace=result.get("tool_trace", []),
    )


@router.post("/chat/file", response_model=ChatResponse)
async def chat_with_file(
    message: str = Form(""),
    session_id: str = Form("default"),
    file: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    # 2026-07-13 #P1 三档推理模式
    thinking_mode: Optional[str] = Form(None),
    # #P5: 附加文档 ID (逗号分隔)
    attached_knowledge_ids: Optional[str] = Form(None),
):
    """文件对话接口（图片/PDF/Word/Excel/TXT）"""
    # #P5: 解析附加文档 ID
    effective_attached_ids: Optional[List[int]] = None
    if attached_knowledge_ids is None or attached_knowledge_ids.strip() == "":
        from app.models.chat_session_attached_document import ChatSessionAttachedDocument
        stmt = (
            select(ChatSessionAttachedDocument.knowledge_id)
            .where(ChatSessionAttachedDocument.user_id == current_user.id)
            .limit(8)
        )
        effective_attached_ids = [r[0] for r in (await db.execute(stmt)).all()]
    else:
        try:
            effective_attached_ids = [int(x.strip()) for x in attached_knowledge_ids.split(",") if x.strip()]
        except (ValueError, TypeError):
            effective_attached_ids = None

    file_data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    if content_type.startswith("image/"):
        media_type = content_type
        result = await v2_agent.chat(
            message=message or "请描述这张图片",
            session_id=session_id,
            db=db,
            image_data=file_data,
            image_media_type=media_type,
            user_id=current_user.id,
            thinking_mode=thinking_mode,  # 2026-07-13 #P1 透传
            attached_knowledge_ids=effective_attached_ids,  # #P5 透传
        )
        return ChatResponse(
            content=result["content"], session_id=session_id,
            rich_blocks=result.get("rich_blocks", []),
        )

    # 文档
    from app.services.file_parser_service import file_parser_service
    try:
        extracted_text = await file_parser_service.extract_text(
            file_data, filename, content_type
        )
    except ValueError:
        raise ValidationException(f"不支持的文件类型: {filename}")
    except Exception as e:
        raise ValidationException(f"文件解析失败: {str(e)}")

    if not extracted_text.strip():
        raise ValidationException("未能从文件中提取到文本内容")

    if len(extracted_text) > 50000:
        extracted_text = extracted_text[:50000] + "\n... (内容过长，已截断)"

    # MinIO 上传
    file_url = None
    try:
        from app.services.file_service import file_service
        upload_result = await file_service.upload_file(
            file_data=file_data, filename=filename,
            content_type=content_type, prefix=f"chat/{session_id}"
        )
        file_url = upload_result.get("url")
    except Exception:
        pass

    file_context = f"[文件: {filename}]\n{extracted_text}"
    if message:
        full_message = f"{file_context}\n\n用户问题: {message}"
    else:
        full_message = f"请分析以下文件内容:\n{file_context}"

    result = await v2_agent.chat(
        message=full_message, session_id=session_id, db=db,
        user_id=current_user.id,
        thinking_mode=thinking_mode,  # 2026-07-13 #P1 透传
        attached_knowledge_ids=effective_attached_ids,  # #P5 透传
    )
    return ChatResponse(
        content=result["content"],
        session_id=session_id,
        file_url=file_url,
        file_name=filename,
        knowledge_content=extracted_text,
        is_brief=True,
        rich_blocks=result.get("rich_blocks", []),
        tool_trace=result.get("tool_trace", []),
    )


# ============================================================================
# 端点：流式 /chat/stream (v2 新)
# ============================================================================


@router.post("/chat/stream")
async def chat_stream_route(
    request: ChatRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式对话端点

    客户端（前端 sse.ts）：
    ```js
    const res = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ message, session_id })
    })
    const reader = res.body.getReader()
    // ... 逐行解析 data: {...} ...
    ```

    事件类型（见 app/agent/protocol.py StreamEvent）：
    - thinking        "正在分析..."
    - tool_use        {tool_name, tool_input}
    - tool_result     {tool_output, tool_duration_ms}
    - rich_block      {block: {type, data, title}}
    - text_delta      {delta}
    - brief           {delta}  【简要】完整文本
    - detail          {delta}  【详细】完整文本
    - error           {code, message}
    - done            {usage, duration_ms, session_id}
    - message_persisted  [snapshot] #043 持久化成功（user 落库后 + assistant 落库后 各一次）
    - sync_required      [snapshot] 流式中断/异常，建议重新拉历史（reason: aborted|error）

    #043 持久化（2026-06-29）：
    - 入场时 user 消息落到 chat_messages 表（含 client_msg_id 幂等键）
    - 流结束时 assistant 消息落库（含完整 accumulated text + rich_blocks + tool_trace）
    - 中断（CancelledError）时已累积 assistant text 作为 is_partial=True 落库
    - 异常（非中断）时同样落 partial + yield sync_required

    # #P5 改进: attached_knowledge_ids 优先级:
    #   - 显式传 (request.attached_knowledge_ids 非 None) → 用显式的 (临时覆盖)
    #   - 没传 (None) → 自动从 chat_session_attached_documents 查用户全局附加
    # 这样前端不用每次发消息都传 ID, 用户全局附加的文档会自动注入
    """
    async def event_generator() -> AsyncIterator[str]:
        try:
            # #P5: 自动从 DB 读用户全局附加 (如果没显式传)
            effective_attached_ids = request.attached_knowledge_ids
            if effective_attached_ids is None:
                from app.models.chat_session_attached_document import ChatSessionAttachedDocument
                stmt = (
                    select(ChatSessionAttachedDocument.knowledge_id)
                    .where(ChatSessionAttachedDocument.user_id == current_user.id)
                    .limit(8)
                )
                effective_attached_ids = [r[0] for r in (await db.execute(stmt)).all()]

            async for event in v2_agent.chat_stream(
                message=request.message,
                session_id=request.session_id,
                db=db,
                user_id=current_user.id,
                model=request.model,
                # 2026-07-13 #P1 三档推理模式透传
                thinking_mode=request.thinking_mode,
                # #P5: 知识库手动附加文档 (显式传优先, 否则查用户全局)
                attached_knowledge_ids=effective_attached_ids,
                # 2026-09-03: 前端幂等键透传 (用户消息防双写)
                client_msg_id=request.client_msg_id,
            ):
                yield event.to_sse()
        except Exception as e:
            logger.error(f"SSE 流式异常: {e}", exc_info=True)
            err = StreamEvent(
                type="error",
                code="STREAM_ERROR",
                message=str(e),
            )
            yield err.to_sse()
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 不缓冲
        },
    )


# ============================================================================
# 端点：会话历史 / WebSocket（兼容旧）
# ============================================================================


@router.websocket("/ws/chat/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: str, token: str = ""):
    """WebSocket 实时对话（兼容旧接口）

    v2 行为：WS 断连时只 mark_dirty（不 clear_session）
    """
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
    token_user_id = payload.get("sub")
    try:
        token_user_id = int(token_user_id) if token_user_id else None
    except (ValueError, TypeError):
        token_user_id = None

    from app.core.database import async_session
    from app.agent.session_manager import session_manager

    async with async_session() as db:
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                message = message_data.get("content", "")
                msg_type = message_data.get("type", "text")

                if msg_type == "text":
                    result = await v2_agent.chat(
                        message=message, session_id=session_id,
                        db=db, user_id=token_user_id,
                    )
                    # v2 返回 rich_blocks 等，前端用 type=text 简单模式
                    await websocket.send_json({
                        "type": "text",
                        "content": result["content"],
                        # 同时带 rich_blocks 让前端可选渲染
                        "rich_blocks": result.get("rich_blocks", []),
                    })
                elif msg_type == "image":
                    import base64
                    image_b64 = message_data.get("image", "")
                    image_media_type = message_data.get("media_type", "image/png")
                    if image_b64:
                        image_data = base64.b64decode(image_b64)
                        result = await v2_agent.chat(
                            message=message, session_id=session_id, db=db,
                            image_data=image_data, image_media_type=image_media_type,
                            user_id=token_user_id,
                        )
                        await websocket.send_json({
                            "type": "text",
                            "content": result["content"],
                            "rich_blocks": result.get("rich_blocks", []),
                        })
                    else:
                        await websocket.send_json({"type": "error", "content": "图片数据为空"})
                elif msg_type == "voice":
                    await websocket.send_json({
                        "type": "text",
                        "content": "请通过语音输入区域发送语音消息，或直接输入文字。",
                    })
        except WebSocketDisconnect:
            # v2: 标 dirty 而非 clear_session（保留历史）
            await session_manager.mark_dirty(session_id, reason="ws_disconnect")


@router.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    after_index: int = 0,
    current_user: Member = Depends(get_current_user),
):
    """获取会话历史（轮询【详细】回复，向后兼容）"""
    messages = await session_store.get_messages(session_id)
    new_messages = messages[after_index:] if after_index < len(messages) else []
    return {"messages": new_messages, "total": len(messages)}
