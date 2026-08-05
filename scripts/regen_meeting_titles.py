"""Generate AI meeting titles via direct ollama call.
Bypasses celery worker contention / startup ordering issues.
W2 +N 2026-08-05: 会议 229/202/242/260 仍是"正在听会（ID X）"占位符.
"""
import json
import sys
import urllib.request
import os
import asyncio

# Add app path
sys.path.insert(0, r'E:\microbubble-agent')

# 导入 - 先确保 docker cp 同步
import subprocess

CONFIRM = "--confirm" in sys.argv

# 4 个 placeholder 会议
MEETING_IDS = [229, 202, 242, 260]

# 1. 取每个会议 transcript
def fetch_transcripts(ids):
    """通过 API 取会议 (用 wangtianzhi admin token)"""
    import requests
    token_resp = requests.post(
        "https://agent.mnb-lab.cn/api/v1/auth/login",
        json={"username": "wangtianzhi", "password": "123456"},
        timeout=30,
    )
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    results = {}
    for mid in ids:
        r = requests.get(
            f"https://agent.mnb-lab.cn/api/v1/meetings/{mid}",
            headers=headers,
            timeout=30,
        )
        d = r.json()
        text = d.get("transcript") or ""
        if isinstance(text, list):
            text = "\n".join(
                f"{s.get('speaker', '?')}: {s.get('text', '')}"
                for s in text[:20]
            )
        results[mid] = {
            "title": d.get("title"),
            "transcript": text[:2000],
            "status": d.get("status"),
        }
    return results


def call_ollama(transcript: str) -> str:
    """直接调 ollama qwen3:8b 生成标题 (禁用 thinking mode, 否则 content 全是空)"""
    req = urllib.request.Request(
        "http://ollama:11434/api/chat",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "model": "qwen3:8b",
            "messages": [{
                "role": "user",
                "content": f"会议内容:\n{transcript}\n\n请根据会议内容生成一个精炼的中文标题（20字以内）。直接输出标题，不要其他内容。"
            }],
            "stream": False,
            "think": False,  # 关键: 禁用 qwen3 thinking mode (否则 content 一直是空)
            "options": {
                "temperature": 0.3,
                "num_predict": 100,
            },
        }).encode("utf-8"),
    )
    r = urllib.request.urlopen(req, timeout=60)
    result = json.loads(r.read().decode("utf-8"))
    return result.get("message", {}).get("content", "").strip()


def update_title_in_db(meeting_id: int, new_title: str):
    """直接 SQL UPDATE meetings.title (用 \\$'' 语法避免中文引号转义)"""
    import subprocess
    # 写临时 SQL 文件, 避免命令行引号崩溃
    sql = f"UPDATE meetings SET title = '{new_title.replace(chr(39), chr(39)+chr(39))}' WHERE id = {meeting_id};"
    sql_file = f"/tmp/_update_{meeting_id}.sql"
    write_cmd = f"docker exec microbubble-agent-db-1 sh -c \"echo {repr(sql)} > {sql_file}\""
    subprocess.run(write_cmd, shell=True, capture_output=True)
    cmd = f"docker exec microbubble-agent-db-1 sh -c 'PGPASSWORD=postgres psql -U postgres -d microbubble -f {sql_file}'"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"  update {meeting_id}: {r.stdout.strip()}")
    # 清理
    subprocess.run(f"docker exec microbubble-agent-db-1 sh -c 'rm -f {sql_file}'", shell=True, capture_output=True)


def main():
    print("=== 1. 取 4 个会议 transcript ===")
    meetings = fetch_transcripts(MEETING_IDS)
    for mid, d in meetings.items():
        text_preview = d["transcript"][:150].replace("\n", " | ")
        print(f"  meeting {mid}: title={d['title']!r:40s} | status={d['status']} | transcript: {text_preview}...")

    if not CONFIRM:
        print()
        print(f"=== 需生成 {len(MEETING_IDS)} 个标题 (dry-run). 加 --confirm 实际写 DB ===")
        for mid in MEETING_IDS:
            if meetings[mid]["title"].startswith("正在听会（ID"):
                print(f"  {mid}: 需重生成 (当前是 placeholder)")
            else:
                print(f"  {mid}: 已有 AI 标题, 跳过")
        return

    print()
    print("=== 2. 调 ollama 生成标题 ===")
    new_titles = {}
    for mid in MEETING_IDS:
        if not meetings[mid]["title"].startswith("正在听会（ID"):
            print(f"  {mid}: 跳过 (已有 AI 标题)")
            continue
        text = meetings[mid]["transcript"]
        if not text:
            print(f"  {mid}: 跳过 (transcript 空)")
            continue
        try:
            new_title = call_ollama(text)
            new_titles[mid] = new_title
            print(f"  {mid}: → {new_title!r}")
        except Exception as e:
            print(f"  {mid}: FAILED {e}")

    print()
    print("=== 3. 写回 DB ===")
    for mid, t in new_titles.items():
        update_title_in_db(mid, t)


if __name__ == "__main__":
    main()
