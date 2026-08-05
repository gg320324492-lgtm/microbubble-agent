"""Generate AI summary + key_points for meeting 242 via direct ollama call.
W2 +N 2026-08-05: audio 文件丢失, 但 transcript 591 段可用.
"""
import json
import sys
import urllib.request
import subprocess

# 1. 取 242 transcript
def fetch_transcript(meeting_id=242):
    import requests
    token = requests.post(
        "https://agent.mnb-lab.cn/api/v1/auth/login",
        json={"username": "wangtianzhi", "password": "123456"},
        timeout=30,
    ).json()["access_token"]
    r = requests.get(
        f"https://agent.mnb-lab.cn/api/v1/meetings/{meeting_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    d = r.json()
    t = d.get("transcript") or []
    if isinstance(t, list):
        text = "\n".join(
            f"{s.get('speaker', '?')}: {s.get('text', '')}"
            for s in t[:30]  # 前 30 段够 AI 总结
        )
    else:
        text = str(t)[:3000]
    return text, d.get("title", "")


def call_ollama_summary(transcript_text: str) -> dict:
    """直接调 ollama qwen3:8b 生成 summary + key_points (think: false 必加)"""
    prompt = f"""请根据以下会议转录内容, 输出严格的 JSON 格式 (不要其他任何文字):

{{
  "summary": "会议纪要 (200-400 字, 概括核心讨论 + 决议)",
  "key_points": [
    {{"text": "关键决策/行动项1", "kind": "decision"}},
    {{"text": "关键决策/行动项2", "kind": "todo"}},
    {{"text": "关键讨论点1", "kind": "key"}}
  ]
}}

会议转录:
{transcript_text}
"""
    req = urllib.request.Request(
        "http://ollama:11434/api/chat",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,  # 关键: 禁用 qwen3 thinking mode (类 20.151)
            "format": "json",  # 强制 JSON 输出
            "options": {
                "temperature": 0.3,
                "num_predict": 2048,
            },
        }).encode("utf-8"),
    )
    r = urllib.request.urlopen(req, timeout=60)
    result = json.loads(r.read().decode("utf-8"))
    content = result.get("message", {}).get("content", "").strip()
    # 尝试解析 JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 提取 JSON 块
        import re
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {"summary": content[:500], "key_points": []}


def update_meeting_242(summary: str, key_points: list):
    """直接 SQL UPDATE meetings.summary + key_points"""
    kp_json = json.dumps(key_points, ensure_ascii=False)
    # 用单引号 + 双引号转义
    summary_safe = summary.replace("'", "''")
    sql = (
        f"UPDATE meetings SET "
        f"summary = '{summary_safe}', "
        f"key_points = '{kp_json.replace(chr(39), chr(39)+chr(39))}'::jsonb "
        f"WHERE id = 242;"
    )
    sql_file = "/tmp/_update_242.sql"
    # 写 SQL 文件 (避免 bash 转义)
    write_cmd = f"docker exec microbubble-agent-db-1 sh -c \"echo {repr(sql)} > {sql_file}\""
    subprocess.run(write_cmd, shell=True, capture_output=True)
    exec_cmd = f"docker exec microbubble-agent-db-1 sh -c 'PGPASSWORD=postgres psql -U postgres -d microbubble -f {sql_file}'"
    r = subprocess.run(exec_cmd, shell=True, capture_output=True, text=True)
    print(f"UPDATE 242: {r.stdout.strip()}")
    subprocess.run(f"docker exec microbubble-agent-db-1 sh -c 'rm -f {sql_file}'", shell=True, capture_output=True)


def main():
    print("=== 1. 取 242 transcript ===")
    transcript, title = fetch_transcript(242)
    print(f"title: {title}")
    print(f"transcript 前 300 字符: {transcript[:300]}...")

    print()
    print("=== 2. 调 ollama 生成 summary + key_points ===")
    result = call_ollama_summary(transcript)
    summary = result.get("summary", "")
    key_points = result.get("key_points", [])
    print(f"summary 长度: {len(summary)}")
    print(f"summary: {summary[:200]}")
    print(f"key_points 数量: {len(key_points)}")
    for kp in key_points[:3]:
        print(f"  kp ({kp.get('kind')}): {kp.get('text', '')[:100]}")

    print()
    print("=== 3. 写回 DB ===")
    update_meeting_242(summary, key_points)


if __name__ == "__main__":
    main()
