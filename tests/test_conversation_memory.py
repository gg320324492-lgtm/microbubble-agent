"""对话长期记忆 (2026-11-04 C 档) —— 溢出捕获 + 语义召回

覆盖三层，缺一不可:

1. **筛选规则** (纯函数): 尤其「只存 user 轮」这一条 —— 把模型输出回灌成记忆
   = 把幻觉固化成"事实"，本仓为此付过代价 (memory #30)，所以它是**回归目标**，
   不只是实现细节;
2. **两道门禁**: 特性开关默认关 (灰度)，以及「embedding 模型没热就别召回」
   —— 召回挂在首字延迟的关键路径上，而按需加载冷启动实测 20–36 秒;
3. **接线**: 用 AST 断言两条对话路径都接了捕获、system 构造里真的调了召回
   (类 20.250 ①「同一门禁多个写入方必须逐一对齐」+ 类 20.225「用 AST 不用 grep」)。

另有一个走真测试库的往返用例 —— `memories` 表建了三年**从未有 ORM 覆盖过**，
这条是唯一能证明「模型映射与真表列对得上、向量检索真的能跑」的证据 (类 20.220)。
"""
import ast
import pathlib

import pytest

from app.config import settings
from app.services.conversation_memory_service import (
    MAX_CONTENT_CHARS,
    MEMORY_TYPE_EPISODE,
    content_key,
    format_memory_block,
    pick_memorable_turns,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


def _user(text):
    return {"role": "user", "content": text}


def _assistant(text):
    return {"role": "assistant", "content": text}


# ---------------------------------------------------------------- 筛选规则


def test_only_user_turns_are_kept():
    """⛔ 助手输出**绝不**入库 —— 那是幻觉的自我固化通道。"""
    dropped = [
        _user("我们组今年的重点是臭氧耦合微纳米气泡处理养殖尾水"),
        _assistant("好的，已记录该研究方向为臭氧微纳米气泡处理。"),
    ]
    out = pick_memorable_turns(dropped)
    assert len(out) == 1
    assert "我们组今年的重点" in out[0]
    assert all("已记录" not in t for t in out), "模型输出被当成用户记忆存下了"


def test_tool_result_user_turn_is_not_memory():
    """role=user 但内容是 tool_result —— 那是系统数据，不是用户说过的话。

    存进去会在召回时把工具返回冒充成"用户原话"喂回模型。
    """
    dropped = [{"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tu_1", "content": "成员列表..."}]}]
    assert pick_memorable_turns(dropped) == []


def test_text_block_user_turn_is_extracted():
    """Anthropic 风格的块数组内容要能取到文本。"""
    dropped = [{"role": "user", "content": [
        {"type": "text", "text": "参数记一下：气液比 1:8，接触时间 25 分钟"}]}]
    out = pick_memorable_turns(dropped)
    assert out and "气液比 1:8" in out[0]


def test_short_turns_are_dropped():
    assert pick_memorable_turns([_user("嗯"), _user("继续"), _user("好的")]) == []


def test_min_chars_boundary_is_explicit():
    """19 字丢 / 20 字留 —— 边界写死，防测试数据自己踩线还以为是实现坏了。"""
    from app.services.conversation_memory_service import MIN_TURN_CHARS
    just_under = "甲" * (MIN_TURN_CHARS - 1)
    at_line = "甲" * MIN_TURN_CHARS
    assert pick_memorable_turns([_user(just_under)]) == []
    assert len(pick_memorable_turns([_user(at_line)])) == 1


def test_long_turn_is_truncated_to_cap():
    out = pick_memorable_turns([_user("纳米气泡" * 500)])
    assert len(out) == 1
    assert len(out[0]) <= MAX_CONTENT_CHARS


def test_duplicate_within_batch_appears_once():
    t = "下周组会轮流汇报，顺序按上一轮的逆序来安排"
    out = pick_memorable_turns([_user(t), _user(t), _user(t)])
    assert len(out) == 1


