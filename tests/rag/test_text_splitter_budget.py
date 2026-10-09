"""split_for_tsvector 输出预算回归 (2026-10-09, agent24)

事故背景
--------
`split_for_tsvector` 的 `max_chars` 截的是**原始输入**, 而 `" ".join(tokens)`
会在每两个 jieba token 之间插 1 个空格 —— 中文平均词长 1.5-2.5 字, 拼接后
长度系统性膨胀 20%-60% (实测 5400 字原文 -> 6599 字输出, +22%)。

输出撞库约束
`ck_knowledge_search_text_len (search_text IS NULL OR length(search_text) <= 6000)`
-> 抛异常 -> 被 3 个入库钩子 (`knowledge_service.py:63` / `:208`,
`rag_auto_ingest_service.py:161`) 的 `except` **吞成 warning**
-> 表现为 **search_text 静默留空** (全文检索通道对该文档彻底失效, 无报错)。

本文件锁死的不变量:
  I1. len(split_for_tsvector(text, max_chars=N)) <= N          (对任意 N)
  I2. 输出的每个空格分隔段都是**完整 token**, 不出现半个词
  I3. 保持前缀语义 (预算裁剪不会重新排序/跳词)
  I4. max_chars 真的生效 (修复前 truncate_for_embedding 分支完全忽略它)
  I5. 短文本 (< 预算) 行为与修复前逐字节一致

设计约束
--------
- 不依赖 jieba: 半词断言用 `tokenize_chinese` 自己产出的 token 集合做参照,
  jieba 可用/不可用两种模式下断言都成立 (容器内 production 必装 jieba)。
- 不连数据库: 纯函数测试, 可在任意 CI 片跑。
"""
import pytest


# ============== fixtures / helpers ==============

# 6000 = ck_knowledge_search_text_len 的 CHECK 上限 (alembic 089)
CHECK_MAX = 6000

# 中文 PPT 正文风格样本 (jieba 会切成大量 1-3 字短词 -> 空格膨胀最严重)
CN_PPT = "项目背景：微纳米气泡在污水处理中的应用研究。技术路线包括气液两相流制备。"
# 英文/ASCII 长 run (jieba 输出 1 个超长 token -> 几乎不膨胀)
ASCII_RUN = "a" * 8000
# 中英混排
MIXED = "微纳米气泡 research progress 进展 "*300


def _reference_tokens(text: str, max_chars: int = CHECK_MAX):
    """复刻 split_for_tsvector 的切词步骤, 产出"合法 token 全集"参照"""
    from app.services.embedding_truncation_policy import truncate_for_embedding
    from app.services.text_splitter import tokenize_chinese

    truncated = truncate_for_embedding(text)
    if len(truncated) > max_chars:
        truncated = truncated[:max_chars]
    return tokenize_chinese(truncated)


def _assert_no_half_token(out: str, text: str, max_chars: int = CHECK_MAX):
    """I2: 输出每个空格分隔段必须是切词产出的**完整** token"""
    allowed = set(_reference_tokens(text, max_chars))
    for seg in out.split(" "):
        if seg:
            assert seg in allowed, f"半词/非法 token: {seg!r} 不在切词结果中"


def _assert_within(out: str, max_chars, label: str):
    """I1: 输出长度硬门"""
    if max_chars is not None:
        assert len(out) <= max_chars, f"{label}: 输出 {len(out)} > 预算 {max_chars}"


# ============== 核心复现: raw 8000 -> 输出必须 <= 6000 ==============

# (label, raw, ids) —— ids 显式给短名, 否则 pytest 用整个 4000+ 字样本当 test id
OVERSIZE_CASES = [
    ("chinese_ppt", CN_PPT * 120),          # ~4320 字, 输出实测曾膨胀
    ("chinese_dense", "微纳米气泡研究进展" * 600),  # 5400 字 -> 6599 (实测撞线)
    ("ascii_run", ASCII_RUN),               # 8000 字
    ("mixed_cjk_en", MIXED),                # 8100 字
]
OVERSIZE_IDS = [c[0] for c in OVERSIZE_CASES]


