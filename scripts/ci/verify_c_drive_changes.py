"""Verify the C-drive-prevention changes actually work, by executing them.

Covers:
  T4  offsite-oss-sync.py / rotate_offsite_passphrase.py  -> tempfile lands on E:
  T5  audio_processor.py                                  -> TORCH_HOME points at E:
                                                             and the model loads from there
  T2  desktop userData                                   -> MNB_USER_DATA honoured

Run from the repo root:
    python scripts/ci/verify_c_drive_changes.py
"""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

FAILURES = []


def check(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {label}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILURES.append(label)


print("=== T4: tempfile lands on E: ===")
# offsite-oss-sync.py
sys.path.insert(0, str(REPO / "apps" / "desktop" / "scripts" / "server"))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "oos", REPO / "apps" / "desktop" / "scripts" / "server" / "offsite-oss-sync.py"
)
oos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oos)

tmp_root = Path(oos._TMP_ROOT)
check("offsite _TMP_ROOT is on E:", str(tmp_root).upper().startswith("E:"), str(tmp_root))
tmp_root.mkdir(parents=True, exist_ok=True)
d = Path(tempfile.mkdtemp(prefix="verify-oos-", dir=tmp_root))
check("mkdtemp(dir=_TMP_ROOT) created it there", d.exists() and str(d).upper().startswith("E:"), str(d))
d.rmdir()

# rotate_offsite_passphrase.py
spec2 = importlib.util.spec_from_file_location(
    "rot", REPO / "scripts" / "backup" / "rotate_offsite_passphrase.py"
)
# it imports the sync script by path at module import time; that works because
# the sync script is a plain module. Guard it so a missing optional dep does
# not abort the whole check.
try:
    rot = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(rot)
    r_root = Path(rot._TMP_ROOT)
    check("rotate _TMP_ROOT is on E:", str(r_root).upper().startswith("E:"), str(r_root))
    r_root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".enc", delete=False, dir=r_root) as tf:
        tf.write(b"x")
        tmp = Path(tf.name)
    check("NamedTemporaryFile(dir=_TMP_ROOT) created it there", tmp.exists() and str(tmp).upper().startswith("E:"), str(tmp))
    tmp.unlink(missing_ok=True)
    d2 = Path(tempfile.mkdtemp(prefix="verify-", dir=r_root))
    check("mkdtemp(prefix=verify-, dir=_TMP_ROOT) created it there", d2.exists() and str(d2).upper().startswith("E:"), str(d2))
    d2.rmdir()
except SystemExit as exc:
    check("rotate module imported", False, f"SystemExit: {exc}")
except Exception as exc:
    check("rotate module imported", False, f"{type(exc).__name__}: {exc}")

print()
print("=== T5: TORCH_HOME points at E: and the model loads from there ===")
os.environ.pop("TORCH_HOME", None)
try:
    from app.services import audio_processor as ap
except Exception as exc:
    check("audio_processor imported", False, f"{type(exc).__name__}: {exc}")
    ap = None

if ap is not None:
    import numpy as np
    # segment_audio lives on the AudioProcessor CLASS; it has to be instantiated,
    # otherwise `self` would be bound to the first argument.
    try:
        proc = ap.AudioProcessor()
    except Exception as exc:
        proc = None
        check("AudioProcessor() instantiated", False, f"{type(exc).__name__}: {exc}")
    if proc is not None:
        before = os.environ.get("TORCH_HOME")
        audio = (np.random.randn(16000) * 0.01).astype(np.float32)
        try:
            out = proc.segment_audio(audio, 16000)
            after = os.environ.get("TORCH_HOME")
            check("segment_audio executed", True, f"{len(out)} segments")
            check("TORCH_HOME was set by the code", bool(after), str(after))
            check("TORCH_HOME is on E:", bool(after) and after.upper().startswith("E:"), str(after))
            hub = Path(after) / "hub" if after else None
            check("torch.hub root exists under TORCH_HOME", bool(hub and hub.exists()), str(hub))
            import torch
            check("torch.hub.get_dir() resolves into that root",
                  bool(after) and torch.hub.get_dir().upper().startswith(after.upper()),
                  torch.hub.get_dir())
        except Exception as exc:
            check("segment_audio executed", False, f"{type(exc).__name__}: {exc}")

print()
print("=== T2: desktop userData env ===")
# The value a NEWLY launched process gets is the user-level one (the Task
# Scheduler / Explorer compose the environment from the registry). The current
# process still carries the pre-change environment because it was started
# before the change - that is exactly the caveat the runbook documents.
import winreg

def user_env(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None

env = user_env("MNB_USER_DATA")
check("MNB_USER_DATA exists at the user level", bool(env), str(env))
if env:
    p = Path(env)
    check("MNB_USER_DATA is on E:", str(p).upper().startswith("E:"), str(p))
    check("MNB_USER_DATA exists", p.is_dir(), str(p))
    db = p / "data" / "workbench.db"
    check("workbench.db migrated there", db.exists(), f"{db} ({db.stat().st_size if db.exists() else 0} bytes)")
    tok = p / "data" / "session-token.enc"
    check("session-token.enc migrated there", tok.exists(), str(tok))
proc_env = os.environ.get("MNB_USER_DATA")
print(f"  NOTE  this process still sees MNB_USER_DATA={proc_env!r} "
      f"(started before the change; a new process gets the user-level value above)")

print()
if FAILURES:
    print(f"RESULT: {len(FAILURES)} check(s) FAILED: {FAILURES}")
    sys.exit(1)
print("RESULT: all checks passed")
