#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W2 T2.3 — DB 提取 117 题（从 PostgreSQL 抽真实数据生成）"""
import json, sys, io, os
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import psycopg2
from psycopg2.extras import RealDictCursor

OUT = Path("/tmp/questions_db_117.jsonl")  # write to container, then docker cp
NOW = "2026-06-30T16:35:00Z"

# Connect to PG inside Docker network
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "microbubble2026")
DB_NAME = os.environ.get("DB_NAME", "microbubble")


def connect():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
                            password=DB_PASS, dbname=DB_NAME)


KM = ["王天志","杜同贺","赵航佳","杨慈","宋洋","贾琦","李胜景","李松泽","周之超",
      "苏杭","王田志","邹雨","梁博","雒培媛","李胜奕","吴梦全","吴孟全","吴孟拴",
      "赵航家","王天之","洪辉","李子涵","张红","刘红","韩梅","陈伟","测试","test_json","test_user"]


def M(cat, sub, diff, dim, n, q, gt, tools, intent="data_query", must=None, kw=None, mn=20, mx=300, r=False, tags=None):
    return {
      "id": f"{cat}-L{diff[1]}-{n:04d}", "version": 3, "category": cat,
      "subcategory": sub, "dimension": dim, "difficulty": diff,
      "source": "db_extract", "author": "db_extractor.py@2026-06-30",
      "created_at": NOW, "updated_at": NOW, "question": q,
      "expect": {"intent": intent, "tools_any": tools, "tools_must_all": [],
        "must_contain_any": must or [], "forbidden_names": KM,
        "must_contain_keywords": kw or [], "min_length": mn, "max_length": mx,
        "rich_block_required": r, "domain_check": None},
      "ground_truth": gt,
      "ground_truth_refs": [f"kb://{cat.lower()}/x{n}"],
      "detector": ["hallucinated_names", "filler_phrases", "fake_xml", "duration"],
      "tags": ["db_extract", "real_data"] + (tags or []),
      "deprecated": False, "supersedes": None,
    }


