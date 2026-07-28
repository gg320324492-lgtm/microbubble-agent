"""W83 B-1 P1-4: agentic_loop silent except 3 处 e2e

验证 agentic_loop.py 三处静默 except 已被修复:
1. ``compress_tool_result`` 失败: 之前 ``logger.warning`` 继续无 fallback → 现在
   logger.error + 标记 ``compression_failed=True`` 注入 round_results + continue.
2. tool_result inner parse 失败: 之前 ``except Exception: pass`` 吞错 → 现在
   logger.warning + 把 tool 视为空 (``empty_tools.append``) 让模型看到"数据缺失"警告.
3. ``_normalize_fake_tool_input`` 失败: 之前 ``return input_dict`` 含 LLM 幻想字段
   污染 Pydantic → 现在 logger.error + 返回 known_fields-only safe_copy (或空 dict
   让 Pydantic 显式报错).

防 silent regression: 用户看到"模型编造"现象时, 监控/告警能捕获这些异常.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from app.agent.agentic_loop import _normalize_fake_tool_input


class TestW83B1AgenticLoopSilentExcept:
    """W83 B-1 P1-4: agentic_loop 3 处 silent except 修复验证."""

    # ----- P1-4.1: _normalize_fake_tool_input -----

    def test_normalize_unknown_tool_logs_warning_not_silent(self, caplog):
        """P1-4.1.1: 工具未注册时打 warning, 不再静默 return."""
        with caplog.at_level(logging.WARNING, logger="app.agent.agentic_loop"):
            result = _normalize_fake_tool_input("totally_fake_tool_xyz", {"name": "x"})
            # 必须打 warning (不是 silent bypass)
            assert any("not in TOOL_REGISTRY" in r.message for r in caplog.records), \
                "expected warning when tool not in TOOL_REGISTRY"
            # 仍返回原 input_dict (让 Pydantic 报错暴露给模型)
            assert result == {"name": "x"}

    def test_normalize_strips_unknown_fields_silently_after_processing(self):
        """P1-4.1.2: 正常路径过滤 unknown field (existing 行为)."""
        # 用真实注册工具 (假设 get_member_profile 已注册)
        # 如果没注册则跳过
        from app.agent.tool_registry import TOOL_REGISTRY
        if not TOOL_REGISTRY.get("get_member_profile"):
            pytest.skip("get_member_profile not registered (test 环境允许)")
        result = _normalize_fake_tool_input(
            "get_member_profile",
            {"name": "张三", "fake_field": "value", "member_id": 1},
        )
        assert "fake_field" not in result
        assert "fake_field" not in result.values() or result.get("fake_field") is None

    def test_normalize_empty_input_returns_empty(self):
        """P1-4.1.3: 空 input → 空 dict (existing 行为)."""
        assert _normalize_fake_tool_input("any_tool", {}) == {}
        assert _normalize_fake_tool_input("any_tool", None) is None

    def test_normalize_fallback_logs_error_when_registry_lookup_fails(self, caplog, monkeypatch):
        """P1-4.1.4: TOOL_REGISTRY 抛异常 → logger.error + safe fallback (known_fields only)."""
        from app.agent import agentic_loop

        # 模拟 TOOL_REGISTRY.get 抛异常 — 通过 monkeypatch agentic_loop 内部的 import
        # (TOOL_REGISTRY 是 dict, get 是 dict 原生方法, 不能 monkeypatch dict.get)
        # 用一个会抛异常的 fake 模块
        class BrokenToolRegistry:
            @staticmethod
            def get(name):
                raise RuntimeError("simulated registry broken")

        import sys
        fake_mod = type(sys)("app.agent.tool_registry")
        fake_mod.TOOL_REGISTRY = BrokenToolRegistry()
        # 在 agentic_loop 模块里 ``from app.agent.tool_registry import TOOL_REGISTRY``
        # → sys.modules 替换
        original = sys.modules.get("app.agent.tool_registry")
        sys.modules["app.agent.tool_registry"] = fake_mod
        try:
            with caplog.at_level(logging.ERROR, logger="app.agent.agentic_loop"):
                result = _normalize_fake_tool_input("any_tool", {"name": "x", "id": 1, "fake": "y"})
                # 必须打 error
                assert any("failed" in r.message.lower() for r in caplog.records), \
                    "expected error log when registry lookup fails"
                # fallback 返空 dict (Pydantic 会报"缺少必填字段"暴露给模型)
                assert result == {}, f"expected empty dict fallback, got {result}"
        finally:
            sys.modules["app.agent.tool_registry"] = original

    # ----- P1-4.2 / P1-4.3: agentic_loop 内部 silent excepts -----

    def test_agentic_loop_module_imports(self):
        """P1-4.2.1: agentic_loop 可正常 import (无 import-time error)."""
        from app.agent import agentic_loop  # noqa: F401
        # 进一步验证关键函数存在
        assert hasattr(agentic_loop, "_normalize_fake_tool_input")
        assert hasattr(agentic_loop, "compress_tool_result")
        assert hasattr(agentic_loop, "_sanitize_pending_tool_uses")

    def test_compress_tool_result_handled_by_error_path_in_source(self):
        """P1-4.2.2: 源码验证 compress_tool_result except 块不再静默吞错.

        源码层面 grep — 验证 logger.error + ``compression_failed`` 标记 + continue.
        防 regression: 未来有人改回 ``pass`` 直接 fail test.
        """
        import pathlib
        p = pathlib.Path(__file__).resolve().parent.parent / "app/agent/agentic_loop.py"
        src = p.read_text(encoding="utf-8")
        # 找 compress_tool_result 块
        idx = src.find("compression = await compress_tool_result(")
        assert idx > 0, "compress_tool_result call not found"
        # 找对应的 except 块 (向后 500 字符)
        except_idx = src.find("except Exception as e:", idx)
        assert except_idx > 0, "except block not found for compress_tool_result"
        # 限制 except block 在 1500 字符内 (避免进入下一个 except)
        except_block = src[except_idx:except_idx + 1500]
        # 验证有 logger.error (不是 logger.warning)
        assert "logger.error" in except_block, \
            "compress_tool_result except should use logger.error (not warning) for visibility"
        # 验证有 compression_failed 标记 (fallback signal)
        assert "compression_failed" in except_block, \
            "compress_tool_result except should mark compression_failed=True for fallback"
        # 验证有 continue (跳出本轮, 避免重复 append)
        assert "continue" in except_block, \
            "compress_tool_result except should continue to avoid double-append"

    def test_empty_tools_parse_handled_by_error_path_in_source(self):
        """P1-4.2.3: 源码验证 empty_tools inner-parse except 块不再 ``pass``."""
        import pathlib
        p = pathlib.Path(__file__).resolve().parent.parent / "app/agent/agentic_loop.py"
        src = p.read_text(encoding="utf-8")
        idx = src.find("json.loads(inner)")
        assert idx > 0
        except_idx = src.find("except Exception as e:", idx)
        assert except_idx > 0
        except_block = src[except_idx:except_idx + 1500]
        # 验证 logger.warning
        assert "logger.warning" in except_block, \
            "inner-parse except should use logger.warning"
        # 验证 empty_tools.append (兜底: 解析失败也视为空)
        assert "empty_tools.append" in except_block, \
            "inner-parse except should append to empty_tools (treat as empty)"
        # 验证 not just a bare pass — the immediate next line after except header
        # must NOT be only pass.
        # find end of ``except Exception as e:`` line
        next_newline = except_block.find("\n")
        after_except_header = except_block[next_newline + 1: next_newline + 200]
        assert not after_except_header.lstrip().startswith("pass"), \
            f"inner-parse except block should NOT start with bare pass, got: {after_except_header[:50]!r}"

    def test_normalize_fake_tool_input_except_handled_by_error_path_in_source(self):
        """P1-4.2.4: 源码验证 _normalize_fake_tool_input except 不再 ``return input_dict``."""
        import pathlib
        import re
        p = pathlib.Path(__file__).resolve().parent.parent / "app/agent/agentic_loop.py"
        src = p.read_text(encoding="utf-8")
        # 找 _normalize_fake_tool_input 函数
        idx = src.find("def _normalize_fake_tool_input")
        assert idx > 0
        # 找函数内 except 块 (顶层 except, 排除 fallback 的 nested except)
        except_idx = src.find("except Exception as e:", idx)
        assert except_idx > 0
        # 限制在 except block 内: 直到函数结束 (下一个 ``def `` / 文件尾)
        next_def = src.find("\ndef ", except_idx)
        end = next_def if next_def > 0 else len(src)
        except_block = src[except_idx:end]
        # 验证 logger.error (不是 logger.warning)
        assert "logger.error" in except_block, \
            "_normalize_fake_tool_input except should use logger.error"
        # 验证 fallback 是 filtered / empty dict, 不是 input_dict
        # 排除 comment 提及 (中文 docstring 可能说"不再 return input_dict")
        # 用 ``re.findall(r"^\s*return input_dict", ...)`` 只匹配真 return 语句
        bad_returns = re.findall(r"^\s*return input_dict\b", except_block, re.MULTILINE)
        assert not bad_returns, \
            f"_normalize_fake_tool_input except should NOT have 'return input_dict' as code, found {bad_returns}"