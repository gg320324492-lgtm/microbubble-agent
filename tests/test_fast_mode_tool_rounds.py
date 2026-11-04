"""fast 模式按需放行 Phase 1 工具循环 (2026-11-04)

## 要修的到底是什么

`resolve_thinking_config("fast")` 把 `max_tool_rounds=0`,
`agentic_loop.run()` 在 831 行 `min()` 一钳 ⇒ **整段 Phase 1 工具循环不跑**,
所有意图都拿不到真实数据, 只能凭对话历史答 (答"暂未找到"或编)。

⚠️ **930 行那个白名单不是开关** —— 它是 Phase 0 强制预派工具的白名单,
而 fast 的 `skip_plan_step=True` 让那一整段根本不执行。改它既不生效,
还会拆掉当年「闲聊/写操作不误调」的保护。本测试用 AST 钉住这一点。

## 设计

- 只给**只读**的 DATA_QUERY / RECOMMEND_PERSON / SEARCH_INFO 放行有限轮
  (默认 2, << balanced 的 5) ⇒ 保住 fast 的「快」;
- EXECUTE_ACTION 刻意不放 —— fast 原本没有写库能力, 放行 = 悄悄新增写路径;
- CASUAL_CHAT / FOLLOW_UP / EXPLAIN_CONCEPT / TEAM_OVERVIEW 保持 0 轮;
- `AGENT_FAST_TOOL_ROUNDS_FOR_DATA_INTENTS=0` 即完全回退到旧行为。
"""
import ast
import pathlib

import pytest

from app.agent.agentic_loop import _FAST_DATA_INTENTS
from app.agent.intent_classifier import IntentCategory
from app.agent.thinking_config import resolve_thinking_config
from app.config import settings

REPO = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- 意图集合


def test_only_readonly_data_intents_allowed():
    assert _FAST_DATA_INTENTS == frozenset({
        IntentCategory.DATA_QUERY,
        IntentCategory.RECOMMEND_PERSON,
        IntentCategory.SEARCH_INFO,
    })


def test_write_intent_stays_disabled():
    """⛔ 写操作不放行 —— 别在"让答案有数据"里顺手新增一条写路径。"""
    assert IntentCategory.EXECUTE_ACTION not in _FAST_DATA_INTENTS


def test_chitchat_and_overview_stay_disabled():
    for cat in (IntentCategory.CASUAL_CHAT, IntentCategory.FOLLOW_UP,
                IntentCategory.EXPLAIN_CONCEPT, IntentCategory.TEAM_OVERVIEW):
        assert cat not in _FAST_DATA_INTENTS, "%s 不该在 fast 下起工具" % cat.value


def test_config_default_and_rollback():
    """默认 2 轮; 设 0 就是旧行为 (灰度回退开关)。"""
    assert settings.AGENT_FAST_TOOL_ROUNDS_FOR_DATA_INTENTS == 2
    assert settings.AGENT_FAST_TOOL_ROUNDS_FOR_DATA_INTENTS < settings.AGENT_MAX_TOOL_ROUNDS, (
        "fast 的放行轮数必须小于 balanced 的 5 轮, 否则失去「快」的语义")


def test_thinking_config_frozen_unchanged():
    """配置层没被改动 —— 放行逻辑在 loop 层, 冻结的 dataclass 保持原值。"""
    fast = resolve_thinking_config("fast")
    assert fast.max_tool_rounds == 0
    assert fast.skip_plan_step is True
    assert resolve_thinking_config("balanced").max_tool_rounds == settings.AGENT_MAX_TOOL_ROUNDS


# ---------------------------------------------------------------- 真值表 (纯函数)


def resolve_effective_rounds(mode: str, category: IntentCategory, flag: int = 2) -> int:
    """复刻 agentic_loop.run() 里那段判据的纯函数版本, 便于穷举真值表。

    ⚠️ 这不是生产代码的一份拷贝, 而是**契约测试**: 生产实现若漂移成
    "所有意图都放行"或"写操作也放行", 下面的真值表会与生产 AST 守卫一起红。
    """
    cfg = resolve_thinking_config(mode)
    configured = cfg.max_tool_rounds
    if mode == "fast" and configured == 0 and category in _FAST_DATA_INTENTS:
        configured = min(flag, settings.AGENT_MAX_TOOL_ROUNDS)
    return min(settings.AGENT_MAX_TOOL_ROUNDS, configured)


@pytest.mark.parametrize("cat,expected", [
    (IntentCategory.DATA_QUERY, 2),
    (IntentCategory.RECOMMEND_PERSON, 2),
    (IntentCategory.SEARCH_INFO, 2),
    (IntentCategory.EXECUTE_ACTION, 0),
    (IntentCategory.CASUAL_CHAT, 0),
    (IntentCategory.FOLLOW_UP, 0),
    (IntentCategory.EXPLAIN_CONCEPT, 0),
    (IntentCategory.TEAM_OVERVIEW, 0),
])
def test_fast_truth_table(cat, expected):
    assert resolve_effective_rounds("fast", cat) == expected


@pytest.mark.parametrize("mode", ["balanced", "deep"])
def test_non_fast_modes_unchanged(mode):
    """改动不得影响 balanced / deep 的任何意图。"""
    for cat in IntentCategory:
        assert resolve_effective_rounds(mode, cat) == settings.AGENT_MAX_TOOL_ROUNDS


