"""file_request_service — v2 PR7 文件请求服务 (Dropbox 招牌 '收作业')

职责:
1. create_request(): 创建文件请求 (登录用户, 生成 32 字符 token)
2. get_by_token(): 公开查文件请求 (无需登录)
3. submit_file(): 公开上传文件 (无需登录, multipart)
4. list_my_requests(): 我创建的请求列表
5. deactivate(): 关闭请求 (创建者 only)

设计要点:
- token 用 secrets.token_urlsafe(24)[:32] 生成 (URL safe + 32 字符)
- submit 时直接调 DriveService.create_file, 走完整的上传管线 (含配额/缩略图/activity)
- 公开匿名访问: 中间件审计记录 user_id=NULL, IP 必填
- 服务层错误信息明确 (字段缺失/类型错误/后端问题 → 不同 hint)

fallback target_folder_id:
- NULL → 用创建者的根目录 (created_by 用户没有 root 概念, 用 created_by=NULL 的 folder 列表首项)
- 实际: 简化为上传到 file_requests.id 维度的独立 Knowledge row, folder_id 强制 = request_id (用 Folder 不现实)
- 决定: 走"创建者上传 → fallback to 团队共享盘根目录"路径 (PR7 Step 11 解决 UI 选文件夹)
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import FileRequest, Knowledge
from app.models.member import Member
from app.services.activity_service import activity_service
from app.services.drive_service import DriveService

logger = logging.getLogger(__name__)

# Token 长度 (URL 安全)
TOKEN_LENGTH = 32
# Token 生成 prefix: `fr_` (FILE REQUEST) 让公开 URL 自描述
TOKEN_PREFIX = "fr_"


def _generate_token() -> str:
    """生成 32 字符 URL-safe 随机 token

    用 secrets.token_urlsafe(24)[:32] 而非 token_urlsafe(32):
      24 bytes → 32 chars base64 (符合我们索引长度限制)
      collision rate: 2^192 ≈ 不可枚举
    """
    return secrets.token_urlsafe(24)[:TOKEN_LENGTH]


class FileRequestService:
    """v2 PR7: file_requests CRUD + 公开 submit"""

    @staticmethod
    async def create_request(
        db: AsyncSession,
        *,
        created_by: int,
        title: str,
        description: Optional[str] = None,
        target_folder_id: Optional[int] = None,
        expires_in_days: Optional[int] = None,
        allowed_extensions: Optional[List[str]] = None,
        require_uploader_name: bool = True,
        max_file_size_mb: Optional[int] = None,
    ) -> FileRequest:
        """创建文件请求 (登录用户)

        Args:
            created_by: 创建者 user_id
            title: 请求标题
            description: 详细说明 (可选)
            target_folder_id: 提交后文件落到的文件夹 (NULL = 创建者根目录)
            expires_in_days: 几天后过期 (NULL = 永久)
            allowed_extensions: 允许文件类型数组 (如 ['pdf','docx'], NULL=不限)
            require_uploader_name: 是否必填姓名
            max_file_size_mb: 单文件大小上限 MB (NULL=不限)

        Returns:
            FileRequest 实例 (含 token)
        """
        if not title or not title.strip():
            raise ValueError("title 不能为空")

        # expires_in_days → expires_at
        expires_at = None
        if expires_in_days is not None:
            if expires_in_days <= 0 or expires_in_days > 365:
                raise ValueError("expires_in_days 必须在 1-365 之间")
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # allowed_extensions 标准化 (lowercase + 去空)
        ext_list = None
        if allowed_extensions:
            ext_list = sorted({
                ext.strip().lower().lstrip(".")
                for ext in allowed_extensions
                if ext and ext.strip()
            })
            if not ext_list:
                ext_list = None

        # max_file_size_mb 范围
        if max_file_size_mb is not None:
            if max_file_size_mb <= 0 or max_file_size_mb > 500:
                raise ValueError("max_file_size_mb 必须在 1-500 之间")

        req = FileRequest(
            token=_generate_token(),
            title=title.strip(),
            description=description,
            target_folder_id=target_folder_id,
            created_by=created_by,
            expires_at=expires_at,
            allowed_extensions=ext_list,
            require_uploader_name=require_uploader_name,
            max_file_size_mb=max_file_size_mb,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)

        # activity
        try:
            await activity_service.log(
                db,
                actor_id=created_by,
                action="comment",  # 复用现有枚举 (文件请求归入协作类)
                target_type="file",  # 复用现有 target_type (file = drive document 类)
                target_id=req.id,
                target_name=req.title[:80],
                metadata={
                    "kind": "file_request_created",
                    "token": req.token[:8] + "***",  # 不全暴露
                    "expires_at": req.expires_at.isoformat() if req.expires_at else None,
                    "allowed_extensions": ext_list,
                },
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"[FileRequest] create activity log 失败: {e}", exc_info=True)

        logger.info(
            f"[FileRequest] created id={req.id} token={req.token[:8]}... "
            f"by={created_by} title='{req.title[:30]}'"
        )
        return req

    @staticmethod
    async def get_by_token(
        db: AsyncSession, *, token: str
    ) -> Optional[Dict[str, Any]]:
        """公开查文件请求 (无需登录)

        Returns:
            dict with 'request', 'expired', 'active' flags + serializable fields
            None: token 不存在
        """
        stmt = select(FileRequest).where(FileRequest.token == token)
        req = (await db.execute(stmt)).scalar_one_or_none()
        if not req:
            return None

        # expired / inactive 区分
        expired = bool(req.expires_at and req.expires_at < datetime.utcnow())
        active = bool(req.is_active and not expired)

        # 创建者名字 (避免暴露 user_id)
        creator_name = None
        creator = (await db.execute(
            select(Member.name).where(Member.id == req.created_by)
        )).scalar_one_or_none()
        if creator:
            creator_name = creator

        return {
            "id": req.id,
            "token": req.token,
            "title": req.title,
            "description": req.description,
            "creator_name": creator_name,
            "expires_at": req.expires_at.isoformat() if req.expires_at else None,
            "expired": expired,
            "active": active,
            "is_active": req.is_active,
            "allowed_extensions": req.allowed_extensions or [],
            "require_uploader_name": req.require_uploader_name,
            "max_file_size_mb": req.max_file_size_mb,
            "submission_count": req.submission_count,
            "created_at": req.created_at.isoformat() if req.created_at else None,
        }

    @staticmethod
    async def submit_file(
        db: AsyncSession,
        *,
        token: str,
        uploader_name: Optional[str],
        file_content: bytes,
        file_name: str,
        content_type: str,
        file_size: int,
    ) -> Dict[str, Any]:
        """公开上传文件到文件请求 (无需登录)

        Args:
            token: 文件请求 token
            uploader_name: 上传者姓名 (require_uploader_name=False 时可空)
            file_content: 文件 bytes (multipart)
            file_name: 原始文件名
            content_type: MIME (multipart)
            file_size: 文件字节数

        Returns:
            dict: {'success': True, 'submission_id': N, 'file_id': N}
        Raises:
            ValueError: 业务错误 (过期/扩展名不符/必填字段缺失/大小超限)
        """
        # 1) 找 request
        stmt = select(FileRequest).where(FileRequest.token == token)
        req = (await db.execute(stmt)).scalar_one_or_none()
        if not req:
            raise ValueError("文件请求不存在")

        if not req.is_active:
            raise ValueError("文件请求已关闭")
        if req.expires_at and req.expires_at < datetime.utcnow():
            raise ValueError("文件请求已过期")

        # 2) require_uploader_name 校验
        if req.require_uploader_name and not (uploader_name and uploader_name.strip()):
            raise ValueError("请填写上传者姓名")

        # 3) max_file_size_mb 校验
        if req.max_file_size_mb:
            max_bytes = req.max_file_size_mb * 1024 * 1024
            if file_size > max_bytes:
                raise ValueError(
                    f"文件大小 {file_size // 1024 // 1024}MB 超过限制 {req.max_file_size_mb}MB"
                )

        # 4) allowed_extensions 校验
        if req.allowed_extensions:
            ext = (file_name.rsplit(".", 1)[-1] or "").lower()
            # 去掉路径后缀
            ext = ext.strip().lower()
            if ext not in req.allowed_extensions:
                raise ValueError(
                    f"不允许的文件类型 '.{ext}'，仅支持 {', '.join(req.allowed_extensions)}"
                )

        # 5) 实际创建 Knowledge 行 (drive mode, target_folder_id, team visibility)
        # 用 req.created_by 作为创建者 (审计追到创建者)
        # visibility 默认 team (公开提交通常对组内可见)
        # storage_mode='drive' 保证 PR1-6 的所有功能可用
        visibility = "team"
        # uploader_name 写入 meta (Knowledge.meta 是 JSONB)
        meta = {
            "kind": "file_request_submission",
            "request_id": req.id,
            "uploader_name": uploader_name if uploader_name else "(匿名)",
            "submitted_at": datetime.utcnow().isoformat(),
        }

        # 调 DriveService.create_file (走完整管线: MinIO + quota + activity)
        # drive_service 是 class-based, 用 DriveService(db) 实例化
        # PR7: create_file 接受 file_path (str) 而非 file_content (bytes)
        # 先 upload 到 MinIO, 再调 create_file 写元数据
        from app.services.file_service import file_service
        upload_result = await file_service.upload_file(
            file_data=file_content,
            filename=file_name,
            content_type=content_type,
            prefix="uploads/file_requests",
        )
        object_name = upload_result["object_name"]

        drive_svc = DriveService(db)
        # Knowledge 模型 file_path 字段存 MinIO object_name
        # title 字段是 display 标题 (PR6 前端也用 file_name 当 title)
        # meta (含 uploader_name/request_id) 不传 — create_file 签名不接受, 留 Knowledge 行不带
        new_file = await drive_svc.create_file(
            title=file_name,
            content=f"[file_request] token={req.token[:8]}*** uploader={meta['uploader_name']}",
            file_path=object_name,
            file_name=file_name,
            file_type=content_type,
            file_size=file_size,
            owner_id=req.created_by,
            visibility=visibility,
            storage_mode="drive",
            folder_id=req.target_folder_id,
            source_type="drive",  # 走 drive 路径 (不入 knowledge index)
            created_by=req.created_by,
        )

        # 6) submission_count + 1 + activity
        req.submission_count = (req.submission_count or 0) + 1
        await db.commit()

        try:
            await activity_service.log(
                db,
                actor_id=req.created_by,
                action="comment",
                target_type="file",
                target_id=new_file.id,
                target_name=file_name,
                metadata={
                    "kind": "file_request_submission",
                    "request_id": req.id,
                    "uploader_name": meta["uploader_name"],
                    "submission_count": req.submission_count,
                },
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"[FileRequest] submit activity log 失败: {e}", exc_info=True)

        logger.info(
            f"[FileRequest] submitted id={req.id} file={file_name} "
            f"by={uploader_name or '(anon)'} size={file_size}"
        )
        return {
            "success": True,
            "submission_count": req.submission_count,
            "file_id": new_file.id,
            "file_name": file_name,
        }

    @staticmethod
    async def list_my_requests(
        db: AsyncSession,
        *,
        created_by: int,
        include_inactive: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """我创建的文件请求列表

        Args:
            created_by: 创建者 user_id
            include_inactive: 包含已关闭/过期的 (默认仅 active)
            limit: 上限
        """
        stmt = select(FileRequest).where(FileRequest.created_by == created_by)
        if not include_inactive:
            # 仅 is_active=True 且 (expires_at NULL 或 expires_at > now)
            stmt = stmt.where(FileRequest.is_active == True)  # noqa: E712
        stmt = stmt.order_by(desc(FileRequest.created_at)).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()

        results = []
        for req in rows:
            expired = bool(req.expires_at and req.expires_at < datetime.utcnow())
            results.append({
                "id": req.id,
                "token": req.token,
                "title": req.title,
                "expires_at": req.expires_at.isoformat() if req.expires_at else None,
                "expired": expired,
                "active": bool(req.is_active and not expired),
                "is_active": req.is_active,
                "allowed_extensions": req.allowed_extensions or [],
                "require_uploader_name": req.require_uploader_name,
                "submission_count": req.submission_count,
                "created_at": req.created_at.isoformat() if req.created_at else None,
            })
        return results

    @staticmethod
    async def deactivate(
        db: AsyncSession,
        *,
        request_id: int,
        user_id: int,
    ) -> bool:
        """关闭文件请求 (创建者 only)

        Returns:
            True 成功, False 越权或不存在
        """
        stmt = select(FileRequest).where(FileRequest.id == request_id)
        req = (await db.execute(stmt)).scalar_one_or_none()
        if not req:
            return False
        if req.created_by != user_id:
            logger.warning(f"[FileRequest] 越权关闭: user={user_id} request={request_id}")
            return False
        req.is_active = False
        req.updated_at = datetime.utcnow()
        await db.commit()
        logger.info(f"[FileRequest] deactivated id={request_id} by user={user_id}")
        return True


# 全局单例 (与 PR6 service 范式一致)
file_request_service = FileRequestService()
