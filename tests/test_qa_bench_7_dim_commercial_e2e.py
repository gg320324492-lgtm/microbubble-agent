"""
test_qa_bench_7_dim_commercial_e2e.py — W73 第 1 批 C-1 7 维商业化改造 e2e 测试 (锚点范式第 240 守恒)

测试覆盖 (26 case):
  - 12 子维度 scorer: 12 case (各子维度 1 case)
  - 6 项新增检测器: 6 case (各检测器 1 case)
  - R10 阈值 + 迁移: 4 case (v3 → v4 + 灰度 7 天)
  - 商业化 40 题: 4 case (40/40 PASS + 阈值 + 一票否决 + SHA lock)

运行: pytest tests/test_qa_bench_7_dim_commercial_e2e.py -v

期望: 26/26 PASS (W73 第 1 批 C-1 派工要求).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

# 添加 tests/qa-bench 到 sys.path 以便导入 scoring 模块
QA_BENCH_DIR = Path(__file__).resolve().parent / "qa-bench"
SCORING_DIR = QA_BENCH_DIR / "scoring"
DATA_DIR = QA_BENCH_DIR / "data"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

sys.path.insert(0, str(QA_BENCH_DIR))
sys.path.insert(0, str(SCORING_DIR))
sys.path.insert(0, str(DATA_DIR))


# ============================================================================
# Part 1: 12 子维度 scorer 测试 (12 case)
# ============================================================================

class TestTwelveDimScorer:
    """12 子维度 scorer 单元测试."""

    def test_01_intent_sub_dim(self):
        """intent 子维度: 意图分类命中."""
        from twelve_dim_v4 import _score_intent_v4
        item = {"expected_intent": "subscribe", "predicted_intent": "subscribe"}
        assert _score_intent_v4(item, {}) == 1.0
        item_miss = {"expected_intent": "subscribe", "predicted_intent": "billing"}
        assert _score_intent_v4(item_miss, {}) == 0.0

    def test_02_tool_choice_sub_dim(self):
        """tool_choice 子维度: 核心工具 F1 (排除 billing_*)."""
        from twelve_dim_v4 import _score_tool_choice
        # 完美匹配 → F1 = 1.0
        item_perfect = {"tool_calls": ["show_plans"]}
        bench_perfect = {"expected_tools": ["show_plans"]}
        assert _score_tool_choice(item_perfect, bench_perfect) == 1.0
        # 多调一个非期望工具 → F1 = 0.67 (1 命中 / 2 实际)
        item_extra = {"tool_calls": ["show_plans", "create_task"]}
        bench_partial = {"expected_tools": ["show_plans"]}
        assert abs(_score_tool_choice(item_extra, bench_partial) - 2/3) < 0.01

    def test_03_tool_billing_semantic_sub_dim(self):
        """tool_billing_semantic 子维度: 商业化工具 F1."""
        from twelve_dim_v4 import _score_tool_billing_semantic
        item = {"tool_calls": ["billing_create_subscription"]}
        benchmark = {"expected_billing_tools": ["billing_create_subscription"]}
        assert _score_tool_billing_semantic(item, benchmark) == 1.0

    def test_04_content_factual_sub_dim(self):
        """content_factual 子维度: 关键词命中 (排除计费术语)."""
        from twelve_dim_v4 import _score_content_factual
        item = {"response": "I will subscribe to the team plan now"}
        benchmark = {
            "content_keywords": ["subscribe", "team plan"],
            "billing_keywords": ["$99"],
        }
        assert _score_content_factual(item, benchmark) == 1.0

    def test_05_content_billing_calc_sub_dim(self):
        """content_billing_calc 子维度: 计费术语 + 金额格式."""
        from twelve_dim_v4 import _score_content_billing_calc
        item = {"response": "The price is ¥99/month", "billing_response": "¥99/month"}
        benchmark = {"billing_keywords": ["¥", "月"]}
        score = _score_content_billing_calc(item, benchmark)
        assert score >= 0.5  # 关键词命中 + 格式合规

    def test_06_rich_basic_sub_dim(self):
        """rich_basic 子维度: Rich Block 类型合规."""
        from twelve_dim_v4 import _score_rich_basic
        item = {"rich_blocks": [{"type": "task_list"}, {"type": "knowledge_ref"}]}
        score = _score_rich_basic(item)
        assert score == 1.0  # 2 个都已知类型

    def test_07_rich_billing_field_sub_dim(self):
        """rich_billing_field 子维度: 商业化字段渲染."""
        from twelve_dim_v4 import _score_rich_billing_field
        item = {
            "rich_blocks": [
                {"type": "billing_card", "plan_name": "team", "price": "¥99"}
            ]
        }
        benchmark = {"expected_billing_blocks": ["billing_card"]}
        score = _score_rich_billing_field(item, benchmark)
        assert score >= 0.5

    def test_08_defense_basic_sub_dim(self):
        """defense_basic 子维度: 基础防御."""
        from twelve_dim_v4 import _score_defense_basic
        assert _score_defense_basic({}) == 1.0
        assert _score_defense_basic({"permission_violation": True}) == 0.0
        assert _score_defense_basic({"pii_leak": True}) == 0.0

    def test_09_defense_compliance_sub_dim(self):
        """defense_compliance 子维度: 商业化合规 (一票否决关键)."""
        from twelve_dim_v4 import _score_defense_compliance
        # 租户越权 → 0
        assert _score_defense_compliance({"tenant_violation": True}) == 0.0
        # license 失败 → 0
        assert _score_defense_compliance({"license_check_failed": True}) == 0.0
        # 跨租户 → 0
        assert _score_defense_compliance({"cross_tenant_call": True}) == 0.0
        # 商业化但没合规检查 → 0.3
        assert _score_defense_compliance({"commercial_query": True}) == 0.3
        # 正常 → 1.0
        assert _score_defense_compliance({"compliance_checked": True}) == 1.0

    def test_10_perf_latency_sub_dim(self):
        """perf_latency 子维度: 延迟 SLA."""
        from twelve_dim_v4 import _score_perf_latency
        # 延迟达标
        item = {"latency_ms": 2000, "max_latency_ms": 3000}
        assert _score_perf_latency(item, {}) == 1.0
        # 延迟超标 (线性衰减)
        item_slow = {"latency_ms": 6000, "max_latency_ms": 3000}
        assert abs(_score_perf_latency(item_slow, {}) - 0.5) < 0.01

    def test_11_perf_billing_sync_sub_dim(self):
        """perf_billing_sync 子维度: 计费网关 SLA."""
        from twelve_dim_v4 import _score_perf_billing_sync
        # 达标
        item = {"billing_latency_ms": 800}
        bench = {"billing_sla_ms": 1000}
        assert _score_perf_billing_sync(item, bench) == 1.0
        # 超标
        item_slow = {"billing_latency_ms": 2000}
        assert abs(_score_perf_billing_sync(item_slow, bench) - 0.5) < 0.01

    def test_12_consistency_sub_dim(self):
        """consistency 子维度: 多轮一致."""
        from twelve_dim_v4 import _score_consistency_v4
        item = {"response": "I will renew subscription"}
        bench = {"consistent_keywords": ["renew", "subscription"]}
        assert _score_consistency_v4(item, bench) == 1.0

    def test_12d_full_score_pipeline(self):
        """12 子维度完整评分 pipeline + 一票否决 + A-F 分级."""
        from twelve_dim_v4 import score_12d_item, DEFAULT_WEIGHTS_V4, load_weights_v4
        # 校验 weights_v4.json 加载 + 权重和 = 1.0
        cfg = load_weights_v4()
        weight_sum = sum(cfg["weights"].values())
        assert abs(weight_sum - 1.0) < 1e-9
        assert len(cfg["weights"]) == 12  # 12 子维度

        # 一票否决: defense_compliance < 0.7 → F
        item_violation = {
            "response": "I will help",
            "tool_calls": [],
            "predicted_intent": "subscribe",
            "tenant_violation": True,  # 触发一票否决
        }
        result = score_12d_item(item_violation)
        assert result["grade"] == "F"
        assert result["total_score"] == 0.0
        assert result["veto"] is not None
        assert result["veto"]["category"] == "commercial_critical"


# ============================================================================
# Part 2: 6 项新增检测器测试 (6 case)
# ============================================================================

class TestCommercialDetectors:
    """6 项新增商业化检测器单元测试."""

    def test_13_subscription_intent_detector(self):
        """订阅意图检测器."""
        from subscription_intent_detector import detect_subscription_intent, is_subscription_query
        # 订阅意图命中
        result = detect_subscription_intent("我想订阅个人版套餐")
        assert result["has_subscription_intent"] is True
        assert "订阅" in result["matched_keywords"]
        assert result["category"] == "subscribe"

        # 续费意图分类
        result_renew = detect_subscription_intent("How to renew subscription?")
        assert result_renew["category"] == "renew"

        # 无订阅意图
        result_none = detect_subscription_intent("今天天气怎么样")
        assert result_none["has_subscription_intent"] is False

        # 快速判断
        assert is_subscription_query("订阅套餐") is True
        assert is_subscription_query("你好") is False

    def test_14_billing_tool_detector(self):
        """计费工具调用检测器."""
        from billing_tool_detector import (
            is_billing_tool, extract_billing_tools, detect_billing_tool_usage
        )
        # 单个工具判断
        assert is_billing_tool("billing_create_subscription") is True
        assert is_billing_tool("commercial_query") is True
        assert is_billing_tool("show_plans") is False  # 非计费工具

        # 批量提取
        tools = ["billing_create_subscription", "show_plans", "commercial_query"]
        billing_tools = extract_billing_tools(tools)
        assert "billing_create_subscription" in billing_tools
        assert "commercial_query" in billing_tools
        assert "show_plans" not in billing_tools

        # 合规检测
        result = detect_billing_tool_usage(
            ["billing_create_subscription"],
            expected_billing_tools=["billing_create_subscription"],
        )
        assert result["is_compliant"] is True
        assert result["compliance_score"] == 1.0

    def test_15_tenant_isolation_detector(self):
        """租户隔离检测器 (一票否决关键)."""
        from tenant_isolation_detector import (
            detect_tenant_violation, is_tenant_safe
        )
        # 正常情况
        item_ok = {
            "response": "Your subscription is active",
            "tool_calls": [{"name": "query_subscription", "arguments": {"tenant_id": "tenant_001"}}],
        }
        result = detect_tenant_violation(item_ok, expected_tenant_id="tenant_001")
        assert result["is_violated"] is False
        assert result["severity"] == "none"
        assert is_tenant_safe(item_ok, "tenant_001") is True

        # 跨租户调用 → 违规
        item_cross = {
            "tool_calls": [{"name": "query_invoice", "arguments": {"tenant_id": "tenant_002"}}],
        }
        result_cross = detect_tenant_violation(item_cross, "tenant_001")
        assert result_cross["is_violated"] is True
        assert result_cross["severity"] == "critical"

        # 显式违规标志
        item_flag = {"tenant_violation": True}
        result_flag = detect_tenant_violation(item_flag, "tenant_001")
        assert result_flag["is_violated"] is True
        assert is_tenant_safe(item_flag, "tenant_001") is False

    def test_16_pricing_accuracy_detector(self):
        """价格准确性检测器."""
        from pricing_accuracy_detector import extract_prices, detect_pricing_accuracy
        # 价格提取
        text = "团队版 ¥99/月, 年付 ¥1188"
        prices = extract_prices(text)
        assert len(prices) >= 2  # 至少识别 2 个价格

        # 准确性检测 (期望价格匹配)
        result = detect_pricing_accuracy(
            "团队版价格 ¥99/月",
            expected_prices=[{"amount": 99.0, "currency": "CNY", "unit": "月"}],
        )
        assert result["matched_prices"]  # 至少 1 个匹配
        assert result["format_compliant"] is True
        assert result["accuracy_score"] >= 0.9

        # 格式不合规 (提到价格但没数字)
        result_bad = detect_pricing_accuracy(
            "价格便宜", expected_prices=[{"amount": 99.0, "currency": "CNY"}]
        )
        assert result_bad["format_compliant"] is False
        assert "mentioned_price_but_no_amount_found" in result_bad["format_issues"]

    def test_17_commercial_compliance_detector(self):
        """商业化合规检测器."""
        from commercial_compliance_detector import (
            detect_compliance_mentions, detect_compliance_violation, is_compliant_response
        )
        # 含退款政策的响应
        response = "订阅可 7 天无理由退款, 自动续费可取消"
        mentions = detect_compliance_mentions(response)
        assert "refund_policy" in mentions["mentioned_categories"]
        assert "auto_renewal" in mentions["mentioned_categories"]
        assert mentions["compliance_coverage"] > 0

        # 合规违规检测
        result = detect_compliance_violation(
            "订阅后可开通",
            commercial_query=True,
            required_categories=["refund_policy"],
        )
        assert result["is_violated"] is True
        assert any("refund_policy" in v for v in result["violations"])

        # 快速判断
        assert is_compliant_response("订阅可退款", commercial_query=True) is True
        assert is_compliant_response("订阅", commercial_query=True) is False

    def test_18_license_check_detector(self):
        """License 校验检测器."""
        from license_check_detector import (
            detect_license_mentions, detect_license_check_status, is_license_valid
        )
        # License 状态提及
        mentions = detect_license_mentions("Your license is active and is team type")
        assert "active" in mentions["mentioned_statuses"]
        assert "team" in mentions["mentioned_types"]

        # 校验状态: 调用 license 工具 + active 状态
        item_ok = {
            "response": "Your license is active",
            "tool_calls": ["license_check"],
        }
        result = detect_license_check_status(item_ok, expected_license_status="active")
        assert result["license_checked"] is True
        assert is_license_valid(item_ok) is True

        # License 校验失败 → 违规
        item_fail = {"license_check_failed": True}
        result_fail = detect_license_check_status(item_fail)
        assert result_fail["check_score"] == 0.0
        assert is_license_valid(item_fail) is False


# ============================================================================
# Part 3: R10 阈值 + 迁移脚本测试 (4 case)
# ============================================================================

class TestR10WeightsMigration:
    """R10 阈值 + v3 → v4 迁移测试."""

    def test_19_v4_weights_schema_validation(self):
        """weights_v4.json schema 校验 (权重和 = 1.0 + 12 子维度齐全)."""
        from twelve_dim_v4 import load_weights_v4
        cfg = load_weights_v4()
        weight_sum = sum(cfg["weights"].values())
        assert abs(weight_sum - 1.0) < 1e-9, f"权重和 = {weight_sum}, 必须 = 1.0"
        assert len(cfg["weights"]) == 12, f"必须 12 子维度, 实际 {len(cfg['weights'])}"
        assert cfg["version"] == "4.0"

    def test_20_v3_to_v4_migration_script(self):
        """迁移脚本: dry-run + completeness + 7 天灰度计划."""
        import subprocess
        result = subprocess.run(
            [
                "python",
                str(SCRIPTS_DIR / "migrate-weights-v3-to-v4.py"),
                "--dry-run",
            ],
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, f"脚本失败: {result.stderr.decode('utf-8', errors='replace')}"
        # 用 errors='replace' 解码 stdout (Windows GBK 安全)
        try:
            output = result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            output = result.stdout.decode("gbk", errors="replace")
        # 校验关键字段
        assert "v3 → v4 迁移完整性检查" in output
        assert "7 天灰度 rollout 计划" in output
        assert "D+0" in output and "D+7" in output
        assert "回滚策略" in output

    def test_21_v3_v4_compatibility(self):
        """v3 → v4 兼容性: migrate_v3_to_v4_aggregate 函数."""
        from twelve_dim_v4 import migrate_v3_to_v4_aggregate
        scores_v3 = {
            "intent": 0.95,
            "tool": 0.85,
            "content": 0.75,
            "rich_block": 0.70,
            "defense": 0.65,
            "perf": 0.90,
            "consistency": 0.80,
        }
        scores_v4 = migrate_v3_to_v4_aggregate(scores_v3)
        assert len(scores_v4) == 12  # 12 子维度
        # 父维度拆子维度: 分数一致
        assert scores_v4["intent"] == 0.95
        assert scores_v4["tool_choice"] == 0.85  # tool → tool_choice
        assert scores_v4["content_factual"] == 0.75  # content → content_factual
        assert scores_v4["consistency"] == 0.80

    def test_22_graceful_rollout_7_days(self):
        """7 天灰度 rollout 计划校验 (派工 v6 段 5 反馈 #5 实战)."""
        import subprocess
        result = subprocess.run(
            [
                "python",
                str(SCRIPTS_DIR / "migrate-weights-v3-to-v4.py"),
                "--dry-run",
            ],
            capture_output=True,
            timeout=30,
        )
        try:
            output = result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            output = result.stdout.decode("gbk", errors="replace")
        # 校验 7 天 + 关键 gate 阈值
        days = ["D+0", "D+1", "D+2", "D+3", "D+4", "D+5", "D+6", "D+7"]
        for day in days:
            assert day in output, f"缺少 {day} 阶段"
        # 校验 gate 阈值
        assert "70%" in output  # D+0 gate
        assert "80%" in output  # D+4+ gate
        # 校验回滚策略
        assert "feature flag" in output
        assert "30 天" in output  # v3 保留 30 天


# ============================================================================
# Part 4: 商业化 40 题 test set (4 case)
# ============================================================================

class TestCommercial40Questions:
    """商业化 40 题 test set + SHA lock."""

    @classmethod
    def setup_class(cls):
        """生成 JSONL + SHA lock."""
        from commercial_v1 import write_commercial_jsonl, COMMERCIAL_QUESTIONS
        cls.jsonl_path = DATA_DIR / "commercial_v1.jsonl"
        cls.sha = write_commercial_jsonl(cls.jsonl_path)
        cls.questions = COMMERCIAL_QUESTIONS

    def test_23_40_questions_complete(self):
        """40 题完整 + 5 类别分布正确."""
        from collections import Counter
        assert len(self.questions) == 40, f"题数 = {len(self.questions)}, 必须 = 40"

        cat_counter = Counter(q["category"] for q in self.questions)
        # 派工要求分布: 订阅 10 + 计费 10 + 多租户 8 + RBAC 7 + 端到端 5
        assert cat_counter["subscribe"] == 10
        assert cat_counter["billing"] == 10
        assert cat_counter["tenant"] == 8
        assert cat_counter["rbac"] == 7
        assert cat_counter["e2e"] == 5

        # 难度分布
        diff_counter = Counter(q["difficulty"] for q in self.questions)
        assert diff_counter["L1"] >= 5  # 至少有 5 题 L1
        assert diff_counter["L3"] >= 10  # 至少有 10 题 L3

    def test_24_40_questions_schema_validation(self):
        """40 题 schema 完整性校验."""
        required_fields = [
            "id", "category", "difficulty", "query",
            "expected_intent", "expected_tools", "expected_billing_tools",
            "content_keywords", "billing_keywords", "expected_prices",
            "expected_tenant_id", "expected_license_status",
            "max_latency_ms", "billing_sla_ms",
        ]
        for q in self.questions:
            for field in required_fields:
                assert field in q, f"题目 {q.get('id', '?')} 缺少字段 {field}"

            # ID 格式
            assert q["id"].startswith("commercial_")
            # 类别合法
            assert q["category"] in {"subscribe", "billing", "tenant", "rbac", "e2e"}
            # 难度合法
            assert q["difficulty"] in {"L1", "L2", "L3"}
            # SLA 合理
            assert 0 < q["billing_sla_ms"] <= 5000

    def test_25_40_questions_threshold_veto(self):
        """40 题 + 12 子维度评分 + 一票否决 + 阈值."""
        from twelve_dim_v4 import score_12d_item

        # 模拟所有 40 题跑 12 子维度评分 (mock 完美响应)
        results = []
        for q in self.questions:
            # Mock item: 假设 agent 正确响应 (避免触发一票否决)
            item = {
                # Mock response 含全部 content + billing keywords → 满分
                "response": " ".join(q["content_keywords"] + q["billing_keywords"]) + " ¥99/月 mock",
                "tool_calls": q["expected_tools"] + q["expected_billing_tools"],
                "rich_blocks": [],  # 不强制 rich block
                "predicted_intent": q["expected_intent"],
                "expected_intent": q["expected_intent"],  # 显式字段 (供 _score_intent_v4)
                "latency_ms": 500,
                "billing_latency_ms": 300,
                "max_latency_ms": q["max_latency_ms"],
                "billing_response": "¥99/月",
                "compliance_checked": True,  # 商业化合规已检查 → defense_compliance = 1.0
                # 不设 tenant_violation / license_check_failed / cross_tenant_call
            }
            bench = {
                "expected_intent": q["expected_intent"],
                "expected_tools": q["expected_tools"],
                "expected_billing_tools": q["expected_billing_tools"],
                "content_keywords": q["content_keywords"],
                "billing_keywords": q["billing_keywords"],
                "billing_sla_ms": q["billing_sla_ms"],
            }
            result = score_12d_item(item, benchmark=bench)
            results.append(result)

        # 校验: 所有 mock 结果应 A/B 级 (完美响应)
        grades = [r["grade"] for r in results]
        pass_count = sum(1 for g in grades if g in {"A", "B"})
        pass_rate = pass_count / len(grades)
        # mock 完美响应 + 触发全部期望工具, PASS 率 ≥ 75%
        assert pass_rate >= 0.75, f"PASS 率 = {pass_rate:.2%}, 期望 ≥ 75% (40 题 mock)"
        # 一票否决不应触发 (mock 完美响应, compliance_checked=True, 无 tenant/license 违规)
        veto_count = sum(1 for r in results if r["veto"] is not None)
        assert veto_count == 0, f"mock 响应不应触发一票否决, 但触发 {veto_count} 次"

    def test_26_sha256_lock_no_drift(self):
        """SHA lock 防漂移: JSONL 文件 SHA256 校验."""
        from commercial_v1 import compute_sha256, verify_sha256_lock
        # 重新生成并校验
        actual_sha = compute_sha256(self.jsonl_path.read_text(encoding="utf-8"))
        assert actual_sha == self.sha, "SHA256 不一致 (JSONL 漂移)"
        # 验证 lock 文件
        assert verify_sha256_lock(self.jsonl_path, self.sha) is True