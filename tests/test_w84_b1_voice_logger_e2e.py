"""W84 第 1 批 B-1 P1-8 — app/voice/ + app/utils/audio.py print → logger.

派工前提铁律 12 (类 20.13 实战 18 派生): 修 silent print 必先 grep 实测.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

os.environ.setdefault("SKIP_DB_SETUP", "1")


def _collect_print_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = []

    def _walk(node):
        yield node
        for child in ast.iter_child_nodes(node):
            yield from _walk(child)

    for n in _walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print":
            lines.append(n.lineno)
    return lines


def test_voice_recorder_no_print():
    """P1-8: app/voice/recorder.py 内 print( 调用必须为 0 行."""
    repo_root = Path(__file__).parent.parent
    target = repo_root / "app" / "voice" / "recorder.py"
    assert not _collect_print_calls(target), (
        f"recorder.py 含 print 调用, 应改 logger: {target}"
    )


def test_voice_segmenter_no_print():
    """P1-8: app/voice/segmenter.py 内 print( 调用必须为 0 行 (派工前提列出范围)."""
    repo_root = Path(__file__).parent.parent
    target = repo_root / "app" / "voice" / "segmenter.py"
    assert not _collect_print_calls(target), (
        f"segmenter.py 含 print 调用, 应改 logger: {target}"
    )


def test_utils_audio_no_print():
    """P1-8: app/utils/audio.py 内 print( 调用必须为 0 行.

    旧: cleanup except: pass → silent.
    新: logger.warning(..., exc_info=True).
    """
    repo_root = Path(__file__).parent.parent
    target = repo_root / "app" / "utils" / "audio.py"
    assert not _collect_print_calls(target), (
        f"audio.py 含 print 调用: {target}"
    )
