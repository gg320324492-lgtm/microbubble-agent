"""文件请求（外部收件）的**唯一一份**门禁判定 (2026-11-09)。

为什么单独成模块
----------------
同一个 FileRequest 有**两条写入路径**：

| 通路 | 入口 | 场景 |
|---|---|---|
| 单请求 multipart | `POST /api/v1/file-requests/{token}/submit` | 小文件，一次 POST |
| 匿名分片 | `POST /api/v1/file-requests/{token}/uploads/*` | 10GB 大文件 |

两条路都受同一组闸约束（单文件大小 / 累计总量 / 提交次数 / 链接是否开着）。
**各写一遍必然漂移** —— 本仓已有先例：2026-10-09 给质量门禁修 `ai_polish_skipped`
只补了原始流水线，重跑路径三个月后才暴露（类 20.250 ①，"「修好了」只对被改的那条
路径成立"）。所以闸判定、记账、有效期检查全部收在这一个模块里，两条路各自只剩
"调用它"这一件事。

错误类型选择
------------
`FileRequestGateError` **故意继承 ValueError**：单请求通路现有的 API 层写的是
`except ValueError → 422`，继承可以让老行为逐字不变；同时带上 `status_code`
供新通路映射成精确的 409/413/410/415。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.file_request_upload import FileRequestUpload
from app.models.knowledge import FileRequest


class FileRequestGateError(ValueError):
    """收件门禁拒绝。继承 ValueError ⇒ 老调用方的 except ValueError 仍然接得住。"""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def utcnow_naive() -> datetime:
    """naive UTC —— DB 列是 TIMESTAMP WITHOUT TIME ZONE。

    ⚠️ tz-aware 传进 asyncpg 的 naive 列会 DataError（类 20.251 ①，本仓已因此
    让一个后台任务静默失败一个月）；`datetime.now()` 则是本地 +0800，
    **不报错但差 8 小时**（类 20.221）。两种都是 bug，写法只认这一种。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def single_file_limit_bytes(req: Optional[FileRequest] = None) -> int:
    """单文件字节上限 = **三重取最小**，不信任任何单一来源。

    三个来源：网盘技术天花板 / 本功能的收件天花板 / 该请求自己声明的上限。
    只取其中一个会出问题：请求级字段可以被创建者写得比容器扛得住的大。
    """
    limits = [
        int(settings.DRIVE_MAX_FILE_SIZE_MB) * 1024 * 1024,
        int(settings.FILE_REQUEST_MAX_SINGLE_MB) * 1024 * 1024,
    ]
    if req is not None and req.max_file_size_mb:
        limits.append(int(req.max_file_size_mb) * 1024 * 1024)
    return max(1, min(limits))


def extension_of(filename: str) -> str:
    base = os.path.basename((filename or "").strip())
    return (base.rsplit(".", 1)[-1] or "").lower() if "." in base else ""


def check_extension(req: FileRequest, filename: str) -> None:
    """扩展名白名单。未配置 = 不限（保持既有语义）。"""
    if not req.allowed_extensions:
        return
    allowed = [str(e).lstrip(".").lower() for e in req.allowed_extensions if e]
    if not allowed:
        return
    ext = extension_of(filename)
    if ext not in allowed:
        raise FileRequestGateError(
            f"不允许的文件类型 .{ext or '(无扩展名)'}，仅支持 {', '.join(sorted(allowed))}",
            415,
        )


async def load_open_request(db: AsyncSession, token: str) -> FileRequest:
    """取请求并校验它还开着 —— **两条通路共用**，不要各自查一遍。"""
    req = (
        await db.execute(select(FileRequest).where(FileRequest.token == token))
    ).scalar_one_or_none()
    if not req:
        raise FileRequestGateError("文件请求不存在", 404)
    if not req.is_active:
        raise FileRequestGateError("这个收件链接已关闭，请联系发起人重新开启", 410)
    if req.expires_at and req.expires_at < utcnow_naive():
        raise FileRequestGateError("这个收件链接已过期", 410)
    return req


