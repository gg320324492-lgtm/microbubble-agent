"""企业微信 Webhook 回调端点"""

import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.core.database import async_session
from app.wechat.crypto import WXBizMsgCrypt
from app.wechat.handler import message_handler

logger = logging.getLogger("microbubble.wechat.api")

router = APIRouter()


def _get_crypt() -> WXBizMsgCrypt:
    """获取加解密实例"""
    if not settings.WECHAT_CALLBACK_TOKEN or not settings.WECHAT_ENCODING_AES_KEY:
        raise HTTPException(status_code=500, detail="企业微信回调配置未设置")
    return WXBizMsgCrypt(
        token=settings.WECHAT_CALLBACK_TOKEN,
        encoding_aes_key=settings.WECHAT_ENCODING_AES_KEY,
        corp_id=settings.WECHAT_CORP_ID
    )


@router.get("/wechat/callback")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    """
    企业微信 URL 验证

    配置回调 URL 时，企业微信会发送 GET 请求验证服务器有效性。
    需要解密 echostr 并原样返回。
    """
    logger.info(f"收到 URL 验证请求: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")
    try:
        crypt = _get_crypt()
        echo = crypt.verify_url(msg_signature, timestamp, nonce, echostr)
        logger.info(f"URL 验证成功，返回 echostr")
        return PlainTextResponse(content=echo)
    except Exception as e:
        logger.error(f"URL 验证失败: {e}", exc_info=True)
        raise HTTPException(status_code=403, detail=f"验证失败: {str(e)}")


@router.post("/wechat/callback")
async def receive_message(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    request: Request = None
):
    """
    接收企业微信消息

    企业微信要求 5 秒内返回响应，否则会重试。
    策略：先返回 "success"，后台异步处理消息。
    """
    try:
        post_data = await request.body()
        post_data = post_data.decode("utf-8")

        crypt = _get_crypt()
        msg = crypt.decrypt_msg(post_data, msg_signature, timestamp, nonce)

        # 后台异步处理，不阻塞响应
        asyncio.create_task(_process_message(msg))

        return PlainTextResponse(content="success")

    except Exception as e:
        logger.error(f"处理企业微信消息失败: {e}", exc_info=True)
        return PlainTextResponse(content="success")


async def _process_message(msg: dict):
    """后台异步处理消息"""
    try:
        async with async_session() as db:
            await message_handler.handle_message(msg, db)
    except Exception as e:
        logger.error(f"异步处理消息失败: {e}", exc_info=True)


# ==================== 微信客服回调 ====================

@router.post("/wechat/kf/callback")
async def receive_kf_message(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    request: Request = None
):
    """
    接收微信客服消息

    微信客服的消息通过此回调推送到应用。
    """
    try:
        post_data = await request.body()
        post_data = post_data.decode("utf-8")

        crypt = _get_crypt()
        msg = crypt.decrypt_msg(post_data, msg_signature, timestamp, nonce)

        logger.info(f"收到微信客服消息: {msg}")

        # 后台异步处理
        asyncio.create_task(_process_kf_message(msg))

        return PlainTextResponse(content="success")

    except Exception as e:
        logger.error(f"处理微信客服消息失败: {e}", exc_info=True)
        return PlainTextResponse(content="success")


async def _process_kf_message(msg: dict):
    """后台异步处理微信客服消息"""
    try:
        async with async_session() as db:
            # 微信客服消息格式与普通消息不同，需要转换
            # msg 包含: MsgType, Content, FromUserName (external_userid), CreateTime 等
            await message_handler.handle_kf_message(msg, db)
    except Exception as e:
        logger.error(f"异步处理微信客服消息失败: {e}", exc_info=True)


@router.get("/wechat/kf/callback")
async def verify_kf_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    """微信客服回调 URL 验证"""
    logger.info(f"收到微信客服 URL 验证请求: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}, echostr={echostr[:20]}...")
    try:
        crypt = _get_crypt()
        # 计算期望的签名用于调试
        expected = crypt._sha1_sign(crypt.token, timestamp, nonce, echostr)
        logger.info(f"签名对比: 期望={expected}, 实际={msg_signature}, token={crypt.token[:6]}...")
        echo = crypt.verify_url(msg_signature, timestamp, nonce, echostr)
        logger.info(f"微信客服 URL 验证成功")
        return PlainTextResponse(content=echo)
    except Exception as e:
        logger.error(f"微信客服 URL 验证失败: {e}", exc_info=True)
        raise HTTPException(status_code=403, detail=f"验证失败: {str(e)}")
