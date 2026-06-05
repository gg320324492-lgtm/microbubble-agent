"""统一业务异常类层次"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    """业务异常基类"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundException(AppException):
    """资源不存在"""

    def __init__(self, resource: str, resource_id: Any = None):
        details = {}
        if resource_id is not None:
            details[f"{resource.lower()}_id"] = resource_id
        super().__init__(
            code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource}不存在",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationException(AppException):
    """数据验证失败"""

    def __init__(self, message: str, field: str = None):
        details = {}
        if field:
            details["field"] = field
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AuthException(AppException):
    """认证失败"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(
            code="AUTH_ERROR",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(AppException):
    """权限不足"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictException(AppException):
    """资源冲突"""

    def __init__(self, message: str, resource: str = None):
        details = {}
        if resource:
            details["resource"] = resource
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class RateLimitException(AppException):
    """请求过于频繁"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"请求过于频繁，请 {retry_after} 秒后重试",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """统一异常响应格式"""
    logger.warning(
        f"AppException: {exc.code} - {exc.message} | "
        f"path={request.url.path} method={request.method} details={exc.details}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "details": {},
            }
        },
    )
