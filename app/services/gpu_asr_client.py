# -*- coding: utf-8 -*-
"""GPU 会议 ASR 客户端（app 容器侧）— 调用 host 守护服务

约定:
  - 音频为 16kHz mono float32 numpy
  - 服务不可用/超时/出错一律抛 GPUASRError，由调用方回退 SenseVoice
  - 显存生命周期由 host 守护服务保证（每任务子进程，退出归零）

=== 2026-09-15 事故修复（会议 250 重跑失败）===
事故现场：96 分 27 秒的会议提交 7B 作业后，轮询在 21:50:51 抛了一次异常，
`str(e)` 为**空字符串**，日志只留下 `GPU ASR 链路失败, 回退 SenseVoice: 轮询失败: `。
原实现对这次异常直接放弃整条 GPU 链路，白扔 40 分钟；而未被放弃的作业本身
又跑到 7200s 硬超时才被杀（全程无进展信号）。事后定位到三条：
  1. `raise_for_status()` 的 HTTPStatusError 在 httpx 里 `str()` 为空 →
     错误信息丢失（真正的 404 原因：host 上同时跑了 3 个守护实例，
     job 表是进程内内存字典，轮询落到非持有实例就 404）。
  2. 只管"进程在不在"，不管"有没有在推进" → 卡死无法识别，只能等 2 小时硬超时。
  3. 放弃时不做取消，卡死的作业继续独占 GPU。

本文件对应修复：可读错误（含状态码/原因）、进度推进检测（stall）、
放弃时主动取消、以及对超长音频直接不走 7B（避免必然失败的尝试）。
"""
import asyncio
import logging
import time

import httpx
import numpy as np

logger = logging.getLogger("microbubble.gpu_asr")


class GPUASRError(Exception):
    pass


