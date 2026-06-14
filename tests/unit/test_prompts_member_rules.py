"""回归测试：prompts.py Member Query Rules（2026-06-15 杜同贺痛点修复）

防止后续 prompt 重构时丢关键句：
- 「X 呢？」简写延续必须调 get_member_profile
- query_all_member_tasks 绝不能用于「X 呢？」单人查询
- 显式任务查询仍允许 query_tasks
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.agent.prompts import get_system_prompt


class TestMemberQueryRulesRegression:
    """Member Query Rules 关键句永久保留（防止 prompt 重构丢）"""

    def _prompt(self) -> str:
        return get_system_prompt()

    def test_x_ne_continue_member_profile_rule_present(self):
        """「X 呢？」简写延续 → get_member_profile 规则必须存在"""
        p = self._prompt()
        assert "X 呢？" in p or "「X 呢？」" in p, "Member Query Rules must cover 「X 呢？」"
        assert "get_member_profile" in p, "Must reference get_member_profile tool"

    def test_query_all_member_tasks_not_for_single_member(self):
        """query_all_member_tasks 绝不能用于「X 呢？」单人查询 — 关键警告必须存在"""
        p = self._prompt()
        # 必须显式禁止 query_all_member_tasks 用于单人查询
        assert "query_all_member_tasks" in p, "Rule about query_all_member_tasks must exist"
        # 锁定 Member Query Rules section（从 ## Member Query Rules 到下一个 ## 标题）
        section_start = p.find("## Member Query Rules")
        assert section_start != -1, "## Member Query Rules section must exist"
        section_end = p.find("\n## ", section_start + 1)
        if section_end == -1:
            section_end = len(p)
        section = p[section_start:section_end]
        # 在 Member Query Rules section 内必须有「不是单人资料」警告
        assert "query_all_member_tasks" in section, \
            "Member Query Rules section must mention query_all_member_tasks"
        assert "不是" in section or "不能" in section or "绝不能" in section, \
            "Member Query Rules section must warn query_all_member_tasks is NOT for single member"

    def test_explicit_task_query_still_allowed(self):
        """显式问任务「X 的任务」/「X 的工作清单」仍允许 query_tasks"""
        p = self._prompt()
        # 显式任务查询必须分流到 query_tasks（而非 get_member_profile）
        assert "query_tasks" in p, "query_tasks must be referenced"
        # 必须有「显式问任务」分流的句子
        assert (
            "显式问任务" in p or "具体任务" in p or "任务清单" in p
        ), "Explicit task query branch must exist in Member Query Rules"

    def test_member_query_rules_section_header_present(self):
        """Member Query Rules section 必须存在（防止被删）"""
        p = self._prompt()
        assert "## Member Query Rules" in p, "## Member Query Rules section must exist"

    def test_key_distinction_x_ne_covered(self):
        """Member Query Rules 必须明确「X 呢？」/「X 怎么样」/「X 做什么」覆盖"""
        p = self._prompt()
        # 简写延续列举
        for kw in ["X 呢？", "X 怎么样", "X 做什么"]:
            assert kw in p, f"Member Query Rules must list '{kw}' as shorthand patterns"

    def test_x_research_direction_uses_get_member_profile(self):
        """「X 的研究方向」/「XX 是研究什么的」必须 → get_member_profile"""
        p = self._prompt()
        # 这些完整句式必须存在
        for kw in ["XX 是研究什么的", "X 的研究方向", "XX 做什么研究"]:
            assert kw in p, f"Member Query Rules must cover full pattern '{kw}'"


class TestIntentClassifierPromptRegression:
    """intent_classifier.py 关键区分点永久保留（防止 LLM 分类器 prompt 重构丢）"""

    def test_x_ne_classified_as_search_info(self):
        """intent classifier 必须明确「X 呢？」→ search_info"""
        from app.agent.intent_classifier import _INTENT_PROMPT
        assert "X 呢？" in _INTENT_PROMPT
        assert "search_info" in _INTENT_PROMPT or "找资料" in _INTENT_PROMPT

    def test_x_research_question_classified_as_search_info(self):
        """「X 是研究什么的」/「X 做什么研究」必须 → search_info"""
        from app.agent.intent_classifier import _INTENT_PROMPT
        assert "X 是研究什么的" in _INTENT_PROMPT
        assert "X 做什么研究" in _INTENT_PROMPT

    def test_all_member_tasks_classified_as_data_query(self):
        """「所有成员任务」必须 → data_query（query_all_member_tasks）"""
        from app.agent.intent_classifier import _INTENT_PROMPT
        assert "所有成员任务" in _INTENT_PROMPT
        assert "query_all_member_tasks" in _INTENT_PROMPT
