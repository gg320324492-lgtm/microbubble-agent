"""W84 第 1 批 B-1 P1-5 — app/core/llm.py docstring print → logger.debug.

docstring 例子用 print (注释里), 误导未来开发者.
派工前提铁律 12: 改前改后 grep 验证.
"""
from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_SETUP", "1")


def test_llm_py_has_no_active_print_calls():
    """P1-5: app/core/llm.py 内 print( 调用必须为 0 行.

    旧: line 263 docstring 例子 print(chunk).
    新: 改用 logger.debug(chunk).
    """
    import ast
    import inspect
    from pathlib import Path

    src_path = Path(__file__).parent.parent / "app" / "core" / "llm.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))

    def _walk(node):
        yield node
        for child in ast.iter_child_nodes(node):
            yield from _walk(child)

    violations = []
    for n in _walk(tree):
        if isinstance(n, ast.Call):
            func = n.func
            if isinstance(func, ast.Name) and func.id == "print":
                violations.append(inspect.getsourcefile(n) or "llm.py")

    assert not violations, f"print( found in llm.py at: {violations}"
