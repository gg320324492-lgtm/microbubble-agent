"""test_end_to_end.py — KB 闭环端到端 4 阶段串联测试 (W71 B-4)

W71 B-4 派工要求 6/6 e2e PASS:
  scenario_1: 4 阶段全过 → saved=True
  scenario_2: 阶段 1 veto → saved=False
  scenario_3: 阶段 2 防线 reject → saved=False
  scenario_4: 阶段 3 抽检 5% trigger → reviewed=True
  scenario_5: 阶段 3 抽检 95% skip → reviewed=False
  scenario_6: 阶段 4 rollback 7 天前 → rolled_back 接口契约

边界 (派工纪要 v6 段 7 + W68 第 6+7 批纪律沉淀):
- 不依赖 PostgreSQL (SKIP_DB_SETUP=1, pytest.ini 已有)
- 不连真实 Claude API (mock)
- 不修改 production code 老路径
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
from pathlib import Path

# 自包含 import: tests/qa-bench/kb_queue/end_to_end.py
# pytest 不会自动把它当 package, 需要 sys.path 注入
_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

from end_to_end import (  # noqa: E402
    KBLoopResult,
    kb_loop_end_to_end,
    auto_intake_rollback_dry,
    _local_score_item,
    _local_apply_five_defenses,
    _local_maybe_human_review,
    _enqueue_review_jsonl,
    ANCHOR_PARADIGM_ID,
)


class TestKBLoopEndToEnd:
    """KB 闭环 6 场景 e2e 测试"""

    def setup_method(self):
        """每个测试前清理 JSONL"""
        self.review_queue_path = Path("tests/qa-bench/data/admin_review_queue.jsonl")
        if self.review_queue_path.exists():
            self.review_queue_path.unlink()

    def teardown_method(self):
        """测试后清理 JSONL"""
        if self.review_queue_path.exists():
            self.review_queue_path.unlink()

    # ---------------------------------------------------------------
    # scenario_1: 4 阶段全过 → saved=True
    # ---------------------------------------------------------------
    def test_scenario_1_all_stages_pass(self):
        """阶段 1+2+3+4 全过, saved=True"""
        # 强制 grayscale 开启 + 答案文本满足所有防线
        with patch.dict(os.environ, {"AUTO_KB_INTAKE_ENABLED": "true"}):
            answer = "这是一段长文本" * 50  # > 200 字
            result = asyncio.run(kb_loop_end_to_end(answer))

        assert isinstance(result, KBLoopResult)
        assert result.saved is True, f"期望 saved=True, 实际 {result.saved}"
        assert result.stage_passed == 4, f"期望 stage_passed=4, 实际 {result.stage_passed}"
        assert result.score is not None
        assert result.score.get("veto") is None
        assert result.defense is not None
        assert result.defense.get("saved") is True
        assert result.defense.get("passed_count") == 5
        assert result.review is not None
        assert result.rollback_eligible_after_7d is True
        assert result.error is None

    # ---------------------------------------------------------------
    # scenario_2: 阶段 1 veto → saved=False
    # ---------------------------------------------------------------
    def test_scenario_2_stage1_veto(self):
        """阶段 1 (评分) 一票否决 → saved=False, stage_passed=0"""
        # 空内容触发 veto
        result = asyncio.run(kb_loop_end_to_end(""))

        assert result.saved is False
        assert result.stage_passed == 0, f"期望 stage_passed=0, 实际 {result.stage_passed}"
        assert result.veto is not None, "veto 必须被设置"
        assert result.veto == "empty_content"
        assert result.defense is None, "阶段 1 veto 时阶段 2 不应执行"

    # ---------------------------------------------------------------
    # scenario_3: 阶段 2 防线 reject → saved=False
    # ---------------------------------------------------------------
    def test_scenario_3_stage2_defense_reject(self):
        """阶段 2 (防线) 拦截 → saved=False, stage_passed=1"""
        # AUTO_KB_INTAKE_ENABLED 未开启 → 防线 4 拦截
        env_backup = os.environ.pop("AUTO_KB_INTAKE_ENABLED", None)
        try:
            # 文本长度足够通过阶段 1 评分 (>= 500 字让 completeness 维度达标)
            answer = "足够长的答案文本内容用于通过阶段 1 评分检查的样例 " * 15  # 600+ 字
            result = asyncio.run(kb_loop_end_to_end(answer))
        finally:
            if env_backup is not None:
                os.environ["AUTO_KB_INTAKE_ENABLED"] = env_backup

        assert result.saved is False
        assert result.stage_passed == 1, f"期望 stage_passed=1, 实际 {result.stage_passed}"
        assert result.score is not None
        assert result.score.get("veto") is None, "阶段 1 不应 veto (答案够长)"
        assert result.defense is not None
        assert result.defense.get("saved") is False
        assert result.defense.get("blocked_by") == "grayscale"

    # ---------------------------------------------------------------
    # scenario_4: 阶段 3 抽检 5% trigger → reviewed=True
    # ---------------------------------------------------------------
    def test_scenario_4_stage3_review_trigger(self):
        """强制 random < 0.05 → reviewed=True"""
        # mock random.random 强制触发抽检
        with patch.dict(os.environ, {"AUTO_KB_INTAKE_ENABLED": "true"}):
            with patch("end_to_end.random.random", return_value=0.01):
                answer = "长文本测试" * 100
                result = asyncio.run(kb_loop_end_to_end(answer))

        assert result.saved is True
        assert result.review is not None
        assert result.review.get("reviewed") is True, "5% 抽检应触发 reviewed=True"
        assert result.review.get("pending_admin") is True
        assert result.review.get("priority") == "medium"
        assert "queue_id" in result.review, "应写入 JSONL 并返回 queue_id"

        # 验证 JSONL 落盘
        assert self.review_queue_path.exists(), "JSONL 文件应已创建"
        lines = self.review_queue_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["status"] == "pending"
        assert record["priority"] == "medium"

    # ---------------------------------------------------------------
    # scenario_5: 阶段 3 抽检 95% skip → reviewed=False
    # ---------------------------------------------------------------
    def test_scenario_5_stage3_review_skip(self):
        """强制 random >= 0.05 → reviewed=False"""
        with patch.dict(os.environ, {"AUTO_KB_INTAKE_ENABLED": "true"}):
            with patch("end_to_end.random.random", return_value=0.99):
                answer = "长文本测试" * 100
                result = asyncio.run(kb_loop_end_to_end(answer))

        assert result.saved is True
        assert result.review is not None
        assert result.review.get("reviewed") is False, "95% 应跳过抽检"
        assert result.review.get("pending_admin") is False

        # JSONL 不应被写入
        assert not self.review_queue_path.exists(), "95% 跳过不应写入 JSONL"

    # ---------------------------------------------------------------
    # scenario_6: 阶段 4 rollback 7 天前 → 接口契约
    # ---------------------------------------------------------------
    def test_scenario_6_stage4_rollback_contract(self):
        """阶段 4 rollback 接口契约 (B-3 Celery 7 天 dry-run)"""
        # 模拟 7 天前 cutoff
        cutoff = datetime.utcnow() - timedelta(days=7)

        # 接口契约: 返回 list[int] (空 list, 因为不连真实 DB)
        result = auto_intake_rollback_dry(cutoff=cutoff, rollback_days=7)
        assert isinstance(result, list), "rollback 接口应返回 list[int]"
        assert result == [], "无 DB 连接时应返回空 list (B-3 实际执行由 Celery task)"

        # 验证 cutoff 计算正确
        with patch.dict(os.environ, {"AUTO_KB_INTAKE_ENABLED": "true"}):
            answer = "rollback 测试" * 50
            full_result = asyncio.run(kb_loop_end_to_end(answer))
        assert full_result.rollback_eligible_after_7d is True


class TestKBSubComponents:
    """B-4 子组件单元测试 (防御性回归)"""

    def test_score_item_empty(self):
        """空内容触发 veto"""
        score = _local_score_item("")
        assert score["veto"] == "empty_content"
        assert score["grade"] == "F"

    def test_score_item_too_short(self):
        """过短内容触发 veto"""
        score = _local_score_item("短")
        assert score["veto"] == "too_short"

    def test_score_item_valid(self):
        """正常文本通过评分"""
        answer = "正常长度的答案" * 50  # > 500 字
        score = _local_score_item(answer)
        assert score.get("veto") is None
        assert score["grade"] in ("A", "B", "C")

    def test_five_defenses_no_grayscale(self):
        """灰度未开启时防线 4 拦截"""
        env_backup = os.environ.pop("AUTO_KB_INTAKE_ENABLED", None)
        try:
            result = _local_apply_five_defenses("内容" * 200)
        finally:
            if env_backup is not None:
                os.environ["AUTO_KB_INTAKE_ENABLED"] = env_backup

        assert result["saved"] is False
        assert result["blocked_by"] == "grayscale"

    def test_five_defenses_too_short(self):
        """内容过短时防线 1 (content_length_min) 拦截"""
        with patch.dict(os.environ, {"AUTO_KB_INTAKE_ENABLED": "true"}):
            result = _local_apply_five_defenses("短")  # 1 字, < 100 字
        assert result["saved"] is False
        assert result["blocked_by"] == "content_length_min"

    def test_five_defenses_full_pass(self):
        """5 道防线全过"""
        with patch.dict(os.environ, {"AUTO_KB_INTAKE_ENABLED": "true"}):
            result = _local_apply_five_defenses("内容" * 200)
        assert result["saved"] is True
        assert result["passed_count"] == 5

    def test_anchor_paradigm_id(self):
        """锚点范式第 199 守恒"""
        assert ANCHOR_PARADIGM_ID == 199


if __name__ == "__main__":
    # 直接运行: python -m tests.qa_bench.kb_queue.test_end_to_end
    pytest.main([__file__, "-v"])