@pytest.mark.parametrize("label,raw", OVERSIZE_CASES, ids=OVERSIZE_IDS)
def test_budget_01_oversize_input_respects_check(label, raw):
    """I1 (bug 直接复现): 输入超 6000 时, 输出必须 <= 6000

    变异测试锚点: 修复前 line 161-168 只截输入, `chinese_dense` 输出 6599 > 6000 -> RED
    """
    from app.services.text_splitter import split_for_tsvector

    out = split_for_tsvector(raw)  # 默认 max_chars=6000
    _assert_within(out, CHECK_MAX, label)
    _assert_no_half_token(out, raw, CHECK_MAX)


# ============== 边界值 ==============

@pytest.mark.parametrize("n", [0, 1, 2, 10, 5999, 6000, 6001, 20000])
def test_budget_02_exact_length_boundaries(n):
    """边界: raw 长度 = 0/1/2/10/5999/6000/6001/20000 时输出均 <= 6000"""
    from app.services.text_splitter import split_for_tsvector

    raw = "微纳米气泡研究进展" * (n // 8 + 1)
    raw = raw[:n] if n else ""
    out = split_for_tsvector(raw)
    _assert_within(out, CHECK_MAX, f"n={n}")
    if out:
        _assert_no_half_token(out, raw, CHECK_MAX)


@pytest.mark.parametrize("budget", [1, 5, 17, 100, 999, 5999, 6000, 6001, 10000])
def test_budget_03_arbitrary_budgets(budget):
    """I1: 对任意 max_chars, 输出长度都不超预算"""
    from app.services.text_splitter import split_for_tsvector

    for raw in (CN_PPT * 120, "微纳米气泡研究进展" * 600, ASCII_RUN, MIXED):
        out = split_for_tsvector(raw, max_chars=budget)
        _assert_within(out, budget, f"budget={budget}")
        if out:
            _assert_no_half_token(out, raw, budget)


def test_budget_04_one_char_budget_returns_empty_not_crash():
    """极端预算: max_chars=1 时不崩、不超长 (不可能装下任何 >=2 字 token)"""
    from app.services.text_splitter import split_for_tsvector

    out = split_for_tsvector(CN_PPT * 50, max_chars=1)
    assert len(out) <= 1


def test_budget_05_exact_fit_not_over_truncated():
    """预算刚好装下时不应多砍: 单 token 长度 == 预算 -> 原样返回

    注: 用 jieba 不会拆开的词 ("气泡" 而非 "微气泡" —— 后者被切成
    ["微", "气泡"], 单字 "微" 又被 tokenize_chinese 的 len<=1 规则滤掉)
    """
    from app.services.text_splitter import split_for_tsvector

    out = split_for_tsvector("气泡", max_chars=2)
    assert out == "气泡"
    assert len(out) == 2

    # 预算差 1 时只保留能装下的部分, 且仍是完整 token
    out2 = split_for_tsvector("气泡", max_chars=1)
    assert len(out2) <= 1
    _assert_no_half_token(out2, "气泡", 1)


# ============== 中文 / 混排 的膨胀差异 ==============

def test_budget_06_chinese_inflation_is_the_root_cause():
    """取证: 中文输入切词拼接确实膨胀, ASCII run 不膨胀 —— 证明必须按输出裁剪

    这条不是断言"必须膨胀"(jieba 版本变化会波动), 而是记录实测行为:
    同一个 8000 字量级下, 中文输出显著长于 ASCII 输出。
    """
    from app.services.text_splitter import split_for_tsvector

    cn = split_for_tsvector("微纳米气泡研究进展" * 600)
    en = split_for_tsvector(ASCII_RUN)
    # ASCII run 被切成单个超长 token, 几乎无空格膨胀
    assert " " not in en.strip() or en.count(" ") < cn.count(" ")


def test_budget_07_mixed_cjk_en_no_half_token():
    """中英混排下的半词断言 (jieba 对英文按空格/标点切, 对中文按词切)"""
    from app.services.text_splitter import split_for_tsvector

    out = split_for_tsvector(MIXED)
    _assert_within(out, CHECK_MAX, "mixed")
    _assert_no_half_token(out, MIXED, CHECK_MAX)


# ============== 修复前第二个 bug: max_chars 被忽略 ==============

def test_budget_08_max_chars_actually_honored():
    """I4: max_chars 真生效

    变异测试锚点: 修复前 `truncate_for_embedding` 分支硬编码 MAX_EMBED_INPUT_CHARS,
    `split_for_tsvector('a'*8000, max_chars=100)` 实测返回 6000 字符 -> RED
    """
    from app.services.text_splitter import split_for_tsvector

    assert len(split_for_tsvector(ASCII_RUN, max_chars=100)) <= 100
    assert len(split_for_tsvector(CN_PPT * 120, max_chars=100)) <= 100
    assert len(split_for_tsvector(MIXED, max_chars=250)) <= 250


def test_budget_09_max_chars_none_means_no_cap():
    """文档化语义: max_chars=None = 不裁剪 (调用方显式放弃上限)"""
    from app.services.text_splitter import split_for_tsvector

    out = split_for_tsvector("微纳米气泡研究进展" * 600, max_chars=None)
    assert len(out) > CHECK_MAX  # 确实不裁剪 (与 docstring 一致)


# ============== 前缀语义 / 与修复前一致 ==============

def test_budget_10_prefix_semantics_preserved():
    """I3: 预算裁剪保留**前缀**, 不跳词、不重排

    对比"无预算输出"的前缀 —— 修复前的行为是"取原文前 N 字",
    修复后是"取输出前 N 字", 但两者都是前缀, 且起点一致。
    """
    from app.services.text_splitter import split_for_tsvector

    full = split_for_tsvector(CN_PPT * 120, max_chars=None)
    budgeted = split_for_tsvector(CN_PPT * 120, max_chars=200)
    assert budgeted  # 非空
    assert full.startswith(budgeted), "预算输出必须是完整输出的前缀"
    assert len(budgeted) <= 200


def test_budget_11_short_text_byte_identical_to_legacy():
    """I5: 输入本就短于预算时, 输出与"纯 joiner"逐字节一致 (未引入回归)"""
    from app.services.text_splitter import split_for_tsvector, tokens_to_tsvector_input
    from app.services.text_splitter import tokenize_chinese

    short = "微纳米气泡在污水处理中的应用研究"
    assert split_for_tsvector(short) == tokens_to_tsvector_input(
        tokenize_chinese(truncate_for_embedding_safe(short))
    )


def truncate_for_embedding_safe(text: str) -> str:
    """小 helper: 短文本不会被截断, 直接返回原文"""
    from app.services.embedding_truncation_policy import truncate_for_embedding

    return truncate_for_embedding(text)


# ============== tokens_to_tsvector_input 保持纯 joiner ==============

def test_budget_12_tokens_to_tsvector_input_still_pure_joiner():
    """边界说明: 长度裁剪只在 split_for_tsvector 内做, joiner 不变

    (避免下游误以为 joiner 会截断 —— 它的 docstring 已写明)
    """
    from app.services.text_splitter import tokens_to_tsvector_input

    assert tokens_to_tsvector_input([]) == ""
    assert tokens_to_tsvector_input(["微气泡", "zeta"]) == "微气泡 zeta"
    # 超长 token 不会被 joiner 截断 (调用方自行负责)
    assert tokens_to_tsvector_input(["x" * 9999]) == "x" * 9999


# ============== 空输入 ==============

@pytest.mark.parametrize("raw", ["", "   ", "\n\t "])
def test_budget_13_blank_input_returns_empty(raw):
    from app.services.text_splitter import split_for_tsvector

    assert split_for_tsvector(raw) == ""
    assert split_for_tsvector(raw, max_chars=100) == ""