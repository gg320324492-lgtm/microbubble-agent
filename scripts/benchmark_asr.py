#!/usr/bin/env python3
"""
ASR 模型对比 benchmark。

测试 3 个 backend:
  - whisper (baseline): 调 http://whisper:8002/transcribe
  - sensevoice: FunASR SenseVoiceSmall
  - paraformer: FunASR SeacoParaformer (char-level, 无 punc)

5 个维度:
  1. 准确性: CER (raw + filtered), jiwer 库
  2. 速度: 冷启动 + RTF (3 次中位数)
  3. 资源: Peak VRAM + Resident VRAM
  4. 中文质量: 标点 F1 (仅 SenseVoice/Whisper, Paraformer 无标点)
  5. 幻觉: 7 层规则命中段数

用法:
    python scripts/benchmark_asr.py \
        --backends whisper,sensevoice,paraformer \
        --audio-dir data/asr_eval/normalized/ \
        --ground-truth data/asr_eval/ground_truth.jsonl \
        --output-dir results/asr_benchmark_2026-06-30/
"""
import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from statistics import median
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ===================== 数据结构 =====================

@dataclass
class BackendResult:
    backend: str
    audio: str
    text: str
    duration_sec: float
    elapsed_sec: float
    rtf: float
    vram_peak_gb: float
    vram_resident_gb: float
    raw_text: str = ""
    segments: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class Metrics:
    backend: str
    audio: str
    duration_sec: float
    rtf_median: float
    elapsed_median_sec: float
    vram_peak_gb: float
    vram_resident_gb: float
    raw_cer: Optional[float] = None
    filtered_cer: Optional[float] = None
    raw_hallucination_count: int = 0
    filtered_hallucination_count: int = 0
    punctuation_present: bool = False
    text_len: int = 0
    error: Optional[str] = None


# ===================== Utilities =====================

