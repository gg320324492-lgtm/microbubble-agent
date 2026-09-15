"""音频处理服务 — WebM 转 WAV + 离线 VAD 分段

用于录音机模式的后处理：将完整录音切割为有意义的语音片段。
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import List

import numpy as np

logger = logging.getLogger("microbubble.audio_processor")

SAMPLE_RATE = 16000


@dataclass
class AudioSegment:
    """音频片段"""
    audio: np.ndarray      # float32 PCM, 16kHz mono
    start_time: float      # 起始时间（秒）
    end_time: float        # 结束时间（秒）


class AudioProcessor:
    """音频格式转换 + 离线 VAD 分段"""

    # ---------- 2026-09-16 P0: 低能量窗口二次 VAD 救援参数 ----------
    # 事故：会议 250 出现 186s 无转录窗口，音频能量与语音段相当（1s 子窗最大 -24.9dB
    # vs 语音段 RMS p50 -26.5dB），但一次 VAD 在该窗口只判出 0.5s。silero 默认
    # threshold=0.4 对远场/轻声偏严；而 SenseVoice 链路只转写 VAD 段 → 直接丢语音。
    # 关掉只需把 VAD_RESCUE_ENABLED 置 False。
    VAD_RESCUE_ENABLED = True
    VAD_RESCUE_MIN_GAP_SEC = 20.0      # 只复检长于此时长的空窗
    VAD_RESCUE_THRESHOLD = 0.15        # 二次检测阈值（比主检测的 0.4 低）
    VAD_RESCUE_MIN_SPEECH_MS = 150     # 二次检测的最小语音时长
    VAD_RESCUE_ENERGY_MARGIN_DB = 6.0  # 地板 = 已检出语音 per-1s RMS 的 p20 - 此余量
    VAD_RESCUE_MAX_WINDOWS = 40        # 单场最多复检多少个空窗（控成本）
    # "语音样"判定门槛：捞回时长 ≥ 10s，或占空窗比例 ≥ 5% —— 低于此视为
    # 噪声碎片（椅子/咳嗽/桌椅声），不算"漏抓语音"。
    VAD_RESCUE_SPEECH_LIKE_MIN_SEC = 10.0
    VAD_RESCUE_SPEECH_LIKE_MIN_RATIO = 0.05
    # 最近一次 segment_audio() 的音频证据报告（长空窗分类），供质量门禁使用。
    # 约定：单例 + 单场串行处理，调用方在 segment_audio 之后立即读取。
    last_segment_report: dict = {}

    async def convert_webm_to_wav(self, webm_data: bytes) -> np.ndarray:
        """WebM/Opus → 16kHz mono float32 PCM（通过 ffmpeg）

        Args:
            webm_data: WebM 格式的音频字节

        Returns:
            float32 numpy 数组，16kHz 单声道，值范围 [-1, 1]
        """
        def _convert():
            import subprocess
            import wave

            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f_in:
                f_in.write(webm_data)
                input_path = f_in.name

            output_path = input_path.replace('.webm', '.wav')
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', input_path,
                    '-ar', str(SAMPLE_RATE),
                    '-ac', '1',
                    '-f', 'wav',
                    output_path
                ], capture_output=True, check=True, timeout=300)

                with wave.open(output_path, 'rb') as wf:
                    pcm_bytes = wf.readframes(wf.getnframes())
                    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                return audio
            finally:
                try:
                    os.unlink(input_path)
                except OSError:
                    pass
                try:
                    os.unlink(output_path)
                except OSError:
                    pass

        return await asyncio.to_thread(_convert)

    def segment_audio(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> List[AudioSegment]:
        """用 VAD 将完整音频切割为语音段（离线模式）

        直接调用 silero-vad 的 get_speech_timestamps 对整段音频检测，
        比逐块 process_chunk 更准确。

        Args:
            audio: float32 numpy 数组，16kHz 单声道
            sample_rate: 采样率（默认 16000）

        Returns:
            AudioSegment 列表，每段包含音频数据和时间戳
        """
        import torch
        import os

        # 加载 silero-vad（带重试和本地缓存）
        try:
            # 尝试从本地缓存加载
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
        except Exception as e:
            logger.warning(f"从 GitHub 加载 silero-vad 失败: {e}，尝试使用本地缓存")
            # 如果下载失败，尝试使用本地缓存（如果存在）
            hub_dir = os.path.expanduser("~/.cache/torch/hub")
            if os.path.exists(os.path.join(hub_dir, "snakers4_silero-vad_master")):
                model, utils = torch.hub.load(
                    repo_or_dir=os.path.join(hub_dir, "snakers4_silero-vad_master"),
                    model="silero_vad",
                    force_reload=False,
                    trust_repo=True,
                    source="local",
                )
            else:
                raise RuntimeError(f"无法加载 silero-vad 模型，请检查网络连接或手动下载模型到 {hub_dir}") from e

        get_speech_timestamps = utils[0]

        # 转为 tensor
        audio_tensor = torch.from_numpy(audio.copy())

        # 获取语音时间戳
        speeches = get_speech_timestamps(
            audio_tensor,
            model,
            threshold=0.4,
            min_speech_duration_ms=200,
            min_silence_duration_ms=100,
            return_seconds=False,
            sampling_rate=sample_rate,
        )

        if not speeches:
            # 没有检测到语音，返回整段
            logger.warning("VAD 未检测到语音，返回整段音频")
            return [AudioSegment(
                audio=audio,
                start_time=0,
                end_time=len(audio) / sample_rate,
            )]

        # 合并相邻过近的语音段（间隔 < 0.15s 的合并，避免合并不同发言人的语音）
        merged = [speeches[0]]
        for seg in speeches[1:]:
            gap_samples = seg["start"] - merged[-1]["end"]
            if gap_samples < sample_rate * 0.1:  # 间隔 < 0.1s，合并
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(seg)

        # 2026-09-16 P0: 低能量窗口二次救援
        # 背景：会议 250 出现 186s 无转录窗口（39:03~42:09），音频能量与语音段相当
        # （1s 子窗最大 -24.9dB，而语音段 RMS p50=-26.5dB），但一次 VAD 在该窗口
        # 只判出 0.5s 语音 —— silero 默认 threshold=0.4 把远场/轻声误判为静音。
        # 而 SenseVoice 链路**只转写 VAD 段**，所以这段语音根本没送到 ASR，
        # 直接表现为转写缺口（coverage 0.75 / gap_count 24）。
        # 这里对长空窗用更低阈值复检，并以能量为门槛，避免把纯噪声捞成"语音"。
        rescued, self.last_segment_report = self._rescue_low_energy_windows(
            audio, sample_rate, merged, model, get_speech_timestamps)
        if rescued:
            merged.extend(rescued)
            merged.sort(key=lambda s: s["start"])
            remerged = [merged[0]]
            for seg in merged[1:]:
                if seg["start"] - remerged[-1]["end"] < sample_rate * 0.1:
                    remerged[-1]["end"] = max(remerged[-1]["end"], seg["end"])
                else:
                    remerged.append(seg)
            merged = remerged

        # 切割
        segments = []
        for seg in merged:
            start = seg["start"]
            end = min(seg["end"], len(audio))
            segment_audio = audio[start:end]

            if len(segment_audio) < sample_rate * 0.3:  # 跳过 < 300ms 的段
                continue

            segments.append(AudioSegment(
                audio=segment_audio,
                start_time=start / sample_rate,
                end_time=end / sample_rate,
            ))

        logger.info(f"VAD 分段完成: {len(segments)} 段（原始 {len(speeches)} 段，"
                    f"合并后 {len(merged)} 段，救援 {len(rescued)} 段）")
        return segments

    # ---------------------------------------------------------------- 救援
    def _rescue_low_energy_windows(self, audio, sample_rate, merged, model,
                                   get_speech_timestamps) -> tuple:
        """对"长空窗"用低阈值二次 VAD，捞回被误判为静音的低电平语音。

        返回 (rescued_segments, report)。report 会被 `segment_audio` 记到
        `self.last_segment_report`，供上层（质量门禁）判"长间隔到底是真实静音
        还是漏抓"—— 这正是质量检查里 `transcript_long_gap` 一直缺的那份音频证据。

        判定门槛（双重，避免捞进纯噪声）：
          1) 窗口内存在 1s 子窗，其 RMS 高于"救援地板"
             （地板 = 已检出语音的 per-1s RMS 的 20 分位 - MARGIN_DB）
          2) 二次 VAD（低阈值）确实在该窗口内找到时长 ≥ 0.5s 的段
        """
        if not self.VAD_RESCUE_ENABLED or not merged:
            return [], {}
        import numpy as np
        n = len(audio)
        win = int(sample_rate)

        def _rms_db(x) -> float:
            if len(x) == 0:
                return -120.0
            r = float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))
            return 20 * np.log10(max(r, 1e-9))

        # 已检出语音的 per-1s RMS 分布 → 地板
        speech_rms = []
        for seg in merged:
            s, e = int(seg["start"]), int(seg["end"])
            for i in range(s, max(s, e - win) + 1, win):
                chunk = audio[i:i + win]
                if len(chunk) >= win // 2:
                    speech_rms.append(_rms_db(chunk))
        if not speech_rms:
            return [], {}
        floor_db = float(np.percentile(speech_rms, 20)) - self.VAD_RESCUE_ENERGY_MARGIN_DB

        # 找出所有长空窗
        windows = []
        prev_end = 0
        for seg in merged:
            gap = seg["start"] - prev_end
            if gap >= int(self.VAD_RESCUE_MIN_GAP_SEC * sample_rate):
                windows.append((prev_end, seg["start"]))
            prev_end = max(prev_end, seg["end"])
        if n - prev_end >= int(self.VAD_RESCUE_MIN_GAP_SEC * sample_rate):
            windows.append((prev_end, n))
        if not windows:
            return [], {"floor_db": round(floor_db, 1),
                        "long_gap_min_sec": self.VAD_RESCUE_MIN_GAP_SEC,
                        "windows": [], "long_gap_count": 0,
                        "speech_like_gap_count": 0}

        rescued = []
        examined = 0
        report_windows = []
        for w_start, w_end in windows[: self.VAD_RESCUE_MAX_WINDOWS]:
            w_audio = audio[w_start:w_end]
            if len(w_audio) < win:
                continue
            # 能量门槛：窗口内最强 1s 是否够响
            subs = [_rms_db(w_audio[i:i + win])
                    for i in range(0, max(1, len(w_audio) - win), win)]
            peak_db = max(subs) if subs else _rms_db(w_audio)
            examined += 1
            rec = {"start": round(w_start / sample_rate, 1),
                   "end": round(w_end / sample_rate, 1),
                   "gap_sec": round((w_end - w_start) / sample_rate, 1),
                   "peak_db": round(peak_db, 1),
                   "above_floor": bool(peak_db > floor_db),
                   "rescued_sec": 0.0,
                   "speech_like": False}
            if peak_db <= floor_db:
                report_windows.append(rec)   # 连地板都没到 → 明确静音
                continue
            import torch
            try:
                sub_speeches = get_speech_timestamps(
                    torch.from_numpy(w_audio.copy()), model,
                    threshold=self.VAD_RESCUE_THRESHOLD,
                    min_speech_duration_ms=self.VAD_RESCUE_MIN_SPEECH_MS,
                    min_silence_duration_ms=100,
                    return_seconds=False, sampling_rate=sample_rate,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"VAD 救援复检失败（跳过该窗口）: {e}")
                report_windows.append(rec)
                continue
            got = 0.0
            for sp in sub_speeches or []:
                s, e = w_start + sp["start"], w_start + sp["end"]
                if e - s < sample_rate * 0.5:
                    continue
                seg_db = _rms_db(audio[s:e])
                if seg_db <= floor_db:
                    continue  # 复检出来的段本身也太弱 → 视为噪声
                rescued.append({"start": s, "end": e})
                got += (e - s) / sample_rate
            rec["rescued_sec"] = round(got, 1)
            # 判"语音样"：不能只看"有没有捞到片段"—— 186s 空窗里捞到 1.5s 的孤立
            # 片段更像椅子/咳嗽/桌椅噪声，不是"漏抓了 3 分钟语音"。
            # 因此要求捞回时长占空窗比例达标（或绝对时长够长）才算语音样。
            ratio = got / max((w_end - w_start) / sample_rate, 1e-6)
            rec["rescued_ratio"] = round(ratio, 4)
            rec["speech_like"] = bool(
                got >= self.VAD_RESCUE_SPEECH_LIKE_MIN_SEC
                or ratio >= self.VAD_RESCUE_SPEECH_LIKE_MIN_RATIO
            )
            report_windows.append(rec)
        if examined:
            rescued_sec = sum(x["end"] - x["start"] for x in rescued) / sample_rate
            logger.info(
                f"VAD 低能量救援: 检查 {examined} 个长空窗（地板 {floor_db:.1f}dB），"
                f"捞回 {len(rescued)} 段 / {rescued_sec:.1f}s"
            )
        report = {
            "floor_db": round(floor_db, 1),
            "long_gap_min_sec": self.VAD_RESCUE_MIN_GAP_SEC,
            "windows": report_windows,
            "long_gap_count": len(report_windows),
            "speech_like_gap_count": sum(1 for w in report_windows if w["speech_like"]),
        }
        return rescued, report

    async def convert_and_segment(self, webm_data: bytes) -> tuple[np.ndarray, List[AudioSegment], int]:
        """一步完成：WebM → PCM + VAD 分段

        Returns:
            (audio_pcm, segments, sample_rate)
        """
        audio_pcm = await self.convert_webm_to_wav(webm_data)
        segments = self.segment_audio(audio_pcm, SAMPLE_RATE)
        return audio_pcm, segments, SAMPLE_RATE

    @staticmethod
    def numpy_to_wav_bytes(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
        """float32 PCM numpy → WAV bytes（供 ASR 使用）"""
        import wave
        import io

        # float32 → int16
        pcm_int16 = (audio * 32768).clip(-32768, 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_int16.tobytes())
        return buf.getvalue()


audio_processor = AudioProcessor()
