# -*- coding: utf-8 -*-
"""GPU 会议 worker 管理器（父进程侧）

职责:
  1. 会议开始/录音上传时，以独立子进程拉起 meeting_worker
  2. 子进程正常退出（含崩溃）后，校验显存回落到基线 → 保证"无会议不占显存"
  3. 汇集结果 JSON 返回给调用方（后续接入会议分析 Celery task / API）

用法:
  python -m app.gpu_worker.manager --selftest          # 端到端生命周期自测
  python -m app.gpu_worker.manager --job job.json --output result.json
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from app.gpu_worker.meeting_worker import vram_used_mb

WORKER = "app.gpu_worker.meeting_worker"
VRAM_TOLERANCE_MB = 256   # 退出后允许的显存波动


def run_meeting_job(job_path: str, output_path: str,
                    timeout_sec: float = 3600) -> dict:
    """拉起 worker 子进程处理一次会议，返回结果 dict

    保证:
      - 子进程退出 = CUDA 上下文销毁 = 显存释放（无论成败）
      - 退出后显存必须回落到启动前基线 ± VRAM_TOLERANCE_MB，否则告警
    """
    baseline = vram_used_mb()
    cmd = [sys.executable, "-m", WORKER, "--job", job_path,
           "--output", output_path]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout_sec)
    elapsed = time.perf_counter() - t0

    result = {}
    out = Path(output_path)
    if out.exists():
        result = json.loads(out.read_text(encoding="utf-8"))
    else:
        result = {"status": "error", "error": "worker 未产出结果文件",
                  "stderr": (proc.stderr or "")[-2000:]}

    after = vram_used_mb()
    leaked = None
    if baseline is not None and after is not None:
        leaked = after - baseline
        if leaked > VRAM_TOLERANCE_MB:
            # 子进程被强杀/卡死时会走到这里；正常退出时不应发生
            result.setdefault("meta", {})["vram_leak_warning_mb"] = leaked

    result.setdefault("meta", {}).update({
        "worker_exit_code": proc.returncode,
        "wall_sec": round(elapsed, 2),
        "vram_baseline_mb": baseline,
        "vram_after_mb": after,
    })
    return result


def _selftest():
    print("[manager] 生命周期自测（无 GPU 也应通过）")
    baseline = vram_used_mb()
    print(f"  显存基线: {baseline} MB"
          f"{'' if baseline is not None else ' (驱动不可用，跳过显存校验)'}")
    out = Path("_selftest_result.json")
    # 直接以当前解释器跑子进程 selftest（与真实会议同一 spawn 路径）
    proc = subprocess.run(
        [sys.executable, "-m", WORKER, "--selftest", "--output", str(out)],
        capture_output=True, text=True, timeout=120)
    ok = proc.returncode == 0 and out.exists()
    print(f"  子进程退出码: {proc.returncode}")
    if not ok:
        print("  stderr:", (proc.stderr or "")[-1000:])
        return 1
    result = json.loads(out.read_text(encoding="utf-8"))
    passed = (result.get("status") == "ok"
              and len(result.get("meta", {}).get("chunk_points", [])) == 5)
    print(f"  分块点: {result.get('meta', {}).get('chunk_points')}")
    print(f"  显存回落校验: 基线 {baseline} → "
          f"{vram_used_mb()} MB")
    out.unlink(missing_ok=True)
    print(f"[manager] 自测{'通过 ✅' if passed else '失败 ❌'}")
    return 0 if passed else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--output")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    if not args.job or not args.output:
        ap.error("需要 --job 和 --output")
    result = run_meeting_job(args.job, args.output)
    print(json.dumps(result.get("meta", {}), ensure_ascii=False, indent=2))
    print("status:", result.get("status"))


if __name__ == "__main__":
    main()
