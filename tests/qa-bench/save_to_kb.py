"""
qa-bench/save_to_kb.py — 把 onebyone_log.jsonl 中高分 (4-5) 答案批量保存到知识库

设计：
- 读 results/onebyone_log.jsonl
- 筛 auto_score >= 4 的题（高质量回答）
- 对每条调用 save_conversation_knowledge 工具的语义：直接 DB INSERT 到 knowledge 表
- 标记 title 用 "拓展-{id}-{topic}"
- 关联到 category=知识库分类

由于 save_conversation_knowledge 工具需要 LLM 来分类（耗时），
我们用直接的 SQL INSERT 来快速保存（绕过 LLM 分类）。
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import psycopg2
import psycopg2.extras


CATEGORY_MAP = {
    "core": "基础知识",
    "method": "实验方法",
    "industry": "行业应用",
    "application": "应用案例",
    "academic": "学术研究",
    "policy": "政策法规",
    "theory": "理论基础",
    "emerging": "新兴方向",
}


def save_to_knowledge_base():
    log_path = Path("results/onebyone_log.jsonl")
    if not log_path.exists():
        print(f"❌ 找不到 {log_path}")
        return

    results = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("id", "").startswith("S") and d.get("quality", {}).get("auto_score", 0) >= 4:
                results.append(d)

    print(f"📊 高分 (≥4/5) 题: {len(results)}")

    if not results:
        print("没有需要保存的")
        return

    # 用 docker exec 内部 psql (避免本地连不到 db)
    # 改成本地通过 docker cp + 容器内 python 插入
    import subprocess

    # 生成 SQL 脚本
    sql_statements = []
    saved = 0
    skipped = 0
    for r in results:
        qid = r["id"]
        question = r["question"]
        content = r["content"]
        if not content or len(content) < 100:
            skipped += 1
            continue
        scope = r.get("scope", "core")
        category = CATEGORY_MAP.get(scope, "基础知识")
        title = f"[拓展-{qid}] {question[:60]}"
        # 用 Question + Answer 形式存
        full_content = f"## 问题\n{question}\n\n## 回答\n{content}"
        sql_statements.append({
            "id": qid, "title": title, "category": category, "content": full_content,
            "scope": scope, "score": r["quality"]["auto_score"],
        })
        saved += 1

    print(f"准备保存 {saved} 条到知识库（跳过 {skipped} 条过短）")

    # 通过 docker exec 在容器内用 Python 插入（用容器内的 DB 连接）
    code = '''
import sys
import psycopg2
import psycopg2.extras
import json

statements = json.loads(sys.stdin.read())
conn = psycopg2.connect(
    host="db", port=5432, dbname="microbubble",
    user="postgres", password="microbubble2026",
)
cur = conn.cursor()
inserted = 0
errors = []
for stmt in statements:
    try:
        cur.execute("""
            INSERT INTO knowledge (title, category, content, knowledge_type, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        """, (stmt["title"], stmt["category"], stmt["content"], stmt["scope"]))
        result = cur.fetchone()
        if result:
            inserted += 1
            stmt["db_id"] = result[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        errors.append(f"{stmt['id']}: {str(e)[:100]}")

print(f"\\n✅ 插入 {inserted} 条到 knowledge 表")
if errors:
    print(f"\\n❌ 失败 {len(errors)} 条:")
    for e in errors[:5]:
        print(f"  {e}")
conn.close()
'''

    # 把 Python 脚本写到本地临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        script_path = f.name

    # 复制到容器
    subprocess.run(["docker", "cp", script_path, "microbubble-agent-app-1:/tmp/save_kb.py"], check=True)

    # 写入 statements 到临时文件
    tmp_json = Path("/tmp/save_statements.json")
    tmp_json.write_text(json.dumps(sql_statements, ensure_ascii=False), encoding="utf-8")

    # 复制到容器
    subprocess.run(["docker", "cp", str(tmp_json.absolute()), "microbubble-agent-app-1:/tmp/save_statements.json"], check=True)

    # 容器内执行
    result = subprocess.run(
        ["docker", "exec", "microbubble-agent-app-1", "bash", "-c",
         "cat /tmp/save_statements.json | python /tmp/save_kb.py"],
        capture_output=True, text=True, timeout=120,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ 错误: {result.stderr[:500]}")


if __name__ == "__main__":
    save_to_knowledge_base()
