"""预览转换管线三 bug 修复回归测试 (2026-09-12)

背景: 组会PPT/李胜景 22 个 PPT 预览巡检发现三个后端 bug:
  B1 worker 失败分支 lock.acquire() 永久阻塞 → 锁表 key 永不清理,
     error.txt 一旦被清理 (运维) 该文件预览永远返回 converting (需重启进程)
  B2 soffice 无全局串行 → 多文件并发转换共享 LibreOffice profile 冲突,
     随机 exit 1 → 写入 error.txt
  B3 error.txt 永久粘滞 → 失败后同一缓存 key 永不重试 (直到 updated_at 变化)

修复 (drive_files.py):
  F1 pptx/docx/pdf 统一 xlsx/zip 已验证的 setdefault + acquire(blocking=False)
     锁模式; 删除 worker 失败分支 acquire/release 死代码
  F2 _LIBREOFFICE_GATE = Semaphore(1) 全局串行 pptx/docx 的 soffice 调用
  F3 error.txt 600s TTL: 过期自动清除并允许重转 (全部 5 条管线)

全部单测不触 DB: monkeypatch DriveService / file_service / cache_dir / subprocess。
"""
import hashlib
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.v1 import drive_files

UPDATED = datetime(2026, 9, 12, 12, 0, 0)


# ---------- 测试替身 ----------

def _v1_key(updated) -> str:
    return hashlib.md5(("v1:" + str(updated)).encode()).hexdigest()[:12]


def _called_process_error(cmd):
    import subprocess as _sp
    return _sp.CalledProcessError(1, cmd)


class _StubSvc:
    """DriveService 替身: get_file 只认 file_id"""

    def __init__(self, fake_file):
        self._f = fake_file

    async def get_file(self, file_id, current_user_id=None):
        return self._f if self._f.id == file_id else None


class _NoStartThread:
    """替身 Thread: 记录 target 但不启动 — 让端点锁保持占用, 去重测试确定性"""

    def __init__(self, target=None, args=(), daemon=False, **kwargs):
        self.target = target
        self.args = args

    def start(self):
        pass


def _fake_run_factory(soffice_log=None, soffice_sleep=0.0, fail_soffice=False):
    """subprocess.run 替身: soffice 可失败/计时/记并发; pdftoppm 产出 2 页 png"""

    def fake_run(cmd, **kwargs):
        exe = cmd[0]
        if exe == "soffice":
            if soffice_log is not None:
                soffice_log["active"] += 1
                soffice_log["max"] = max(soffice_log["max"], soffice_log["active"])
            try:
                if soffice_sleep:
                    time.sleep(soffice_sleep)
                if fail_soffice:
                    raise _called_process_error(cmd)
            finally:
                if soffice_log is not None:
                    soffice_log["active"] -= 1
            outdir = cmd[cmd.index("--outdir") + 1]
            Path(outdir, "in.pdf").write_bytes(b"%PDF-fake")
        elif exe == "pdftoppm":
            prefix = cmd[-1]
            Path(prefix + "-1.png").write_bytes(b"PNG")
            Path(prefix + "-2.png").write_bytes(b"PNG")
        return SimpleNamespace(returncode=0)

    return fake_run


class _PipelineEnv:
    """单条预览管线的无 DB 测试环境"""

    def __init__(self, tmp_path, monkeypatch, endpoint_name, locks_attr,
                 cache_dir_attr, file_name, key_func):
        self.tmp_path = tmp_path
        self.endpoint_name = endpoint_name
        self.endpoint = getattr(drive_files, endpoint_name)
        self.locks_attr = locks_attr
        self.locks = {}
        monkeypatch.setattr(drive_files, locks_attr, self.locks)
        monkeypatch.setattr(drive_files, cache_dir_attr,
                            lambda fid, key: tmp_path / f"{fid}_{key}")
        self.key_func = key_func
        self.fake_file = _fake_drive_file(1, file_name)
        monkeypatch.setattr(drive_files, "DriveService",
                            lambda db: _StubSvc(self.fake_file))

        async def _fake_download(key):
            return b"PK-fake-content"

        monkeypatch.setattr(drive_files.file_service, "download_file",
                            _fake_download)
        # 只 patch run, 保留 subprocess.DEVNULL 真实属性 (worker 传参要访问)
        monkeypatch.setattr(drive_files.subprocess, "run", _fake_run_factory())
        self.user = SimpleNamespace(id=1)

    def cache_dir(self):
        return self.tmp_path / f"1_{self.key_func(1, UPDATED)}"


