"""2026-07-02 Step 4: 三轮对比脚本 (R3 / R6 / R7)

输入: results.json 路径
输出: 表格对比 pass rate, 各类 issue 计数, 排除 qa-bench 数据 bug 后真实 pass rate
"""
import json
import sys
from pathlib import Path


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def count_issues(results, issue_types):
    counts = {it: 0 for it in issue_types}
    for r in results:
        for issue in r.get("issues", []):
            t = issue.get("type")
            if t in counts:
                counts[t] += 1
    return counts


def compute_real_pass_rate(results, forbid_conflict_types=("forbidden_names_data_bug",)):
    """排除 qa-bench 数据 bug 后的真实 pass rate"""
    real_total = 0
    real_pass = 0
    for r in results:
        verdict = r.get("verdict", "FAIL")
        issues = r.get("issues", [])
        # 移除数据 bug 类型 (Step 1 修复加的)
        real_issues = [i for i in issues if i.get("type") not in forbid_conflict_types]
        # 重新判定: 如果真 issues 没 critical, 视为 PASS
        if real_issues:
            has_critical = any(i["type"] in (
                "fake_xml_leaked", "placeholder_text", "hallucinated_names",
                "forbidden_names_appeared", "missing_tools", "missing_required_terms",
                "found_forbidden_terms", "duration_too_long",
                "stream_no_done", "stream_error_event", "tool_error_propagated",
                "llm_excuse_no_tool_error", "technical_leak",
            ) for i in real_issues)
        else:
            has_critical = False

        real_total += 1
        if not has_critical and verdict != "ERROR":
            real_pass += 1
    return real_pass, real_total


def main():
    rounds = [
        ("R3 BGE m3 raw",
         "tests/qa-bench/results/reranker-benchmark/round3-bge-m3/results.json"),
        ("R6 ms-marco",
         "tests/qa-bench/results/reranker-benchmark/round6-ms-marco-openai-compat/results.json"),
        ("R7 BGE m3 clean",
         "tests/qa-bench/results/reranker-benchmark/round7-bge-m3-clean/results.json"),
    ]

    issue_types = [
        "stream_error_event", "forbidden_names_appeared",
        "fake_xml_leaked", "intent_mismatch", "missing_tools",
        "duration_warn", "forbidden_names_data_bug",
    ]

    print(f"{'Round':25s} | {'pass':>6s} {'warn':>6s} {'fail':>6s} {'err':>6s} | {'real_pass':>10s} {'real_rate':>10s} | {'429':>5s} {'fna':>5s} {'fxm':>5s} {'im':>5s}")
    print("-" * 130)

    for label, path in rounds:
        if not Path(path).exists():
            print(f"{label:25s} | NOT FOUND: {path}")
            continue
        d = load(path)
        s = d.get("summary", {})
        total = s.get("total", len(d["results"]))
        passed = s.get("pass", 0)
        warn = s.get("warn", 0)
        fail = s.get("fail", 0)
        err = s.get("error", 0)

        real_pass, real_total = compute_real_pass_rate(d["results"])
        real_rate = f"{real_pass/real_total*100:.1f}%" if real_total else "N/A"

        issue_counts = count_issues(d["results"], issue_types)
        stream_429 = issue_counts.get("stream_error_event", 0)
        fna = issue_counts.get("forbidden_names_appeared", 0)
        fxm = issue_counts.get("fake_xml_leaked", 0)
        im = issue_counts.get("intent_mismatch", 0)

        print(f"{label:25s} | {passed:6d} {warn:6d} {fail:6d} {err:6d} | "
              f"{real_pass:>10d} {real_rate:>10s} | "
              f"{stream_429:>5d} {fna:>5d} {fxm:>5d} {im:>5d}")


if __name__ == "__main__":
    main()