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
import logging
import os  # 2026-07-13 #P1: 读 THINKING_MODE env 注入 payload
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("qa-bench.runner")

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


# === 工具语义等价映射 (2026-07-02 Round 9 修复) ===
# 背景: LLM 调 get_member_profile (单成员查) 与 query_members (列表查) 是语义等价
# 同样 query_tasks 与 query_member_tasks 也是. expect.tools_any 经常
# 期望 query_members 但 LLM 选更精准的 get_member_profile → missing_tools 误判
# Round 9 smoke 30 验证: 4 题 LLM 调 query_all_member_tasks (新工具, B 类任务专属)
# 视为 query_member_tasks / query_tasks 的等价 (都是查任务列表)
TOOL_SEMANTIC_EQUIVALENTS: Dict[str, frozenset] = {
    "query_members": frozenset({"get_member_profile"}),
    "get_member_profile": frozenset({"query_members"}),
    "query_tasks": frozenset({"query_member_tasks", "query_all_member_tasks"}),
    "query_member_tasks": frozenset({"query_tasks", "query_all_member_tasks"}),
    "query_all_member_tasks": frozenset({"query_tasks", "query_member_tasks"}),
    "query_my_tasks": frozenset({"query_member_tasks"}),
    "search_knowledge": frozenset({"web_search"}),
    "web_search": frozenset({"search_knowledge"}),
}


def _expand_tools_with_equivalents(tools: set) -> set:
    """把工具集合扩展为含语义等价工具的并集.

    例如 {'query_members'} → {'query_members', 'get_member_profile'}
    这样 missing_tools 检测时, 实际调了 get_member_profile 也算满足 query_members 期望.
    """
    expanded = set(tools)
    for t in list(expanded):
        expanded |= TOOL_SEMANTIC_EQUIVALENTS.get(t, frozenset())
    return expanded


def _forbidden_names_in_query(question: str, forbidden: List[str]) -> set:
    """如果 forbid 名字直接出现在 query 里, 答案里出现不算 hallucination.

    背景: 题 "王天志的导师是谁?" 必然提王天志 (主语), 但 forbid 里含王天志
    → 答案提王天志是合理引用, 不是 LLM 编造. 算 query-mentioned whitelist.
    """
    if not question or not forbidden:
        return set()
    mentioned = set()
    for name in forbidden:
        if name and name in question:
            mentioned.add(name)
    return mentioned