def _fake_drive_file(file_id=1, name="a.pptx"):
    return SimpleNamespace(
        id=file_id, file_name=name, file_path=f"drive/{file_id}.bin",
        updated_at=UPDATED,
    )


def _pptx_env(tmp_path, monkeypatch):
    return _PipelineEnv(tmp_path, monkeypatch, "get_pptx_pages_status",
                        "_PPTX_CONVERT_LOCKS", "_pptx_cache_dir", "a.pptx",
                        lambda fid, u: _v1_key(u))


def _docx_env(tmp_path, monkeypatch):
    return _PipelineEnv(tmp_path, monkeypatch, "get_docx_pages_status",
                        "_DOCX_CONVERT_LOCKS", "_docx_cache_dir", "a.docx",
                        lambda fid, u: _v1_key(u))


def _pdf_env(tmp_path, monkeypatch):
    return _PipelineEnv(tmp_path, monkeypatch, "get_pdf_pages_status",
                        "_PDF_CONVERT_LOCKS", "_pdf_cache_dir", "a.pdf",
                        lambda fid, u: _v1_key(u))


def _xlsx_env(tmp_path, monkeypatch):
    return _PipelineEnv(tmp_path, monkeypatch, "get_xlsx_preview_status",
                        "_XLSX_PREVIEW_LOCKS", "_xlsx_cache_dir", "a.xlsx",
                        lambda fid, u: drive_files._xlsx_cache_key(u))


def _zip_env(tmp_path, monkeypatch):
    return _PipelineEnv(tmp_path, monkeypatch, "get_zip_list",
                        "_ZIP_PREVIEW_LOCKS", "_zip_cache_dir", "a.zip",
                        lambda fid, u: drive_files._zip_cache_key(u))


SUBPROCESS_PIPELINES = (_pptx_env, _docx_env, _pdf_env)
ALL_PIPELINES = (_pptx_env, _docx_env, _pdf_env, _xlsx_env, _zip_env)


