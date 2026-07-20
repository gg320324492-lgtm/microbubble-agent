"""论文翻译 API (2026-07-20 实装)

端点:
  POST /api/v1/translation/translate
    body: { text: str, target_lang: str }
    response: { translated_text: str, target_lang: str, source_length: int }

复用:
  - app.services.translation_service.translate_text (LLMClient + Redis cache)
  - app.core.security.get_current_user (JWT 鉴权, 与 chat/task 对齐)

错误码:
  - 401: 未登录
  - 422: text 为空 / 超长 / target_lang 不在白名单
  - 500: LLM 服务异常 (兜底由 service 层处理, 此处不抛)
"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.services.translation_service import translate_text

logger = logging.getLogger("microbubble.api.translation")
router = APIRouter(prefix="/translation", tags=["翻译"])


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000, description="待翻译文本")
    target_lang: str = Field(..., min_length=2, max_length=10, description="目标语言代码 (en/zh/ja/...)")


class TranslateResponse(BaseModel):
    translated_text: str = Field(..., description="翻译结果")
    target_lang: str = Field(..., description="回显目标语言")
    source_length: int = Field(..., description="原文长度 (字符)")


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    body: TranslateRequest,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """翻译文本到目标语言

    - 支持 9 种语言: en / zh / zh-TW / ja / ko / fr / de / es / ru
    - 8000 字符硬上限 (超出返 422)
    - Redis 缓存 24h (同 text+lang 命中)
    - LLM 异常时兜底返原文 (前端不显示空白)
    """
    try:
        translated = await translate_text(body.text, body.target_lang)
    except ValueError as e:
        # 输入校验失败 → 422 (与 chat_service ValueError→422 范式一致)
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(e))

    return TranslateResponse(
        translated_text=translated,
        target_lang=body.target_lang.strip().lower(),
        source_length=len(body.text),
    )
