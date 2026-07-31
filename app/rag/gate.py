"""app/rag/gate.py — 框架门控回退装饰器

每个框架能力调用包装在 try-except 中, 失败时自动回退到 Layer 1 手写实现。
"""

import functools
import logging

logger = logging.getLogger("microbubble.rag.framework_gate")


def framework_gate(feature_flag: bool, fallback_fn=None):
    """框架门控装饰器 — 开关关闭或异常时自动回退"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not feature_flag:
                # 开关关闭: 直接走回退
                if fallback_fn:
                    return await fallback_fn(*args, **kwargs)
                return None
            try:
                return await func(*args, **kwargs)
            except ImportError as e:
                logger.warning(f"Framework dependency not installed for {func.__name__}: {e}")
            except Exception as e:
                logger.error(f"Framework {func.__name__} failed, degrading: {e}", exc_info=True)
            # 回退
            if fallback_fn:
                return await fallback_fn(*args, **kwargs)
            return None
        return wrapper
    return decorator
