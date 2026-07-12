"""重评估 Round 9 smoke 30 results.json — 用新 runner (含 query_all_member_tasks)"""
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
    return any(
        i["type"] in CRITICAL_TYPES
        and i.get("severity") not in ("warn", "info")
        for i in issues
    )


def main():
    in_path = Path("tests/qa-bench/results/reranker-benchmark/round9-smoke-30/results.json")

    with open(in_path, encoding="utf-8") as f:
        d = json.load(f)

    results = []
    for r in d["results"]:
        if "error" in r or not r.get("actual"):
            results.append({
                "id": r["id"], "verdict_old": r.get("verdict"),
                "verdict_new": "ERROR", "critical_left": [],
            })
            continue
        expect = r.get("expect", {})
        actual = r.get("actual", {})
        actual["question"] = r.get("question", "")
        new_expect_issues = evaluate_expectation(expect, actual)
        critical_left = [
            i["type"] for i in new_expect_issues
            if i["type"] in CRITICAL_TYPES and i.get("severity") not in ("warn", "info")
        ]
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

    from collections import Counter
    old_c = Counter(r["verdict_old"] for r in results)
    new_c = Counter(r["verdict_new"] for r in results)
    print("=" * 70)
    print("Round 9 smoke 30 重评估 (含 query_all_member_tasks 语义等价)")
    print("=" * 70)
    print(f"{'verdict':<10} {'old':>8} {'new':>8} {'delta':>8}")
    for v in ["PASS", "WARN", "FAIL", "ERROR"]:
        print(f"{v:<10} {old_c[v]:>8} {new_c[v]:>8} {new_c[v]-old_c[v]:>+8}")
    print()

    # 列出 13 FAIL 的新状态
    print("=" * 70)
    print("13 FAIL 题 Round 9 修复 + query_all_member_tasks 后的 verdict")
    print("=" * 70)
    for r in results:
        if r["verdict_old"] != "FAIL":
            continue
        full_r = next(x for x in d["results"] if x["id"] == r["id"])
        old_issues = {i["type"] for i in full_r.get("issues", [])}
        new_issues = set(r["expect_issues_new"])
        diff_removed = old_issues - new_issues
        diff_added = new_issues - old_issues
        delta = "→".join([f"{r['verdict_old']}", f"{r['verdict_new']}"])
        print(f"\n[{r['id']}] {r['question']}")
        print(f"  {delta} | critical: {r['critical_left']}")
        if diff_removed:
            print(f"  移除: {diff_removed}")
        if diff_added:
            print(f"  新增: {diff_added}")

    # 写重评估结果
    out_path = Path("tests/qa-bench/results/reranker-benchmark/round9-smoke-30-reeval/results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "old_verdicts": {r["id"]: r["verdict_old"] for r in results},
            "new_verdicts": {r["id"]: r["verdict_new"] for r in results},
            "new_issues_summary": {r["id"]: r.get("expect_issues_new", []) for r in results},
            "old_counts": dict(old_c),
            "new_counts": dict(new_c),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📄 评估结果: {out_path}")


if __name__ == "__main__":
    main()