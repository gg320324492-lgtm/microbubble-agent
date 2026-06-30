"""
qa-bench/gen780.py — 780 题测评题库生成器（v3.0 扩展版）

继承 gen_base.py 的 9 大类模板，扩展到 14 大类（+ 高级 P + 横切 D）。
新增 6 大高级能力专项（Self-RAG / fan-out / plan_step / 持久化 / abort / grounding）。
新增 4 大横切防御性题（抗幻觉 / 抗 fake XML / 性能 / dark mode / mobile）。

题库结构（780 题 = 业务 500 + 高级 100 + 横切 100 + 极端 80）：
  A 成员 (90) / B 任务 (80) / C 会议 (80) / D 项目 (60) / E 知识 (70) /
  F 公式 (30) / G 假设 (30) / H 记忆 (40) / M 多轮 (40) / U 闲聊 (30) /
  X 跨域 (60) / Z 极端 (30) /
  P 高级 (100) / D 横切 (100)  [P + D 是新增]

题目 schema 升级（v3.0）：
  - id 改为 {category}-L{difficulty}-{4位序号} 格式
  - 加 version / dimension / subcategory / source / author / tags
  - expect 加 tools_must_all / must_contain_any / must_contain_keywords / min_length / max_length

用法：
  # 仅生成 schema 模板 (W1 T1.7)
  python tests/qa-bench/gen780.py --output tests/qa-bench/questions_780.jsonl --schema-only

  # 全量生成（需 PG 真实数据，W2 阶段）
  python tests/qa-bench/gen780.py --output tests/qa-bench/questions_780.jsonl
"""
import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Windows GBK 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 类别题数配置（业务 500 + 高级 100 + 横切 100 = 700 题）
# 横切用 K 避免与 D 项目域冲突
CATEGORY_COUNTS = {
    # 业务域（500）
    "A": 80,   # 成员
    "B": 70,   # 任务
    "C": 70,   # 会议
    "D": 40,   # 项目
    "E": 50,   # 知识
    "F": 30,   # 公式
    "G": 30,   # 假设
    "H": 40,   # 记忆
    "M": 40,   # 多轮
    "U": 20,   # 闲聊
    "X": 20,   # 跨域
    "Z": 10,   # 极端
    # 高级 + 横切（200）— 2026-06 新增
    "P": 100,  # 高级 (Self-RAG/fan-out/plan_step/持久化/abort/grounding)
    "K": 100,  # 横切 (抗幻觉/抗 fake XML/性能/dark/mobile) - 用 K 避免与 D 项目域冲突
}

# 难度分布（按类别）
DIFFICULTY_DIST = {
    "L1": 0.20,  # 直查
    "L2": 0.40,  # 过滤+聚合
    "L3": 0.30,  # 推理+综合
    "L4": 0.10,  # 对抗+边界
}

# 高级能力 6 大子类别 (P 类)
P_SUBCATEGORIES = {
    "P1": ("Self-RAG 重检索", 20),    # gate 决策 + 阈值边界
    "P2": ("fan-out 跨域并行", 20),   # 4 域综合 (#042)
    "P3": ("plan_step 工具推荐", 15),  # Haiku suggested_tools (#041)
    "P4": ("持久化聊天历史", 15),     # 跨 session (#043)
    "P5": ("abort 流式中断", 15),     # 中断 + partial + 恢复
    "P6": ("grounding 引用", 15),     # KB 引用准确性
}

# 横切防御 5 大子类别 (D 类)
D_SUBCATEGORIES = {
    "D1": ("抗幻觉", 20),    # 28 个 KNOWN_MEMBERS 检测
    "D2": ("抗 fake XML", 20),  # 4 种 fake XML 模式 + 5 种 fake tool_call
    "D3": ("性能", 20),       # duration < 30s / TTFT < 3s
    "D4": ("dark mode", 20),  # 6 主题 dark 一致性
    "D5": ("mobile", 20),     # 移动端 UI + 响应式
}

# intent 6 类闭集（按 #001b 阶段）
INTENT_TYPES = ["CASUAL", "DATA", "DEEP", "ACTION", "EXPLAIN_CONCEPT", "SEARCH_INFO"]