async def check_gates(
    db: AsyncSession,
    req: FileRequest,
    *,
    incoming_bytes: int,
    count_active_sessions: bool = False,
) -> None:
    """提交次数 / 累计总量 / (分片通路) 活跃会话数 三道闸。

    Args:
        count_active_sessions: 分片通路传 True。
            ⚠️ 这条专门堵 DoS：`init` 本身不花钱，只限 submission_count 的话，
            任何人都能反复 init 把 staging 前缀灌满 —— 老行为里就没有这道闸，
            因为老通路根本没有"会话"这个概念。
    """
    max_sub = getattr(req, "max_submissions", None)
    if max_sub is not None:
        if int(req.submission_count or 0) >= int(max_sub):
            raise FileRequestGateError(
                f"该收件链接已收满 {max_sub} 个文件", 409
            )
        if count_active_sessions:
            active = (
                await db.execute(
                    select(func.count(FileRequestUpload.id)).where(
                        and_(
                            FileRequestUpload.request_id == req.id,
                            FileRequestUpload.status.in_(("pending", "uploading")),
                            FileRequestUpload.expires_at > utcnow_naive(),
                        )
                    )
                )
            ).scalar_one()
            # 2026-11-10 多件上传: 活跃会话数必须跟**剩余配额**比, 不是跟总上限比。
            # 旧写法 `active >= max_sub` 在已收过几件后**太松**: max_sub=5 已收 2 件、
            # active=3 时仍放行新 init ⇒ 已收 2 + 进行中 4 = 6 件, 越过总配额。
            # 本次新 init 会让进行中变成 active+1, 故判据是 active >= remain
            # (前面的 submission_count >= max_sub 已先抛错, 故 remain >= 1)。
            # ⚠️ 此闸只挡"已存在多个进行中会话"(浏览器并发/多窗口), 本次 init
            #    自己的会话尚未落库; 超额边界由前面的 submission_count 与累计总量闸把守。
            # 串行队列同一时刻通常只有 1 个 active; 两个窗口并发时才按剩余配额收紧。
            remain = int(max_sub) - int(req.submission_count or 0)
            if int(active) >= max(1, remain):
                raise FileRequestGateError(
                    "该链接的进行中上传数已达上限，请等待当前上传完成或过期", 409
                )

    max_total = getattr(req, "max_total_bytes", None)
    if max_total is not None:
        used = int(req.used_bytes or 0)
        limit = int(max_total)
        if used + int(incoming_bytes) > limit:
            raise FileRequestGateError(
                f"本次收件已达总量上限：已用 {used // 1024 // 1024} MB"
                f" + 本次 {int(incoming_bytes) // 1024 // 1024} MB"
                f" > 上限 {limit // 1024 // 1024} MB",
                413,
            )


def apply_accounting(req: FileRequest, size_bytes: int) -> bool:
    """落地成功后的记账 —— **两条通路共用**（原先只有单请求通路 +1，
    既没有 used_bytes 也不会自动关闭）。

    Returns:
        链接是否因此被关闭。
    """
    req.used_bytes = int(req.used_bytes or 0) + int(size_bytes)
    req.submission_count = int(req.submission_count or 0) + 1
    closed = False
    max_sub = getattr(req, "max_submissions", None)
    if (
        max_sub is not None
        and bool(getattr(req, "auto_close_on_limit", True))
        and int(req.submission_count) >= int(max_sub)
    ):
        req.is_active = False
        closed = True
    return closed


def public_shape(req: FileRequest) -> dict:
    """公开信息端点要回给匿名者的门禁摘要（不含 token 之外的敏感字段）。"""
    return {
        "max_single_file_mb": single_file_limit_bytes(req) // 1024 // 1024,
        "max_submissions": getattr(req, "max_submissions", None),
        "max_total_mb": (
            int(req.max_total_bytes) // 1024 // 1024
            if getattr(req, "max_total_bytes", None) else None
        ),
        "used_mb": int(req.used_bytes or 0) // 1024 // 1024,
        "auto_close_on_limit": bool(getattr(req, "auto_close_on_limit", True)),
        "chunked_supported": True,
        "max_chunk_mb": int(settings.FILE_REQUEST_MAX_CHUNK_MB),
    }


def parse_extensions(raw: Optional[str]) -> List[str]:
    """把 settings.FILE_REQUEST_VIDEO_EXTS 这类逗号串解析成白名单列表。"""
    if not raw:
        return []
    return sorted({
        e.strip().lower().lstrip(".") for e in raw.split(",") if e.strip()
    })
