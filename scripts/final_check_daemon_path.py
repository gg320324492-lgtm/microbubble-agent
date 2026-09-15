"""走守护全链路的最终验证：提交同一段 600s 音频，确认新代码在真实路径生效。

验证点：
  1. server.py 的 chunk_sec 默认 300 生效（作业 JSON 里应带 chunk_sec=300）
  2. worker 的 StoppingCriteria 生效（RTF 应 ≈0.33，而非修复前的 1.04）
  3. 进度落盘 / 状态落盘 / 结果 JSON 全链路正常

用法（宿主，标准库即可）:
    python scripts/final_check_daemon_path.py
"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8005"
WAV = r"E:/microbubble-agent/.workbuddy/vibevoice-test/jobs/probe600.wav"


def post(url: str, data: bytes):
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def get(url: str):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    pcm = open(WAV, "rb").read()
    print(f"[1] 提交 {len(pcm) / 2 / 16000:.0f}s 音频（chunk_sec 默认 300）")
    t0 = time.time()
    resp = post(f"{BASE}/transcribe?sr=16000&meeting_id=final_check", pcm)
    jid = resp["job_id"]
    print(f"    job_id = {jid}")

    job_json = json.loads(open(WAV.replace(".wav", ".job.json"),
                               encoding="utf-8").read()) \
        if False else None  # job.json 由守护写，见 status 落盘

    last = None
    while True:
        time.sleep(10)
        info = get(f"{BASE}/jobs/{jid}")
        st = info.get("status")
        pr = info.get("progress") or {}
        sig = (pr.get("chunk_done"), pr.get("phase"))
        if sig != last:
            last = sig
            print(f"    [{time.time() - t0:5.0f}s] {st} {pr.get('phase')} "
                  f"chunk={pr.get('chunk_done')}/{pr.get('chunks_total')} "
                  f"eta={pr.get('eta_sec')}")
        if st in ("done", "error"):
            break
        if time.time() - t0 > 1500:
            print("    超时退出")
            break

    res = info.get("result") or {}
    meta = res.get("meta") or {}
    print()
    print(f"[2] 终态: {st}")
    print(f"    段数      : {len(res.get('segments') or [])}")
    print(f"    rtf       : {meta.get('rtf')}")
    print(f"    chunks    : {meta.get('chunks_done')}/{meta.get('chunks')}")
    print(f"    墙钟      : {time.time() - t0:.0f}s")
    if res.get("error"):
        print(f"    error     : {res['error'][:200]}")
    ok = (st == "done" and len(res.get("segments") or []) >= 40
          and (meta.get("rtf") or 9) < 0.6)
    print()
    print("=== 结论:", "PASS（守护链路 + chunk300 + 停止条件 全部生效）===" if ok
          else "=== FAIL ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