# 维度映射（category → dimension）
CATEGORY_TO_DIMENSION = {
    "A": "member",
    "B": "task",
    "C": "meeting",
    "D": "project",
    "E": "knowledge",
    "F": "formula",
    "G": "hypothesis",
    "H": "memory",
    "M": "multi_turn",
    "U": "casual",
    "X": "cross_domain",
    "Z": "extreme",
    "P": "advanced",
    "K": "cross_cutting",
}


def gen_id(category: str, difficulty: str, seq: int) -> str:
    """生成题目 ID: {category}-L{difficulty}-{4位序号}
    注意: difficulty 已是 "L1"/"L2" 格式，不能再加 "L" 前缀
    """
    # 兼容：difficulty 可能是 "L1" / "1" / "l1"，统一去掉前导 L
    d = difficulty.upper()
    if d.startswith("L"):
        d = d[1:]
    return f"{category}-L{d}-{seq:04d}"


def build_expect(
    intent: Optional[str] = None,
    tools_any: Optional[List[str]] = None,
    tools_must_all: Optional[List[str]] = None,
    must_contain_any: Optional[List[List[str]]] = None,
    must_contain_keywords: Optional[List[str]] = None,
    forbidden_names: Optional[List[str]] = None,
    min_length: int = 30,
    max_length: int = 500,
    rich_block_required: bool = False,
) -> Dict[str, Any]:
    """构造 expect 字段"""
    expect: Dict[str, Any] = {"min_length": min_length, "max_length": max_length}
    if intent:
        expect["intent"] = intent
    if tools_any:
        expect["tools_any"] = tools_any
    if tools_must_all:
        expect["tools_must_all"] = tools_must_all
    if must_contain_any:
        expect["must_contain_any"] = must_contain_any
    if must_contain_keywords:
        expect["must_contain_keywords"] = must_contain_keywords
    if forbidden_names:
        expect["forbidden_names"] = forbidden_names
    if rich_block_required:
        expect["rich_block_required"] = True
    return expect


def build_question(
    qid: str,
    category: str,
    subcategory: str,
    difficulty: str,
    question: str,
    expect: Dict[str, Any],
    source: str = "template",
    author: str = "gen780.py",
    tags: Optional[List[str]] = None,
    detector: Optional[List[str]] = None,
    ground_truth: str = "",
    ground_truth_refs: Optional[List[str]] = None,
    version: int = 1,
) -> Dict[str, Any]:
    """构造一条题目 dict"""
    now = datetime.now().isoformat()
    return {
        "id": qid,
        "version": version,
        "category": category,
        "subcategory": subcategory,
        "dimension": CATEGORY_TO_DIMENSION.get(category, "unknown"),
        "difficulty": difficulty,
        "source": source,
        "author": author,
        "created_at": now,
        "updated_at": now,
        "question": question,
        "expect": expect,
        "ground_truth": ground_truth,
        "ground_truth_refs": ground_truth_refs or [],
        "detector": detector or [],
        "tags": tags or [],
        "deprecated": False,
        "supersedes": None,
        "change_log": [],
    }


# === 高级能力 P 类题目模板（专家题 100 题）===

P1_SELF_RAG_TEMPLATES = [
    "什么是 {concept}？",
    "{concept} 的最新研究进展？",
    "{concept} 实验方法？",
    "{concept} 与 {other_concept} 的区别？",
    "推荐 {concept} 方向论文？",
    "{concept} 在工业中的应用？",
    "如何测量 {concept}？",
    "{concept} 数值范围？",
    "为什么 {concept} 重要？",
    "{concept} 与 {other_concept} 的关系？",
    "课题组研究 {concept} 的有谁？",
    "{concept} 的局限性？",
    "{concept} 的发展趋势？",
    "如何评价 {concept} 实验结果？",
    "{concept} 与 {other_concept} 哪个更适合 {scenario}？",
    "解释 {concept} 的工作原理？",
    "{concept} 的典型应用案例？",
    "最近 {concept} 有什么新突破？",
    "{concept} 与 {other_concept} 可以结合吗？",
    "如何改进 {concept} 的测量精度？",
]