def _wait_lock_released(locks, key, timeout=15.0):
    """等待 worker finally 清理锁表 (daemon 线程完成后 key 被 pop)"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if key not in locks:
            return True
        time.sleep(0.05)
    return False


def _write_error(cache_dir, message="soffice exploded", age_seconds=None):
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / "error.txt"
    p.write_text(message, encoding="utf-8")
    if age_seconds is not None:
        t = time.time() - age_seconds
        os.utime(p, (t, t))
    return p


# ---------- B1: worker 失败不得死锁, 锁表必须清理 ----------

def test_pptx_worker_failure_cleans_lock_table(tmp_path, monkeypatch):
    """失败分支: worker 线程必须结束且锁表 key 被 pop (旧代码在此永久挂起)"""
    key = _v1_key(UPDATED)
    cache_dir = tmp_path / "cache"
    src = tmp_path / "src.pptx"
    src.write_bytes(b"PKfake")
    lock = threading.Lock()
    lock.acquire()  # 模拟端点线程持锁 (旧代码端点 acquire 后永不释放)
    monkeypatch.setattr(drive_files, "_PPTX_CONVERT_LOCKS", {key: lock})
    monkeypatch.setattr(drive_files.subprocess, "run",
                        _fake_run_factory(fail_soffice=True))

    done = threading.Event()

    def _run():
        drive_files._pptx_convert_worker(1, str(src), cache_dir, key)
        done.set()

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    assert done.wait(timeout=10), "worker 线程 10s 未结束 — 失败分支死锁 (B1)"
    assert key not in drive_files._PPTX_CONVERT_LOCKS, "失败后锁表 key 未清理 (B1)"
    assert (cache_dir / "error.txt").exists(), "失败后未写 error.txt"


def test_pptx_worker_success_cleans_lock_table(tmp_path, monkeypatch):
    """成功路径: ready.json 写入 + 锁表 key 清理 (回归保护)"""
    key = _v1_key(UPDATED)
    cache_dir = tmp_path / "cache"
    src = tmp_path / "src.pptx"
    src.write_bytes(b"PKfake")
    monkeypatch.setattr(drive_files, "_PPTX_CONVERT_LOCKS", {key: threading.Lock()})

    drive_files._pptx_convert_worker(1, str(src), cache_dir, key)

    assert (cache_dir / "ready.json").exists()
    assert key not in drive_files._PPTX_CONVERT_LOCKS


def test_docx_worker_failure_cleans_lock_table(tmp_path, monkeypatch):
    """docx 同构回归: 失败不死锁"""
    key = _v1_key(UPDATED)
    cache_dir = tmp_path / "cache"
    src = tmp_path / "src.docx"
    src.write_bytes(b"PKfake")
    lock = threading.Lock()
    lock.acquire()
    monkeypatch.setattr(drive_files, "_DOCX_CONVERT_LOCKS", {key: lock})
    monkeypatch.setattr(drive_files.subprocess, "run",
                        _fake_run_factory(fail_soffice=True))

    done = threading.Event()
    th = threading.Thread(
        target=lambda: (drive_files._docx_convert_worker(1, str(src), cache_dir, key),
                        done.set()),
        daemon=True)
    th.start()
    assert done.wait(timeout=10), "docx worker 失败分支死锁 (B1)"
    assert key not in drive_files._DOCX_CONVERT_LOCKS


def test_pdf_worker_failure_cleans_lock_table(tmp_path, monkeypatch):
    """pdf 同构回归: 失败不死锁 (pdf 无 soffice, 仅 pdftoppm)"""
    key = _v1_key(UPDATED)
    cache_dir = tmp_path / "cache"
    src = tmp_path / "src.pdf"
    src.write_bytes(b"%PDFfake")

    def _fail_run(cmd, **kwargs):
        raise _called_process_error(cmd)

    lock = threading.Lock()
    lock.acquire()  # 模拟端点线程持锁 (旧代码端点 acquire 后永不释放)
    monkeypatch.setattr(drive_files, "_PDF_CONVERT_LOCKS", {key: lock})
    monkeypatch.setattr(drive_files.subprocess, "run", _fail_run)

    done = threading.Event()
    th = threading.Thread(
        target=lambda: (drive_files._pdf_convert_worker(1, str(src), cache_dir, key),
                        done.set()),
        daemon=True)
    th.start()
    assert done.wait(timeout=10), "pdf worker 失败分支死锁 (B1)"
    assert key not in drive_files._PDF_CONVERT_LOCKS


# ---------- B2: soffice 全局串行 + profile 隔离 ----------

@pytest.mark.parametrize("worker_name,locks_attr", [
    ("_pptx_convert_worker", "_PPTX_CONVERT_LOCKS"),
    ("_docx_convert_worker", "_DOCX_CONVERT_LOCKS"),
])
def test_soffice_global_gate_serializes_conversions(tmp_path, monkeypatch,
                                                    worker_name, locks_attr):
    """3 个并发 worker 的 soffice 执行必须完全串行 (max 并发 == 1)"""
    log = {"active": 0, "max": 0}
    monkeypatch.setattr(drive_files, locks_attr, {})
    monkeypatch.setattr(drive_files.subprocess, "run",
                        _fake_run_factory(soffice_log=log, soffice_sleep=0.15))
    worker = getattr(drive_files, worker_name)

    threads = []
    for i in range(3):
        cache_dir = tmp_path / f"c{i}"
        src = tmp_path / f"s{i}.bin"
        src.write_bytes(b"PKfake")
        th = threading.Thread(target=worker,
                              args=(10 + i, str(src), cache_dir, f"k{i}"),
                              daemon=True)
        threads.append(th)
        th.start()
    for th in threads:
        th.join(timeout=20)

    assert log["max"] == 1, f"soffice 并发 max={log['max']} — 未全局串行 (B2)"
    for i in range(3):
        assert (tmp_path / f"c{i}" / "ready.json").exists(), "串行后有 worker 未完成"


def test_pptx_soffice_uses_isolated_profile(tmp_path, monkeypatch):
    """pptx 的 soffice 调用必须带独立 UserInstallation (与默认/docx profile 隔离)"""
    seen_cmds = []
    monkeypatch.setattr(drive_files, "_PPTX_CONVERT_LOCKS", {})
    real_run = _fake_run_factory()

    def _record_run(cmd, **kwargs):
        if cmd[0] == "soffice":
            seen_cmds.append(cmd)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(drive_files.subprocess, "run", _record_run)
    src = tmp_path / "src.pptx"
    src.write_bytes(b"PKfake")

    drive_files._pptx_convert_worker(1, str(src), tmp_path / "cache",
                                     _v1_key(UPDATED))

    assert seen_cmds, "soffice 未被调用"
    joined = " ".join(seen_cmds[0])
    assert "-env:UserInstallation=" in joined, "pptx soffice 缺独立 profile 隔离"


# ---------- B3: error.txt 600s TTL 过期重试 (5 条管线) ----------

@pytest.mark.parametrize("env_factory", ALL_PIPELINES)
async def test_fresh_error_returns_error_without_reconvert(tmp_path, monkeypatch,
                                                           env_factory):
    """未过期 (刚失败) 的 error.txt 仍返回 error — 不误重转"""
    env = env_factory(tmp_path, monkeypatch)
    _write_error(env.cache_dir(), "boom", age_seconds=10)
    calls = {"n": 0}

    async def _count_download(key):
        calls["n"] += 1
        return b"x"

    monkeypatch.setattr(drive_files.file_service, "download_file",
                        _count_download)

    resp = await env.endpoint(1, db=None, current_user=env.user)
    assert resp["status"] == "error"
    assert "boom" in resp["message"]
    assert calls["n"] == 0, "fresh error 不应触发重新转换"
    assert env.cache_dir().joinpath("error.txt").exists(), \
        "fresh error 不应删除 error.txt"


@pytest.mark.parametrize("env_factory", ALL_PIPELINES)
async def test_expired_error_clears_and_reconverts(tmp_path, monkeypatch, env_factory):
    """过期 (>600s) 的 error.txt 被清除并触发重转"""
    env = env_factory(tmp_path, monkeypatch)
    key = env.key_func(1, UPDATED)
    _write_error(env.cache_dir(), "stale boom", age_seconds=660)

    resp = await env.endpoint(1, db=None, current_user=env.user)

    assert resp["status"] == "converting", "过期 error 应触发重转而非继续报错 (B3)"
    assert not env.cache_dir().joinpath("error.txt").exists(), "过期 error.txt 应被清除"
    assert _wait_lock_released(env.locks, key), "重转后锁表未清理"
    # subprocess 三管线 (pptx/docx/pdf) fake 转换必成功 → 再轮询应 ready
    if env_factory in SUBPROCESS_PIPELINES:
        resp2 = await env.endpoint(1, db=None, current_user=env.user)
        assert resp2["status"] == "ready"
        assert resp2["total"] == 2


# ---------- 端点锁模式回归: converting 去重 ----------

@pytest.mark.parametrize("env_factory", ALL_PIPELINES)
async def test_converting_dedupe_second_poll_returns_converting(tmp_path, monkeypatch,
                                                                env_factory):
    """首次触发转换后, worker 运行期间的轮询返回 converting 且不重复启动.

    用 _NoStartThread 让 worker 不真正运行 (锁保持占用), 测试确定性。
    """
    env = env_factory(tmp_path, monkeypatch)
    monkeypatch.setattr(drive_files.threading, "Thread", _NoStartThread)

    first = await env.endpoint(1, db=None, current_user=env.user)
    assert first["status"] == "converting"
    second = await env.endpoint(1, db=None, current_user=env.user)
    assert second["status"] == "converting", "转换期间重复轮询应去重为 converting"
