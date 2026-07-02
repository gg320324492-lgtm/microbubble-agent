"""qa-bench runner 智能过滤单测 — Round 9 数据 bug 修复

覆盖 3 类 qa-bench 数据 bug + 3 组工具语义等价 + 评分 defense 维度过滤:
1. forbidden_names ∩ must_contain_any (Step 1 修复延续)
2. forbid 名字在 query 里 (Round 9 新增)
3. query 是"列出/所有"题型 (Round 9 新增)
4. get_member_profile ≈ query_members 语义等价
5. query_tasks ≈ query_member_tasks 语义等价
6. search_knowledge ≈ web_search 语义等价
7. severity=info/warn 不阻塞 verdict (Round 9 新增)
8. content 维度评分过滤数据 bug (Round 9 新增)

设计原则 (2026-07-02 Round 9 沉淀):
- 数据 bug 不应阻塞真问题: severity=warn/info 永远不阻塞 verdict
- 工具语义等价: 实际调用更精准工具 (单成员查询 vs 列表查询) 算满足 expect
"""
import sys
from pathlib import Path

# 允许直接 import runner.py (runner.py 在 tests/qa-bench/ 目录)
sys.path.insert(0, str(Path(__file__).parent / "qa-bench"))

# 顶层 import (runner.py 在 qa-bench 子目录)
from runner import (
    _expand_tools_with_equivalents,
    _forbidden_names_in_query,
    _is_listing_question,
    evaluate_expectation,
    TOOL_SEMANTIC_EQUIVALENTS,
)


# === Case 1: 工具语义等价 (get_member_profile ≈ query_members) ===
def test_equivalent_get_member_profile_to_query_members():
    """query_members 期望, 实际调 get_member_profile (单成员查询), 不应 missing_tools"""
    actual = {
        "tools_called": ["get_member_profile"],
        "content": "王天志是博士生...",
        "question": "王天志是干什么的？",
    }
    expect = {"tools_any": ["query_members"]}
    issues = evaluate_expectation(expect, actual)
    missing = [i for i in issues if i["type"] == "missing_tools"]
    assert len(missing) == 0, f"语义等价应满足, 但被判 missing_tools: {missing}"
    print("  ✅ Case 1: get_member_profile ≈ query_members 语义等价")


# === Case 2: 工具语义等价 (query_tasks ≈ query_member_tasks) ===
def test_equivalent_query_tasks_to_query_member_tasks():
    """query_member_tasks 期望, 实际调 query_tasks, 不应 missing_tools"""
    actual = {
        "tools_called": ["query_tasks"],
        "content": "王天志有 3 个未完成任务...",
        "question": "王天志手上还有多少个未完成的任务？",
    }
    expect = {"tools_any": ["query_member_tasks"]}
    issues = evaluate_expectation(expect, actual)
    missing = [i for i in issues if i["type"] == "missing_tools"]
    assert len(missing) == 0, f"query_tasks ≈ query_member_tasks 应满足, 但被判 missing: {missing}"
    print("  ✅ Case 2: query_tasks ≈ query_member_tasks 语义等价")


# === Case 2b: Round 9 smoke 30 发现 query_all_member_tasks 也应语义等价 ===
def test_equivalent_query_all_member_tasks_to_query_member_tasks():
    """query_member_tasks 期望, 实际调 query_all_member_tasks (B 类任务), 不应 missing_tools"""
    actual = {
        "tools_called": ["query_all_member_tasks"],
        "content": "课题组任务: ...",
        "question": "课题组任务完成率是多少?",
    }
    expect = {"tools_any": ["query_member_tasks"]}
    issues = evaluate_expectation(expect, actual)
    missing = [i for i in issues if i["type"] == "missing_tools"]
    assert len(missing) == 0, f"query_all_member_tasks ≈ query_member_tasks 应满足, 但被判 missing: {missing}"
    print("  ✅ Case 2b: query_all_member_tasks ≈ query_member_tasks 语义等价 (B 类任务新发现)")


# === Case 3: 工具语义等价 (search_knowledge ≈ web_search) ===
def test_equivalent_search_knowledge_to_web_search():
    actual = {"tools_called": ["web_search"], "content": "...", "question": "..."}
    expect = {"tools_any": ["search_knowledge"]}
    issues = evaluate_expectation(expect, actual)
    missing = [i for i in issues if i["type"] == "missing_tools"]
    assert len(missing) == 0
    print("  ✅ Case 3: search_knowledge ≈ web_search 语义等价")


# === Case 4: 工具语义等价 (反向 get_member_profile → query_members) ===
def test_equivalent_reverse_get_member_profile():
    """get_member_profile 期望, 实际调 query_members (LLM 选了列表而非单成员), 仍应满足"""
    actual = {
        "tools_called": ["query_members"],
        "content": "...",
        "question": "...",
    }
    expect = {"tools_any": ["get_member_profile"]}
    issues = evaluate_expectation(expect, actual)
    missing = [i for i in issues if i["type"] == "missing_tools"]
    assert len(missing) == 0
    print("  ✅ Case 4: 反向 get_member_profile ← query_members 语义等价")