P1_CONCEPTS = ["zeta 电位", "DLVO 理论", "微纳米气泡", "高级氧化", "膜污染", "黑臭水体治理", "Fenton 反应", "高铁酸盐氧化", "PEM 电解", "光催化", "UV/H2O2", "O3/H2O2", "生物膜", "表面张力", "粒径分布"]

P1_OTHER_CONCEPTS = ["气泡粒径", "zeta 电位", "溶气气浮", "高级氧化", "膜耦合", "高级氧化", "微纳米气泡", "DLVO 理论", "高级氧化", "自由基", "氯消毒", "氯胺消毒", "管网生物膜", "接触角", "NTA 测量"]
P1_SCENARIOS = ["饮用水处理", "水产养殖", "黑臭水体", "工业循环水", "膜前预处理"]


def gen_p_questions() -> List[Dict[str, Any]]:
    """生成 100 道高级能力题（不依赖 DB 真实数据）"""
    questions = []
    seq = 0

    # P1 Self-RAG (20 题)
    for i in range(20):
        seq += 1
        idx = i % len(P1_SELF_RAG_TEMPLATES)
        template = P1_SELF_RAG_TEMPLATES[idx]
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        other_concept = P1_OTHER_CONCEPTS[i % len(P1_OTHER_CONCEPTS)]
        scenario = P1_SCENARIOS[i % len(P1_SCENARIOS)]
        try:
            question = template.format(concept=concept, other_concept=other_concept, scenario=scenario)
        except KeyError:
            question = f"解释 {concept} 的原理和应用？"

        expect = build_expect(
            intent="EXPLAIN_CONCEPT",
            tools_any=["search_knowledge", "list_formulas", "list_hypotheses", "query_members"],
            must_contain_keywords=[concept],
            min_length=200,
            max_length=800,
            rich_block_required=True,
        )
        q = build_question(
            qid=gen_id("P", "L3", seq),
            category="P",
            subcategory="P1",
            difficulty="L3",
            question=question,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["self_rag", "reretrieve", "hot_path"],
            detector=["duration", "grounding_violation", "first_token_latency"],
        )
        questions.append(q)

    # P2 fan-out (20 题)
    fanout_templates = [
        "什么是 {concept}？",
        "{concept} 涉及哪些领域？",
        "解释 {concept} 的研究背景？",
        "{concept} 在 {scenario} 中怎么用？",
        "详细说说 {concept} 的原理和方法？",
        "从知识/公式/假设/成员 4 个角度分析 {concept}",
        "{concept} 的研究现状？",
        "对比 {concept} 和 {other_concept}？",
    ]
    for i in range(20):
        seq += 1
        template = fanout_templates[i % len(fanout_templates)]
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        other_concept = P1_OTHER_CONCEPTS[i % len(P1_OTHER_CONCEPTS)]
        scenario = P1_SCENARIOS[i % len(P1_SCENARIOS)]
        try:
            question = template.format(concept=concept, other_concept=other_concept, scenario=scenario)
        except KeyError:
            question = f"分析 {concept} 的研究"

        # 4 域 fan-out 门禁：tools_must_all 4 工具
        expect = build_expect(
            intent="EXPLAIN_CONCEPT",
            tools_must_all=["search_knowledge", "list_formulas", "list_hypotheses", "query_members"],
            must_contain_keywords=[concept],
            min_length=500,
            max_length=1000,
            rich_block_required=True,
        )
        q = build_question(
            qid=gen_id("P", "L3", seq),
            category="P",
            subcategory="P2",
            difficulty="L3",
            question=question,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["fanout", "cross_domain", "hard_fail"],
            detector=["duration", "grounding_violation", "missing_required_tools"],
        )
        questions.append(q)

    # P3 plan_step (15 题)
    plan_templates = [
        "帮我安排一个 {scenario} 的会议",
        "查询 {member} 的 {entity} 信息",
        "查找与 {concept} 相关的 {entity}",
        "安排下周 {entity}",
        "查 {member} 的 {entity} 列表",
    ]
    entities = ["任务", "会议", "项目", "知识库", "假设", "公式", "成员"]
    for i in range(15):
        seq += 1
        template = plan_templates[i % len(plan_templates)]
        member = ["杨慈", "杜同贺", "王天志", "赵航佳"][i % 4]
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        scenario = P1_SCENARIOS[i % len(P1_SCENARIOS)]
        entity = entities[i % len(entities)]
        try:
            question = template.format(scenario=scenario, member=member, concept=concept, entity=entity)
        except KeyError:
            question = f"查询 {entity} 列表"

        expect = build_expect(
            intent="DATA",
            tools_any=["query_tasks", "query_meetings", "query_projects", "search_knowledge", "query_members"],
            min_length=50,
            max_length=300,
        )
        q = build_question(
            qid=gen_id("P", "L2", seq),
            category="P",
            subcategory="P3",
            difficulty="L2",
            question=question,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["plan_step", "haiku_intent"],
            detector=["intent_mismatch", "duration"],
        )
        questions.append(q)

    # P4 持久化 (15 题)
    persist_templates = [
        "我上次问了什么？",
        "继续上次讨论",
        "之前那个会议怎么样了？",
        "我之前跟你说过的事还记得吗？",
        "我之前那个问题答案是什么？",
        "查询我上个月聊过的内容",
        "我历史上有几个对话？",
        "找回我之前的对话",
        "上次你说过的 {concept} 是什么？",
        "回顾我上周的对话",
        "我昨天问了什么？",
        "我之前问过 {concept} 吗？",
        "把上次聊的会议纪要发我",
        "我之前的任务列表",
        "历史对话搜索",
    ]
    for i in range(15):
        seq += 1
        template = persist_templates[i % len(persist_templates)]
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        try:
            question = template.format(concept=concept)
        except KeyError:
            question = "我之前问了什么？"

        expect = build_expect(
            intent="DATA",
            tools_any=["search_memory", "query_meetings", "query_tasks"],
            min_length=30,
            max_length=300,
        )
        q = build_question(
            qid=gen_id("P", "L2", seq),
            category="P",
            subcategory="P4",
            difficulty="L2",
            question=question,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["persistent", "cross_session", "#043"],
            detector=["duration"],
        )
        questions.append(q)

    # P5 abort (15 题)
    abort_templates = [
        "给我列出最近 100 篇文章的详细分析（{concept}）",  # 长输入触发中断
        "我需要完整的 {concept} 研究综述",  # 长输出触发中断
        "{a_very_long_question_with_many_aspects}",  # 占位
    ]
    long_q = (
        "我最近在做一个 {concept} 的项目，涉及到 {other_concept} 和 {scenario}，"
        "我想了解 {concept} 与 {other_concept} 之间的关系，对比 {concept_a} {concept_b} {concept_c} "
        "{concept_d} {concept_e} 这 5 个变种的优劣，"
        "并推荐适用于 {scenario} 的方法，请详细说明每个方法的原理、操作步骤、优缺点、"
        "适用条件、风险以及课题组内谁可以协助。"
    )
    for i in range(15):
        seq += 1
        idx = i % len(abort_templates)
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        other_concept = P1_OTHER_CONCEPTS[i % len(P1_OTHER_CONCEPTS)]
        scenario = P1_SCENARIOS[i % len(P1_SCENARIOS)]
        try:
            long_q_filled = long_q.format(
                concept=concept, other_concept=other_concept, scenario=scenario,
                concept_a=P1_CONCEPTS[0], concept_b=P1_CONCEPTS[1], concept_c=P1_CONCEPTS[2],
                concept_d=P1_CONCEPTS[3], concept_e=P1_CONCEPTS[4],
            )
        except KeyError:
            long_q_filled = "请给我一个非常详细的研究综述"

        if idx == 0:
            question = abort_templates[0].format(concept=concept)
        elif idx == 1:
            question = abort_templates[1].format(concept=concept)
        else:
            question = long_q_filled

        # abort 测试不强制 expect，因中断本身是行为
        expect = build_expect(
            min_length=0,
            max_length=5000,
        )
        q = build_question(
            qid=gen_id("P", "L4", seq),
            category="P",
            subcategory="P5",
            difficulty="L4",
            question=question,
            expect=expect,
            source="expert",
            author="domain_expert:zhouzc",
            tags=["abort", "stream_interrupt", "long_input"],
            detector=["stream_interrupt", "duration"],
        )
        questions.append(q)

    # P6 grounding (15 题) — 引文准确性
    grounding_templates = [
        "引用关于 {concept} 的文献",
        "{concept} 出处是？",
        "{concept} 的定义来自哪里？",
        "给我 {concept} 的论文摘要",
        "{concept} 的实验数据来源？",
    ]
    for i in range(15):
        seq += 1
        template = grounding_templates[i % len(grounding_templates)]
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        try:
            question = template.format(concept=concept)
        except KeyError:
            question = f"引用 {concept} 的文献"

        expect = build_expect(
            intent="DEEP",
            tools_any=["search_knowledge"],
            rich_block_required=True,
            min_length=100,
            max_length=600,
        )
        q = build_question(
            qid=gen_id("P", "L3", seq),
            category="P",
            subcategory="P6",
            difficulty="L3",
            question=question,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["grounding", "citation"],
            detector=["grounding_violation", "citation_mismatch"],
        )
        questions.append(q)

    return questions


