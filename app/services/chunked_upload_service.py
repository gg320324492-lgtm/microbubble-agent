"""分片上传服务 — 边录边传的后端支撑

解决问题：2026-06-12 会议 #84 案例 — 录音丢失。
本服务把前端每 5s 推过来的 chunk 存到 MinIO 子目录，
录音结束时合并成完整文件，触发后处理。
"""

import asyncio
import io
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.services.file_service import file_service

logger = logging.getLogger("microbubble.chunked_upload")


class ChunkedUploadService:
    """分片上传 + 合并 + 清理"""

    CHUNK_PREFIX_TMPL = "recordings/{meeting_id}/chunks"
    MERGED_OBJECT_TMPL = "recordings/{meeting_id}/merged.webm"
    CHUNK_NAME_TMPL = "chunk_{idx:05d}.webm"  # 5 位数零填充，方便排序

    @property
    def chunk_prefix(self) -> str:
        return self.CHUNK_PREFIX_TMPL

    def _chunk_object_name(self, meeting_id: int, idx: int) -> str:
        return f"{self.chunk_prefix.format(meeting_id=meeting_id)}/{self.CHUNK_NAME_TMPL.format(idx=idx)}"

    def _merged_object_name(self, meeting_id: int) -> str:
        return self.MERGED_OBJECT_TMPL.format(meeting_id=meeting_id)

    async def save_chunk(self, meeting_id: int, idx: int, blob: bytes) -> str:
        """
        保存单个 chunk 到 MinIO。
        返回 MinIO object_name。
        """
        object_name = self._chunk_object_name(meeting_id, idx)
        await file_service.upload_to_path(
            object_name=object_name,
            file_data=blob,
            content_type="audio/webm",
        )
        return object_name

    async def list_chunks(self, meeting_id: int) -> list:
        """
        列出某会议的所有 chunk，按 idx 升序。
        返回 [{'object_name', 'size', 'chunk_index'}]
        """
        prefix = self.chunk_prefix.format(meeting_id=meeting_id) + "/"
        all_objs = await file_service.list_objects(prefix=prefix)
        result = []
        pattern = re.compile(r"chunk_(\d+)\.webm$")
        for obj in all_objs:
            m = pattern.search(obj["object_name"])
            if m:
                result.append({
                    **obj,
                    "chunk_index": int(m.group(1)),
                })
        result.sort(key=lambda x: x["chunk_index"])
        return result

    async def merge_chunks(self, meeting_id: int) -> str:
        """
        合并某会议的所有 chunk 成完整 webm 文件。
        使用 ffmpeg concat demuxer（保编码，0 质量损失）。
        返回合并后的 MinIO object_name。
        """
        chunks = await self.list_chunks(meeting_id)
        if not chunks:
            raise ValueError(f"会议 {meeting_id} 无 chunk 可合并")

        logger.info(f"开始合并会议 {meeting_id} 的 {len(chunks)} 个 chunk")

        with tempfile.TemporaryDirectory(prefix=f"merge_{meeting_id}_") as tmpdir:
            tmp_path = Path(tmpdir)
            chunks_dir = tmp_path / "chunks"
            chunks_dir.mkdir()
            chunks_txt = tmp_path / "chunks.txt"
            merged_path = tmp_path / "merged.webm"

            # 1. 下载所有 chunk 到本地 + 写 concat 列表
            with chunks_txt.open("w", encoding="utf-8") as f:
                for chunk in chunks:
                    local = chunks_dir / f"chunk_{chunk['chunk_index']:05d}.webm"
                    data = await file_service.download_file(chunk["object_name"])
                    local.write_bytes(data)
                    f.write(f"file '{local.absolute().as_posix()}'\n")

            # 2. ffmpeg concat
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(chunks_txt),
                "-c", "copy",
                str(merged_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"ffmpeg 合并失败: {stderr.decode()[:500]}")
                raise RuntimeError(
                    f"ffmpeg concat 失败 (rc={proc.returncode}): {stderr.decode()[:200]}"
                )

            if not merged_path.exists() or merged_path.stat().st_size == 0:
                raise RuntimeError("ffmpeg 合并输出为空")

            # 3. 上传合并后的文件
            merged_data = merged_path.read_bytes()
            merged_object_name = self._merged_object_name(meeting_id)
            await file_service.upload_to_path(
                object_name=merged_object_name,
                file_data=merged_data,
                content_type="audio/webm",
            )
            logger.info(
                f"会议 {meeting_id} 合并完成: {merged_object_name} "
                f"({len(merged_data)} bytes from {len(chunks)} chunks)"
            )
            return merged_object_name

    async def delete_chunks(self, meeting_id: int) -> int:
        """
        删除某会议的所有 chunk + merged 文件。
        返回删除的对象数。
        """
        prefix = self.chunk_prefix.format(meeting_id=meeting_id) + "/"
        all_objs = await file_service.list_objects(prefix=prefix)
        deleted = 0
        for obj in all_objs:
            try:
                file_service.delete_file(obj["object_name"])
                deleted += 1
            except Exception as e:
                logger.warning(f"删除 chunk 失败 {obj['object_name']}: {e}")

        # 顺手删 merged
        merged = self._merged_object_name(meeting_id)
        try:
            file_service.delete_file(merged)
            deleted += 1
        except Exception:
            pass  # 可能不存在

        return deleted

    async def delete_all(self, meeting_id: int) -> int:
        """
        删除某会议的所有相关文件（chunks + merged + 旧版 audio_url）。
        用于 DELETE /meetings/{id} 兜底清理。
        """
        # 1. chunks + merged (chunked 模式)
        deleted = await self.delete_chunks(meeting_id)
        return deleted


# 全局实例
chunked_upload_service = ChunkedUploadService()
