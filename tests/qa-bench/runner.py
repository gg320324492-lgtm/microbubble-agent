"""
qa-bench/runner.py — 100 题批量测试运行器 + 自动检测

设计：
1. 读 tests/qa-bench/questions.jsonl 题库
2. 每题 POST /api/v1/chat/stream 收集 SSE 事件
3. 解析事件，按 expect 字段检测：
   - intent 分类是否对
   - tools 是否按预期调用
   - 内容必须包含/不能包含的字符串
   - 是否有 fake XML 泄露给用户
   - 是否有 hallucination 名字
   - 是否有内部事件标签（🧠/📊/🔄）
   - duration 阈值
4. 汇总：pass / fail / warn + 失败原因
5. 写入 results/ 目录（json + md 报告）

用法：
  python tests/qa-bench/runner.py --token <jwt> --output results/run-N
"""
import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Windows GBK console 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# === 配置 ===
API_BASE = "http://127.0.0.1:8000"
STREAM_TIMEOUT_S = 90
DURATION_WARN_S = 30
DURATION_FAIL_S = 60

# 内部事件标签（修复 1 前端 toggle 默认隐藏 — content 里出现算 leak）
INTERNAL_LABELS = ["🧠 意图", "✨ 综合", "📊 自评", "🔄 重试", "⚠️ 自评"]

# Fake tool_call 模板（用户应看不到）
FAKE_XML_PATTERNS = [
    re.compile(r"<function\s*=[^>]+>", re.IGNORECASE),
    re.compile(r"<function_calls?\s*>", re.IGNORECASE),
    re.compile(r"</tool_call>\s*\{", re.IGNORECASE),
    re.compile(r"```json\s*\{[^{}]*\"(?:name|function|tool)\"", re.IGNORECASE),
]

# Hallucination 黑名单（来自数据库 — 不在工具结果里就不该出现在回复里）
KNOWN_MEMBERS = [
    "王天志", "赵航佳", "杜同贺", "陈天祥", "张懿", "耿嘉栋", "陈金薪", "董昊宇",
    "关小未", "胡小琪", "李胜景", "刘子毅", "宋洋", "王书馨", "吴孟铨", "韩重阳",
    "李锐远", "杨慈", "余歆睿", "张宏魁", "贾琦", "周之超", "邓国祥", "雒培媛",
    "孟祥琪", "吴怡霏", "蒋芦笛", "刘莫菲",
]


def parse_sse(response_text: str) -> List[Dict[str, Any]]:
    """解析 SSE data 行成事件列表"""
    events = []
    for line in response_text.split("\n"):
        if not line.startswith("data: "):
            continue
        try:
            events.append(json.loads(line[6:]))
        except json.JSONDecodeError:
            continue
    return events


def assemble_content(events: List[Dict[str, Any]]) -> str:
    """拼装 text_delta 为完整 content"""
    parts = []
    for evt in events:
        if evt.get("type") == "text_delta" and evt.get("delta"):
            parts.append(evt["delta"])
    return "".join(parts)


def detect_fake_xml_leaked(content: str) -> List[str]:
    """检测是否有 fake tool_call XML 泄露到用户"""
    leaked = []
    for pat in FAKE_XML_PATTERNS:
        if pat.search(content):
            leaked.append(pat.pattern)
    return leaked


def detect_internal_labels(content: str) -> List[str]:
    """检测内部事件标签（前端 toggle off 时不应出现）"""
    found = [label for label in INTERNAL_LABELS if label in content]
    return found


def detect_hallucinated_names(content: str, tools_called: List[str], grounded_names: set) -> List[str]:
    """检测回复里出现的成员名是否都在 grounded 集合里

    规则：如果工具调过 query_members / get_member_profile，回复里出现的姓名
    必须在 grounded_names 里。否则视为 hallucination。
    """
    if not any(t in ("get_member_profile", "query_members") for t in tools_called):
        return []  # 没调成员工具不检测
    found_hallu = []
    for name in KNOWN_MEMBERS:
        if name in content and name not in grounded_names:
            found_hallu.append(name)
    return found_hallu


def detect_placeholder_text(content: str) -> List[str]:
    """检测占位符（承诺的"严禁编造"）"""
    placeholders = [
        "暂无详细信息", "待补充", "建议查询数据库", "请查阅",
        "系统故障", "技术问题", "数据同步中", "请联系管理员",
    ]
    return [p for p in placeholders if p in content]