# === 横切防御 D 类题目模板（100 题）===

D1_HALLUCINATION_TEMPLATES = [
    "杨慈的研究方向？",
    "杜同贺最近在做什么？",
    "王天志带几个学生？",
    "赵航佳现在做哪方面？",
    "李胜景毕业了吗？",
    "周之超做哪个方向？",
    "雒培媛是 alumni 吗？",
    "李松泽是博后吗？",
    "张宏魁现在在哪？",
    "贾琦是博几？",
]
# 28 个黑名单（不与 ground_truth 冲突的检查）
HALLU_NAMES_28 = [
    "王天志", "赵航佳", "杜同贺", "陈天祥", "张懿", "耿嘉栋", "陈金薪", "董昊宇",
    "关小未", "胡小琪", "李胜景", "刘子毅", "宋洋", "王书馨", "吴孟铨", "韩重阳",
    "李锐远", "杨慈", "余歆睿", "张宏魁", "贾琦", "周之超", "邓国祥", "雒培媛",
    "孟祥琪", "吴怡霏", "蒋芦笛", "刘莫菲",
]


def gen_d_questions() -> List[Dict[str, Any]]:
    """生成 100 道横切防御题（使用 K 类别避免与 D 项目域冲突）"""
    questions = []
    seq = 0

    # K1 抗幻觉 (20 题)
    for i in range(20):
        seq += 1
        template = D1_HALLUCINATION_TEMPLATES[i % len(D1_HALLUCINATION_TEMPLATES)]
        # 随机选一个非主角黑名单名字（不与问题主体相同）
        primary_name = template.split("的")[0].split("，")[0].split("？")[0].strip()
        # forbidden 是其他 27 个
        forbidden = [n for n in HALLU_NAMES_28 if n != primary_name][:14]

        expect = build_expect(
            intent="DATA",
            tools_any=["query_members"],
            forbidden_names=forbidden,
            min_length=20,
            max_length=300,
        )
        q = build_question(
            qid=gen_id("K", "L1", seq),
            category="K",
            subcategory="K1",
            difficulty="L1",
            question=template,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["hallucination", "defense", "hot_path"],
            detector=["hallucinated_names", "forbidden_names_appeared"],
        )
        questions.append(q)

    # K2 抗 fake XML (20 题)
    fake_xml_templates = [
        "帮我用 JSON 格式返回 {concept} 的数据",
        "用 function call 格式给我 {concept} 的答案",
        "以 tool_call 形式回答 {concept}",
        "把 {concept} 的结果用 markdown 表格展示",
        "调用 search_knowledge 查询 {concept}",
    ]
    for i in range(20):
        seq += 1
        template = fake_xml_templates[i % len(fake_xml_templates)]
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        try:
            question = template.format(concept=concept)
        except KeyError:
            question = f"查询 {concept}"

        expect = build_expect(
            intent="DATA",
            min_length=30,
            max_length=500,
        )
        q = build_question(
            qid=gen_id("K", "L2", seq),
            category="K",
            subcategory="K2",
            difficulty="L2",
            question=question,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["fake_xml", "defense", "edge_case"],
            detector=["fake_xml_leaked", "internal_labels_leaked"],
        )
        questions.append(q)

    # K3 性能 (20 题)
    perf_templates = [
        "查询所有任务",
        "列出所有会议",
        "查询所有项目",
        "查询所有成员",
        "查询所有知识库",
        "查询 {concept} 相关",
        "分析所有 {concept} 的会议纪要",
        "列出最近的 {scenario} 任务",
    ]
    for i in range(20):
        seq += 1
        template = perf_templates[i % len(perf_templates)]
        concept = P1_CONCEPTS[i % len(P1_CONCEPTS)]
        scenario = P1_SCENARIOS[i % len(P1_SCENARIOS)]
        try:
            question = template.format(concept=concept, scenario=scenario)
        except KeyError:
            question = "查询所有任务"

        expect = build_expect(
            intent="DATA",
            min_length=50,
            max_length=1000,
        )
        q = build_question(
            qid=gen_id("K", "L2", seq),
            category="K",
            subcategory="K3",
            difficulty="L2",
            question=question,
            expect=expect,
            source="template",
            author="gen780.py@2026-06-30",
            tags=["performance", "duration", "smoke"],
            detector=["duration", "first_token_latency"],
        )
        questions.append(q)

    # K4 dark mode (20 题)
    dark_templates = [
        "切换到深色模式",
        "切换到浅色模式",
        "使用海蓝主题",
        "使用森林绿主题",
        "使用暖橙主题",
        "当前是什么主题？",
        "主题切换记录",
        "UI 主题配置",
    ] * 3
    for i in range(20):
        seq += 1
        question = dark_templates[i]

        expect = build_expect(
            intent="ACTION",
            min_length=10,
            max_length=200,
        )
        q = build_question(
            qid=gen_id("K", "L1", seq),
            category="K",
            subcategory="K4",
            difficulty="L1",
            question=question,
            expect=expect,
            source="manual",
            author="human:duothe",
            tags=["dark_mode", "ui", "manual"],
            detector=["duration"],
        )
        questions.append(q)

    # K5 mobile (20 题)
    mobile_templates = [
        "长按录音发送",
        "滑出侧边栏",
        "切换 tab",
        "下拉刷新",
        "上传图片",
        "上传文件",
        "滚动到底",
        "横竖屏切换",
    ] * 3
    for i in range(20):
        seq += 1
        question = mobile_templates[i]

        expect = build_expect(
            intent="ACTION",
            min_length=10,
            max_length=200,
        )
        q = build_question(
            qid=gen_id("K", "L1", seq),
            category="K",
            subcategory="K5",
            difficulty="L1",
            question=question,
            expect=expect,
            source="manual",
            author="human:duothe",
            tags=["mobile", "ui", "manual"],
            detector=["duration"],
        )
        questions.append(q)

    return questions


