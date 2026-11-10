"""file_requests REST API (PR7 + 2026-11-09 大文件分片收件)

登录端点:
  POST   /api/v1/file-requests                           创建文件请求
  GET    /api/v1/file-requests/my                       我创建的请求列表
  POST   /api/v1/file-requests/{id}/deactivate          关闭请求 (owner only)

匿名端点 (**无 JWT**, 仅凭 32 字符 token):
  GET    /api/v1/file-requests/{token}/info                 公开信息 (含门禁摘要)
  POST   /api/v1/file-requests/{token}/submit               单请求上传 (小文件)
  POST   /api/v1/file-requests/{token}/uploads                    分片会话 init
  GET    /api/v1/file-requests/{token}/uploads/{upload_id}        断点续传进度
  PUT    /api/v1/file-requests/{token}/uploads/{upload_id}/chunks/{index}  传一片
  POST   /api/v1/file-requests/{token}/uploads/{upload_id}/complete        服务端合并
  POST   /api/v1/file-requests/{token}/uploads/{upload_id}/abort           放弃

为什么匿名通路要再开一套分片: 10GB 单请求过不去 —— 也**不需要**动云端 nginx
(分片每片 ≤32 MiB, 远低于 nginx 的 1024m)。详见 file_request_upload_service 模块头。

错误统一响应:
  404 token / 会话不存在
  409 已收满 (次数或活跃会话达上限) / 片未传齐
  410 inactive / expired / 会话已中止或过期
  413 单文件或累计总量超上限
  415 扩展名不允许
  422 字段缺失
  500 合并/校验失败 (已自动丢弃残缺对象)
"""
import logging
import re
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.models.file_request_upload import FileRequestUpload
from app.models.knowledge import FileRequest, Knowledge
from app.models.member import Member
from app.services import file_request_gates as gates
from app.services.file_request_service import file_request_service
from app.services.file_request_upload_service import (
    FileRequestUploadError,
    file_request_upload_service,
)

logger = logging.getLogger("microbubble.file_requests_api")
router = APIRouter(prefix="/file-requests", tags=["文件请求"])


# === Schemas ===

class CreateFileRequestBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    target_folder_id: Optional[int] = None
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    # 小时粒度 (2026-11-09): 一次外部收件用"天"太粗; 给了就优先于 expires_in_days
    expires_in_hours: Optional[int] = Field(None, ge=1, le=8760)
    allowed_extensions: Optional[List[str]] = None
    require_uploader_name: bool = True
    # 上限从写死 500 MB 抬到 settings.FILE_REQUEST_MAX_SINGLE_MB (默认 20 GiB),
    # 否则 10GB 级收件连"创建请求"这一步都过不去
    max_file_size_mb: Optional[int] = Field(
        None, ge=1, le=int(settings.FILE_REQUEST_MAX_SINGLE_MB)
    )
    # ── 安全闸 (None = 用严格档默认; 0 = 显式不限) ──
    max_submissions: Optional[int] = Field(None, ge=0, le=100000)
    max_total_mb: Optional[int] = Field(None, ge=0, le=10_485_760)  # ≤10 TiB
    auto_close_on_limit: Optional[bool] = None
    # 便利开关: 只想收视频时置 True ⇒ 自动套用 settings 的视频白名单
    video_only: bool = False


# === 登录端点 ===

@router.post("", status_code=201)
async def create_request(
    body: CreateFileRequestBody,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """创建文件请求

    返回含 token (公开 URL 用)
    """
    allowed = body.allowed_extensions
    if body.video_only and not allowed:
        allowed = gates.parse_extensions(settings.FILE_REQUEST_VIDEO_EXTS)

    try:
        req = await file_request_service.create_request(
            db,
            created_by=user.id,
            title=body.title,
            description=body.description,
            target_folder_id=body.target_folder_id,
            expires_in_days=body.expires_in_days,
            expires_in_hours=body.expires_in_hours,
            allowed_extensions=allowed,
            require_uploader_name=body.require_uploader_name,
            max_file_size_mb=body.max_file_size_mb,
            max_submissions=body.max_submissions,
            max_total_mb=body.max_total_mb,
            auto_close_on_limit=body.auto_close_on_limit,
        )
    except gates.FileRequestGateError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "id": req.id,
        "token": req.token,
        "title": req.title,
        "description": req.description,
        "target_folder_id": req.target_folder_id,
        "expires_at": req.expires_at.isoformat() if req.expires_at else None,
        "allowed_extensions": req.allowed_extensions or [],
        "require_uploader_name": req.require_uploader_name,
        "max_file_size_mb": req.max_file_size_mb,
        "submission_count": req.submission_count,
        "is_active": req.is_active,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        # 门禁实际生效值 (可能是严格档默认, 不是请求里传的那个) ——
        # 前端要展示"这个链接最多收多少", 不能显示用户填的数
        **gates.public_shape(req),
    }