def test_polluted_turn_is_not_stored():
    """带原生工具标记的污染轮不得进长期记忆。

    标记按**拼接**构造 —— 测试文件里直接写字面量的话，这个文件自己就会
    "包含标记"，与本仓 message_sanitizer 同样的自我匹配坑 (类 20.225)。
    """
    marker = "]" + "minimax" + "["
    polluted = "先说一句正常的话" + marker + "query_members{}" + "x" * 30
    out = pick_memorable_turns([_user(polluted)])
    assert out == []


def test_content_key_is_stable_and_distinct():
    assert content_key("甲乙丙") == content_key("  甲乙丙  ")  # 前后空白无关
    assert content_key("甲乙丙") != content_key("甲乙丁")
    assert len(content_key("x")) == 16  # 存进 varchar(20)  comfortably


def test_junk_input_tolerated():
    assert pick_memorable_turns(None) == []
    assert pick_memorable_turns([]) == []
    assert pick_memorable_turns([None, "不是dict", 123, {}]) == []


# ---------------------------------------------------------------- 注入块


class _Row:
    def __init__(self, content):
        self.content = content
        self.id = 1


def test_no_memories_yields_empty_block():
    assert format_memory_block([]) == ""


def test_block_heading_matches_prompts_discipline():
    """注入标题必须含「长期记忆」—— prompts.py 的反幻觉纪律按这个名字生效。

    这是**跨文件耦合**：prompts.py 改了称呼而这里没跟着改，那条纪律就指向空气。
    所以断言直接读 prompts.py 的原文，而不是各写一份常量。
    """
    block = format_memory_block([_Row("某条历史原话")])
    assert "长期记忆" in block
    prompts_src = (REPO / "app/agent/prompts.py").read_text(encoding="utf-8")
    assert "长期记忆" in prompts_src, "prompts.py 已不再提长期记忆, 该复核这条断言"


def test_block_carries_reverify_instruction():
    """注入块自带"必须重新验证"，与 prompts.py:381 同一条反幻觉纪律。"""
    block = format_memory_block([_Row("张三负责膜分离那一块")])
    assert "参考" in block and ("重新" in block or "验证" in block)
    assert "- 张三负责膜分离那一块" in block


def test_block_flattens_newlines():
    """记忆条内的换行会破坏 "- " 列表结构，必须压平。"""
    block = format_memory_block([_Row("第一行\n第二行")])
    assert "第一行 第二行" in block


# ---------------------------------------------------------------- 两道门禁


@pytest.mark.asyncio
async def test_capture_disabled_by_flag_touches_nothing(monkeypatch):
    """开关关掉时**完全不碰 DB / 不碰模型** —— 默认关是灰度前提。"""
    import app.core.database as database_mod
    import app.services.embedding_service as emb

    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", False)

    def _boom(*a, **k):
        raise AssertionError("开关关闭时不应建立 DB session")

    class _Exploding:
        def __call__(self, *a, **k):
            _boom()

    monkeypatch.setattr(database_mod, "async_session", _Exploding())

    async def _never(*a, **k):
        raise AssertionError("开关关闭时不应调用 embedding")

    monkeypatch.setattr(emb, "generate_embeddings", _never)

    from app.services.conversation_memory_service import capture_overflow
    assert await capture_overflow(1, [_user("一条足够长的历史用户原话内容")], "s1") == 0


@pytest.mark.asyncio
async def test_recall_skipped_when_model_cold(monkeypatch):
    """⚠️ 核心延迟回归: embedding 未加载时**不得**触发加载。

    召回在 `_build_system_prompt` 里，挂在**首字延迟**的关键路径上；
    按需加载冷启动实测 20–36 秒 (类 20.237)，而 generate_embedding 的超时是 60s
    ⇒ 不设这道门的话，冷卡时用户的"助手卡住半分钟"就是这里来的。
    """
    import app.services.embedding_service as emb

    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", True)
    monkeypatch.setattr(emb, "is_embedding_loaded", lambda: False)

    called = []

    async def _spy(*a, **k):
        called.append(1)
        return [0.0] * 1024

    monkeypatch.setattr(emb, "generate_embedding", _spy)

    from app.services.conversation_memory_service import recall_memories
    assert await recall_memories(object(), 1, "臭氧气泡") == []
    assert called == [], "冷模型时被触发了 embedding (会把首字延迟拖成几十秒)"


