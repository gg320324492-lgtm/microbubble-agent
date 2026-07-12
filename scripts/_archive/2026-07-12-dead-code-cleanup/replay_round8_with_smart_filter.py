"""用新 runner (Round 9 智能过滤) 重新评估 Round 8 results.json, 看 verdict 改善"""
import json
import sys
from pathlib import Path

# import runner
sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "qa-bench"))
from runner import evaluate_expectation


def main():
    in_path = Path("tests/qa-bench/results/reranker-benchmark/round8-bge-m3-openai-compat/results.json")
    out_path = Path("tests/qa-bench/results/reranker-benchmark/round9-smart-filter-reeval/results.json")

    with open(in_path, encoding="utf-8") as f:
        d = json.load(f)

    # 重新跑 evaluate_expectation 评估, 对比新 verdict
    verdicts_old = {r["id"]: r.get("verdict") for r in d["results"]}
    issues_old = {r["id"]: [i["type"] for i in r.get("issues", [])] for r in d["results"]}

    new_verdicts = {}
    new_issues_summary = {}
    promoted = []  # FAIL → PASS/WARN
    regressed = []  # PASS/WARN → FAIL

    for r in d["results"]:
        if "error" in r or r.get("actual") is None:
            new_verdicts[r["id"]] = "ERROR"
            continue
        expect = r.get("expect", {})
        actual = r.get("actual", {})
        actual["question"] = r.get("question", "")
        new_expect_issues = evaluate_expectation(expect, actual)
        new_issues_summary[r["id"]] = [i["type"] for i in new_expect_issues]
        # 自动 issues (auto) 没法从 result 重现, 用旧 auto_issues + 新 expect_issues 合并
        old_issues = r.get("issues", [])
        auto_issues = [i for i in old_issues if i not in [
            x for x in new_expect_issues if x["type"] == i["type"]
        ]]
        all_issues = auto_issues + new_expect_issues
        # 关键判定: has_critical_issue 与新逻辑一致
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
            for i in all_issues
        )
        new_v = "FAIL" if has_critical else ("WARN" if all_issues else "PASS")
        new_verdicts[r["id"]] = new_v
        if verdicts_old[r["id"]] == "FAIL" and new_v != "FAIL":
            promoted.append((r["id"], r["question"][:50], new_v))
        elif verdicts_old[r["id"]] != "FAIL" and new_v == "FAIL":
            regressed.append((r["id"], r["question"][:50]))

    # 统计
    from collections import Counter
    old_counts = Counter(verdicts_old.values())
    new_counts = Counter(new_verdicts.values())
    print("=" * 70)
    print("Round 9 智能过滤修复: verdict 对比")
    print("=" * 70)
    print(f"{'verdict':<10} {'old':>8} {'new':>8} {'delta':>8}")
    print("-" * 35)
    for v in ["PASS", "WARN", "FAIL", "ERROR"]:
        print(f"{v:<10} {old_counts[v]:>8} {new_counts[v]:>8} {new_counts[v]-old_counts[v]:>+8}")
    print()
    print(f"Promoted (FAIL → {promoted and 'OK'}): {len(promoted)} 题")
    for qid, q, v in promoted[:5]:
        print(f"  [{qid}] → {v}: {q}")
    if regressed:
        print(f"\nRegressed (PASS/WARN → FAIL): {len(regressed)} 题 (不应发生)")
        for qid, q in regressed[:5]:
            print(f"  [{qid}]: {q}")
    print()
    # 13 个 FAIL 详情
    print("=" * 70)
    print("13 FAIL 题新 verdict (Round 9 修复后)")
    print("=" * 70)
    for r in d["results"]:
        if verdicts_old[r["id"]] != "FAIL":
            continue
        old_issue_set = set(issues_old.get(r["id"], []))
        new_issue_set = set(new_issues_summary.get(r["id"], []))
        diff_removed = old_issue_set - new_issue_set
        diff_added = new_issue_set - old_issue_set
        print(f"\n[{r['id']}] {r.get('question', '')[:60]}")
        print(f"  old: {verdicts_old[r['id']]}  new: {new_verdicts[r['id']]}")
        if diff_removed:
            print(f"  移除 issues: {diff_removed}")
        if diff_added:
            print(f"  新增 issues: {diff_added}")

    # 写评估结果
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "old_verdicts": verdicts_old,
            "new_verdicts": new_verdicts,
            "new_issues_summary": new_issues_summary,
            "promoted": promoted,
            "regressed": regressed,
            "old_counts": dict(old_counts),
            "new_counts": dict(new_counts),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📄 评估结果: {out_path}")


if __name__ == "__main__":
    main()