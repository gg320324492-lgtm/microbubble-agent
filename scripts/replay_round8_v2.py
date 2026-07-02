"""用新 runner (Round 9 智能过滤) 重新评估 Round 8 — 准确版

不再 mix 旧 auto_issues (会产生假数据), 直接基于 actual content 重新跑:
1. evaluate_expectation (新, 智能过滤)
2. has_critical_issue (新, severity=warn/info 跳过)
3. 列出每题真实剩余 critical issues
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "qa-bench"))
from runner import evaluate_expectation


CRITICAL_TYPES = {
    "fake_xml_leaked", "placeholder_text", "hallucinated_names",
    "forbidden_names_appeared", "missing_tools", "missing_required_terms",
    "found_forbidden_terms", "duration_too_long",
    "stream_no_done", "stream_error_event", "tool_error_propagated",
    "llm_excuse_no_tool_error", "technical_leak",
}


def has_critical_round9(issues):
    """Round 9 新逻辑: severity=warn/info 永远不阻塞"""
    return any(
        i["type"] in CRITICAL_TYPES
        and i.get("severity") not in ("warn", "info")
        for i in issues
    )


def main():
    in_path = Path("tests/qa-bench/results/reranker-benchmark/round8-bge-m3-openai-compat/results.json")

    with open(in_path, encoding="utf-8") as f:
        d = json.load(f)

    # 真实重评估: 仅基于 actual 重新 evaluate_expectation
    # 不复用 auto_issues (它们是旧 runner 跑的, 不能跟新 evaluate 比对)
    results = []
    for r in d["results"]:
        # 跳过 error 题
        if "error" in r or not r.get("actual"):
            results.append({
                "id": r["id"], "verdict_old": r.get("verdict"),
                "verdict_new": "ERROR", "expect_issues_new": [], "critical_left": [],
            })
            continue

        expect = r.get("expect", {})
        actual = r.get("actual", {})
        actual["question"] = r.get("question", "")

        # 仅跑 evaluate_expectation (新)
        new_expect_issues = evaluate_expectation(expect, actual)

        # 只把这些 issues 算 verdict (因为 auto_issues 都是 LLM 真问题, 跟数据修复无关)
        # 但 missing_tools / forbidden_names_appeared 等都在 evaluate_expectation 里处理
        critical_left = [
            i["type"] for i in new_expect_issues
            if i["type"] in CRITICAL_TYPES and i.get("severity") not in ("warn", "info")
        ]
        # 如果没有 critical, 看是否还有其他 issues
        is_fail = bool(critical_left)
        verdict_new = "FAIL" if is_fail else ("WARN" if new_expect_issues else "PASS")

        results.append({
            "id": r["id"],
            "question": r.get("question", "")[:50],
            "verdict_old": r.get("verdict"),
            "verdict_new": verdict_new,
            "expect_issues_new": [i["type"] for i in new_expect_issues],
            "critical_left": critical_left,
        })

    # 统计
    from collections import Counter
    old_c = Counter(r["verdict_old"] for r in results)
    new_c = Counter(r["verdict_new"] for r in results)

    print("=" * 70)
    print("Round 9 智能过滤: 仅 evaluate_expectation 重评估 (不含 auto_issues)")
    print("=" * 70)
    print(f"{'verdict':<10} {'old':>8} {'new':>8} {'delta':>8}")
    for v in ["PASS", "WARN", "FAIL", "ERROR"]:
        print(f"{v:<10} {old_c[v]:>8} {new_c[v]:>8} {new_c[v]-old_c[v]:>+8}")
    print()
    # 13 FAIL 题详情
    print("=" * 70)
    print("13 FAIL 题 Round 9 评估 (看 critical_left)")
    print("=" * 70)
    for r in results:
        if r["verdict_old"] != "FAIL":
            continue
        full_r = next(x for x in d["results"] if x["id"] == r["id"])
        old_issues_set = {i["type"] for i in full_r.get("issues", [])}
        new_issues_set = set(r["expect_issues_new"])
        diff_removed = old_issues_set - new_issues_set
        diff_added = new_issues_set - old_issues_set
        print(f"\n[{r['id']}] {r['question']}")
        print(f"  old: {r['verdict_old']} → new: {r['verdict_new']}")
        print(f"  期望问题 (new): {r['expect_issues_new']}")
        print(f"  剩余 critical: {r['critical_left']}")
        if diff_removed or diff_added:
            print(f"  diff removed: {diff_removed}")
            print(f"  diff added: {diff_added}")


if __name__ == "__main__":
    main()