"""音频元数据提取 — ffprobe 时长探测

W2-7: 从 ffprobe 写入 Meeting.media_duration_seconds。

设计要点:
- 仅依赖系统 ffprobe（不引入新 Python 包）。
- 通过 subprocess 调 ffprobe，传入 -（stdin）读取音频字节，避免落盘。
- 返回 int（秒，向下取整）；ffprobe 失败/不可用返回 None（best-effort 降级，不抛错）。
- 同进程并发安全：每次调用独立 Popen，无全局状态。
"""

import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger("microbubble.audio_metadata")


def _find_ffprobe() -> Optional[str]:
    """定位 ffprobe 可执行文件。

    顺序: shutil.which("ffprobe") → PATH 各路径探测 → None。
    """
    found = shutil.which("ffprobe")
    if found:
        return found
    # 常见 fallback 路径（开发机 + Linux 服务器）
    for cand in ("/usr/bin/ffprobe", "/usr/local/bin/ffprobe", "/opt/homebrew/bin/ffprobe"):
        try:
            import os
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
        except Exception:
            pass
    return None


def ffprobe_duration(audio_bytes: bytes, timeout: float = 30.0) -> Optional[int]:
    """同步版: 用 ffprobe 探测音频时长（秒，整数）。

    Args:
        audio_bytes: 任意 ffprobe 可识别的容器（webm / wav / mp3 / opus 等）。
        timeout: subprocess 超时秒数，默认 30s。

    Returns:
        整数秒数；探测失败返回 None（best-effort，不抛错）。
    """
    if not audio_bytes:
        return None
    ffprobe_bin = _find_ffprobe()
    if not ffprobe_bin:
        logger.warning("ffprobe_duration: ffprobe 不在 PATH，跳过时长探测")
        return None
    try:
        return _run_ffprobe_sync(ffprobe_bin, audio_bytes, timeout)
    except Exception as e:  # noqa: BLE001 — best-effort 兜底
        logger.warning(f"ffprobe_duration 探测失败: {e}")
        return None


def _run_ffprobe_sync(ffprobe_bin: str, audio_bytes: bytes, timeout: float) -> Optional[int]:
    """同步调用 ffprobe，输出 stderr 解析 duration。

    使用 NamedTemporaryFile 落盘再探测（更稳，避免 stdio 兼容问题）。
    """
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        try:
            proc = subprocess.run(
                [ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        except FileNotFoundError as e:
            # Windows: 二进制不存在时直接 FileNotFoundError（不被 returncode 捕获）
            logger.warning(f"ffprobe 二进制未找到 ({ffprobe_bin}): {e}")
            return None
        if proc.returncode != 0:
            logger.warning(f"ffprobe 返回 {proc.returncode}: {proc.stderr.strip()[:200]}")
            return None
        raw = (proc.stdout or "").strip()
        if not raw:
            return None
        # raw 形如 "2025.400000" 或 "2025.4"
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
        if not m:
            return None
        seconds = float(m.group(1))
        return int(seconds)  # 向下取整
    finally:
        try:
            import os
            os.unlink(path)
        except OSError:
            pass


async def ffprobe_duration_async(audio_bytes: bytes, timeout: float = 30.0) -> Optional[int]:
    """异步版: 包装到线程池，避免阻塞 event loop。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: ffprobe_duration(audio_bytes, timeout=timeout))