@pytest.mark.asyncio
async def test_recall_guards_bad_args(monkeypatch):
    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", True)
    from app.services.conversation_memory_service import recall_memories
    assert await recall_memories(None, 1, "x") == []       # 无 db
    assert await recall_memories(object(), None, "x") == []  # 无用户
    assert await recall_memories(object(), 1, "   ") == []   # 空 query
    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_TOP_K", 0)
    assert await recall_memories(object(), 1, "有内容的问题") == []  # top_k=0 = 关闭


@pytest.mark.asyncio
async def test_recall_returns_empty_on_exception(monkeypatch):
    """召回失败必须返 []，**不许把异常抛到对话主流程**。"""
    import app.services.embedding_service as emb

    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", True)
    monkeypatch.setattr(emb, "is_embedding_loaded", lambda: True)

    async def _explode(*a, **k):
        raise RuntimeError("embedding 后端挂了")

    monkeypatch.setattr(emb, "generate_embedding", _explode)

    from app.services.conversation_memory_service import recall_memories
    assert await recall_memories(object(), 1, "问题内容") == []


@pytest.mark.asyncio
async def test_capture_swallows_embedding_failure(monkeypatch):
    """写路径失败也不能冒泡 —— 它在 create_task 里，抛出去没有接收方。"""
    import app.services.embedding_service as emb

    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", True)

    async def _none(*a, **k):
        return None

    monkeypatch.setattr(emb, "generate_embeddings", _none)

    from app.services.conversation_memory_service import capture_overflow
    assert await capture_overflow(1, [_user("一条足够长会被写入的用户历史原话")], "s") == 0


# ---------------------------------------------------------------- 默认值


def test_flag_defaults_off():
    """默认关 —— 增益链路先灰度, 由主指挥决定放量。"""
    assert settings.CONVERSATION_MEMORY_ENABLED is False
    assert settings.CONVERSATION_MEMORY_TOP_K > 0
    assert settings.CONVERSATION_MEMORY_MAX_PER_USER > 0


# ---------------------------------------------------------------- 白名单灰度


def test_parse_allowed_users_handles_junk(monkeypatch):
    """坏值跳过并记日志，不该让整份名单静默失效。"""
    from app.services.conversation_memory_service import parse_allowed_users
    assert parse_allowed_users("3, 58 ,7") == {3, 58, 7}
    assert parse_allowed_users("") == set()
    assert parse_allowed_users("3,abc,58") == {3, 58}
    assert parse_allowed_users(None) == set()


@pytest.mark.parametrize("raw,flag,uid,expected", [
    # 白名单非空 ⇒ 优先于总开关: 名单内即使总开关关着也生效 (灰度期的形态)
    ("3,58", False, 3, True),
    ("3,58", False, 58, True),
    ("3,58", False, 9, False),
    ("3,58", True, 9, False),
    # 白名单为空 ⇒ 退回全局总开关
    ("", False, 3, False),
    ("", True, 3, True),
    # 无名用户一律关
    ("3", True, None, False),
])
def test_whitelist_truth_table(monkeypatch, raw, flag, uid, expected):
    """完整真值表 —— 两侧门禁共用这一个函数, 表对了行为就不会分叉。"""
    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ALLOWED_USERS", raw)
    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", flag)
    from app.services.conversation_memory_service import is_conversation_memory_enabled
    assert is_conversation_memory_enabled(uid) is expected


