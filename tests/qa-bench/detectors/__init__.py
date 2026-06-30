"""
detectors/__init__.py — 检测器注册表

每个检测器模块导出 `detect_xxx` 函数（约定）。
v3.0 计划：从 7 个内置检测器扩展到 15 个。

当前注册：
  P0 (现有 7 个，in runner.py):
    - fake_xml_leaked
    - internal_labels
    - placeholder_text
    - hallucinated_names
    - filler_phrases
    - duration
    - expect 字段对比
  P0 (新增 3 个):
    - stream_interrupt        [stream_interrupt.py]
    - tool_error_propagated   [tool_error_propagated.py]
    - first_token_latency     [first_token_latency.py]
  P1 (待 W2 阶段实现):
    - grounding_violation
    - citation_mismatch
  P2 (待 W3 阶段实现):
    - rich_block_malformed
    - ui_consistency
    - token_budget
    - idempotency
"""
from typing import Any, Callable, Dict, List

# 检测器注册表
# 格式: { "detector_name": { "module": "...", "function": "...", "priority": "P0/P1/P2" } }
DETECTORS: Dict[str, Dict[str, Any]] = {
    # 现有（在 runner.py 中）
    "fake_xml_leaked": {
        "module": "runner",
        "function": "detect_fake_xml_leaked",
        "priority": "P0",
        "kind": "content",
    },
    "internal_labels_leaked": {
        "module": "runner",
        "function": "detect_internal_labels",
        "priority": "P0",
        "kind": "content",
    },
    "placeholder_text": {
        "module": "runner",
        "function": "detect_placeholder_text",
        "priority": "P0",
        "kind": "content",
    },
    "hallucinated_names": {
        "module": "runner",
        "function": "detect_hallucinated_names",
        "priority": "P0",
        "kind": "content",
    },
    "filler_phrases": {
        "module": "runner",
        "function": "detect_filler_phrases",
        "priority": "P0",
        "kind": "content",
    },
    "duration": {
        "module": "runner",
        "function": None,  # 内置在 run_qa_test 中
        "priority": "P0",
        "kind": "performance",
    },
    "expect_mismatch": {
        "module": "runner",
        "function": "evaluate_expectation",
        "priority": "P0",
        "kind": "expect",
    },
    # 新增 3 个 P0 (W1 T1.3)
    "stream_interrupt": {
        "module": "detectors.stream_interrupt",
        "function": "detect_stream_interrupt",
        "priority": "P0",
        "kind": "stream",
    },
    "tool_error_propagated": {
        "module": "detectors.tool_error_propagated",
        "function": "detect_tool_error_propagated",
        "priority": "P0",
        "kind": "content",
    },
    "first_token_latency": {
        "module": "detectors.first_token_latency",
        "function": "detect_first_token_latency",
        "priority": "P1",  # P1 (建议 P0 但依赖 SSE timestamp)
        "kind": "performance",
    },
}


def get_detector(name: str) -> Callable:
    """动态加载检测器函数"""
    if name not in DETECTORS:
        raise ValueError(f"Unknown detector: {name}")

    spec = DETECTORS[name]
    if spec["module"] == "runner":
        # 现有 runner.py 中的检测器
        import runner
        return getattr(runner, spec["function"])
    elif spec["module"] and spec["module"].startswith("detectors."):
        # 新 detectors/ 目录下的检测器
        module_path = spec["module"]
        function_name = spec["function"]
        module = __import__(module_path, fromlist=[function_name])
        return getattr(module, function_name)
    else:
        raise ValueError(f"Invalid module spec: {spec['module']}")


def list_detectors(priority: str = None) -> List[str]:
    """列出所有检测器（可按优先级过滤）"""
    if priority is None:
        return list(DETECTORS.keys())
    return [n for n, s in DETECTORS.items() if s["priority"] == priority]


# 一致性自检
if __name__ == "__main__":
    print(f"Total detectors: {len(DETECTORS)}")
    print(f"P0: {len(list_detectors('P0'))}")
    print(f"P1: {len(list_detectors('P1'))}")
    print(f"P2: {len(list_detectors('P2'))}")
    print()

    # 逐个测试
    for name in DETECTORS:
        try:
            fn = get_detector(name)
            print(f"  ✓ {name}: {fn.__module__}.{fn.__name__}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
