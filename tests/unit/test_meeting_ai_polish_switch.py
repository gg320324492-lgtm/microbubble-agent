"""tests/unit/test_meeting_ai_polish_switch.py — ai_polish 配置开关测试 (2026-10-09)

背景: 会议 255 (3331 段) 实测 ai_polish 切 68 批耗时 ~50-60min, 而产物 100% 被
"差异超过 10% 回退原文" 的兜底丢弃 (polish_real_change_ratio=0.0) —— 净收益为负。
主指挥决策: `MEETING_AI_POLISH_ENABLED` 默认 false, 流水线层提前返回,
润色代码本体保留 (env 设 true 即恢复)。

本文件覆盖三件事:
1. 质量门禁 `MeetingQualityEvaluator` 对 `ai_polish_skipped` 的处理
   —— 这是开关的**连带面**: 关掉润色后 `transcript_polished` 仍是"原文副本",
   照常判定会稳定误报 polish_no_effective_change **fail**, 把每场 >5min 会议的
   quality_status 钉死成 fail。纯函数, 无 DB 依赖。
2. `Settings` 的 bool 解析 (默认值 + true/false/1/0 字符串)。
3. 流水线闸的结构性回归锁 (AST): 闸必须真实存在、必须记 'skipped'、
   `polished_segments` 必须先于使用初始化 (类 20.146 UnboundLocalError 防回归)。
   —— Celery task 主体仍不可单测 (需 DB + celery eager), 沿用
   `test_post_meeting_tasks_pure.py` 既有边界, 不在此扩范围。

无 DB 依赖, 不写生产数据。
"""
from __future__ import annotations

import ast
import inspect

import pytest

from app.services import post_meeting_tasks as pmt
from app.services.meeting_quality_service import MeetingQualityEvaluator

REPO_SRC = "app/services/post_meeting_tasks.py"


# ==========================================================================
# helpers
# ==========================================================================


def _quality_input(*, polished, skipped: bool, duration: float = 900.0):
    """构造一份最小但能触发润色项判定的质量门禁输入。

    duration 默认 900s (>300 阈值) —— 短会议本就不判 0 段变化, 测不出差异。
    """
    transcript = [
        {"speaker": "发言人A", "text": "我们先看一下第一部分"},
        {"speaker": "发言人B", "text": "好的没问题"},
        {"speaker": "发言人A", "text": "那就继续往下"},
    ]
    return {
        "media_duration_seconds": duration,
        "audio_duration": duration,
        "transcript": transcript,
        "transcript_polished": polished,
        "summary": "一段有内容的摘要, 不是空串",
        "key_points": [{"point": "要点一"}],
        "decisions": [{"decision": "决议一"}],
        "ai_polish_skipped": skipped,
    }


def _run_source_tree():
    src = inspect.getsource(pmt)
    return ast.parse(src)


def _walk_all(statements):
    """ast.If.orelse 是**语句列表**, ast.walk 只吃单节点 —— 这里摊平遍历。"""
    for stmt in statements:
        yield from ast.walk(stmt)


def _find_polish_gate():
    """定位 `if not settings.MEETING_AI_POLISH_ENABLED:` 这个闸的 If 节点。"""
    for node in ast.walk(_run_source_tree()):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        # UnaryOp(Not, Attribute(Attribute(Name('settings')), 'MEETING_AI_POLISH_ENABLED'))
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            operand = test.operand
            if (
                isinstance(operand, ast.Attribute)
                and operand.attr == "MEETING_AI_POLISH_ENABLED"
                and isinstance(operand.value, ast.Name)
                and operand.value.id == "settings"
            ):
                return node
    return None


# ==========================================================================
# 1. 质量门禁: ai_polish_skipped 抑制误报
# ==========================================================================


class TestQualityGateSkippedPolish:
    def test_skipped_does_not_raise_polish_fail(self):
        """关掉润色 → 不得报 polish_no_effective_change fail。

        关掉后 transcript_polished 是原文副本 (post_meeting_tasks 用
        seg.get("text_polished", seg["text"]) 兜底), diff 必然 0;
        不抑制的话每场 >5min 会议 quality_status 都会被钉成 fail。
        """
        result = MeetingQualityEvaluator(
            _quality_input(polished=[{"speaker": "发言人A", "text": "我们先看一下第一部分"},
                                     {"speaker": "发言人B", "text": "好的没问题"},
                                     {"speaker": "发言人A", "text": "那就继续往下"}],
                           skipped=True)
        ).evaluate()

        codes = result.get("issue_codes") or [i["code"] for i in result["issues"]]
        assert "polish_no_effective_change" not in codes, (
            f"润色被配置关闭时不应报润色告警, 实际 issues={result['issues']}"
        )

    def test_skipped_records_metric_for_observability(self):
        """跳过也要留痕 —— run.metrics 里要能看出这场是没润色的。"""
        result = MeetingQualityEvaluator(
            _quality_input(polished=[], skipped=True)
        ).evaluate()
        assert result["metrics"].get("ai_polish_skipped") is True

    def test_not_skipped_still_fails_on_zero_change(self):
        """反向锁: 没跳过时 0 段变化的 fail 判定**必须保留**。

        防止本次改动把真实的润色失效告警一并关掉 (那会让会议 242/250 类事故
        静默通过质量门禁)。
        """
        polished = [{"speaker": "发言人A", "text": "我们先看一下第一部分"},
                    {"speaker": "发言人B", "text": "好的没问题"},
                    {"speaker": "发言人A", "text": "那就继续往下"}]
        result = MeetingQualityEvaluator(
            _quality_input(polished=polished, skipped=False)
        ).evaluate()

        codes = result.get("issue_codes") or [i["code"] for i in result["issues"]]
        assert "polish_no_effective_change" in codes, (
            "润色开启时 0 段变化仍应报 fail, 实际 issues=" f"{result['issues']}"
        )
        assert result["status"] == "fail"
        assert result["metrics"]["polish_real_change_ratio"] == 0.0

    def test_skipped_short_meeting_unaffected(self):
        """短会议 (<300s) 本就不判润色, 加不加 skip 都不该有润色 issue。"""
        polished = [{"speaker": "发言人A", "text": "一样的原文"}]
        on = MeetingQualityEvaluator(
            _quality_input(polished=polished, skipped=False, duration=60.0)
        ).evaluate()
        codes = on.get("issue_codes") or [i["code"] for i in on["issues"]]
        assert "polish_no_effective_change" not in codes