def test_three_gates_share_the_whitelist_predicate():
    """AST 守卫: 起任务 / 写库 / 召回 **三处**都调同一个判据。

    这是类 20.250 ① 的直接落地: 灰度期最容易写坏的形态是「读时判白名单、
    写时判总开关」⇒ 名单内用户的记忆永远写不进去 (或反过来一直空跑召回)，
    而总开关关着时**全链路看起来都很安静**，没有任何报错 (类 20.220)。
    """
    svc = (REPO / "app/services/conversation_memory_service.py").read_text(encoding="utf-8")
    tree = ast.parse(svc)
    fns = _funcs(tree)
    for name in ("capture_overflow", "recall_memories"):
        calls = [
            n for n in ast.walk(fns[name]) if isinstance(n, ast.Call)
            and (getattr(n.func, "id", "") == "is_conversation_memory_enabled")
        ]
        assert calls, "%s 没有走统一判据" % name
        # 不许再直接读总开关 (那样就绕过白名单)
        assert not any(
            isinstance(n, ast.Attribute) and n.attr == "CONVERSATION_MEMORY_ENABLED"
            for n in ast.walk(fns[name])
        ), "%s 里仍直接判总开关 ⇒ 白名单会被绕过" % name

    agent_src = (REPO / "app/agent/micro_bubble_agent.py").read_text(encoding="utf-8")
    agent_tree = ast.parse(agent_src)
    fn = _funcs(agent_tree)["_capture_overflow_memory"]
    assert any(
        isinstance(n, ast.Call) and getattr(n.func, "id", "") == "is_conversation_memory_enabled"
        for n in ast.walk(fn)
    ), "起后台任务处没有走统一判据"
    assert "CONVERSATION_MEMORY_ENABLED" not in ast.dump(fn), (
        "起后台任务处仍直接判总开关 ⇒ 灰度用户根本不会起捕获任务")


def test_memory_type_fits_column():
    """`memory_type` 是 varchar(20), 超长会在**写库时**才炸。"""
    assert len(MEMORY_TYPE_EPISODE) <= 20


# ---------------------------------------------------------------- 接线守卫


def _funcs(tree):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            out.setdefault(node.name, node)
    return out


