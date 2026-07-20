"""Drive API 统一错误抛出 helper

## 背景 (2026-07-20 W1 T1 audit)

`app/api/v1/drive_folders.py:_reraise_folder_service_error` 是 folder delete 修复范式
(memory/drive-folder-404-wrap-api-error-2026-07-10.md): FolderServiceError → AppException 子类 →
统一 envelope `{"error": {"code", "message", "details"}}`.

审计发现 `app/api/v1/drive_files.py` 仍有 60+ 处 `raise HTTPException(status_code=..., detail=str(e))`,
走 FastAPI 默认 `{"detail": "..."}` envelope → 前端 `useDriveFiles.js` 必须双 fallback:

    e.response?.data?.error?.message || e.response?.data?.detail || '...'

虽然 fallback 已工作,但前后端契约混乱。本 helper 提供统一 API,让**新 endpoint 必须走统一格式**,
旧 endpoint 暂保留(避免一次性 break 现有前端契约)。

## 使用

```python
from app.api.v1._drive_error_helper import raise_app_error

@router.post("/files/{file_id}/xxx")
async def xxx(file_id: int, current_user: Member = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    f = await DriveService.get_file(db, file_id, owner_id=current_user.id)
    if f is None:
        raise_app_error(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在或非 owner", file_id=file_id)
    ...
```

注册: main.py:126 已注册 AppException handler → 全局统一 envelope 自动生效。

## 5 条铁律 (W1 T1 audit 沉淀)

1. **新 endpoint 必须用 raise_app_error 或 AppException 子类, 不准 raise HTTPException**
   (避免新增一处 fastapi 默认 envelope, 收紧契约统一性)
2. **status_code + code + message 三件套必备**, details 可选 (默认 {})
3. **code 用 SCREAMING_SNAKE_CASE 命名空间** (FILE_NOT_FOUND, FOLDER_FORBIDDEN, ...)
   (与现有 NotFoundException.code 风格一致: `<RESOURCE>_NOT_FOUND`)
4. **不允许 raise HTTPException(detail=...)** — 必须 raise AppException 子类
   (反例: HTTPException 走 `{"detail": "..."}` envelope, 双 fallback 是契约债)
5. **不批量改造旧 endpoint** — 60+ 处改造风险大, 旧契约前端已适配 (双 fallback)
   改单一 endpoint 必须先确认前端是否已迁移到 `.error.message`
"""
from typing import Any, Optional

from app.core.exceptions import AppException


def raise_app_error(
    status_code: int,
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
    **extra_details: Any,
) -> None:
    """统一 Drive API 错误抛出 helper.

    与 folder delete 修复范式一致: AppException 子类 → main.py app_exception_handler
    → `{"error": {"code", "message", "details"}}` envelope.

    Args:
        status_code: HTTP status code (404 / 403 / 400 / 409 / ...)
        code: SCREAMING_SNAKE_CASE 错误码 (e.g. FILE_NOT_FOUND, FOLDER_FORBIDDEN)
        message: 用户可读的错误消息
        details: 额外上下文字典 (e.g. {"file_id": 5}), 默认 {}
        **extra_details: 便捷 kwargs, 自动合并到 details (e.g. file_id=5 → details={"file_id": 5})

    Raises:
        AppException: 全局 handler 自动转 envelope

    Examples:
        >>> raise_app_error(404, "FILE_NOT_FOUND", "文件 5 不存在", file_id=5)
        >>> raise_app_error(403, "FILE_FORBIDDEN", "无权修改该私有文件", file_id=5)
        >>> raise_app_error(409, "FILE_CONFLICT", "filename 已存在", filename="x.pdf")
    """
    merged_details: dict[str, Any] = dict(details or {})
    merged_details.update(extra_details)
    raise AppException(
        code=code,
        message=message,
        status_code=status_code,
        details=merged_details,
    )


# ============================================================================
# 常用错误码常量 (避免散落字符串)
# ============================================================================

# 资源不存在类 (404)
ERR_FILE_NOT_FOUND = "FILE_NOT_FOUND"
ERR_FOLDER_NOT_FOUND = "FOLDER_NOT_FOUND"
ERR_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"

# 权限不足类 (403)
ERR_FILE_FORBIDDEN = "FILE_FORBIDDEN"
ERR_FOLDER_FORBIDDEN = "FOLDER_FORBIDDEN"

# 数据验证类 (400 / 422)
ERR_INVALID_VISIBILITY = "INVALID_VISIBILITY"
ERR_INVALID_FILE_SIZE = "INVALID_FILE_SIZE"
ERR_FILE_EMPTY = "FILE_EMPTY"
ERR_BATCH_PARAM_MISSING = "BATCH_PARAM_MISSING"

# 分享链接类 (404 / 403)
ERR_SHARE_LINK_NOT_FOUND = "SHARE_LINK_NOT_FOUND"
ERR_SHARE_LINK_EXPIRED = "SHARE_LINK_EXPIRED"
ERR_SHARE_LINK_PASSWORD = "SHARE_LINK_PASSWORD_INVALID"