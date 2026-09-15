# -*- coding: utf-8 -*-
"""GPU ASR 守护服务（host 侧常驻，自身不占显存）

架构：应用容器 (app-1) → http://host.docker.internal:8005 → 本守护服务
      → 每个会议任务 spawn 一个 meeting_worker 子进程 → 子进程退出显存归零。

接口:
  GET  /health                          → {"ok": true, "running": bool, "queue": n}
  GET  /jobs/{job_id}                   → {"status": pending|running|done|error, "result", "progress"}
  POST /transcribe?sr=16000&meeting_id=1  body=raw int16 PCM → 202 {"job_id": ...}
  POST /jobs/{job_id}/cancel            → 杀掉在跑的子进程（含子进程树）

仅依赖标准库。单并发（GPU 同一时刻只处理一场会议），队列容量 4。

=== 2026-09-15 事故修复（会议 250 重跑失败）===
事故现象：作业 c3509b183672 提交后 90+ 分钟仍 `running:true`，客户端轮询
在 21:50 抛了一次**错误信息为空**的异常（`轮询失败: `）后放弃整条 GPU 链路，
白扔 40 分钟；最终该作业在 7200s 超时被杀。事后查出四个独立缺陷：

1. **同端口起了 3 个守护实例**（PID 12900/63096/51268，8 秒内先后启动）。
   `ThreadingHTTPServer.allow_reuse_address` 在 Windows 上等价于 SO_REUSEADDR，
   允许多进程绑同一端口；而 `_jobs` 是**进程内内存字典**，于是 POST 落在 A 实例、
   GET 落到 B 实例时就会 404 → `raise_for_status()` 抛 HTTPStatusError，
   其 `str()` 为空 → 客户端只看到 "轮询失败: "。**空错误的真正来源。**
   修：启动时探测 /health，已有存活实例则拒绝启动（单实例守卫）。
2. **job 状态只存内存** → 守护重启/多实例时状态丢失，客户端永远 404。
   修：状态落盘 `{job_id}_*.status.json`，`/jobs/{id}` 内存优先、落盘兜底。
3. **子进程 stdout/stderr 被 `capture_output=True` 吞掉**，2 小时里没有任何
   可见进度，无法判断"在跑"还是"卡死"。修：落 `{job_id}_*.log`，
   并把最后一行进度写进 status.json，`/jobs/{id}` 一并返回。
4. **没有取消能力**，一个卡住的作业独占 GPU 长达 2 小时。
   修：`POST /jobs/{id}/cancel` + `GPU_ASR_JOB_TIMEOUT` 可配置。
"""
import io
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

PORT = int(os.environ.get("GPU_ASR_PORT", "8005"))
TMP_DIR = Path(os.environ.get("GPU_ASR_TMP", r"E:\microbubble-agent\.workbuddy\vibevoice-test\jobs"))
HOTWORDS_FILE = Path(__file__).parent / "hotwords.txt"
# 2026-09-15: 单作业硬超时（秒）。原硬编码 7200 太长——卡住的作业会独占 GPU 2 小时。
JOB_TIMEOUT = int(os.environ.get("GPU_ASR_JOB_TIMEOUT", "3600"))

_jobs = {}                    # job_id -> {"status","result","error","ts",...}
_q = queue.Queue(maxsize=4)
_lock = threading.Lock()
_procs = {}                   # job_id -> subprocess.Popen（供 cancel 使用）
_cancel_requested = set()     # job_id 集合


def _status_path(job_id: str) -> Path | None:
    """状态落盘路径。job_id 里含会议号，用 glob 找首次出现的那份。"""
    for p in TMP_DIR.glob(f"{job_id}_*.status.json"):
        return p
    return None


def _write_status(job_id: str, **fields):
    """把作业状态落盘（原子写），供跨实例/重启查询。"""
    p = _status_path(job_id)
    if p is None:
        return
    try:
        cur = {}
        if p.exists():
            cur = json.loads(p.read_text(encoding="utf-8"))
        cur.update(fields)
        cur["job_id"] = job_id
        cur["updated_at"] = time.time()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def _read_status_file(job_id: str) -> dict | None:
    p = _status_path(job_id)
    if p is None or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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


