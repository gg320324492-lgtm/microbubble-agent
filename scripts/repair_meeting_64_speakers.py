"""会议 #64 发言人误标修复脚本 (data-only, 不改生产代码)

历史背景 (见 plan 2026-06-05-19-10-melodic-donut.md):
- 会议 64 录制时 (2026-06-05) 杜同贺 / 吴孟铨 都没录入声纹, 只有李胜景 1 个 sample
- 后处理把 7 段本应归杜同贺的发言误标为 李胜景
- 5 个下游字段全部错: transcript_polished / speaker_stats / summary / key_points / decisions
- transcript / speaker_mapping / meeting_participants 字段已正确

本脚本:
  1. 备份 meeting_id=64 的 transcript_polished + speaker_stats + summary + key_points + decisions (文件, 不靠 DB 列)
  2. 修 transcript_polished (镜像 transcript[i].speaker, 同长度 11 段)
  3. 调 LLM 重生成 summary / key_points / decisions, 显式约束"只输出 杜同贺 + 吴孟铨"
  4. 重算 speaker_stats (基于 transcript, 不靠 LLM)
  5. 默认 dry-run 只 print diff, --apply 才落库

用法:
  # dry-run (默认)
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/repair_meeting_64_speakers.py

  # 实际落库
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/repair_meeting_64_speakers.py --apply

回滚: /tmp/meeting_64_backup_<ts>.json 留有完整 5 字段快照, 用 SQL 写回即可.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("repair_meeting_64")

MEETING_ID = 64
ALLOWED_SPEAKERS = ["杜同贺", "吴孟铨"]  # 实际发言人 (已与 meeting_participants 核对)
FORBIDDEN_SPEAKER = "李胜景"
BACKUP_DIR = Path("/tmp")


def _conn_str() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("ERROR: DATABASE_URL env 未设置, 需 postgresql://user:pass@host:port/db")
    return url


async def fetch_meeting(cur, meeting_id: int) -> dict:
    cur.execute(
        """
        SELECT id, title, transcript, transcript_polished, speaker_mapping,
               speaker_stats, summary, key_points, decisions
          FROM meetings
         WHERE id = %s
        """,
        (meeting_id,),
    )
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"ERROR: meeting id={meeting_id} 不存在")
    return row


async def backup_to_file(m: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"meeting_64_backup_{ts}.json"
    payload = {
        "meeting_id": MEETING_ID,
        "backup_at": ts,
        "transcript": m["transcript"],
        "transcript_polished": m["transcript_polished"],
        "speaker_mapping": m["speaker_mapping"],
        "speaker_stats": m["speaker_stats"],
        "summary": m["summary"],
        "key_points": m["key_points"],
        "decisions": m["decisions"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"备份写入 {path}")
    return path


def fix_transcript_polished(m: dict) -> list:
    """镜像 transcript[i].speaker 到 transcript_polished[i].speaker (11 段平行数组)"""
    transcript = list(m["transcript"] or [])
    polished = [dict(seg) for seg in (m["transcript_polished"] or [])]
    if len(transcript) != len(polished):
        raise RuntimeError(f"长度不匹配: transcript={len(transcript)} vs polished={len(polished)}")
    for i, seg in enumerate(polished):
        seg["speaker"] = transcript[i]["speaker"]
    return polished


def compute_speaker_stats_local(transcript_entries: list) -> list:
    """纯本地计算 speaker_stats (与 meeting_analysis_service.compute_speaker_stats 同 schema)"""
    speaker_data: dict = {}
    total_words = 0
    for entry in transcript_entries:
        name = entry.get("speaker", "未知")
        text = entry.get("text", "")
        words = len(text.replace(" ", ""))
        if name not in speaker_data:
            speaker_data[name] = {"name": name, "turn_count": 0, "word_count": 0}
        speaker_data[name]["turn_count"] += 1
        speaker_data[name]["word_count"] += words
        total_words += words
    stats = []
    for name, data in speaker_data.items():
        ratio = round(data["word_count"] / total_words, 3) if total_words > 0 else 0
        stats.append({
            "name": name,
            "turn_count": data["turn_count"],
            "word_count": data["word_count"],
            "speaking_ratio": ratio,
            "avg_turn_length": round(data["word_count"] / data["turn_count"]) if data["turn_count"] else 0,
            "topics": [],
        })
    stats.sort(key=lambda x: x["word_count"], reverse=True)
    return stats


async def call_llm_regen(transcript_entries: list) -> dict:
    """调 LLM (复用 app 内的 mimo cloud 客户端) 重生成 summary/key_points/decisions.

    显式约束: 实际参与者只有 杜同贺 + 吴孟铨, 不得出现 李胜景.
    """
    # 复用 app 内的 LLM 客户端 (避免重复实现)
    sys.path.insert(0, "/app")
    from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

    # 把 transcript 转成 build_transcript_text 风格
    lines = []
    cur_speaker, cur_texts = None, []
    for entry in transcript_entries:
        sp = entry.get("speaker", "未知")
        text = entry.get("text", "")
        if not text or len(text) < 2 or text in ("嗯", "啊", "哦", "哎", "好", "的", "了"):
            continue
        if sp != cur_speaker:
            if cur_speaker and cur_texts:
                lines.append(f"【{cur_speaker}】{''.join(cur_texts)}")
            cur_speaker, cur_texts = sp, [text]
        else:
            cur_texts.append(text)
    if cur_speaker and cur_texts:
        lines.append(f"【{cur_speaker}】{''.join(cur_texts)}")
    transcript_text = "\n".join(lines)

    system_prompt = (
        "你是微纳米气泡课题组的会议纪要生成助手。"
        "**重要约束**: 本次会议的实际参与者只有 "
        f"{' + '.join(ALLOWED_SPEAKERS)}"
        f", 严禁在输出中出现 `{FORBIDDEN_SPEAKER}` (他并未参加此会议)。"
        "按要求输出严格 JSON。"
    )
    user_prompt = (
        "你是一个专业的会议纪要生成助手。请分析以下会议转录内容。\n"
        "按课题组标准会议纪要格式输出 (3-6 句摘要 / 5-8 条 key_points / 决议事项)。\n"
        f"【强制约束】输出中所有发言人只能从 {ALLOWED_SPEAKERS} 中选择, "
        f"绝不允许出现 {FORBIDDEN_SPEAKER} 或其他未参会人员。\n\n"
        f"会议转录:\n{transcript_text}\n\n"
        "请输出严格 JSON:\n"
        '{"summary": "...", "key_points": ["【xxx】..."], "decisions": ["【xxx】..."]}'
    )

    client = get_anthropic_client()
    model = get_default_model()
    logger.info(f"调 LLM (model={model}, transcript {len(transcript_text)} 字符) ...")

    async def _call():
        response = await client.messages.create(
            model=model,
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = extract_text_from_response(response)
        if not text:
            raise RuntimeError("LLM 返回空")
        return parse_llm_json(text)

    return await _call()


def diff_summary(before: dict, after: dict) -> str:
    """生成可读 diff 供 dry-run 输出"""
    lines = []
    lines.append("--- summary ---")
    lines.append(f"BEFORE: {(before.get('summary') or '')[:80]}...")
    lines.append(f"AFTER:  {(after.get('summary') or '')[:80]}...")
    lines.append(f"BEFORE 李胜景 计数: {(before.get('summary') or '').count(FORBIDDEN_SPEAKER)}")
    lines.append(f"AFTER  李胜景 计数: {(after.get('summary') or '').count(FORBIDDEN_SPEAKER)}")
    lines.append("--- key_points ---")
    for i, kp in enumerate(after.get("key_points", [])):
        tag = "✓ 含李胜景" if FORBIDDEN_SPEAKER in kp else "ok"
        lines.append(f"  [{i}] {tag}: {kp[:60]}...")
    lines.append("--- decisions ---")
    for i, dec in enumerate(after.get("decisions", [])):
        tag = "✓ 含李胜景" if FORBIDDEN_SPEAKER in dec else "ok"
        lines.append(f"  [{i}] {tag}: {dec[:60]}...")
    lines.append("--- speaker_stats ---")
    for s in after.get("speaker_stats", []):
        lines.append(f"  {s['name']}: turns={s['turn_count']} words={s['word_count']}")
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际落库 (默认 dry-run)")
    args = parser.parse_args()

    conn_str = _conn_str()
    async with await psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            m = await fetch_meeting(cur, MEETING_ID)
            backup_path = await backup_to_file(m)
            fixed_polished = fix_transcript_polished(m)
            new_stats = compute_speaker_stats_local(list(m["transcript"]))

            logger.info("transcript 实际发言人分布:")
            for s in new_stats:
                logger.info(f"  {s['name']}: turns={s['turn_count']} words={s['word_count']}")

            new_llm = await call_llm_regen(list(m["transcript"]))
            new_payload = {
                "transcript_polished": fixed_polished,
                "speaker_stats": new_stats,
                "summary": (new_llm.get("summary", "") or "").strip(),
                "key_points": new_llm.get("key_points", []),
                "decisions": new_llm.get("decisions", []),
            }

            logger.info("=" * 60)
            logger.info(diff_summary(m, new_payload))
            logger.info("=" * 60)

            if not args.apply:
                logger.info("DRY-RUN: 加 --apply 才落库")
                logger.info(f"备份文件: {backup_path}")
                return

            # 实际落库
            await cur.execute(
                """
                UPDATE meetings
                   SET transcript_polished = %s::jsonb,
                       speaker_stats       = %s::jsonb,
                       summary             = %s,
                       key_points          = %s::jsonb,
                       decisions           = %s::jsonb
                 WHERE id = %s
                """,
                (
                    json.dumps(new_payload["transcript_polished"], ensure_ascii=False),
                    json.dumps(new_payload["speaker_stats"], ensure_ascii=False),
                    new_payload["summary"],
                    json.dumps(new_payload["key_points"], ensure_ascii=False),
                    json.dumps(new_payload["decisions"], ensure_ascii=False),
                    MEETING_ID,
                ),
            )
            await conn.commit()
            logger.info(f"落库完成 (id={MEETING_ID}, {cur.rowcount} 行)")


if __name__ == "__main__":
    asyncio.run(main())