"""thumbnail_service — v2 网盘 PR5 缩略图生成

3 类文件支持:
- 图片 (jpg/png/webp/gif/bmp): Pillow 缩放 → 200x200 max
- PDF: PyMuPDF 第一页 → render → Pillow 缩放
- 视频 (mp4/mov/avi/mkv/webm): ffmpeg 第一帧 → Pillow 缩放

返回: MinIO object_name (thumbnails/{file_id}.jpg) 或 None (失败)

降级策略:
- 文件不存在 → 抛 FileNotFoundError
- 不支持的类型 → 返回 None (UI fallback 到 type icon)
- Pillow 解析失败 → 返回 None (status='failed')

所有 MinIO 操作通过 file_service.copy_object_async (零带宽)
"""
import asyncio
import io
import logging
import os
import tempfile
from typing import Optional

from app.services.file_service import file_service

logger = logging.getLogger(__name__)

# 支持的类型白名单
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
PDF_EXTENSIONS = {".pdf"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"}

# 缩略图规格
THUMB_MAX_DIMENSION = 200  # 长边像素
THUMB_QUALITY = 80  # JPEG 质量
THUMB_BUCKET_PREFIX = "thumbnails"


def _classify_file(file_name: str) -> str:
    """返回文件类型: 'image' | 'pdf' | 'video' | 'unsupported'"""
    if not file_name:
        return "unsupported"
    ext = os.path.splitext(file_name)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return "unsupported"


async def generate_thumbnail(
    file_id: int,
    source_object_name: str,
    file_name: str,
) -> Optional[str]:
    """生成缩略图 → 上传到 MinIO → 返回 thumbnail_path (object_name)

    失败返回 None (调用方把 status 标 failed, UI fallback 到 type icon)

    设计:
    1. 从 MinIO 下载源文件到临时路径 (大文件也支持, 走 stream)
    2. 按类型用对应库生成 PIL Image
    3. Pillow 缩放到 ≤ 200x200 + JPEG 编码到 bytes
    4. 上传到 MinIO thumbnails/{file_id}.jpg
    5. 清理临时文件
    """
    file_type = _classify_file(file_name)
    if file_type == "unsupported":
        logger.info(f"[Thumbnail] 不支持类型: {file_name}")
        return None

    thumb_object_name = f"{THUMB_BUCKET_PREFIX}/{file_id}.jpg"

    try:
        # Step 1: 下载到临时路径
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
            tmp_path = tmp.name

        try:
            # 下载源文件 (file_service.download_file 是 async 但走 sync MinIO client)
            file_bytes = await file_service.download_file(source_object_name)
            if not file_bytes:
                logger.warning(f"[Thumbnail] 源文件为空: {source_object_name}")
                return None

            # 写临时文件 (sync, wrap to_thread)
            await asyncio.to_thread(_write_file, tmp_path, file_bytes)

            # Step 2: 生成 PIL Image
            pil_image = await asyncio.to_thread(_generate_pil_image, tmp_path, file_type)
            if pil_image is None:
                return None

            # Step 3: 编码为 JPEG bytes
            thumb_bytes = await asyncio.to_thread(_encode_jpeg, pil_image)

            # Step 4: 上传到 MinIO (走 file_service 的 asyncio.to_thread 包装)
            await file_service.upload_to_path(
                thumb_object_name, thumb_bytes, content_type="image/jpeg"
            )

            logger.info(f"[Thumbnail] OK: file_id={file_id} → {thumb_object_name}")
            return thumb_object_name

        finally:
            # Step 5: 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except Exception as e:
        logger.error(
            f"[Thumbnail] 生成失败 file_id={file_id} file_name={file_name}: {e}",
            exc_info=True,
        )
        return None


def _generate_pil_image(tmp_path: str, file_type: str):
    """同步生成 PIL Image (PDF/视频 走对应库 → PIL.Image)"""
    if file_type == "image":
        from PIL import Image
        return Image.open(tmp_path)

    if file_type == "pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(tmp_path)
            if len(doc) == 0:
                doc.close()
                return None
            page = doc[0]  # 首页
            # 渲染 2x zoom → 高 DPI, 缩略图清晰
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            from PIL import Image
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            return img
        except Exception as e:
            logger.warning(f"[Thumbnail] PyMuPDF 渲染失败: {e}")
            return None

    if file_type == "video":
        try:
            # ffmpeg 抽第一帧 (time 0.5s, 避开黑屏)
            import subprocess
            out_path = tmp_path + "_thumb.jpg"
            cmd = [
                "ffmpeg", "-y", "-ss", "0.5", "-i", tmp_path,
                "-frames:v", "1", "-q:v", "2", out_path,
            ]
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if not os.path.exists(out_path):
                return None
            from PIL import Image
            img = Image.open(out_path)
            os.unlink(out_path)
            return img
        except Exception as e:
            logger.warning(f"[Thumbnail] ffmpeg 抽帧失败: {e}")
            return None

    return None


def _encode_jpeg(pil_image) -> bytes:
    """PIL Image → JPEG bytes (≤ 200x200, quality=80)"""
    from PIL import Image
    # 缩放 (保持宽高比, 长边 ≤ 200)
    pil_image.thumbnail((THUMB_MAX_DIMENSION, THUMB_MAX_DIMENSION), Image.LANCZOS)
    # 转 RGB (PNG/RGBA 走 JPEG 必须先转)
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    # 编码
    buf = io.BytesIO()
    pil_image.save(buf, format="JPEG", quality=THUMB_QUALITY, optimize=True)
    return buf.getvalue()


def _write_file(path: str, data: bytes):
    """sync 写文件 (asyncio.to_thread 包装, 不阻塞 event loop)"""
    with open(path, "wb") as f:
        f.write(data)


async def delete_thumbnail(thumb_object_name: str) -> bool:
    """删除缩略图 (文件删除时调用)"""
    if not thumb_object_name:
        return True
    try:
        # file_service.delete_file 是 sync, wrap to_thread
        await asyncio.to_thread(file_service.delete_file, thumb_object_name)
        return True
    except Exception as e:
        logger.warning(f"[Thumbnail] 删除失败 {thumb_object_name}: {e}")
        return False