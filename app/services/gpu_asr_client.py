# -*- coding: utf-8 -*-
"""GPU 会议 ASR 客户端（app 容器侧）— 调用 host 守护服务

约定:
  - 音频为 16kHz mono float32 numpy
  - 服务不可用/超时/出错一律抛 GPUASRError，由调用方回退 SenseVoice
  - 显存生命周期由 host 守护服务保证（每任务子进程，退出归零）
"""
import asyncio
import time

import httpx
import numpy as np


class GPUASRError(Exception):
    pass


class GPUASRClient:
    def __init__(self, base_url: str, timeout_submit: float = 120,
                 timeout_total: float = 7200, poll_interval: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_submit = timeout_submit
        self.timeout_total = timeout_total
        self.poll_interval = poll_interval
        self._healthy_until = 0.0
        self._healthy = False

    async def healthy(self) -> bool:
        """60s 缓存的健康探测"""
        if time.time() < self._healthy_until:
            return self._healthy
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/health")
                ok = (r.status_code == 200 and r.json().get("ok") is True
                      and not r.json().get("running"))
        except Exception:
            ok = False
        self._healthy, self._healthy_until = ok, time.time() + 60
        return ok

    async def transcribe_meeting(self, pcm: np.ndarray, sr: int = 16000,
                                 meeting_id: int | str = "unknown",
                                 progress_cb=None) -> list[dict]:
        """提交整场会议 PCM，轮询至完成，返回 7B 结构化段落

        segments: [{"start","end","speaker_label","content"}]
        """
        if not await self.healthy():
            raise GPUASRError("GPU ASR 服务不可用或正忙")

        pcm16 = (np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes()
        url = (f"{self.base_url}/transcribe?sr={sr}&meeting_id={meeting_id}")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_submit) as client:
                r = await client.post(url, content=pcm16,
                                      headers={"Content-Type":
                                               "application/octet-stream"})
            if r.status_code == 503:
                raise GPUASRError("GPU ASR 队列已满")
            r.raise_for_status()
            job_id = r.json()["job_id"]
        except GPUASRError:
            raise
        except Exception as e:
            raise GPUASRError(f"提交失败: {e}") from e

        t0 = time.time()
        # 2026-09-15 P0 修复（会议 250 重跑事故）：轮询瞬时故障容错。
        # 事故现场：21:10 提交 7B 作业，21:50:51 轮询抛了一次异常（错误信息为空），
        # 原实现直接 `raise GPUASRError(...)` 放弃整条 GPU 链路 → 白扔 40 分钟
        # 后回退 SenseVoice，最终把整条流水线拖过 1 小时、触发 broker 重复投递。
        # 修法：连续 N 次轮询失败才放弃；单次抖动只是重试。
        consecutive_failures = 0
        max_consecutive_failures = 6  # 6 次 × poll_interval(5s) ≈ 30s 容忍窗口
        while True:
            if time.time() - t0 > self.timeout_total:
                raise GPUASRError("转写超时")
            await asyncio.sleep(self.poll_interval)
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.get(f"{self.base_url}/jobs/{job_id}")
                r.raise_for_status()
                info = r.json()
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    raise GPUASRError(
                        f"轮询失败 {consecutive_failures} 次: {e}"
                    ) from e
                # 瞬时抖动 → 继续下一轮轮询
                import logging as _logging
                _logging.getLogger("microbubble.gpu_asr").warning(
                    f"GPU ASR 轮询第 {consecutive_failures}/{max_consecutive_failures} 次失败"
                    f"（继续重试）: {e}"
                )
                continue
            status = info.get("status")
            if progress_cb:
                try:
                    progress_cb(status)
                except Exception:
                    pass
            if status == "done":
                result = info.get("result") or {}
                return result.get("segments", [])
            if status == "error":
                result = info.get("result") or {}
                raise GPUASRError(f"worker 失败: {result.get('error')}")
            # pending / running → 继续轮询


def get_gpu_asr_client() -> GPUASRClient:
    from app.config import settings
    return GPUASRClient(settings.GPU_ASR_URL)