@router.get("/{request_id}/files")
async def list_request_files(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """文件请求详情: 已收到的文件 + 正在上传的会话 (带实时进度百分比)

    仅创建者可查看 (匿名 token 不暴露这个列表 —— 那是收件方的私有视图)。

    uploading 里的 percent 是**分片计数**口径 (len(uploaded_chunks)/total_chunks),
    与公开提交页给上传者看的是同一个进度来源; 它不代表字节进度误差 (片等长,
    只有末片短, 差异 ≤ 1 片)。
    """
    req = (
        await db.execute(select(FileRequest).where(FileRequest.id == request_id))
    ).scalar_one_or_none()
    if not req or req.created_by != user.id:
        raise HTTPException(status_code=404, detail="文件请求不存在")

    rows = (
        await db.execute(
            select(Knowledge)
            .where(
                Knowledge.file_request_id == request_id,
                Knowledge.deleted_at.is_(None),
            )
            .order_by(desc(Knowledge.created_at))
            .limit(500)
        )
    ).scalars().all()

    # uploader_name: 分片通路有会话表可 join; 单请求通路只写在 content 标记里
    # (`[file_request] token=... uploader=张三`), 这里用同一正则兜底解析。
    upload_names = {}
    try:
        done_uploads = (
            await db.execute(
                select(FileRequestUpload).where(
                    FileRequestUpload.request_id == request_id,
                    FileRequestUpload.knowledge_id.isnot(None),
                )
            )
        ).scalars().all()
        upload_names = {
            u.knowledge_id: u.uploader_name for u in done_uploads if u.knowledge_id
        }
    except Exception:
        # 会话表问题不该拖垮"看已收文件"这个主视图
        logger.warning("[file_requests] 读 uploader_name 失败, 退回 content 解析", exc_info=True)

    files = []
    for k in rows:
        uploader = upload_names.get(k.id)
        if not uploader:
            m = re.search(r"uploader=([^\s]+)", k.content or "")
            uploader = m.group(1) if m else None
        files.append({
            "id": k.id,
            "title": k.title,
            "file_name": k.file_name,
            "file_size": int(k.file_size or 0),
            "file_type": k.file_type,
            "file_hash": k.file_hash,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            # DriveFileTable 的"上传者"列读 owner_name/owner_username
            "owner_name": uploader,
            "owner_username": uploader,
            "storage_mode": k.storage_mode,
            "folder_id": k.folder_id,
        })

    active = (
        await db.execute(
            select(FileRequestUpload)
            .where(
                FileRequestUpload.request_id == request_id,
                FileRequestUpload.status.in_(("pending", "uploading")),
                FileRequestUpload.expires_at > gates.utcnow_naive(),
            )
            .order_by(desc(FileRequestUpload.created_at))
        )
    ).scalars().all()

    uploading = []
    for u in active:
        total = int(u.total_chunks or 0)
        done = len(u.uploaded_chunks or [])
        uploading.append({
            "upload_id": u.upload_id,
            "filename": u.filename,
            "file_size": int(u.file_size or 0),
            "uploader_name": u.uploader_name,
            "uploaded_chunks": done,
            "total_chunks": total,
            "percent": (round(done * 100.0 / total, 1) if total else 0.0),
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "expires_at": u.expires_at.isoformat() if u.expires_at else None,
        })

    return {
        "request": {
            "id": req.id,
            "title": req.title,
            "submission_count": req.submission_count,
            "is_active": req.is_active,
        },
        "files": files,
        "uploading": uploading,
    }


@router.get("/my")
async def list_my_requests(
    include_inactive: bool = Query(False),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """我创建的文件请求列表"""
    items = await file_request_service.list_my_requests(
        db,
        created_by=user.id,
        include_inactive=include_inactive,
        limit=limit,
    )
    return {"items": items, "total": len(items)}


@router.post("/{request_id}/deactivate", status_code=204)
async def deactivate_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """关闭文件请求 (创建者 only)"""
    ok = await file_request_service.deactivate(
        db, request_id=request_id, user_id=user.id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="不存在或越权")


# === 公开端点 (无需登录) ===

@router.get("/{token}/info")
async def get_public_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """公开查文件请求信息 (无需登录)

    404: token 不存在
    """
    info = await file_request_service.get_by_token(db, token=token)
    if not info:
        raise HTTPException(status_code=404, detail="文件请求不存在")
    return info


@router.post("/{token}/submit", status_code=201)
async def submit_file_public(
    token: str,
    uploader_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """公开提交文件 (无需登录, multipart)

    表单字段:
      file: 文件二进制
      uploader_name: 上传者姓名 (require_uploader_name=False 时可选)

    ⚠️ 本通路把请求体整份 read() 进内存 ⇒ **只适合小文件**。
    大文件（GB 级）必须走下面的 `/uploads` 分片通路。

    错误码:
      404: token 不存在
      409: 已收满
      410: inactive 或 expired
      413: 单文件或累计总量超上限
      415: 扩展名不允许
      422: 字段缺失 / 其他业务错误
    """
    # 读文件内容 (UploadFile 必须 await read())
    content = await file.read()
    file_size = len(content)
    file_name = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"

    try:
        result = await file_request_service.submit_file(
            db,
            token=token,
            uploader_name=uploader_name,
            file_content=content,
            file_name=file_name,
            content_type=content_type,
            file_size=file_size,
        )
    except gates.FileRequestGateError as e:
        # 2026-11-09: 原先靠**在中文错误串里找关键字**分状态码 ("不存在"/"关闭"),
        # 新增的 409/413/415 三类会被全部误判成 422 —— 闸改了语义、码却不动，
        # 前端就分不清"链接过期"和"已经收满了"。改为直接读异常带的 code。
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except ValueError as e:
        err = str(e)
        # 区分 404 / 410 / 422
        if "不存在" in err:
            raise HTTPException(status_code=404, detail=err)
        if "关闭" in err or "过期" in err:
            raise HTTPException(status_code=410, detail=err)
        raise HTTPException(status_code=422, detail=err)

    return result


# ============================================================================
# 匿名分片上传 (2026-11-09, 10GB 级外部收件)
#
# 五个端点全部**只依赖 get_db**（无 JWT）—— 与既有 submit/info 同一口径, 这是
# FileRequest 的设计初衷: 外部人员没有账号。安全靠 token 不可枚举 + 上面的三道闸,
# 审计靠 audit_middleware 落 user_id=NULL + IP + UA。
#
# ⚠️ 限流档位: 这些路径都以 /api/v1/file-requests 开头 ⇒ 落 `write` tier
#    (30 次/分钟/IP)。10 GiB / 32 MiB = 320 片，同一 IP 连续 PUT 会被 429 掐住
#    —— 分片必须**限速**(前端串行/低并发) 或给它单独一档。见下面的说明。
# ============================================================================

@router.post("/{token}/uploads", status_code=201)
async def init_chunked_upload(
    token: str,
    filename: str = Form(...),
    file_size: int = Form(...),
    chunk_size: Optional[int] = Form(None),
    uploader_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """发起一次匿名分片上传 (无需登录)

    返回 upload_id + 服务端定的 chunk_size + 总片数。
    chunk_size 不传则服务端按文件大小自动选（大文件用满 32 MiB 上限，
    既压请求数、又仍远低于云端 nginx 的 1024m 单请求上限）。
    """
    try:
        return await file_request_upload_service.init_upload(
            db,
            token=token,
            filename=filename,
            file_size=file_size,
            chunk_size=chunk_size,
            uploader_name=uploader_name,
        )
    except FileRequestUploadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{token}/uploads/{upload_id}")
async def get_chunked_upload_status(
    token: str,
    upload_id: str,
    db: AsyncSession = Depends(get_db),
):
    """查询分片会话进度 (无需登录) —— 断点续传靠它拿到 missing_chunks"""
    try:
        return await file_request_upload_service.get_status(
            db, token=token, upload_id=upload_id
        )
    except FileRequestUploadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/{token}/uploads/{upload_id}/chunks/{index}")
async def put_chunk(
    token: str,
    upload_id: str,
    index: int,
    chunk: UploadFile = File(...),
    chunk_sha256: Optional[str] = Header(
        None, alias="X-Chunk-SHA256",
        description="本片字节的 SHA256 hex；传了就必须一致（写入即校验）",
    ),
    db: AsyncSession = Depends(get_db),
):
    """上传第 index 片 (无需登录)

    单片 ≤32 MiB ⇒ 远低于云端 nginx 的 client_max_body_size 1024m,
    **所以本通路不需要动 nginx 配置**。

    ⚠️ 非末片长度必须恰好等于 chunk_size —— 否则拼接位置会错。
    ⚠️ X-Chunk-SHA256 是"画质无损"最硬的一环: 客户端算、服务端实测比对,
       不一致直接 422 拒绝这一片, 而不是等合并完才发现坏。
    """
    data = await chunk.read()
    try:
        return await file_request_upload_service.put_chunk(
            db,
            token=token,
            upload_id=upload_id,
            index=index,
            data=data,
            expected_sha256=chunk_sha256,
        )
    except FileRequestUploadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{token}/uploads/{upload_id}/complete")
async def complete_chunked_upload(
    token: str,
    upload_id: str,
    checksum: Optional[str] = Form(
        None, description="整文件 SHA256 hex (可选)；传了就与服务端实算值比对"
    ),
    db: AsyncSession = Depends(get_db),
):
    """完成: MinIO **服务端**拼接 → 长度对账 → 流式实算 SHA256 → 落 drive 行

    合并全程不进 Python 内存 (app 容器 mem_limit=8g 扛不住 10 GiB 缓冲,
    这正是 drive 常规分片通路传不动 10GB 的真因)。

    任何一步校验不过 ⇒ 已合并的对象会被**立即删除**, 不会留下
    "元数据没建但对象躺在盘上"的孤儿。
    """
    try:
        return await file_request_upload_service.complete_upload(
            db, token=token, upload_id=upload_id, checksum=checksum
        )
    except FileRequestUploadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{token}/uploads/{upload_id}/abort")
async def abort_chunked_upload(
    token: str,
    upload_id: str,
    db: AsyncSession = Depends(get_db),
):
    """放弃会话并清 staging 对象 (无需登录)"""
    try:
        return await file_request_upload_service.abort_upload(
            db, token=token, upload_id=upload_id
        )
    except FileRequestUploadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
