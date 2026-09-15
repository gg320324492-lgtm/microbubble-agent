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
        # 2026-09-15 P0: 嗅探真实容器 (iOS Safari 出 audio/mp4, 桌面 Chrome 出 webm),
        # 不再硬编码 audio/webm — 否则 iOS 录音的回放 MIME 类型是错的。
        _, content_type = self.sniff_audio_container(blob)
        await file_service.upload_to_path(
            object_name=object_name,
            file_data=blob,
            content_type=content_type,
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

    @staticmethod
    def sniff_audio_container(first_bytes: bytes) -> tuple:
        """从首个分片的文件头嗅探真实容器格式。

        2026-09-15 P0 新增 (听会 09-14 事故): 原实现把所有录音硬编码成
        `audio/webm`。但 iOS Safari 的 MediaRecorder 只支持 audio/mp4 (AAC),
        落库/落 MinIO 的 content_type 写成 webm 会让 <audio> 在 iOS 上无法回放。
        返回 (扩展名, content_type)。
        """
        head = (first_bytes or b"")[:16]
        if head[:4] == b"\x1a\x45\xdf\xa3":
            return "webm", "audio/webm"
        if len(head) >= 12 and head[4:8] == b"ftyp":
            return "m4a", "audio/mp4"
        if head[:4] == b"OggS":
            return "ogg", "audio/ogg"
        if head[:4] == b"RIFF":
            return "wav", "audio/wav"
        if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"):
            return "mp3", "audio/mpeg"
        return "webm", "audio/webm"

    async def merge_chunks_raw(self, meeting_id: int) -> str:
        """字节级按序拼接所有 chunk（不做任何容器解析）。

        2026-09-15 P0 新增 (听会 09-14 事故): iOS Safari 不遵守
        `MediaRecorder.start(timeslice)`，ondataavailable 只在 stop 触发一次，
        于是前端在停止时把整段 blob 按固定字节数切片上传。这些切片是同一个
        MP4/WebM 容器的**原始字节区间**，不是独立可解码的媒体文件 —— 用
        ffmpeg concat demuxer 解析每一片会失败。此方法直接按 chunk_index 升序
        做字节拼接，对完整 blob 的字节区间是**无损且精确**的还原。

        返回合并后的 MinIO object_name（扩展名按嗅探结果决定）。
        """
        chunks = await self.list_chunks(meeting_id)
        if not chunks:
            raise ValueError(f"会议 {meeting_id} 无 chunk 可合并")

        logger.info(f"开始原始字节拼接会议 {meeting_id} 的 {len(chunks)} 个 chunk")

        parts = []
        for chunk in chunks:
            data = await file_service.download_file(chunk["object_name"])
            if not data:
                raise RuntimeError(f"chunk {chunk['object_name']} 下载为空")
            parts.append(data)

        merged_data = b"".join(parts)
        if not merged_data:
            raise RuntimeError("原始拼接结果为空")

        ext, content_type = self.sniff_audio_container(merged_data)
        object_name = self.MERGED_OBJECT_TMPL.format(meeting_id=meeting_id).rsplit(".", 1)[0] + f".{ext}"
        await file_service.upload_to_path(
            object_name=object_name,
            file_data=merged_data,
            content_type=content_type,
        )
        logger.info(
            f"会议 {meeting_id} 原始拼接完成: {object_name} "
            f"({len(merged_data)} bytes [{content_type}] from {len(chunks)} chunks)"
        )
        return object_name

    async def delete_chunks(self, meeting_id: int) -> int:
        """
        仅删除某会议的 chunk 文件（不删 merged.webm）。
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
        return deleted

    async def delete_merged(self, meeting_id: int) -> bool:
        """仅删除 merged.webm（merge 后的最终文件）"""
        merged = self._merged_object_name(meeting_id)
        try:
            file_service.delete_file(merged)
            return True
        except Exception:
            return False

    async def delete_all(self, meeting_id: int) -> int:
        """
        删除某会议的所有相关文件（chunks + merged）。
        用于 DELETE /meetings/{id} 兜底清理。
        """
        deleted = await self.delete_chunks(meeting_id)
        if await self.delete_merged(meeting_id):
            deleted += 1
        return deleted


# 全局实例
chunked_upload_service = ChunkedUploadService()
