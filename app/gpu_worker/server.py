# -*- coding: utf-8 -*-
"""GPU ASR 守护服务（host 侧常驻，自身不占显存）

架构：应用容器 (app-1) → http://host.docker.internal:8005 → 本守护服务
      → 每个会议任务 spawn 一个 meeting_worker 子进程 → 子进程退出显存归零。

接口:
  GET  /health                          → {"ok": true, "running": bool, "queue": n}
  POST /transcribe?sr=16000&meeting_id=1  body=raw int16 PCM → 202 {"job_id": ...}
  GET  /jobs/{job_id}                   → {"status": pending|running|done|error, "result": ...}

仅依赖标准库。单并发（GPU 同一时刻只处理一场会议），队列容量 4。
启动（host）:  python -m app.gpu_worker.server   （默认 0.0.0.0:8005）
"""
import io
import json
import queue
import subprocess
import sys
import threading
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

PORT = int(__import__("os").environ.get("GPU_ASR_PORT", "8005"))
TMP_DIR = Path(__import__("os").environ.get("GPU_ASR_TMP", r"E:\microbubble-agent\.workbuddy\vibevoice-test\jobs"))
HOTWORDS_FILE = Path(__file__).parent / "hotwords.txt"

_jobs = {}                    # job_id -> {"status","result","error","ts"}
_q = queue.Queue(maxsize=4)
_lock = threading.Lock()


def _hotwords() -> str | None:
    try:
        t = HOTWORDS_FILE.read_text(encoding="utf-8").strip()
        return t or None
    except OSError:
        return None


def _pcm_to_wav(pcm_bytes: bytes, sr: int, path: Path):
    import array
    samples = array.array("h")
    samples.frombytes(pcm_bytes)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def _run_job(job_id: str, wav_path: Path, out_path: Path):
    with _lock:
        _jobs[job_id]["status"] = "running"
    try:
        cmd = [sys.executable, "-m", "app.gpu_worker.meeting_worker",
               "--job", str(wav_path.with_suffix(".job.json")),
               "--output", str(out_path)]
        job_json = json.loads(wav_path.with_suffix(".job.json").read_text(encoding="utf-8"))
        env = {**__import__("os").environ}
        if job_json.get("hotwords") is None:
            job_json["hotwords"] = _hotwords()
            wav_path.with_suffix(".job.json").write_text(
                json.dumps(job_json, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=7200, env=env, cwd=env.get("GPU_ASR_CWD"))
        result = (json.loads(out_path.read_text(encoding="utf-8"))
                  if out_path.exists() else
                  {"status": "error", "error": "worker 未产出结果",
                   "stderr": (proc.stderr or "")[-2000:]})
        result.setdefault("meta", {})["exit_code"] = proc.returncode
        with _lock:
            _jobs[job_id]["result"] = result
            _jobs[job_id]["status"] = "done" if result.get("status") == "ok" else "error"
    except Exception as e:  # noqa: BLE001
        with _lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["result"] = {"status": "error", "error": str(e)}
    finally:
        # 清理大临时文件（保留 job.json 便于排查）
        for p in (wav_path, out_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def _worker_loop():
    while True:
        job_id = _q.get()
        info = _jobs.get(job_id)
        if not info:
            continue
        _run_job(job_id, Path(info["wav"]), Path(info["out"]))


def _handler_factory():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # 静默默认访问日志
            pass

        def _json(self, code: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                running = any(j["status"] == "running" for j in _jobs.values())
                self._json(200, {"ok": True, "running": running,
                                 "queue": _q.qsize()})
            elif self.path.startswith("/jobs/"):
                jid = self.path.rsplit("/", 1)[-1]
                info = _jobs.get(jid)
                if not info:
                    self._json(404, {"error": "job not found"})
                else:
                    self._json(200, {"job_id": jid, "status": info["status"],
                                     "result": info.get("result")})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self.path.startswith("/transcribe"):
                self._json(404, {"error": "not found"})
                return
            try:
                q = dict(p.split("=", 1) for p in self.path.split("?", 1)[1].split("&")) \
                    if "?" in self.path else {}
                sr = int(q.get("sr", "16000"))
                meeting_id = q.get("meeting_id", "unknown")
                length = int(self.headers.get("Content-Length", 0))
                pcm = self.rfile.read(length)
                if len(pcm) < 32000:
                    self._json(400, {"error": "audio too short"})
                    return
                job_id = uuid.uuid4().hex[:12]
                wav_path = TMP_DIR / f"{job_id}_{meeting_id}.wav"
                out_path = TMP_DIR / f"{job_id}_{meeting_id}.result.json"
                _pcm_to_wav(pcm, sr, wav_path)
                job_json = {"audio_wav": str(wav_path), "hotwords": _hotwords()}
                wav_path.with_suffix(".job.json").write_text(
                    json.dumps(job_json, ensure_ascii=False), encoding="utf-8")
                with _lock:
                    _jobs[job_id] = {"status": "pending", "wav": str(wav_path),
                                     "out": str(out_path), "ts": time.time()}
                try:
                    _q.put_nowait(job_id)
                except queue.Full:
                    with _lock:
                        _jobs.pop(job_id, None)
                    self._json(503, {"error": "queue full"})
                    return
                self._json(202, {"job_id": job_id, "status": "pending"})
            except Exception as e:  # noqa: BLE001
                self._json(500, {"error": str(e)})

    return Handler


def _hide_console() -> None:
    """隐藏宿主控制台窗口（任务栏/Alt+Tab 不再显示，服务照常运行）。
    设 GPU_ASR_SHOW_CONSOLE=1 可保留窗口查看日志。"""
    if sys.platform != "win32":
        return
    import os
    if os.environ.get("GPU_ASR_SHOW_CONSOLE"):
        return
    import ctypes
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE


def main():
    _hide_console()
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_worker_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), _handler_factory())
    print(f"[gpu-asr-daemon] listening on 0.0.0.0:{PORT}, tmp={TMP_DIR}, "
          f"hotwords={'yes' if _hotwords() else 'no'}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