def test_both_chat_paths_capture_overflow():
    """chat() 与 chat_stream() 都必须调 `_capture_overflow_memory`。

    与 B 档那条「两条路径都走预算门禁」是同一条纪律 (类 20.250 ①):
    只接一条的话，非流式路径的历史会永久丢失而流式路径不会 ——
    这种"一半路径生效"的缺陷在功能测试里极难看出 (类 20.220)。
    """
    src = (REPO / "app/agent/micro_bubble_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    agent_cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MicroBubbleAgent")
    covered = set()
    for fn in agent_cls.body:
        if not isinstance(fn, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if fn.name not in ("chat", "chat_stream"):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
                if name == "_capture_overflow_memory":
                    covered.add(fn.name)
    assert covered == {"chat", "chat_stream"}, "只接了 %s" % covered


def test_overflow_is_unpacked_not_sliced_by_caller():
    """两条路径都必须是 `a, b = _trim_messages_to_budget(...)`。

    为什么盯这个形状: 切点会为对齐合法轮次边界而**向前扩展**，被裁掉的是哪几条
    只有裁剪内部知道。调用方自己按 `len(kept)` 反推切片边界 ⇒ 会把仍送给模型的
    轮次也存进记忆，或漏存真正被裁掉的轮次。
    """
    src = (REPO / "app/agent/micro_bubble_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fns = _funcs(tree)
    # 模块函数本身返回二元组
    ret = next(
        n for n in ast.walk(fns["_trim_messages_to_budget"])
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple)
    )
    assert len(ret.value.elts) == 2, "必须返回 (窗口, 溢出区间)"

    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            f = node.value.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name == "_trim_messages_to_budget" and isinstance(node.targets[0], ast.Tuple):
                targets.add(tuple(elt.id for elt in node.targets[0].elts))
    assert targets, "没有任何调用点解包溢出区间"
    assert all(len(t) == 2 for t in targets), "调用点解包个数不对: %s" % targets


def test_system_prompt_injects_long_term_memory():
    """`_build_system_prompt` 必须真的调召回 —— 否则 prompts.py 的"长期记忆"
    section 又是一张空头支票 (C 档之前的状态)。
    """
    src = (REPO / "app/agent/micro_bubble_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = _funcs(tree)["_build_system_prompt"]
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    assert "recall_and_format" in names, "system 里没有注入长期记忆"


def test_memory_model_is_registered():
    """`Memory` 必须在 app/models/__init__.py 里被 import。

    漏了这一条: 测试库 create_all 没有 memories 表 (本用例集立刻红)，
    生产侧则是 alembic autogenerate 看不见它。
    """
    src = (REPO / "app/models/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imported.extend(a.name for a in node.names)
    assert "Memory" in imported, "Memory 未注册, create_all 不会建这张表"


def test_capture_uses_background_task_not_inline_await():
    """写路径必须是 create_task，不能 await 在对话里。

    embedding 冷启动 20–36s (类 20.237)，同步等待等于把每轮对话的首字延迟
    变成半分钟。同时必须**持有 task 引用** —— 裸 create_task 的返回值不被保存时
    任务可能被 GC 回收，表现为"一条都没写、也没有任何报错" (类 20.220)。
    """
    src = (REPO / "app/agent/micro_bubble_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = _funcs(tree)["_capture_overflow_memory"]
    assert not any(isinstance(n, ast.Await) for n in ast.walk(fn)), (
        "捕获里有 await —— 会在对话主路径上同步等 embedding")
    body_src = ast.dump(fn)
    assert "create_task" in body_src, "没有起后台任务"
    assert "_BG_MEMORY_TASKS" in body_src, "create_task 的返回值没被持有引用"


# ---------------------------------------------------------------- 真库往返


@pytest.mark.asyncio
async def test_capture_then_recall_roundtrip(db, monkeypatch):
    """端到端 (真测试库): 写入 → 去重 → 向量召回命中最相关的一条。

    `memories` 表自 2026-05 建表起从未有 ORM 读写覆盖，这条断言是
    「模型列与真表对得上、cosine_distance 在这张表上跑得通」的唯一证据
    (类 20.220 —— 单元 mock 全绿不代表真表能用)。
    """
    import app.services.embedding_service as emb

    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", True)

    # 确定性正交向量: 不用 hash() —— Python 的字符串 hash 按进程随机化,
    # 两条文本可能撞进同一个桶, 排序就没有唯一正确答案 (本次首轮实测踩过:
    # 召回把第二条排到了前面)。按关键词分配互不重叠的维度 ⇒
    # 同方向 cosine_distance=0, 正交=1, "最相关"有硬判据。
    def vec(seed: str):
        base = [0.0] * 1024
        if "膜分离" in seed or "刘莫菲" in seed:
            base[0] = 1.0
        else:
            base[1] = 1.0
        return base

    async def fake_docs(texts, for_query=False, has_query_prompt=False):
        return [vec(t) for t in texts]

    from app.services.conversation_memory_service import (
        capture_overflow, pick_memorable_turns, recall_memories)

    user_id = 9911
    turns = [
        _user("养殖尾水的膜分离预处理由刘莫菲负责对接，下周三之前把方案发给我"),
        _user("臭氧投加量按 1.2 mg/L 计算接触时间，先跑一个星期的对照"),
        _assistant("已记录上述两条要点。"),      # 不该入库
    ]
    written = await capture_overflow(user_id, turns, "roundtrip-session")
    assert written == 2, "只应写入 2 条 user 原话"

    # 幂等: 同一批再投一次不该翻倍 (该表**无唯一约束**, 全靠 key 去重)
    assert await capture_overflow(user_id, turns, "roundtrip-session") == 0

    from app.models.memory import Memory
    rows = (await db.execute(
        Memory.__table__.select().where(Memory.user_id == user_id)
    )).mappings().all()
    assert len(rows) == 2
    assert all(r["memory_type"] == MEMORY_TYPE_EPISODE for r in rows)

    query_kwargs = []

    async def fake_query(text, for_query=None, has_query_prompt=False, caller_path=None):
        # ⚠️ 查询侧必须与存档侧**同表征**: 现役 hybrid_retriever 传的是
        # (for_query=True, has_query_prompt=False) ⇒ build_embedding_prompt(True, False)
        # 返回 None ⇒ 两侧都是无前缀。若这里悄悄改成真 query 模式, 召回会静默变差
        # 且不报错 (类 20.220)。所以除了验证排序, 还要**记下实参**核口径。
        query_kwargs.append({"for_query": for_query, "has_query_prompt": has_query_prompt})
        return vec(pick_memorable_turns(turns)[0])  # 与第一条同方向 ⇒ 应召回第一条

    monkeypatch.setattr(emb, "generate_embedding", fake_query)
    monkeypatch.setattr(emb, "is_embedding_loaded", lambda: True)

    got = await recall_memories(db, user_id, "膜分离那件事谁负责")
    assert query_kwargs == [{"for_query": False, "has_query_prompt": False}], (
        "查询向量口径与存档侧不一致: %s" % query_kwargs)
    assert got, "召回为空 —— 往返链路没通"
    assert "刘莫菲" in got[0].content

    block = format_memory_block(got)
    assert "长期记忆" in block and "刘莫菲" in block

    # 清理: 别把测试数据留给下一个用例
    await db.execute(Memory.__table__.delete().where(Memory.user_id == user_id))
    await db.commit()


@pytest.mark.asyncio
async def test_whitelist_isolation_in_real_db(db, monkeypatch):
    """真库: 名单内用户能写能读, 名单外用户**读不到别人的记忆**。

    白名单不只是"少几个人用", 它同时是隐私边界 —— `recall_memories` 的
    `user_id` 过滤若被绕过, A 用户的历史原话会被注入到 B 用户的 system 里。
    """
    import app.services.embedding_service as emb

    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ALLOWED_USERS", "3")
    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ENABLED", False)  # 仍关着

    def vec(_):
        return [1.0] + [0.0] * 1023

    async def fake_docs(texts, for_query=False, has_query_prompt=False):
        return [vec(t) for t in texts]

    monkeypatch.setattr(emb, "generate_embeddings", fake_docs)
    monkeypatch.setattr(emb, "is_embedding_loaded", lambda: True)

    async def fake_query(*a, **k):
        return vec("q")

    monkeypatch.setattr(emb, "generate_embedding", fake_query)

    from app.services.conversation_memory_service import (
        capture_overflow, recall_memories, is_conversation_memory_enabled)
    from app.models.memory import Memory

    # inside 必须**真的在白名单里** —— 首版写成 9921 而白名单是 "3",
    # 断言自己就 false 了 (测试数据自相矛盾, 不是实现缺陷)。
    inside, outside = 3, 9922
    text = "灰度用户的内部编号是紫蓝鲸七七四一，年底复盘时要用"
    assert is_conversation_memory_enabled(inside) is True
    assert is_conversation_memory_enabled(outside) is False

    # 名单外用户即使被直接调 service，也不会写进去
    assert await capture_overflow(outside, [_user(text)], "isolate") == 0
    # 名单内用户写入 (总开关仍 False ⇒ 证明白名单真的优先)
    assert await capture_overflow(inside, [_user(text)], "isolate") == 1

    got_in = await recall_memories(db, inside, "编号是多少")
    assert got_in and "紫蓝鲸" in got_in[0].content
    # 名单外: 判据直接拦掉
    assert await recall_memories(db, outside, "编号是多少") == []

    # 即便把名单外用户也加进白名单 (绕过判据硬查)，SQL 的 user_id 过滤
    # 也必须挡住 —— 纵深防御，不把隐私边界全押在应用层一个 if 上。
    monkeypatch.setattr(settings, "CONVERSATION_MEMORY_ALLOWED_USERS", "3,9922")
    got_cross = await recall_memories(db, outside, "编号是多少")
    assert got_cross == [], "跨用户读到了别人的记忆"

    await db.execute(Memory.__table__.delete().where(
        Memory.user_id.in_([inside, outside]),
        Memory.source_session == "isolate"))
    await db.commit()