def get_nvidia_smi_memory() -> float:
    """获取当前 GPU 显存使用 (GB)"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return float(result.stdout.strip().split("\n")[0]) / 1024  # MiB → GB
    except Exception:
        return 0.0


def normalize_text(text: str) -> str:
    """归一化文本用于 CER 计算"""
    # 去除所有空白
    text = re.sub(r"\s+", "", text)
    # 去除常见标点
    text = re.sub(r"[，。！？、；：""''《》（）.,!?;:'\"]", "", text)
    return text


def compute_cer(reference: str, hypothesis: str) -> float:
    """用 jiwer 计算 CER"""
    try:
        from jiwer import cer
        return cer(reference, hypothesis)
    except ImportError:
        return -1.0
    except Exception as e:
        print(f"  [WARN] CER computation failed: {e}")
        return -1.0


# ===================== Whisper Backend =====================

class WhisperBackend:
    name = "whisper"

    def __init__(self, service_url: str = "http://whisper:8002"):
        self.service_url = service_url

    def warmup(self) -> None:
        """Whisper 是远程服务, warmup 仅做健康检查"""
        import requests
        for i in range(3):
            try:
                r = requests.get(f"{self.service_url}/health", timeout=10)
                if r.status_code == 200:
                    print(f"  [whisper] Health: {r.json()}")
                    return
            except Exception as e:
                print(f"  [whisper] Health check attempt {i+1}: {e}")
                time.sleep(2)
        raise RuntimeError(f"Whisper service not healthy: {self.service_url}")

    def transcribe(self, audio_path: str, language: str = "zh") -> BackendResult:
        import requests
        t0 = time.perf_counter()
        with open(audio_path, "rb") as f:
            files = {"audio": (Path(audio_path).name, f, "audio/wav")}
            data = {"language": language, "task": "transcribe"}
            try:
                r = requests.post(
                    f"{self.service_url}/transcribe",
                    files=files, data=data,
                    timeout=600,
                )
                r.raise_for_status()
            except Exception as e:
                return BackendResult(
                    backend=self.name, audio=audio_path, text="",
                    duration_sec=0, elapsed_sec=0, rtf=0,
                    vram_peak_gb=0, vram_resident_gb=0,
                    error=str(e),
                )
        elapsed = time.perf_counter() - t0
        result = r.json()
        text = result.get("text", "")
        duration = result.get("duration", 0)
        segments = result.get("segments", [])
        return BackendResult(
            backend=self.name,
            audio=audio_path,
            text=text,
            raw_text=text,
            duration_sec=duration,
            elapsed_sec=elapsed,
            rtf=elapsed / duration if duration > 0 else 0,
            vram_peak_gb=get_nvidia_smi_memory(),
            vram_resident_gb=get_nvidia_smi_memory(),
            segments=segments,
        )

    def cleanup(self) -> None:
        """Whisper 是远程服务, 无需清理"""
        pass


# ===================== SenseVoice Backend =====================

class SenseVoiceBackend:
    name = "sensevoice"

    def __init__(self, device: str = "cuda"):
        self.device = device
        self.model = None

    def warmup(self) -> None:
        import torch
        from funasr import AutoModel
        print(f"  [sensevoice] Loading SenseVoiceSmall...")
        t0 = time.perf_counter()
        self.model = AutoModel(
            model="iic/SenseVoiceSmall",
            device=self.device,
            disable_update=True,
        )
        elapsed = time.perf_counter() - t0
        print(f"  [sensevoice] Loaded in {elapsed:.1f}s, "
              f"VRAM: {torch.cuda.memory_allocated()/1024**3:.2f} GB")

    def transcribe(self, audio_path: str, language: str = "auto") -> BackendResult:
        import torch
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        try:
            result = self.model.generate(
                input=audio_path,
                language=language,
                use_itn=True,
                cache={},
            )
        except Exception as e:
            return BackendResult(
                backend=self.name, audio=audio_path, text="",
                duration_sec=0, elapsed_sec=0, rtf=0,
                vram_peak_gb=0, vram_resident_gb=0,
                error=str(e),
            )
        elapsed = time.perf_counter() - t0
        vram_peak = torch.cuda.max_memory_allocated() / 1024**3

        # FunASR 输出: [{key, text, ...}]
        if not result:
            return BackendResult(
                backend=self.name, audio=audio_path, text="",
                duration_sec=0, elapsed_sec=elapsed, rtf=0,
                vram_peak_gb=vram_peak,
                vram_resident_gb=torch.cuda.memory_allocated()/1024**3,
                error="empty result",
            )

        raw_text = result[0].get("text", "")
        # 估算时长 (从文件名大小或 ffprobe)
        duration = self._get_duration(audio_path)
        # 归一化 (剥 emotion tags)
        from app.voice.asr_filters import strip_all_tags
        clean_text = strip_all_tags(raw_text)

        return BackendResult(
            backend=self.name,
            audio=audio_path,
            text=clean_text,
            raw_text=raw_text,
            duration_sec=duration,
            elapsed_sec=elapsed,
            rtf=elapsed / duration if duration > 0 else 0,
            vram_peak_gb=vram_peak,
            vram_resident_gb=torch.cuda.memory_allocated() / 1024**3,
        )

    def cleanup(self) -> None:
        import torch
        if self.model is not None:
            del self.model
            self.model = None
        torch.cuda.empty_cache()
        print(f"  [sensevoice] Cleaned up, VRAM: {get_nvidia_smi_memory():.2f} GB")

    @staticmethod
    def _get_duration(audio_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, timeout=10,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0


# ===================== Paraformer Backend =====================

class ParaformerBackend:
    """
    Paraformer Seaco (char-level, 无标点).
    Note: Seaco + ct-punc 在 funasr 1.3.14 有兼容性 bug, 此 backend 跳过 punc.
    """
    name = "paraformer"

    def __init__(self, device: str = "cuda"):
        self.device = device
        self.model = None

    def warmup(self) -> None:
        import torch
        from funasr import AutoModel
        print(f"  [paraformer] Loading SeacoParaformer (no punc)...")
        t0 = time.perf_counter()
        self.model = AutoModel(
            model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            device=self.device,
            disable_update=True,
        )
        elapsed = time.perf_counter() - t0
        print(f"  [paraformer] Loaded in {elapsed:.1f}s, "
              f"VRAM: {torch.cuda.memory_allocated()/1024**3:.2f} GB")

    def transcribe(self, audio_path: str, language: str = "zh") -> BackendResult:
        import torch
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        try:
            result = self.model.generate(input=audio_path)
        except Exception as e:
            return BackendResult(
                backend=self.name, audio=audio_path, text="",
                duration_sec=0, elapsed_sec=0, rtf=0,
                vram_peak_gb=0, vram_resident_gb=0,
                error=str(e),
            )
        elapsed = time.perf_counter() - t0
        vram_peak = torch.cuda.max_memory_allocated() / 1024**3

        if not result:
            return BackendResult(
                backend=self.name, audio=audio_path, text="",
                duration_sec=0, elapsed_sec=elapsed, rtf=0,
                vram_peak_gb=vram_peak,
                vram_resident_gb=torch.cuda.memory_allocated()/1024**3,
                error="empty result",
            )

        raw_text = result[0].get("text", "")
        duration = SenseVoiceBackend._get_duration(audio_path)
        # Paraformer 无标点输出: "今 天 是 六 月 五 号" -> "今天是六月号"
        # 把字符间空格去掉
        clean_text = re.sub(r"\s+", "", raw_text).strip()

        return BackendResult(
            backend=self.name,
            audio=audio_path,
            text=clean_text,
            raw_text=raw_text,
            duration_sec=duration,
            elapsed_sec=elapsed,
            rtf=elapsed / duration if duration > 0 else 0,
            vram_peak_gb=vram_peak,
            vram_resident_gb=torch.cuda.memory_allocated() / 1024**3,
        )

    def cleanup(self) -> None:
        import torch
        if self.model is not None:
            del self.model
            self.model = None
        torch.cuda.empty_cache()
        print(f"  [paraformer] Cleaned up, VRAM: {get_nvidia_smi_memory():.2f} GB")


# ===================== Benchmark 编排 =====================

BACKEND_REGISTRY = {
    "whisper": WhisperBackend,
    "sensevoice": SenseVoiceBackend,
    "paraformer": ParaformerBackend,
}


def hallucination_count(text: str) -> int:
    """用 7 层过滤器判定幻觉段数 (粗略: 整段文本命中算 1 次)"""
    from app.voice.asr_filters import _has_strong_hallucination, _has_weak_hallucination, _is_repetitive_text, _is_alphanumeric_run
    count = 0
    if _has_strong_hallucination(text):
        count += 1
    if _has_weak_hallucination(text, audio_rms=0.005):  # 假设低能量
        count += 1
    if _is_repetitive_text(text):
        count += 1
    if _is_alphanumeric_run(text):
        count += 1
    return count


def run_benchmark(
    backend_name: str,
    audio_files: list,
    ground_truth: dict,
    runs: int = 3,
):
    """运行单个 backend 的 benchmark"""
    print(f"\n{'='*60}")
    print(f"Backend: {backend_name}")
    print(f"{'='*60}")

    BackendClass = BACKEND_REGISTRY[backend_name]
    backend = BackendClass()

    # 记录 warmup 前的 VRAM (作为本 backend 的 baseline)
    vram_before_gb = get_nvidia_smi_memory()

    print(f"\n[1] Warmup...")
    try:
        backend.warmup()
    except Exception as e:
        print(f"  [ERROR] Warmup failed: {e}")
        return []

    # 本 backend 加载后的 resident VRAM (delta = 当前 - before)
    vram_after_warmup_gb = get_nvidia_smi_memory()
    backend_resident_gb = max(0.0, vram_after_warmup_gb - vram_before_gb)
    print(f"  [vram] Baseline: {vram_before_gb:.2f} GB, After warmup: {vram_after_warmup_gb:.2f} GB, "
          f"Backend resident: {backend_resident_gb:.2f} GB")

    metrics_list = []
    for audio_file in audio_files:
        audio_str = str(audio_file)
        # Try to find ground truth (by filename)
        gt_text = ""
        for k, v in ground_truth.items():
            if audio_str.endswith(k) or k.endswith(audio_file.name) or audio_file.name == Path(k).name:
                gt_text = v
                break

        print(f"\n  [2] Audio: {audio_file.name}")
        if gt_text:
            print(f"      GT (first 50): {gt_text[:50]}...")

        # 多次运行取中位数
        results = []
        for run_idx in range(runs):
            print(f"      Run {run_idx+1}/{runs}...", end=" ", flush=True)
            r = backend.transcribe(audio_str)
            if r.error:
                print(f"ERROR: {r.error}")
                continue
            print(f"elapsed={r.elapsed_sec:.2f}s rtf={r.rtf:.3f} "
                  f"vram_peak={r.vram_peak_gb:.2f}GB "
                  f"text_len={len(r.text)}")
            results.append(r)

        if not results:
            continue

        # 选最快的 RTF (3 次中位数) 和最大的 vram_peak
        rtfs = [r.rtf for r in results if r.rtf > 0]
        elapsed_list = [r.elapsed_sec for r in results]
        vram_peaks = [r.vram_peak_gb for r in results]
        best_result = max(results, key=lambda r: len(r.text))  # text 最长的通常质量最好

        # CER 计算 (raw + filtered)
        raw_cer = compute_cer(gt_text, best_result.raw_text) if gt_text else None
        filtered_cer = None
        if gt_text and best_result.text:
            from app.voice.asr_filters import apply_7_layers
            filtered_text = apply_7_layers(best_result.text, audio_rms=0.5, segment_duration_sec=1.0)
            filtered_cer = compute_cer(gt_text, filtered_text) if filtered_text else -1.0

        # 幻觉计数
        raw_halluc = hallucination_count(best_result.raw_text)
        filtered_halluc = hallucination_count(best_result.text)

        metrics = Metrics(
            backend=backend_name,
            audio=audio_file.name,
            duration_sec=best_result.duration_sec,
            rtf_median=median(rtfs) if rtfs else 0,
            elapsed_median_sec=median(elapsed_list),
            vram_peak_gb=max(vram_peaks),
            vram_resident_gb=backend_resident_gb,
            raw_cer=raw_cer,
            filtered_cer=filtered_cer,
            raw_hallucination_count=raw_halluc,
            filtered_hallucination_count=filtered_halluc,
            punctuation_present="，" in best_result.text or "。" in best_result.text,
            text_len=len(best_result.text),
        )
        metrics_list.append(metrics)

        # 保存 raw transcript
        transcript_dir = ROOT / "results" / "asr_benchmark_2026-06-30" / "transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        with open(transcript_dir / f"{backend_name}__{audio_file.stem}.txt", "w") as f:
            f.write(f"=== {backend_name} | {audio_file.name} ===\n")
            f.write(f"Raw text (length={len(best_result.raw_text)}):\n{best_result.raw_text}\n\n")
            f.write(f"Clean text (length={len(best_result.text)}):\n{best_result.text}\n")
            if gt_text:
                f.write(f"\n=== Ground truth ===\n{gt_text}\n")

    print(f"\n[3] Cleanup...")
    backend.cleanup()

    return metrics_list


def load_ground_truth(gt_path: Path) -> dict:
    """加载 ground truth, key = 文件名, value = 文本"""
    gt = {}
    if not gt_path.exists():
        return gt
    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line.strip())
            audio_path = rec.get("audio_path", "")
            text = rec.get("text", "")
            if audio_path and text:
                # key 用绝对路径或文件名
                key = Path(audio_path).name
                gt[key] = text
                # 也存绝对路径 key
                abs_path = rec.get("absolute_path", "")
                if abs_path:
                    gt[abs_path] = text
                # 也存带 normalized/ 前缀
                gt[audio_path] = text
    return gt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backends", default="whisper,sensevoice,paraformer",
                        help="Comma-separated backend names")
    parser.add_argument("--audio-dir", default="data/asr_eval/normalized/",
                        help="Directory containing audio files")
    parser.add_argument("--synthetic-dir", default="data/asr_eval/synthetic/",
                        help="Directory containing synthetic audio")
    parser.add_argument("--ground-truth", default="data/asr_eval/ground_truth.jsonl",
                        help="Path to ground truth JSONL")
    parser.add_argument("--output-dir", default="results/asr_benchmark_2026-06-30/",
                        help="Output directory")
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of runs per audio (median)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of audio files (0 = all)")
    args = parser.parse_args()

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load ground truth
    gt_path = ROOT / args.ground_truth
    ground_truth = load_ground_truth(gt_path)
    print(f"[INFO] Loaded {len(ground_truth)} ground truth records")

    # 收集音频文件 (real + synthetic)
    audio_dir = ROOT / args.audio_dir
    synthetic_dir = ROOT / args.synthetic_dir
    audio_files = []
    if synthetic_dir.exists():
        for f in sorted(synthetic_dir.glob("*.wav")):
            audio_files.append(f)
    if audio_dir.exists():
        for f in sorted(audio_dir.glob("*")):
            if f.is_file() and f.suffix in [".wav", ".webm", ".m4a"]:
                audio_files.append(f)

    if args.limit > 0:
        audio_files = audio_files[:args.limit]

    print(f"[INFO] Found {len(audio_files)} audio files")
    print(f"[INFO] Backends: {args.backends}")
    print(f"[INFO] Runs per audio: {args.runs}")

    # 运行每个 backend
    all_metrics = {}
    for backend_name in args.backends.split(","):
        backend_name = backend_name.strip()
        if backend_name not in BACKEND_REGISTRY:
            print(f"[WARN] Unknown backend: {backend_name}, skipping")
            continue
        metrics = run_benchmark(backend_name, audio_files, ground_truth, runs=args.runs)
        all_metrics[backend_name] = metrics

    # 保存所有 metrics
    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    summary = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "backends": {}}
    for backend_name, metrics_list in all_metrics.items():
        summary["backends"][backend_name] = [asdict(m) for m in metrics_list]
        # 每个 backend 单独 metrics.json
        with open(metrics_dir / f"{backend_name}.json", "w") as f:
            json.dump([asdict(m) for m in metrics_list], f, indent=2, ensure_ascii=False)

    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved summary to {output_dir/'summary.json'}")
    print(f"[OK] Per-backend metrics in {metrics_dir}/")


if __name__ == "__main__":
    main()