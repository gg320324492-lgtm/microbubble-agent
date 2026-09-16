"""faststart — 2026-09-13 录音文件 moov 前置重排 (后台任务包装)

iPhone MediaRecorder 流式产出的 m4a / Chrome 产出的 webm, 索引原子在文件尾,
浏览器 <audio> seek 必须顺序拖完已播字节 (96min 会议实测拖动后要等数分钟)。
录制装配完成后调用 ensure_faststart_async, ffmpeg -c copy 秒级重排, 不转码。
"""
import asyncio
import logging

from app.services.file_service import file_service

logger = logging.getLogger(__name__)

# 后台任务强引用集 (防 GC 丢弃未完成任务)
_faststart_tasks = set()


async def run_faststart(object_name: str) -> dict:
    # ensure_faststart 为同步方法 (ffmpeg subprocess + MinIO IO), 放线程池避免阻塞事件循环
    result = await asyncio.to_thread(file_service.ensure_faststart, object_name)
    if result.get("error"):
        logger.warning(f"[faststart] {object_name}: {result['error']}")
    else:
        logger.info(f"[faststart] {object_name} remuxed ({result['size']} bytes)")
    return result


def ensure_faststart_async(object_name: str) -> None:
    """fire-and-forget: 后台执行 faststart 重排 (仅 mp4/m4a/webm)"""
    if not object_name or not object_name.lower().endswith((".mp4", ".m4a", ".webm")):
        return
    loop = asyncio.get_event_loop()
    task = loop.create_task(_run(object_name))
    _faststart_tasks.add(task)
    task.add_done_callback(_faststart_tasks.discard)


async def _run(object_name: str) -> dict:
    try:
        return await run_faststart(object_name)
    except Exception as e:
        logger.warning(f"[faststart] {object_name} 异常: {e}")
        return {"remuxed": False, "error": str(e)}
