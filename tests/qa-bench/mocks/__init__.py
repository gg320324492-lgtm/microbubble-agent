"""W71 B 路线 5 Agents SubAgent 编排 mock loader.

加载 tests/qa-bench/mocks/ 下的 JSON 模板, 用于 B-2/B-3/B-4/B-5 agent
接口契约验证 (派工 v6 段 6 实战).

用法 (qa-bench conftest 会自动 prepend tests/qa-bench/ 到 sys.path)::

    from mocks import load_mock

    b1_output = load_mock("score_item")             # B-1 输出
    b2_output = load_mock("defense")                 # B-2 输出 (list[dict])
    b3_output = load_mock("rollback")               # B-3 输出 (list[dict])
    b4_output = load_mock("kb_loop")                # B-4 输出 (dict)

接口契约详见 docs/w71-batch-orchestration-2026-07-24.md §2.

typing 完备 (派工前提错误复盘 #2: 必含 __future__ + typing):
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MOCKS_DIR = Path(__file__).parent

_MOCK_FILES: dict[str, str] = {
    "score_item": "score_item.json",
    "defense": "defense.json",
    "rollback": "rollback.json",
    "kb_loop": "kb_loop.json",
}


def load_mock(name: str) -> Any:
    """加载指定 mock JSON 模板.

    Args:
        name: mock 简称, 支持: score_item / defense / rollback / kb_loop

    Returns:
        mock 内容 (dict 或 list, 视具体 mock 而定)

    Raises:
        KeyError: name 不在 _MOCK_FILES 中
        FileNotFoundError: mock 文件缺失
    """
    if name not in _MOCK_FILES:
        raise KeyError(
            f"未知 mock 名称: {name!r}, 合法值: {sorted(_MOCK_FILES.keys())}"
        )
    path = MOCKS_DIR / _MOCK_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"mock 文件缺失: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_mocks() -> list[str]:
    """返回所有可用 mock 简称 (调试用)."""
    return sorted(_MOCK_FILES.keys())


__all__ = ["load_mock", "list_mocks", "MOCKS_DIR"]