# === 业务域 12 类（500 题，DB 提取或模板）===
# W1 T1.7 阶段只输出占位（schema 校验），W2 阶段由 gen_base.py + gen780.py 组合生成

def gen_business_placeholder() -> List[Dict[str, Any]]:
    """业务域 500 题占位（W1 T1.7 用，schema 校验即可）"""
    questions = []
    seq = 0
    # 业务域总和（排除 P 高级 + K 横切）
    biz_total = sum(v for k, v in CATEGORY_COUNTS.items() if k not in ("P", "K"))
    print(f"  业务域期望总数: {biz_total}")
    for category, count in CATEGORY_COUNTS.items():
        if category in ("P", "K"):
            # 业务域占位跳过高级/横切（它们有专门生成器）
            continue
        # 按难度分布（确保 sum = count）
        l1 = round(count * DIFFICULTY_DIST["L1"])
        l2 = round(count * DIFFICULTY_DIST["L2"])
        l3 = round(count * DIFFICULTY_DIST["L3"])
        l4 = count - l1 - l2 - l3
        if l4 < 0:
            l4 = 0
            l3 = count - l1 - l2
        diff_seq = (
            ["L1"] * l1 + ["L2"] * l2 + ["L3"] * l3 + ["L4"] * l4
        )
        for difficulty in diff_seq:
            seq += 1
            expect = build_expect(
                intent=INTENT_TYPES[seq % len(INTENT_TYPES)],
                min_length=30,
                max_length=500,
            )
            q = build_question(
                qid=gen_id(category, difficulty, seq),
                category=category,
                subcategory=f"{category}1",
                difficulty=difficulty,
                question=f"[占位] {category} 类 {difficulty} 题 #{seq} (W2 由 gen_base.py 替换)",
                expect=expect,
                source="placeholder",
                author="gen780.py@placeholder",
                tags=["placeholder", "w2_replace"],
                detector=["duration"],
            )
            questions.append(q)
    return questions