class GPUASRClient:
    def __init__(self, base_url: str, timeout_submit: float = 120,
                 timeout_total: float = 7200, poll_interval: float = 5.0,
                 stall_seconds: float = 900.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_submit = timeout_submit
        self.timeout_total = timeout_total
        self.poll_interval = poll_interval
        # 进度停滞阈值：worker 每完成一块都会刷新 progress.json；
        # 超过此秒数没有任何推进就认定卡死并放弃（默认 15 分钟）。
        self.stall_seconds = stall_seconds
        self._healthy_until = 0.0
        self._healthy = False
        self._health_detail = ""

    async def healthy(self) -> bool:
        """60s 缓存的健康探测。要求守护存在且当前无在跑作业（单并发，GPU 不能被抢）。"""
        if time.time() < self._healthy_until:
            return self._healthy
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/health")
                data = r.json() if r.status_code == 200 else {}
                ok = (r.status_code == 200 and data.get("ok") is True
                      and not data.get("running"))
                if data.get("running"):
                    self._health_detail = f"守护正忙 (current_jobs={data.get('current_jobs')})"
                elif r.status_code != 200:
                    self._health_detail = f"守护返回 HTTP {r.status_code}"
                else:
                    self._health_detail = f"守护健康 (pid={data.get('pid')})"
        except Exception as e:  # noqa: BLE001
            ok = False
            self._health_detail = f"守护不可达: {type(e).__name__}: {e}"
        self._healthy, self._healthy_until = ok, time.time() + 60
        return ok

    @property
    def health_detail(self) -> str:
        return self._health_detail

    def _cancel(self, job_id: str, reason: str):
        """放弃时主动取消守护侧作业，别让卡死的作业继续独占 GPU。"""
        try:
            with httpx.Client(timeout=10) as c:
                c.post(f"{self.base_url}/jobs/{job_id}/cancel")
            logger.warning(f"GPU ASR 作业 {job_id} 已请求取消（{reason}）")
        except Exception as ce:  # noqa: BLE001
            logger.warning(f"取消 GPU ASR 作业失败: {ce}")

    async def transcribe_meeting(self, pcm: np.ndarray, sr: int = 16000,
                                 meeting_id: int | str = "unknown",
                                 progress_cb=None) -> list[dict]:
        """提交整场会议 PCM，轮询至完成，返回 7B 结构化段落

        segments: [{"start","end","speaker_label","content"}]
        """
        if not await self.healthy():
            raise GPUASRError(f"GPU ASR 服务不可用或正忙（{self.health_detail}）")

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
            raise GPUASRError(f"提交失败: {type(e).__name__}: {e}") from e

        t0 = time.time()
        consecutive_failures = 0
        max_consecutive_failures = 6   # 6 × poll_interval ≈ 30s 容忍窗口
        first_404_at = None
        last_progress_ts = time.time()
        last_progress_sig = None
        last_elapsed = None

        while True:
            if time.time() - t0 > self.timeout_total:
                self._cancel(job_id, "转写超时")
                raise GPUASRError(f"转写超时（{self.timeout_total:.0f}s）")
            if time.time() - last_progress_ts > self.stall_seconds:
                self._cancel(job_id, "进度停滞")
                raise GPUASRError(
                    f"转写进度停滞 {self.stall_seconds:.0f}s，最后进度: {last_progress_sig}"
                )

            await asyncio.sleep(self.poll_interval)
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.get(f"{self.base_url}/jobs/{job_id}")

                if r.status_code == 404:
                    # 作业在守护侧不存在。前 60s 容忍为"注册延迟"，
                    # 之后视为状态丢失并给出**可读**原因 ——
                    # 而不是让 HTTPStatusError 的空 str() 变成 "轮询失败: "。
                    if first_404_at is None:
                        first_404_at = time.time()
                    waited = time.time() - first_404_at
                    if waited > 60:
                        raise GPUASRError(
                            f"作业 {job_id} 在守护侧不存在（HTTP 404 持续 {waited:.0f}s）。"
                            "常见原因：守护进程重启，或 host 上并存多个 "
                            "app.gpu_worker.server 实例导致作业状态不共享。"
                            "请确认 host 只有一个守护实例在跑。"
                        )
                    consecutive_failures += 1
                    info = {}
                else:
                    r.raise_for_status()
                    info = r.json()
                    consecutive_failures = 0
                    first_404_at = None

                prog = info.get("progress") if isinstance(info, dict) else None
                if prog:
                    sig = (prog.get("phase"), prog.get("chunk_done"),
                           prog.get("updated_at"))
                    if sig != last_progress_sig:
                        last_progress_sig = sig
                        last_progress_ts = time.time()
                        msg = (f'{prog.get("phase")} '
                               f'{prog.get("chunk_done") or 0}/{prog.get("chunks_total") or "?"}'
                               f' eta={prog.get("eta_sec", "?")}s')
                        logger.info(f"GPU ASR 进度: {msg}")
                        if progress_cb:
                            try:
                                progress_cb(msg)
                            except Exception:  # noqa: BLE001
                                pass

                status = info.get("status")
                elapsed = info.get("elapsed_sec")
                if elapsed is not None and elapsed != last_elapsed:
                    last_elapsed = elapsed
                    # 有 elapsed 且作业在跑 = 守护侧存活，算作弱进度信号
                    if status == "running":
                        last_progress_ts = max(last_progress_ts, time.time()
                                               - self.stall_seconds / 2)
            except GPUASRError:
                raise
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    self._cancel(job_id, "轮询连续失败")
                    raise GPUASRError(
                        f"轮询失败 {consecutive_failures} 次: "
                        f"{type(e).__name__}: {e or '(空错误信息)'}"
                    ) from e
                logger.warning(
                    f"GPU ASR 轮询第 {consecutive_failures}/{max_consecutive_failures} 次失败"
                    f"（继续重试）: {type(e).__name__}: {e}"
                )
                continue

            if status == "done":
                result = info.get("result") or {}
                meta = result.get("meta") or {}
                logger.info(
                    f"GPU ASR 完成: {len(result.get('segments', []))} 段, "
                    f"rtf={meta.get('rtf')}, chunks={meta.get('chunks_done')}/{meta.get('chunks')}, "
                    f"耗时 {time.time() - t0:.0f}s"
                )
                return result.get("segments", [])
            if status == "error":
                result = info.get("result") or {}
                raise GPUASRError(
                    f"worker 失败: {result.get('error') or '未知错误'}"
                    + (f" | 日志尾部: {result['log_tail'][-300:]}"
                       if result.get("log_tail") else "")
                )
            # pending / running → 继续轮询


def get_gpu_asr_client() -> GPUASRClient:
    from app.config import settings
    return GPUASRClient(
        settings.GPU_ASR_URL,
        timeout_total=settings.GPU_ASR_TIMEOUT,
        poll_interval=5.0,
        stall_seconds=settings.GPU_ASR_STALL_SEC,
    )