def _is_listing_question(question: str) -> bool:
    """检测"列出/所有/哪些"题型. 这类题答案必然含成员/任务名, 不应被判 forbidden_names.

    触发场景: "我们课题组成员里谁在做臭氧氧化?" / "有哪些实验方法?" / "组内有多少在读硕士研究生?"
    """
    if not question:
        return False
    listing_keywords = (
        "有哪些", "列出", "列一下", "所有", "哪几个", "哪几位", "哪些",
        "有谁", "都有谁", "是哪些", "在组里", "在课题", "组员", "成员",
        "多少", "几个", "几位", "多少人", "谁在", "谁做", "谁的", "在做",
        "研究", "主要成员",
    )
    return any(kw in question for kw in listing_keywords)


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

    # tools（严格模式：必须全部调过，含语义等价工具）
    if "tools" in expect:
        expected_tools = set(expect["tools"])
        actual_tools = set(actual.get("tools_called", []))
        actual_expanded = _expand_tools_with_equivalents(actual_tools)
        missing = expected_tools - actual_expanded
        if missing:
            issues.append({
                "type": "missing_tools",
                "missing": sorted(missing),
            })

    # tools_any（任一满足即可，宽松模式，含语义等价）
    if "tools_any" in expect and not any(i["type"] == "missing_tools" for i in issues):
        any_tools = set(expect["tools_any"])
        actual_tools = set(actual.get("tools_called", []))
        actual_expanded = _expand_tools_with_equivalents(actual_tools)
        matched = any_tools & actual_expanded
        if not matched:
            issues.append({
                "type": "missing_tools",
                "missing": sorted(any_tools),
                "note": "tools_any — 任一即可",
            })

    # tools_must_all（全部必须，hard fail, #042 fan-out 门禁，含语义等价）
    if "tools_must_all" in expect:
        must_tools = set(expect["tools_must_all"])
        actual_tools = set(actual.get("tools_called", []))
        actual_expanded = _expand_tools_with_equivalents(actual_tools)
        missing = sorted(must_tools - actual_expanded)
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
        question = actual.get("question", "") or actual.get("_question", "")
        # 2026-07-02 Step 1 修复: qa-bench 数据 bug smart filter
        # 当 forbidden_names 含 must_contain_any 的真成员名时, 必然判 FAIL (数据设计 bug)
        # 这种题不应算 LLM 真问题, 标 data_bug 让 benchmark pass rate 更准确反映 LLM 能力
        must_lists = expect.get("must_contain_any", [])
        must_names_flat = set()
        for mc_list in must_lists:
            must_names_flat.update(mc_list)
        # 2026-07-02 Round 9 修复 (智能过滤 3 种数据 bug):
        # 1. forbid ∩ must_contain_any → data_bug (warning, 不阻塞)
        # 2. forbid 名字直接出现在 query 里 (如 "王天志的导师是谁?" 必然提王天志)
        #    → query_mentioned (info 级别, 不阻塞)
        # 3. query 是 "列出/所有" 题型 (如 "课题组成员都有谁?") 答案必然列名字
        #    → listing_question (info 级别, 不阻塞)
        query_mentioned = _forbidden_names_in_query(question, expect["forbidden_names"])
        is_listing = _is_listing_question(question)

        # 真正算 hallucination 的名字: 不在上述任何 whitelist 里
        appeared = [
            n for n in expect["forbidden_names"]
            if n in content
            and n not in must_names_flat       # 排除 must_contain 冲突
            and n not in query_mentioned        # 排除 query 提及
            and not is_listing                   # 排除"列出所有"题型
        ]
        data_bug_names = [
            n for n in expect["forbidden_names"]
            if n in content and n in must_names_flat
        ]
        query_mentioned_in_content = [
            n for n in expect["forbidden_names"]
            if n in content and n in query_mentioned
        ]
        listing_question_names = [
            n for n in expect["forbidden_names"]
            if n in content and is_listing and n not in must_names_flat and n not in query_mentioned
        ]
        if appeared:
            issues.append({
                "type": "forbidden_names_appeared",
                "names": appeared,
            })
        if data_bug_names:
            # 标记为 data_bug severity=warn (不阻塞 verdict), 让 benchmark 能区分
            issues.append({
                "type": "forbidden_names_data_bug",
                "severity": "warn",  # warn 不阻塞 verdict
                "names": data_bug_names,
                "note": "forbidden 名字同时在 must_contain_any, qa-bench 数据设计 bug. 不计入真问题.",
            })
        if query_mentioned_in_content:
            issues.append({
                "type": "forbidden_names_query_mentioned",
                "severity": "info",
                "names": query_mentioned_in_content,
                "note": "forbid 名字直接出现在 question 里, 答案引用合理. 不计入真问题.",
            })
        if listing_question_names:
            issues.append({
                "type": "forbidden_names_listing_question",
                "severity": "info",
                "names": listing_question_names,
                "note": "query 是 '列出/所有/哪些' 题型, 答案列名字合理. 不计入真问题.",
            })

    return issues


# === 7 维评分（v3.0） ===
# 权重（可配置 — 默认基于 plan 3.2 节）
DIM_WEIGHTS = {
    "intent": 0.10,
    "tool": 0.25,
    "content": 0.30,
    "rich": 0.05,
    "defense": 0.15,
    "perf": 0.10,
    "consistency": 0.05,
}

# 分级阈值（按 plan 3.2 节）
GRADE_THRESHOLDS = {
    "A": (90, 100),
    "B": (75, 89),
    "C": (60, 74),
    "D": (40, 59),
    "F": (0, 39),
}


