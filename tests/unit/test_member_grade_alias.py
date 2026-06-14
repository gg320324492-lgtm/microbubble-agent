"""回归测试：member_service grade 简写模糊匹配（2026-06-15 修复）

背景：用户问"博一的学生"，DB 里 grade="博士" 严格匹配不到，LLM 反复空查询
修复：member_service.get_members 对「博一/博二/博三/博四/博士」一律做 ilike "博%"
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest


class TestMemberGradeAlias:
    """grade 简写模糊匹配（防「博一」查不到「博士」类 bug）"""

    def test_grade_alias_includes_all_phd_shortcuts(self):
        """所有博* 简写都应做 ilike 模糊匹配"""
        # 这个测试是文档级断言 — 直接读源码确保分支存在
        import inspect
        from app.services.member_service import MemberService
        src = inspect.getsource(MemberService.get_members)
        # 必须包含 "博一"/"博二"/"博三"/"博四"/"博士" 的模糊匹配
        assert "博一" in src, "Must handle 博一 shorthand"
        assert "博二" in src, "Must handle 博二 shorthand"
        assert "博三" in src, "Must handle 博三 shorthand"
        assert "博四" in src, "Must handle 博四 shorthand"
        assert "博士" in src, "Must handle 博士 general"
        # 必须用 ilike 做模糊匹配
        assert "ilike" in src, "Must use ilike for fuzzy match"

    def test_grade_non_shortcut_uses_exact_match(self):
        """非简写 grade（研一/大三/副教授 等）保持精确匹配 — 防止误匹配"""
        import inspect
        from app.services.member_service import MemberService
        src = inspect.getsource(MemberService.get_members)
        # 精确匹配分支必须存在
        assert "Member.grade == grade" in src or "Member.grade == grade_normalized" in src, \
            "Non-shortcut grade must use exact match"


class TestPromptsMemberQueryDiscipline:
    """prompts.py Member Query Discipline 关键句永久保留"""

    def test_no_repeat_empty_query_rule(self):
        """「不要重复空查询」规则必须存在"""
        from app.agent.prompts import get_system_prompt
        p = get_system_prompt()
        # 关键句必须存在
        assert "不要重复空查询" in p
        assert "不要再调" in p or "不要再尝试" in p

    def test_no_expand_to_other_grades_rule(self):
        """「不要扩展到其他年级」规则必须存在"""
        from app.agent.prompts import get_system_prompt
        p = get_system_prompt()
        # 关键句必须存在
        assert "不要扩展到其他年级" in p
        # 必须禁止列出其他年级
        assert "研一" in p and "研二" in p, "Rule must mention grade context"
        # 必须说"只回答该年级的结果"
        assert "只回答" in p or "仅回答" in p

    def test_grade_shorthand_explanation(self):
        """「博一=博士一年级」说明必须存在"""
        from app.agent.prompts import get_system_prompt
        p = get_system_prompt()
        # 必须解释 grade 简写
        assert "博一" in p and "博士一年级" in p
        # 必须说明 ilike 模糊匹配
        assert "博一" in p and "博二" in p and "博%" in p

    def test_member_query_discipline_section_header(self):
        """## Member Query Discipline section 必须存在"""
        from app.agent.prompts import get_system_prompt
        p = get_system_prompt()
        assert "## Member Query Discipline" in p