# === Case 5: forbid 名字 ∩ must_contain_any (Step 1 修复延续) ===
def test_forbidden_intersects_must_contain_data_bug():
    """forbid 含 '杜同贺', must_contain_any 要求 '杜同贺', 答案提 '杜同贺' → severity=warn 不阻塞"""
    actual = {
        "tools_called": [],
        "content": "杜同贺是博士生, 研究方向是水处理",
        "question": "杜同贺是学生吗?",
    }
    expect = {
        "forbidden_names": ["杜同贺", "王天志", "赵航佳"],
        "must_contain_any": [["杜同贺"]],
    }
    issues = evaluate_expectation(expect, actual)
    data_bug = [i for i in issues if i["type"] == "forbidden_names_data_bug"]
    appeared = [i for i in issues if i["type"] == "forbidden_names_appeared"]
    assert len(data_bug) == 1, f"应标 forbidden_names_data_bug warn: {issues}"
    assert len(appeared) == 0, f"不应判 forbidden_names_appeared: {appeared}"
    print("  ✅ Case 5: forbid ∩ must_contain_any → severity=warn (不阻塞)")


# === Case 6: forbid 名字在 query 里 (Round 9 新增) ===
def test_forbidden_in_query_question_mentioned():
    """题 '王天志的导师是谁?' 必然提 '王天志', forbid 含王天志 → info 级别不阻塞"""
    actual = {
        "tools_called": ["query_members"],
        "content": "王天志本身是本课题组负责人, 没有博士导师。",
        "question": "王天志的导师是谁？",
    }
    expect = {
        "forbidden_names": ["王天志", "杜同贺", "赵航佳"],
    }
    issues = evaluate_expectation(expect, actual)
    query_mentioned = [i for i in issues if i["type"] == "forbidden_names_query_mentioned"]
    appeared = [i for i in issues if i["type"] == "forbidden_names_appeared"]
    assert len(query_mentioned) == 1, f"应标 query_mentioned info: {issues}"
    assert "王天志" in query_mentioned[0]["names"]
    assert len(appeared) == 0, f"不应判 appeared: {appeared}"
    print("  ✅ Case 6: forbid 名字在 query → info (不阻塞)")


# === Case 7: query 是"列出所有"题型 (Round 9 新增) ===
def test_forbidden_listing_question():
    """题 '我们课题组成员都有谁?' 必然列成员, forbid 列全员 → info 不阻塞"""
    actual = {
        "tools_called": ["query_members"],
        "content": "我们课题组有: 王天志、杜同贺、赵航佳、杨慈、宋洋...",
        "question": "我们课题组成员都有谁？",
    }
    expect = {
        "forbidden_names": ["王天志", "杜同贺", "赵航佳", "杨慈", "宋洋"],
    }
    issues = evaluate_expectation(expect, actual)
    listing = [i for i in issues if i["type"] == "forbidden_names_listing_question"]
    appeared = [i for i in issues if i["type"] == "forbidden_names_appeared"]
    assert len(listing) == 1, f"应标 listing_question info: {issues}"
    assert len(appeared) == 0, f"不应判 appeared: {appeared}"
    print("  ✅ Case 7: '列出/所有' 题型 → info (不阻塞)")


def test_forbidden_listing_question_with_count_keyword():
    """2026-07-02 扩展: '多少'类计数+枚举题也识别 (A-L2-0009 真 bug)"""
    actual = {
        "tools_called": ["query_members"],
        "content": "我们课题组在读硕士研究生有: 杜同贺、杨慈、宋洋、李胜景 (共 4 人)",
        "question": "我们课题组现在有多少在读硕士研究生？",
    }
    expect = {
        "forbidden_names": ["杜同贺", "杨慈", "宋洋", "李胜景", "王天志"],
    }
    issues = evaluate_expectation(expect, actual)
    listing = [i for i in issues if i["type"] == "forbidden_names_listing_question"]
    appeared = [i for i in issues if i["type"] == "forbidden_names_appeared"]
    assert len(listing) == 1, f"应标 listing_question info: {issues}"
    assert len(appeared) == 0, f"不应判 appeared: {appeared}"
    print("  ✅ Case 7b: '多少' 题型 → info (不阻塞, 扩展关键词)")


# === Case 8: 真 hallucination 仍应被检测 ===
def test_true_hallucination_still_detected():
    """题 '杨慈是谁?' 没列杨慈在 must_contain_any/query/listing, 答案提 '王天志' → 真 hallucination"""
    actual = {
        "tools_called": ["query_members"],
        "content": "杨慈是我们组的成员, 但王天志也常在。",
        "question": "杨慈是谁?",
    }
    expect = {
        "forbidden_names": ["王天志", "杜同贺"],
    }
    issues = evaluate_expectation(expect, actual)
    appeared = [i for i in issues if i["type"] == "forbidden_names_appeared"]
    assert len(appeared) == 1, f"应判 forbidden_names_appeared: {issues}"
    assert "王天志" in appeared[0]["names"]
    print("  ✅ Case 8: 真 hallucination 仍被判 forbidden_names_appeared")