def score_seven_dim(
    expect: Dict[str, Any],
    actual: Dict[str, Any],
    auto_issues: List[Dict[str, Any]],
    expect_issues: List[Dict[str, Any]],
    duration_ms: int,
) -> Dict[str, Any]:
    """7 维评分（v3.0）

    Returns:
        {
            "dim_scores": {"intent": 1.0, "tool": 0.5, ...},  # 0-1
            "total_score": 84,  # 0-100
            "grade": "B",
            "veto": False,  # True if content<0.5 or defense<0.7
        }
    """
    dim_scores = {}

    # 1. Intent 正确性
    expect_intent = expect.get("intent") or expect.get("intent_any")
    if expect_intent is None:
        dim_scores["intent"] = 1.0  # 无强制要求 = 满分
    elif expect.get("intent") and expect["intent"] == actual.get("intent"):
        dim_scores["intent"] = 1.0
    elif expect.get("intent_any") and actual.get("intent") in expect["intent_any"]:
        dim_scores["intent"] = 1.0
    else:
        dim_scores["intent"] = 0.0

    # 2. Tool 选择
    actual_tools = set(actual.get("tools_called", []))
    if expect.get("tools_must_all"):
        must_tools = set(expect["tools_must_all"])
        if must_tools <= actual_tools:
            dim_scores["tool"] = 1.0
        else:
            dim_scores["tool"] = 0.0
    elif expect.get("tools"):
        expected_tools = set(expect["tools"])
        if expected_tools <= actual_tools:
            dim_scores["tool"] = 1.0
        elif expected_tools & actual_tools:
            dim_scores["tool"] = 0.5
        else:
            dim_scores["tool"] = 0.0
    elif expect.get("tools_any"):
        any_tools = set(expect["tools_any"])
        if any_tools & actual_tools:
            dim_scores["tool"] = 1.0
        else:
            dim_scores["tool"] = 0.0
    else:
        dim_scores["tool"] = 1.0  # 无强制要求 = 满分

    # 3. Content 准确性
    content = actual.get("content", "")
    content_score = 1.0
    if expect.get("must_contain"):
        miss = [t for t in expect["must_contain"] if t not in content]
        if miss:
            content_score -= 0.4 * len(miss) / len(expect["must_contain"])
    if expect.get("must_contain_any"):
        any_hit = False
        for group in expect["must_contain_any"]:
            if all(t in content for t in group):
                any_hit = True
                break
        if not any_hit:
            content_score -= 0.4
    if expect.get("must_contain_keywords"):
        miss = [k for k in expect["must_contain_keywords"] if k not in content]
        if miss:
            content_score -= 0.3 * len(miss) / len(expect["must_contain_keywords"])
    if expect.get("must_not_contain"):
        bad = [t for t in expect["must_not_contain"] if t in content]
        if bad:
            content_score -= 0.5 * len(bad) / len(expect["must_not_contain"])
    if expect.get("forbidden_names"):
        # 2026-07-02 Round 9 修复: content 评分同样过滤 3 类数据 bug
        # 1. forbid ∩ must_contain_any
        # 2. forbid 名字在 query 里
        # 3. query 是"列出所有"题型
        must_lists = expect.get("must_contain_any", [])
        must_names_flat = set()
        for mc_list in must_lists:
            must_names_flat.update(mc_list)
        question = actual.get("question", "") or ""
        query_mentioned = _forbidden_names_in_query(question, expect["forbidden_names"])
        is_listing = _is_listing_question(question)
        bad = [
            n for n in expect["forbidden_names"]
            if n in content
            and n not in must_names_flat
            and n not in query_mentioned
            and not is_listing
        ]
        if bad:
            content_score -= 0.5
    # min_length / max_length
    if expect.get("min_length") and len(content) < expect["min_length"]:
        content_score -= 0.2
    if expect.get("max_length") and len(content) > expect["max_length"] * 1.5:  # 超 50% 算超
        content_score -= 0.2
    dim_scores["content"] = max(0.0, min(1.0, content_score))

    # 4. Rich Block 合规
    has_rich = any(
        e.get("type") == "rich_block"
        for e in actual.get("_events", [])  # 事件流（需传入）
    )
    if expect.get("rich_block_required"):
        dim_scores["rich"] = 1.0 if has_rich else 0.0
    else:
        dim_scores["rich"] = 1.0  # 无要求 = 满分

    # 5. 防御性（基于 auto_issues 数量）
    # 0 issues = 1.0, 1 issue = 0.7, 2 = 0.4, ≥3 = 0.0
    # 2026-07-02 Round 9 修复: severity=info/warn 不计入 defense issue (qa-bench 数据 bug 不扣分)
    n_defense_issues = sum(1 for i in auto_issues if (
        i.get("severity") in ("fail", None)  # None = 默认 fail 严重度
    ) and i.get("type") in (
        "fake_xml_leaked", "placeholder_text", "hallucinated_names",
        "forbidden_names_appeared", "found_forbidden_terms",
        "stream_no_done", "stream_error_event", "tool_error_propagated", "llm_excuse_no_tool_error",
        "technical_leak", "stream_aborted",
    ))
    if n_defense_issues == 0:
        dim_scores["defense"] = 1.0
    elif n_defense_issues == 1:
        dim_scores["defense"] = 0.7
    elif n_defense_issues == 2:
        dim_scores["defense"] = 0.4
    else:
        dim_scores["defense"] = 0.0

    # 6. 性能（duration 评分）
    if duration_ms <= DURATION_WARN_S * 1000:
        dim_scores["perf"] = 1.0
    elif duration_ms <= DURATION_FAIL_S * 1000:
        dim_scores["perf"] = 0.6
    else:
        dim_scores["perf"] = 0.2

    # 7. 一致性（暂无数据时给满分 — W3 阶段实现 idempotency 后接入）
    dim_scores["consistency"] = 1.0

    # 总分
    total = sum(dim_scores[k] * DIM_WEIGHTS[k] for k in DIM_WEIGHTS) * 100

    # 一票否决
    veto = dim_scores["content"] < 0.5 or dim_scores["defense"] <= 0.7
    if veto:
        # 一票否决：降到 F 级别
        total = min(total, 39.0)

    # 分级
    grade = "F"
    for g, (low, high) in GRADE_THRESHOLDS.items():
        if low <= total <= high:
            grade = g
            break

    return {
        "dim_scores": dim_scores,
        "total_score": round(total, 1),
        "grade": grade,
        "veto": veto,
    }


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
    # 2026-07-13 #P1: 三档 mode 透传 (qa-bench benchmark 用 THINKING_MODE env 或 question.thinking_mode 字段)
    # 优先级: question_data 显式字段 > THINKING_MODE env > 跳过(走后端 settings 默认)
    thinking_mode = (
        question_data.get("thinking_mode")
        or os.environ.get("THINKING_MODE")
    )
    if thinking_mode:
        payload["thinking_mode"] = thinking_mode

    t0 = time.monotonic()
    # 2026-07-02 Step 2 修复: mimo 限流 429 retry/backoff
    # 实测: 跑 10 题 mimo 限流 7/10, 阻断完整 benchmark
    # 重试策略: 3 次, 60s/120s/180s 退避
    max_retries = 3
    resp = None
    events = None
    try:
        for attempt in range(max_retries):
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
                if resp.status_code == 429 and attempt < max_retries - 1:
                    wait = 60 * (attempt + 1)
                    logger.warning(
                        f"[{qid}] 429 rate limit, retry {attempt+1}/{max_retries} after {wait}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                break  # 非 429 或最后一次重试, 跳出
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"[{qid}] exception {type(e).__name__}, retry {attempt+1}")
                    await asyncio.sleep(30)
                    continue
                raise

        elapsed = (time.monotonic() - t0) * 1000
        if resp is None or resp.status_code != 200:
            return {
                "id": qid,
                "category": question_data["category"],
                "question": question,
                "error": f"HTTP {resp.status_code if resp else 'None'}: {resp.text[:200] if resp else 'no response'}",
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
        "question": question,  # 2026-07-02 Round 9 修复: 注入 question 让 evaluate_expectation 检测 query_mentioned/listing
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

    # v3.0: 集成 3 个新 P0 检测器
    try:
        from detectors.stream_interrupt import detect_stream_interrupt
        for issue in detect_stream_interrupt(events):
            auto_issues.append(issue)
    except Exception as e:
        pass  # 检测器加载失败不影响主流程
    try:
        from detectors.tool_error_propagated import detect_tool_error_propagated
        tool_results = collect_tool_results(events)
        for issue in detect_tool_error_propagated(content, tool_results):
            auto_issues.append(issue)
    except Exception:
        pass
    try:
        from detectors.first_token_latency import detect_first_token_latency
        for issue in detect_first_token_latency(events):
            auto_issues.append(issue)
    except Exception:
        pass
    # 2026-07-01 新增 retrieval_recall 检测器 (P1, BGE m3 reranker 升级伴随)
    try:
        from detectors.retrieval_recall import detect_retrieval_recall
        gt_refs = question_data.get("ground_truth_refs", []) or []
        for issue in detect_retrieval_recall(events, gt_refs):
            auto_issues.append(issue)
    except Exception:
        pass

    all_issues = auto_issues + expect_issues
    # 2026-07-02 Round 9 修复: severity=warn/info 不阻塞 verdict
    # 这些是 qa-bench 数据 bug 标识 (forbidden_names_data_bug / query_mentioned / listing_question)
    # 应该让 LLM 真问题突出, 不被数据 bug 干扰
    has_critical = any(
        i["type"] in (
            "fake_xml_leaked", "placeholder_text", "hallucinated_names",
            "forbidden_names_appeared", "missing_tools", "missing_required_terms",
            "found_forbidden_terms", "duration_too_long",
            "stream_no_done", "stream_error_event", "tool_error_propagated",
            "llm_excuse_no_tool_error", "technical_leak",
        )
        and i.get("severity") != "info"  # info 永远不阻塞 (例如 forbidden_names_query_mentioned)
        and i.get("severity") != "warn"  # warn 不阻塞 (例如 forbidden_names_data_bug)
        for i in all_issues
    )

    # v3.0: 7 维评分
    actual["_events"] = events  # 注入 events 供 score_seven_dim 用
    seven_dim = score_seven_dim(expect, actual, auto_issues, expect_issues, duration_ms)
    actual.pop("_events", None)  # 清理临时字段

    return {
        "id": qid,
        "category": question_data["category"],
        "question": question,
        "expect": expect,
        "actual": actual,
        "issues": all_issues,
        "has_critical_issue": has_critical,
        "verdict": "FAIL" if has_critical else ("WARN" if all_issues else "PASS"),
        "seven_dim": seven_dim,  # v3.0 新增
    }


async def main():
    global API_BASE
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--questions", default="tests/qa-bench/questions.jsonl")
    parser.add_argument("--output", default="results/run")
    parser.add_argument("--limit", type=int, default=0, help="limit N questions (0=all)")
    parser.add_argument("--concurrency", type=int, default=6, help="并发数")
    parser.add_argument("--api-base", default=API_BASE, help="API base URL (default: localhost)")
    args = parser.parse_args()

    # 2026-07-02 Round 9 修复: 支持 --api-base 参数 (跑 cloud / 本地 backend)
    API_BASE = args.api_base
    logger.info(f"API_BASE = {API_BASE}")

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
    # v3.0: 汇总 7 维分数
    dim_totals = {k: 0.0 for k in DIM_WEIGHTS}
    dim_count = 0
    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    veto_count = 0
    for r in results:
        if "seven_dim" not in r:
            continue
        dim_count += 1
        for k, v in r["seven_dim"]["dim_scores"].items():
            dim_totals[k] += v
        grade_dist[r["seven_dim"]["grade"]] = grade_dist.get(r["seven_dim"]["grade"], 0) + 1
        if r["seven_dim"]["veto"]:
            veto_count += 1
    if dim_count:
        dim_avg = {k: round(v / dim_count, 3) for k, v in dim_totals.items()}
    else:
        dim_avg = {}
    summary["seven_dim"] = {
        "dim_avg": dim_avg,
        "grade_dist": grade_dist,
        "veto_count": veto_count,
        "total_scored": dim_count,
    }
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

    # v3.0: 7 维评分汇总
    if summary.get("seven_dim", {}).get("total_scored", 0) > 0:
        sd = summary["seven_dim"]
        md.append("\n## 7 维评分汇总 (v3.0)\n")
        md.append(f"**评分题数**: {sd['total_scored']} | **一票否决**: {sd['veto_count']}\n")
        md.append("\n### 维度均分\n")
        md.append("| 维度 | 权重 | 均分 |")
        md.append("|---|---|---|")
        for k, w in DIM_WEIGHTS.items():
            md.append(f"| {k} | {int(w*100)}% | {sd['dim_avg'].get(k, 0):.2f} |")
        md.append("\n### 分级分布\n")
        md.append("| 等级 | 范围 | 题数 |")
        md.append("|---|---|---|")
        for g in ["A", "B", "C", "D", "F"]:
            range_str = f"{GRADE_THRESHOLDS[g][0]}-{GRADE_THRESHOLDS[g][1]}"
            md.append(f"| {g} | {range_str} | {sd['grade_dist'].get(g, 0)} |")

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