def main():
    questions = []
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    seq = {"A": 100, "B": 100, "C": 200, "D": 250, "E": 300,
           "F": 400, "G": 400, "H": 400, "M": 500, "U": 500, "X": 500, "Z": 500}

    # ============= A 成员 (19 题) =============
    cur.execute("SELECT id, name, role, research_area, grade FROM members WHERE is_active = true ORDER BY id")
    members = cur.fetchall()
    print(f"[A] 抽出 {len(members)} 个活跃成员")

    # A1 基础信息 (5)
    for i, m in enumerate(members[:5]):
        questions.append(M("A", "A1", "L1", "member", seq["A"],
            f"{m['name']}是学生吗？他的研究方向是什么？",
            f"{m['name']}是课题组{m['role'] or '成员'}，研究方向为{m['research_area'] or '（未填写）'}。",
            ["query_members"], must=[[m["name"]]], mn=20))
        seq["A"] += 1

    # A2 画像 (5) - 多跳查询
    for i, m in enumerate(members[5:10]):
        if m.get("research_area"):
            questions.append(M("A", "A2", "L2", "member", seq["A"],
                f"课题组成员中谁的研究方向跟「{m['research_area']}」相关？",
                f"研究方向为「{m['research_area']}」的成员：{m['name']}（{m['role'] or '成员'}）。",
                ["query_members"], must=[[m["name"]], [m["research_area"]]], mn=30))
            seq["A"] += 1

    # A3 任务聚合 (4)
    for i, m in enumerate(members[10:14]):
        questions.append(M("A", "A3", "L2", "member", seq["A"],
            f"{m['name']}最近的任务有哪些？",
            f"{m['name']}当前任务列表请查询数据库（实际状态）。",
            ["query_member_tasks"], must=[[m["name"]]], mn=30))
        seq["A"] += 1

    # A4 跨人 (5)
    for i, m in enumerate(members[14:19]):
        questions.append(M("A", "A4", "L2", "member", seq["A"],
            f"列出与{m['name']}研究方向相近的其他成员。",
            f"{m['name']}的研究方向为{m['research_area'] or '（未填写）'}，相近方向成员查询请见数据库。",
            ["query_members"], must=[[m["name"]]], mn=30))
        seq["A"] += 1

    # ============= B 任务 (16 题) =============
    cur.execute("""SELECT id, title, status, priority, assignee_id,
        (SELECT name FROM members WHERE id = tasks.assignee_id) AS assignee_name
        FROM tasks ORDER BY id LIMIT 16""")
    tasks = cur.fetchall()
    print(f"[B] 抽出 {len(tasks)} 个任务")

    for i, t in enumerate(tasks):
        diff = "L2" if i < 5 else "L3"
        if t.get("assignee_name"):
            questions.append(M("B", "B1" if i < 8 else "B2", diff, "task", seq["B"],
                f"{t['assignee_name']}当前的任务「{t['title']}」是什么状态？",
                f"{t['assignee_name']}的任务「{t['title']}」当前状态为「{t['status']}」，优先级「{t['priority'] or '（未填）'}」。",
                ["query_member_tasks"], must=[[t["assignee_name"]], [t["title"]]], mn=30))
            seq["B"] += 1

    # ============= C 会议 (16 题) =============
    cur.execute("""SELECT id, title, start_time, status FROM meetings ORDER BY id LIMIT 16""")
    meetings = cur.fetchall()
    print(f"[C] 抽出 {len(meetings)} 个会议")

    for i, mt in enumerate(meetings):
        diff = "L2" if i < 8 else "L3"
        questions.append(M("C", "C1" if i < 6 else "C2", diff, "meeting", seq["C"],
            f"会议「{mt['title']}」是什么时候开始的？",
            f"会议「{mt['title']}」开始时间 {mt['start_time']}，状态：{mt['status'] or '（未填）'}。",
            ["query_meetings"], must=[[mt["title"]]], mn=30))
        seq["C"] += 1

    # ============= D 项目 (9 题) =============
    cur.execute("SELECT id, name, status, research_area FROM projects ORDER BY id")
    projects = cur.fetchall()
    print(f"[D] 抽出 {len(projects)} 个项目")

    for i, p in enumerate(projects):
        diff = "L2" if i < 4 else "L3"
        ra = p.get("research_area") or "未填"
        questions.append(M("D", "D1", diff, "project", seq["D"],
            f"项目「{p['name']}」当前进展如何？",
            f"项目「{p['name']}」状态：{p['status']}，研究领域：{ra}。",
            ["query_projects"], must=[[p["name"]]], mn=30))
        seq["D"] += 1
    # 加 5 个 D2 摘要
    for i, p in enumerate(projects[:5]):
        questions.append(M("D", "D2", "L3", "project", seq["D"],
            f"详细说明项目「{p['name']}」的内容。",
            f"项目「{p['name']}」状态：{p['status']}。详细描述请查询数据库。",
            ["query_project_detail"], must=[[p["name"]]], mn=50, r=True))
        seq["D"] += 1

    # ============= E 知识 (12 题) =============
    cur.execute("""SELECT id, title, summary, category FROM knowledge
        WHERE title IS NOT NULL ORDER BY id LIMIT 12""")
    kbs = cur.fetchall()
    print(f"[E] 抽出 {len(kbs)} 条知识")

    for i, kb in enumerate(kbs):
        diff = "L2" if i < 6 else "L3"
        questions.append(M("E", "E1", diff, "knowledge", seq["E"],
            f"知识库中关于「{kb['title']}」的内容是什么？",
            f"{kb['title']}（{kb.get('category', '通用')}）：{kb.get('summary', '（无摘要）')[:80]}。",
            ["search_knowledge"], must=[[kb["title"]]], mn=30))
        seq["E"] += 1

    # ============= F 公式 (7 题) =============
    cur.execute("""SELECT id, name, formula_latex, domain FROM knowledge_formulas
        WHERE formula_latex IS NOT NULL ORDER BY id LIMIT 7""")
    formulas = cur.fetchall()
    print(f"[F] 抽出 {len(formulas)} 个公式")

    for i, f in enumerate(formulas):
        diff = "L2" if i < 3 else "L3"
        questions.append(M("F", "F1", diff, "formula", seq["F"],
            f"公式「{f['name']}」的具体表达式是什么？",
            f"{f['name']} 公式：{f.get('formula_latex', '（未填）')}，领域：{f.get('domain', '通用')}。",
            ["list_formulas"], must=[[f["name"]]], mn=30))
        seq["F"] += 1

    # ============= G 假设 (7 题) =============
    cur.execute("""SELECT id, statement, status, confidence FROM knowledge_hypotheses
        WHERE statement IS NOT NULL ORDER BY id LIMIT 7""")
    hyps = cur.fetchall()
    print(f"[G] 抽出 {len(hyps)} 个假设")

    for i, h in enumerate(hyps):
        diff = "L2" if i < 3 else "L3"
        conf = h.get("confidence") or "未填"
        questions.append(M("G", "G1", diff, "knowledge", seq["G"],
            f"假设「{(h.get('statement') or '未填')[:30]}…」当前的验证状态？",
            f"假设状态：{h.get('status', '未填')}，置信度：{conf}。",
            ["list_hypotheses"], must=[], mn=30))
        seq["G"] += 1

    # ============= H 记忆 (9 题) =============
    cur.execute("""SELECT id, content, user_id,
        (SELECT name FROM members WHERE id = memories.user_id) AS member_name
        FROM memories WHERE is_active = true ORDER BY id LIMIT 9""")
    mems = cur.fetchall()
    print(f"[H] 抽出 {len(mems)} 条记忆")

    for i, mem in enumerate(mems):
        diff = "L2" if i < 5 else "L3"
        if mem.get("member_name"):
            questions.append(M("H", "H2", diff, "memory", seq["H"],
                f"{mem['member_name']}有哪些长期记忆？",
                f"{mem['member_name']}的长期记忆条目请查询数据库（共多条）。",
                ["query_long_memory"], must=[[mem["member_name"]]], mn=30))
            seq["H"] += 1

    # ============= M 多轮 (9 题) =============
    # 多轮场景模板，基于真实数据
    for i, m in enumerate(members[:9]):
        questions.append(M("M", "M1", "L2", "memory", seq["M"],
            f"上次我们聊到「{m['name']}」时讨论了什么？",
            f"上次对话涉及「{m['name']}」相关话题，详情请查询短期/长期记忆。",
            ["query_short_memory"], must=[[m["name"]]], mn=30))
        seq["M"] += 1

    # ============= U 闲聊 (5 题) =============
    cur.execute("SELECT count(*) AS n FROM members WHERE is_active = true")
    total_members = cur.fetchone()["n"]
    for i, m in enumerate(members[:5]):
        questions.append(M("U", "U1", "L1", "casual", seq["U"],
            f"我们课题组有多少人？{m['name']}在吗？",
            f"课题组共 {total_members} 人，{m['name']}当前在组内。",
            [], intent="casual_chat", must=[[f"{total_members}"], [m["name"]]], mn=20))
        seq["U"] += 1

    # ============= X 跨域 (5 题) =============
    if members and projects:
        for i in range(min(5, len(members))):
            m = members[i]
            p = projects[i % len(projects)]
            questions.append(M("X", "X1", "L3", "cross_domain", seq["X"],
                f"结合成员和项目，「{m['name']}」在「{p['name']}」中负责什么？",
                f"{m['name']}在「{p['name']}」中参与情况需结合成员-项目关联表查询。",
                ["query_members", "query_project_detail"], must=[[m["name"]], [p["name"]]], mn=80, r=True))
            seq["X"] += 1

    # ============= Z 极端 (2 题) =============
    questions.append(M("Z", "Z4", "L1", "member", seq["Z"],
        "天志同学在吗？",
        "「天志」可能是「王天志」的昵称/简称。王天志当前在组内。",
        ["query_members"], must=[["王天志"]], mn=15))
    seq["Z"] += 1
    questions.append(M("Z", "Z4", "L2", "casual", seq["Z"],
        "微泡研究方向咋样了？",
        "「微泡」即「微纳米气泡」。课题组研究方向：①微气泡应用（赵航佳）；②微气泡稳定性（杨慈、王田志）。",
        ["query_members", "search_knowledge"], intent="casual_chat", must=[["微纳米气泡"]], mn=30))
    seq["Z"] += 1

    cur.close()
    conn.close()

    with OUT.open("w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"\n[OK] {len(questions)} 道 DB 题写入 {OUT}")


if __name__ == "__main__":
    main()