# ==========================================================================
# 2. Settings: 默认关闭 + bool 解析
# ==========================================================================


class TestSettingsSwitch:
    def test_default_is_disabled(self):
        from app.config import Settings

        s = Settings(_env_file=None)
        assert s.MEETING_AI_POLISH_ENABLED is False, (
            "主指挥决策: ai_polish 默认关闭 (每次省 ~1 小时)"
        )

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("true", True), ("True", True), ("1", True),
            ("false", False), ("False", False), ("0", False),
        ],
    )
    def test_bool_env_parsing(self, raw, expected):
        """env 恢复润色时 .env 里写 true/false/1/0 都要能正确解析。"""
        from app.config import Settings

        s = Settings(_env_file=None, MEETING_AI_POLISH_ENABLED=raw)
        assert s.MEETING_AI_POLISH_ENABLED is expected

    def test_distinct_from_service_layer_switch(self):
        """本开关与既有的 ENABLE_AI_POLISH(service 层兜底闸) 是两个独立开关。

        ENABLE_AI_POLISH 只在 polish_segments_with_cache 缓存未命中时短路,
        不跳批次循环、也不把阶段记成 skipped —— 不能拿它当本开关的替代。
        """
        from app.config import Settings

        s = Settings(_env_file=None)
        assert s.MEETING_AI_POLISH_ENABLED is False
        assert s.ENABLE_AI_POLISH is True, (
            "本次不改 ENABLE_AI_POLISH —— 它仍是 service 层兜底闸, 保持原值"
        )


# ==========================================================================
# 3. 流水线闸的结构性回归锁 (AST)
# ==========================================================================


class TestPipelineGateWiring:
    def test_gate_exists(self):
        gate = _find_polish_gate()
        assert gate is not None, (
            "post_meeting_tasks 必须有 `if not settings.MEETING_AI_POLISH_ENABLED:` 闸"
        )

    def test_skip_branch_persists_skipped_stage(self):
        gate = _find_polish_gate()
        assert gate is not None

        calls = [
            n for n in _walk_all(gate.body)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "_persist_stage"
        ]
        assert calls, "skip 分支必须调 _persist_stage 留阶段记录"

        call = calls[0]
        args = [a.value for a in call.args if isinstance(a, ast.Constant)]
        assert "ai_polish" in args, f"阶段名必须是 ai_polish, 实际 {args}"
        assert "skipped" in args, f"状态必须是 skipped, 实际 {args}"

        kw = {k.arg for k in call.keywords}
        assert "metrics" in kw, "skip 分支应带 metrics 说明跳过原因"

    def test_enabled_branch_still_calls_polish_and_persists_success(self):
        """开关打开时行为零变化: 仍调 polish_segments_batched + 记 success。"""
        gate = _find_polish_gate()
        assert gate is not None
        orelse = gate.orelse
        assert orelse, "闸必须有 else 分支 (开启时走原逻辑)"

        called = {
            n.func.id for n in _walk_all(orelse)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "_persist_stage" in called
        assert "polish_segments_batched" in called, (
            "开启分支必须仍调用 polish_segments_batched —— 润色代码本体不得删除"
        )

        statuses = [
            a.value for n in _walk_all(orelse)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == "_persist_stage"
            for a in n.args if isinstance(a, ast.Constant)
        ]
        assert "success" in statuses, f"开启分支应记 success, 实际 {statuses}"

    def test_polished_segments_initialized_before_use(self):
        """类 20.146 防回归: polished_segments 必须先初始化再使用。

        skip 路径不赋值, 若初始化只在 except 分支里, 后面
        `len(polished_segments)` 会抛 UnboundLocalError。
        """
        tree = _run_source_tree()
        fn = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "post_meeting_process"
        )
        # 收集所有对 polished_segments 的赋值行号
        assign_lines = [
            n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name) and t.id == "polished_segments"
        ]
        assert assign_lines, "polished_segments 必须有显式初始化"

        # 至少有一处初始化为空列表 []
        empty_inits = [
            n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "polished_segments"
                    for t in n.targets)
            and isinstance(n.value, ast.List)
            and not n.value.elts
        ]
        assert empty_inits, (
            "必须存在 `polished_segments = []` 显式初始化 (类 20.146 W2+N 修复)"
        )