def test_flag_zero_is_full_rollback():
    for cat in IntentCategory:
        assert resolve_effective_rounds("fast", cat, flag=0) == 0


def test_flag_cannot_exceed_global_cap():
    assert resolve_effective_rounds("fast", IntentCategory.DATA_QUERY, flag=999) == \
        settings.AGENT_MAX_TOOL_ROUNDS


# ---------------------------------------------------------------- 结构守卫


def test_release_is_in_loop_not_in_thinking_config():
    """AST: 放行判据必须在 agentic_loop.run() 里, 不能改 frozen 配置类。

    若有人把 `resolve_thinking_config("fast")` 的 max_tool_rounds 直接改成 2,
    所有 fast 意图(含闲聊与写操作)都会起工具 —— 正是要防的回归。
    """
    tc_src = (REPO / "app/agent/thinking_config.py").read_text(encoding="utf-8")
    tree = ast.parse(tc_src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "resolve_thinking_config")
    # 找到 fast 分支里的 max_tool_rounds 关键字值, 必须是字面量 0
    vals = [
        kw.value for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        for kw in n.keywords
        if kw.arg == "max_tool_rounds"
    ]
    assert any(isinstance(v, ast.Constant) and v.value == 0 for v in vals), (
        "fast 的配置层默认值被改了 —— 放行应在 loop 层按意图做")
    assert "AGENT_FAST_TOOL_ROUNDS_FOR_DATA_INTENTS" not in tc_src, (
        "灰度开关不该进 thinking_config: 那是全局配置, 会让所有意图一起变")


def test_loop_gate_checks_mode_round_and_intent():
    """AST: loop 里的放行必须同时判 mode / 原值 0 / 意图在只读集合。

    ⚠️ 用 AST 节点判, 不要用 `ast.dump()` 里搜字符串 —— 第一版就栽在
    "configured == 0" 这种源码空格形式根本不出现在 dump 里 (类 20.229:
    探针只产候选, 结论要按被程序消费的结构判)。
    """
    src = (REPO / "app/agent/agentic_loop.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    run_fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "run")
    gates = [n for n in ast.walk(run_fn) if isinstance(n, ast.If)]

    # 找 test 里带 _FAST_DATA_INTENTS 的 if。
    # ⚠️ 不能按「body 里含日志字符串」找 —— ast.walk 是广度优先,
    # 外层 `if _has_thinking_config(ctx):` 的 body 也含内层日志, 会被先命中,
    # 而它的 test 里根本没有判据 (本次首版就栽在这里)。
    targets = [
        g for g in gates if "_FAST_DATA_INTENTS" in ast.dump(g.test)
    ]
    assert len(targets) == 1, "放行分支应恰有一个, 实得 %d" % len(targets)
    target = targets[0]

    test_src = ast.dump(target.test)
    assert "'fast'" in test_src, "没判 mode == fast"
    assert "_FAST_DATA_INTENTS" in test_src, "没判意图白名单"
    # configured == 0 在 AST 里是 Compare(left=Name('configured'), Eq, Constant(0))
    has_zero_guard = any(
        isinstance(n, ast.Compare)
        and isinstance(n.left, ast.Name) and n.left.id == "configured"
        and any(isinstance(c, ast.Constant) and c.value == 0 for c in n.comparators)
        for n in ast.walk(target.test)
    )
    assert has_zero_guard, "没判「原值必须是 0」⇒ 会改变 balanced/deep 的行为"


def _phase0_whitelist(tree):
    """精确定位 Phase 0 那个 if (含 AGENT_PLAN_STEP_ENABLED) 里的意图集合。

    不扫全文件的所有 set —— 本仓别处也有含 DATA_QUERY 的集合,
    全扫会把它们误算进白名单 (类 20.226 ⑨: 探针只产候选)。
    """
    for n in ast.walk(tree):
        if not isinstance(n, ast.If) or "AGENT_PLAN_STEP_ENABLED" not in ast.dump(n.test):
            continue
        for sub in ast.walk(n.test):
            if isinstance(sub, ast.Set):
                names = {
                    getattr(e, "attr", "") for e in sub.elts
                    if isinstance(e, ast.Attribute)
                }
                if "SEARCH_INFO" in names:
                    return names
    return set()


def test_phase0_whitelist_not_widened():
    """AST: Phase 0 白名单保持原样 (3 类)。

    改它既不解决 fast 无工具的问题, 还会让 balanced/deep 多派工具 ——
    这是本次最容易「改错地方」的陷阱, 用结构守卫钉住。
    """
    src = (REPO / "app/agent/agentic_loop.py").read_text(encoding="utf-8")
    allowed = _phase0_whitelist(ast.parse(src))
    assert allowed == {"SEARCH_INFO", "EXPLAIN_CONCEPT", "TEAM_OVERVIEW"}, (
        "Phase 0 白名单被改动: %s" % allowed)
    for forbidden in ("EXECUTE_ACTION", "CASUAL_CHAT", "DATA_QUERY", "RECOMMEND_PERSON"):
        assert forbidden not in allowed, (
            "%s 被塞进 Phase 0 强制预派白名单 —— 会误调工具" % forbidden)