# === Case 9: 完整 has_critical_issue 模拟 — severity=info 不阻塞 PASS ===
def test_severity_info_not_critical():
    """模拟 verify 流程: forbidden_names_query_mentioned (info) 不阻塞 verdict"""
    actual = {
        "tools_called": ["query_members"],
        "content": "王天志是负责人, 副教授...",
        "question": "王天志是负责人吗?",
    }
    expect = {
        "tools_any": ["query_members"],
        "forbidden_names": ["王天志", "杜同贺"],
        "must_contain_any": [["负责人"]],
    }
    issues = evaluate_expectation(expect, actual)
    issue_types = {i["type"] for i in issues}
    # 应该看到 query_mentioned info 出现, 但没有真 critical
    assert "forbidden_names_query_mentioned" in issue_types
    # has_critical_issue 模拟: 检查所有 critical 类型
    CRITICAL_TYPES = {
        "fake_xml_leaked", "placeholder_text", "hallucinated_names",
        "forbidden_names_appeared", "missing_tools", "missing_required_terms",
        "found_forbidden_terms", "duration_too_long",
        "stream_no_done", "stream_error_event", "tool_error_propagated",
        "llm_excuse_no_tool_error", "technical_leak",
    }
    has_critical = any(
        i["type"] in CRITICAL_TYPES
        and i.get("severity") != "info"
        and i.get("severity") != "warn"
        for i in issues
    )
    assert not has_critical, f"info/warn 不应阻塞 verdict, but has_critical=True for {issues}"
    print("  ✅ Case 9: severity=info 不阻塞 verdict (Round 9 修复)")


# === Case 10: _expand_tools_with_equivalents helper 直接测试 ===
def test_expand_tools_helper():
    """_expand_tools_with_equivalents 直接调用"""
    expanded = _expand_tools_with_equivalents({"query_members"})
    assert "query_members" in expanded
    assert "get_member_profile" in expanded
    expanded2 = _expand_tools_with_equivalents({"search_knowledge"})
    assert "web_search" in expanded2
    print("  ✅ Case 10: _expand_tools_with_equivalents 直接测试")


# === Case 11: _forbidden_names_in_query helper 直接测试 ===
def test_forbidden_in_query_helper():
    """query 中含 forbid 名字时返回匹配集合"""
    mentioned = _forbidden_names_in_query("王天志的导师是谁", ["王天志", "杜同贺"])
    assert "王天志" in mentioned
    assert "杜同贺" not in mentioned
    print("  ✅ Case 11: _forbidden_names_in_query 直接测试")


# === Case 12: _is_listing_question helper 直接测试 ===
def test_is_listing_question_helper():
    assert _is_listing_question("我们课题组成员都有谁？")
    assert _is_listing_question("列出所有实验方法")
    assert _is_listing_question("组里有哪些人是博士生？")
    # 2026-07-02 扩展关键词: "多少/几个/谁在做/研究" 类计数+枚举题也识别
    assert _is_listing_question("我们课题组现在有多少在读硕士研究生？")
    assert _is_listing_question("组内有几个人在做臭氧氧化研究？")
    assert _is_listing_question("谁在做微纳米气泡的研究？")
    assert not _is_listing_question("王天志是干什么的？")
    assert not _is_listing_question("杜同贺的导师是谁？")
    print("  ✅ Case 12: _is_listing_question 直接测试 (含扩展关键词)")


def run_all():
    print("\n" + "=" * 60)
    print("qa-bench runner 智能过滤 Round 9 单测 (12 case)")
    print("=" * 60)
    tests = [
        test_equivalent_get_member_profile_to_query_members,
        test_equivalent_query_tasks_to_query_member_tasks,
        test_equivalent_query_all_member_tasks_to_query_member_tasks,
        test_equivalent_search_knowledge_to_web_search,
        test_equivalent_reverse_get_member_profile,
        test_forbidden_intersects_must_contain_data_bug,
        test_forbidden_in_query_question_mentioned,
        test_forbidden_listing_question,
        test_forbidden_listing_question_with_count_keyword,
        test_true_hallucination_still_detected,
        test_severity_info_not_critical,
        test_expand_tools_helper,
        test_forbidden_in_query_helper,
        test_is_listing_question_helper,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print()
    print(f"📊 单测结果: {passed} passed / {failed} failed (total {len(tests)})")
    if failed == 0:
        print("✅ 全部通过")
    else:
        print(f"❌ {failed} 个 case 失败, 需修")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)