def detect_filler_phrases(content: str) -> int:
    """检测 filler 句式（"让我搜索一下..." / "我来帮你查询..."）"""
    fillers = [
        "让我搜索一下", "让我查一下", "让我找一下",
        "我来帮你查询", "我来帮你搜索", "我来帮你找",
        "需要我帮你搜索", "需要我帮你查询", "需要我帮你",
        "让我先查", "让我先搜索", "让我先找",
    ]
    return sum(1 for f in fillers if f in content)


def collect_grounded_names(events: List[Dict[str, Any]]) -> set:
    """从 tool_result 事件里收集真实姓名"""
    names = set()
    for evt in events:
        if evt.get("type") == "tool_result" and evt.get("tool_output"):
            output = evt["tool_output"]
            if isinstance(output, dict):
                members = output.get("members") or []
                for m in members:
                    if isinstance(m, dict) and isinstance(m.get("name"), str):
                        names.add(m["name"])
                # get_member_profile 平铺
                if "name" in output and isinstance(output["name"], str):
                    names.add(output["name"])
    return names


def collect_tools_called(events: List[Dict[str, Any]]) -> List[str]:
    """从 tool_use 事件收集调用的工具名"""
    tools = []
    for evt in events:
        if evt.get("type") == "tool_use" and evt.get("tool_name"):
            tools.append(evt["tool_name"])
    return tools