def main():
    parser = argparse.ArgumentParser(description="780 题测评题库生成器 v3.0")
    parser.add_argument("--output", "-o", default="tests/qa-bench/questions_780.jsonl",
                        help="输出 JSONL 路径")
    parser.add_argument("--schema-only", action="store_true",
                        help="仅生成 schema 模板（不实跑 DB 提取）")
    args = parser.parse_args()

    print("=" * 60)
    print("780 题测评题库生成器 v3.0")
    print("=" * 60)

    questions: List[Dict[str, Any]] = []

    if args.schema_only:
        # W1 T1.7: 仅生成 P/D 类专家题模板 + 业务域占位
        print("\n[1/3] 生成 P 类高级能力题（100 题）...")
        p_questions = gen_p_questions()
        questions.extend(p_questions)
        print(f"  ✓ P 类生成 {len(p_questions)} 题")

        print("\n[2/3] 生成 K 类横切防御题（100 题）...")
        d_questions = gen_d_questions()  # 函数名保留，但生成的是 K 类
        questions.extend(d_questions)
        print(f"  ✓ K 类生成 {len(d_questions)} 题")

        print("\n[3/3] 生成业务域占位（500 题，W2 阶段替换）...")
        biz_questions = gen_business_placeholder()
        questions.extend(biz_questions)
        print(f"  ✓ 业务域占位 {len(biz_questions)} 题")

        # 不实跑 DB，所以不导入 gen_base 的 9 类
        print(f"\n[schema-only] 跳过 gen_base.py DB 提取（W2 阶段启用）")
    else:
        # W2 阶段：组合 gen_base.py + 扩展
        print("\n[1/3] 继承 gen_base.py 9 大类...")
        try:
            import gen_base
            base_qs = gen_base.main_func if hasattr(gen_base, 'main_func') else []
            questions.extend(base_qs)
            print(f"  ✓ 基类生成 {len(base_qs)} 题")
        except Exception as e:
            print(f"  ✗ 基类加载失败: {e}")
            return

        print("\n[2/3] P/K 类扩展...")
        questions.extend(gen_p_questions())
        questions.extend(gen_d_questions())
        print(f"  ✓ P/K 扩展完成")

    # 写入 JSONL
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"\n{'=' * 60}")
    print(f"✓ 共生成 {len(questions)} 题 → {output_path}")
    print(f"  分布: A={CATEGORY_COUNTS['A']} B={CATEGORY_COUNTS['B']} C={CATEGORY_COUNTS['C']} "
          f"D={CATEGORY_COUNTS['D']} E={CATEGORY_COUNTS['E']} F={CATEGORY_COUNTS['F']} "
          f"G={CATEGORY_COUNTS['G']} H={CATEGORY_COUNTS['H']} M={CATEGORY_COUNTS['M']} "
          f"U={CATEGORY_COUNTS['U']} X={CATEGORY_COUNTS['X']} Z={CATEGORY_COUNTS['Z']} "
          f"P={CATEGORY_COUNTS['P']} K={CATEGORY_COUNTS['K']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