def _kill_tree(pid: int):
    """杀掉进程树（Windows 用 taskkill /T，POSIX 用进程组）。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=30)
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001 — 尽力而为
        pass


def _tail(path: Path, n: int = 400) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return ""


def _run_job(job_id: str, wav_path: Path, out_path: Path):
    with _lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started_at"] = time.time()
    _write_status(job_id, status="running", started_at=time.time())
    log_path = wav_path.with_suffix(".log")
    try:
        cmd = [sys.executable, "-m", "app.gpu_worker.meeting_worker",
               "--job", str(wav_path.with_suffix(".job.json")),
               "--output", str(out_path),
               "--progress", str(wav_path.with_suffix(".progress.json")),
               "--log", str(log_path),
               "--max-seconds", str(JOB_TIMEOUT - 120)]
        job_json = json.loads(wav_path.with_suffix(".job.json").read_text(encoding="utf-8"))
        env = {**os.environ}
        if job_json.get("hotwords") is None:
            job_json["hotwords"] = _hotwords()
            wav_path.with_suffix(".job.json").write_text(
                json.dumps(job_json, ensure_ascii=False), encoding="utf-8")

        # 2026-09-15: 不再 capture_output 吞掉日志 —— 子进程 stdout/stderr 直接落文件，
        # 卡死时至少能看到最后停在哪一块。
        with log_path.open("w", encoding="utf-8", errors="replace") as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                    env=env, cwd=env.get("GPU_ASR_CWD"))
            with _lock:
                _procs[job_id] = proc
            try:
                rc = proc.wait(timeout=JOB_TIMEOUT)
            except subprocess.TimeoutExpired:
                _kill_tree(proc.pid)
                rc = -9
                with _lock:
                    _jobs[job_id]["result"] = {
                        "status": "error",
                        "error": f"作业超时 {JOB_TIMEOUT}s 已被守护强制终止",
                        "log_tail": _tail(log_path, 1500),
                    }
                    _jobs[job_id]["status"] = "error"
                _write_status(job_id, status="error", error="timeout",
                              log_tail=_tail(log_path, 1500))
                return
            finally:
                with _lock:
                    _procs.pop(job_id, None)

        cancelled = job_id in _cancel_requested
        _cancel_requested.discard(job_id)
        if cancelled:
            with _lock:
                _jobs[job_id]["result"] = {"status": "error", "error": "作业已被取消",
                                           "log_tail": _tail(log_path, 1500)}
                _jobs[job_id]["status"] = "error"
            _write_status(job_id, status="error", error="cancelled")
            return

        result = (json.loads(out_path.read_text(encoding="utf-8"))
                  if out_path.exists() else
                  {"status": "error", "error": "worker 未产出结果",
                   "log_tail": _tail(log_path, 2000)})
        result.setdefault("meta", {})["exit_code"] = rc
        result["meta"]["log_tail"] = _tail(log_path, 600)
        with _lock:
            _jobs[job_id]["result"] = result
            _jobs[job_id]["status"] = "done" if result.get("status") == "ok" else "error"
        _write_status(job_id,
                      status=_jobs[job_id]["status"],
                      result=result,
                      finished_at=time.time())
    except Exception as e:  # noqa: BLE001
        with _lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["result"] = {"status": "error",
                                       "error": f"{type(e).__name__}: {e}",
                                       "log_tail": _tail(log_path, 1500)}
        _write_status(job_id, status="error", error=f"{type(e).__name__}: {e}")
    finally:
        # 清理大临时文件（保留 job.json / status.json / log 便于排查）
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


def _job_view(job_id: str) -> dict | None:
    """内存优先，落盘兜底 —— 保证任何实例/重启后都能回答 /jobs/{id}。"""
    with _lock:
        info = _jobs.get(job_id)
        if info:
            view = {"job_id": job_id, "status": info["status"],
                    "result": info.get("result")}
            if info.get("started_at"):
                view["elapsed_sec"] = round(time.time() - info["started_at"], 1)
    if info is None:
        disk = _read_status_file(job_id)
        if disk is None:
            return None
        view = {"job_id": job_id, "status": disk.get("status"),
                "result": disk.get("result"), "source": "disk"}
        if disk.get("log_tail"):
            view["result"] = {**(view.get("result") or {}),
                              "log_tail": disk.get("log_tail")}
    # 附上 worker 侧进度（含"最后停在哪一块"），供客户端判断是否卡死
    prog = list(TMP_DIR.glob(f"{job_id}_*.progress.json"))
    if prog:
        try:
            view["progress"] = json.loads(prog[0].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return view


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
                with _lock:
                    running = any(j["status"] == "running" for j in _jobs.values())
                    current = [jid for jid, j in _jobs.items() if j["status"] == "running"]
                self._json(200, {"ok": True, "running": running,
                                 "current_jobs": current,
                                 "queue": _q.qsize(),
                                 "job_timeout_sec": JOB_TIMEOUT,
                                 "pid": os.getpid()})
            elif self.path.startswith("/jobs/"):
                jid = self.path.rstrip("/").rsplit("/", 1)[-1]
                view = _job_view(jid)
                self._json(200, view) if view else self._json(404, {"error": "job not found"})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            # 2026-09-15: 取消接口 —— 卡住的作业不必再等 2 小时
            if path.startswith("/jobs/") and path.endswith("/cancel"):
                jid = path.split("/")[2]
                with _lock:
                    proc = _procs.get(jid)
                    _cancel_requested.add(jid)
                if proc is not None:
                    _kill_tree(proc.pid)
                    self._json(200, {"job_id": jid, "cancelled": True,
                                     "killed_pid": proc.pid})
                else:
                    self._json(200, {"job_id": jid, "cancelled": False,
                                     "reason": "no running process"})
                return

            if not path.startswith("/transcribe"):
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
                _write_status(job_id, status="pending", meeting_id=meeting_id,
                              audio_sec=round(len(pcm) / 2 / sr, 1))
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
    if os.environ.get("GPU_ASR_SHOW_CONSOLE"):
        return
    import ctypes
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE


def _already_running() -> bool:
    """单实例守卫：本机同端口已有存活守护则返回 True。

    2026-09-15 事故：同端口曾起 3 个实例（每个都有独立的内存 job 表），
    轮询落到非持有实例就 404 → 客户端拿到一个空错误信息。
    这里用 /health 探测代替端口占用判断（端口被占但进程已死时应允许启动）。
    """
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
            return bool(data.get("ok"))
    except Exception:  # noqa: BLE001 — 连不上 = 没有存活实例
        return False


def _cleanup_stale_tmp():
    """清理上次异常退出留下的 wav（大文件）；保留 json/log/progress 便于排查。"""
    freed = 0
    for p in TMP_DIR.glob("*.wav"):
        try:
            freed += p.stat().st_size
            p.unlink()
        except OSError:
            pass
    if freed:
        print(f"[gpu-asr-daemon] 清理残留 wav {freed / 1024 / 1024:.1f}MB", flush=True)


class _SingleInstanceHTTPServer(ThreadingHTTPServer):
    """独占绑定的 HTTP server。

    2026-09-15 实测教训：计划任务同时挂了 AtStartup 与 AtLogOn 两个触发器，
    两个实例几乎同时启动，各自探测 /health 时对方都还没开始监听，
    **双双通过单实例守卫并绑定了同一端口**（Windows 上 SO_REUSEADDR
    允许多进程绑同端口）—— 又回到"job 表各自独立、轮询 404"的老问题。
    因此这里关掉 allow_reuse_address，让端口本身成为原子互斥量：
    第二个实例 bind 直接失败并退出，不依赖时序。
    """
    allow_reuse_address = False
    daemon_threads = True


def main():
    _hide_console()
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if _already_running():
        print(f"[gpu-asr-daemon] 已有存活实例在 0.0.0.0:{PORT}，本次启动退出"
              f"（单实例守卫；如需重启请先停掉旧进程）", flush=True)
        return

    _cleanup_stale_tmp()
    # 独占绑定：彻底杜绝"两个实例同时通过守卫"的竞态
    try:
        srv = _SingleInstanceHTTPServer(("0.0.0.0", PORT), _handler_factory())
    except OSError as e:
        print(f"[gpu-asr-daemon] 端口 {PORT} 无法独占绑定（已有实例？）: {e}，本次启动退出",
              flush=True)
        return

    threading.Thread(target=_worker_loop, daemon=True).start()
    print(f"[gpu-asr-daemon] listening on 0.0.0.0:{PORT} (pid={os.getpid()}), "
          f"tmp={TMP_DIR}, hotwords={'yes' if _hotwords() else 'no'}, "
          f"job_timeout={JOB_TIMEOUT}s", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