def collect_tool_inputs(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """收集 tool_use 事件的 input（用于诊断 fake tool_call 的字段名 alias 是否生效）"""
    return [
        {"name": e.get("tool_name"), "input": e.get("tool_input")}
        for e in events if e.get("type") == "tool_use"
    ]


def collect_tool_results(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """收集 tool_result 事件的输出（用于诊断 tool 实际返回）"""
    return [
        {"name": e.get("tool_name"), "result": e.get("tool_output")}
        for e in events if e.get("type") == "tool_result"
    ]


def collect_intent(events: List[Dict[str, Any]]) -> Optional[str]:
    for evt in events:
        if evt.get("type") == "intent_detected" and evt.get("intent"):
            return evt["intent"].get("category")
    return None


def collect_critique_score(events: List[Dict[str, Any]]) -> Optional[int]:
    for evt in events:
        if evt.get("type") == "critique" and evt.get("critique"):
            return evt["critique"].get("score")
    return None


def collect_duration(events: List[Dict[str, Any]]) -> Optional[int]:
    for evt in events:
        if evt.get("type") == "done" and evt.get("duration_ms") is not None:
            return evt["duration_ms"]
    return None


# === 期望对比 ===
def evaluate_expectation(
    expect: Dict[str, Any],
    actual: Dict[str, Any],
) -> List[Dict[str, str]]:
    """对照 expect 字段生成问题列表"""
    issues = []
    if not expect:
        return issues

    # intent
    if "intent" in expect and expect["intent"] != actual.get("intent"):
        issues.append({
            "type": "intent_mismatch",
            "expect": expect["intent"],
            "actual": actual.get("intent"),
        })
    # intent_any（任一满足即可，宽松模式）
    if "intent_any" in expect:
        any_intents = set(expect["intent_any"])
        if actual.get("intent") not in any_intents:
            # 只有当严格的 intent 字段也不匹配时才报
            if "intent" not in expect or expect["intent"] != actual.get("intent"):
                issues.append({
                    "type": "intent_mismatch",
                    "expect": sorted(any_intents),
                    "actual": actual.get("intent"),
                    "note": "intent_any — 任一即可",
                })

    # tools（严格模式：必须全部调过）
    if "tools" in expect:
        expected_tools = set(expect["tools"])
        actual_tools = set(actual.get("tools_called", []))
        missing = expected_tools - actual_tools
        if missing:
            issues.append({
                "type": "missing_tools",
                "missing": sorted(missing),
            })

    # tools_any（任一满足即可，宽松模式）
    if "tools_any" in expect and not any(i["type"] == "missing_tools" for i in issues):
        any_tools = set(expect["tools_any"])
        actual_tools = set(actual.get("tools_called", []))
        matched = any_tools & actual_tools
        if not matched:
            issues.append({
                "type": "missing_tools",
                "missing": sorted(any_tools),
                "note": "tools_any — 任一即可",
            })

    # tools_must_all（全部必须，hard fail, #042 fan-out 门禁）
    if "tools_must_all" in expect:
        must_tools = set(expect["tools_must_all"])
        actual_tools = set(actual.get("tools_called", []))
        missing = sorted(must_tools - actual_tools)
        if missing:
            issues.append({
                "type": "missing_required_tools",  # 不同于 missing_tools — 区分 hard fail
                "missing": missing,
                "note": "tools_must_all — 全部必须 (#042 fan-out 门禁)",
            })

    # must_contain
    if "must_contain" in expect:
        content = actual.get("content", "")
        missing_terms = [t for t in expect["must_contain"] if t not in content]
        if missing_terms:
            issues.append({
                "type": "missing_required_terms",
                "missing": missing_terms,
            })

    # must_not_contain
    if "must_not_contain" in expect:
        content = actual.get("content", "")
        bad_terms = [t for t in expect["must_not_contain"] if t in content]
        if bad_terms:
            issues.append({
                "type": "found_forbidden_terms",
                "found": bad_terms,
            })

    # forbidden_names (硬性 hallucination 检测)
    if "forbidden_names" in expect:
        content = actual.get("content", "")
        appeared = [n for n in expect["forbidden_names"] if n in content]
        if appeared:
            issues.append({
                "type": "forbidden_names_appeared",
                "names": appeared,
            })

    return issues


async def run_single_question(
    client: httpx.AsyncClient,
    question_data: Dict[str, Any],
    token: str,
) -> Dict[str, Any]:
    """跑一道题并返回结果"""
    qid = question_data["id"]
    question = question_data["question"]
    expect = question_data.get("expect", {})
    session_id = f"qa-bench-{qid}-{int(time.time())}"

    payload = {"message": question, "session_id": session_id}

    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{API_BASE}/api/v1/chat/stream",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=STREAM_TIMEOUT_S,
        )
        elapsed = (time.monotonic() - t0) * 1000
        if resp.status_code != 200:
            return {
                "id": qid,
                "category": question_data["category"],
                "question": question,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "duration_ms": int(elapsed),
            }
        events = parse_sse(resp.text)
    except Exception as e:
        return {
            "id": qid,
            "category": question_data["category"],
            "question": question,
            "error": f"Exception: {type(e).__name__}: {str(e)[:200]}",
        }

    content = assemble_content(events)
    tools_called = collect_tools_called(events)
    intent = collect_intent(events)
    grounded_names = collect_grounded_names(events)
    critique_score = collect_critique_score(events)
    duration_ms = collect_duration(events) or int((time.monotonic() - t0) * 1000)

    actual = {
        "intent": intent,
        "tools_called": tools_called,
        "tool_inputs": collect_tool_inputs(events),
        "tool_results": collect_tool_results(events),
        "content": content,
        "grounded_names": sorted(grounded_names),
        "critique_score": critique_score,
        "duration_ms": duration_ms,
    }

    # 自动检测（不需要 expect 也能跑）
    auto_issues = []
    leaked_xml = detect_fake_xml_leaked(content)
    if leaked_xml:
        auto_issues.append({"type": "fake_xml_leaked", "patterns": leaked_xml})
    internal_labels = detect_internal_labels(content)
    if internal_labels:
        auto_issues.append({"type": "internal_labels_leaked", "labels": internal_labels})
    placeholders = detect_placeholder_text(content)
    if placeholders:
        auto_issues.append({"type": "placeholder_text", "phrases": placeholders})
    hallu_names = detect_hallucinated_names(content, tools_called, grounded_names)
    if hallu_names:
        auto_issues.append({"type": "hallucinated_names", "names": hallu_names})
    filler_count = detect_filler_phrases(content)
    if filler_count > 0:
        auto_issues.append({"type": "filler_phrases", "count": filler_count})
    if duration_ms > DURATION_FAIL_S * 1000:
        auto_issues.append({"type": "duration_too_long", "duration_ms": duration_ms})
    elif duration_ms > DURATION_WARN_S * 1000:
        auto_issues.append({"type": "duration_warn", "duration_ms": duration_ms})

    # 期望对比
    expect_issues = evaluate_expectation(expect, actual)

    all_issues = auto_issues + expect_issues
    has_critical = any(
        i["type"] in (
            "fake_xml_leaked", "placeholder_text", "hallucinated_names",
            "forbidden_names_appeared", "missing_tools", "missing_required_terms",
            "found_forbidden_terms", "duration_too_long",
        )
        for i in all_issues
    )

    return {
        "id": qid,
        "category": question_data["category"],
        "question": question,
        "expect": expect,
        "actual": actual,
        "issues": all_issues,
        "has_critical_issue": has_critical,
        "verdict": "FAIL" if has_critical else ("WARN" if all_issues else "PASS"),
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--questions", default="tests/qa-bench/questions.jsonl")
    parser.add_argument("--output", default="results/run")
    parser.add_argument("--limit", type=int, default=0, help="limit N questions (0=all)")
    parser.add_argument("--concurrency", type=int, default=6, help="并发数")
    args = parser.parse_args()

    questions_path = Path(args.questions)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    questions = []
    with open(questions_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            questions.append(json.loads(line))
    if args.limit:
        questions = questions[:args.limit]

    print(f"🚀 qa-bench 启动: {len(questions)} 道题")
    print(f"   输出: {output_dir}")
    print()

    results = []
    completed = 0
    print_lock = asyncio.Lock()
    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def run_with_progress(q, i):
            nonlocal completed
            async with semaphore:
                t0 = time.monotonic()
                r = await run_single_question(client, q, args.token)
                dt = time.monotonic() - t0
                verdict = r.get("verdict", "ERROR")
                issue_types = [i["type"] for i in r.get("issues", [])]
                async with print_lock:
                    completed += 1
                    print(
                        f"  [{completed:3d}/{len(questions)}] {verdict:5s} {r['id']} ({dt:.1f}s) "
                        f"cat={r['category']:18s} {r.get('question', '')[:40]:40s} "
                        f"{' '.join(issue_types) if issue_types else '✓'}",
                        flush=True,
                    )
                return r

        tasks = [run_with_progress(q, i) for i, q in enumerate(questions)]
        results = await asyncio.gather(*tasks)

    # === 写报告 ===
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "pass": sum(1 for r in results if r.get("verdict") == "PASS"),
        "warn": sum(1 for r in results if r.get("verdict") == "WARN"),
        "fail": sum(1 for r in results if r.get("verdict") == "FAIL"),
        "error": sum(1 for r in results if "error" in r),
        "by_category": {},
        "issue_distribution": {},
    }
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in summary["by_category"]:
            summary["by_category"][cat] = {"pass": 0, "warn": 0, "fail": 0, "error": 0}
        v = r.get("verdict", "ERROR").lower()
        if "error" in r:
            v = "error"
        summary["by_category"][cat][v] = summary["by_category"][cat].get(v, 0) + 1
        for issue in r.get("issues", []):
            t = issue["type"]
            summary["issue_distribution"][t] = summary["issue_distribution"].get(t, 0) + 1

    # 写 json
    (output_dir / "results.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写 md
    md = [f"# QA Bench Report — {summary['timestamp']}", ""]
    md.append(f"**总题数**: {summary['total']} | "
              f"**PASS**: {summary['pass']} | "
              f"**WARN**: {summary['warn']} | "
              f"**FAIL**: {summary['fail']} | "
              f"**ERROR**: {summary['error']}")
    pass_rate = (summary['pass'] / summary['total'] * 100) if summary['total'] else 0
    md.append(f"\n**通过率**: {pass_rate:.1f}%\n")
    md.append("## 按分类\n")
    md.append("| 分类 | PASS | WARN | FAIL | ERROR |")
    md.append("|---|---|---|---|---|")
    for cat, stats in sorted(summary["by_category"].items()):
        md.append(f"| {cat} | {stats.get('pass', 0)} | {stats.get('warn', 0)} | "
                  f"{stats.get('fail', 0)} | {stats.get('error', 0)} |")
    md.append("\n## 问题分布\n")
    md.append("| 类型 | 次数 |")
    md.append("|---|---|")
    for t, c in sorted(summary["issue_distribution"].items(), key=lambda x: -x[1]):
        md.append(f"| `{t}` | {c} |")
    md.append("\n## 失败题详情\n")
    for r in results:
        if r.get("verdict") not in ("FAIL", "WARN"):
            continue
        md.append(f"\n### {r['id']} ({r['category']}) — {r.get('verdict', 'ERROR')}")
        md.append(f"**问题**: {r.get('question', '')}")
        if "error" in r:
            md.append(f"**Error**: {r['error']}")
            continue
        issues = r.get("issues", [])
        for i in issues:
            md.append(f"- `{i['type']}`: {json.dumps(i, ensure_ascii=False)[len(i['type'])+2:-1]}")
        actual = r.get("actual", {})
        if "content" in actual:
            md.append(f"\n**回答预览 (前 200 字)**:")
            md.append(f"```\n{actual['content'][:200]}\n```")
    (output_dir / "report.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print(f"📊 汇总: PASS={summary['pass']} WARN={summary['warn']} FAIL={summary['fail']} ERROR={summary['error']}")
    print(f"   通过率: {pass_rate:.1f}%")
    print(f"   报告: {output_dir}/report.md")


if __name__ == "__main__":
    asyncio.run(main())
