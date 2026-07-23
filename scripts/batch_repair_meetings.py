"""批量修复会议误识 (data-only, 不改生产代码)

调用链:
  scripts/scan_meetings_with_historical_misid.py -> candidate_meetings.json
  scripts/batch_repair_meetings.py --input candidate_meetings.json --dry-run
  scripts/batch_repair_meetings.py --input candidate_meetings.json --apply

功能:
  1. 读 candidate_meetings.json
  2. 对每个 meeting_id:
     - 备份 5 字段到 /tmp/meeting_{id}_backup_{ts}.json (单会议模式)
     - 镜像 transcript[i].speaker 到 transcript_polished[i].speaker (修复发言人)
     - 调 LLM 重生成 summary/key_points/decisions (显式约束不含误识姓名)
     - 重算 speaker_stats (基于 transcript, 不靠 LLM)
     - 失败 retry 3 次 (指数退避)
  3. 默认 --dry-run, 加 --apply 才落库
  4. 进度条 (stderr) + 失败汇总 (summary)

用法:
  # 干跑 (默认)
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/batch_repair_meetings.py \\
    --input /tmp/meetings_candidates.json

  # 实际落库
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/batch_repair_meetings.py \\
    --input /tmp/meetings_candidates.json --apply

  # 只处理高严重等级
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/batch_repair_meetings.py \\
    --input /tmp/meetings_candidates.json \\
    --min-severity high

  # 限定只处理前 N 个 (测试用)
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/batch_repair_meetings.py \\
    --input /tmp/meetings_candidates.json \\
    --limit 3

回滚: /tmp/meeting_{id}_backup_*.json 留有完整 5 字段快照, 用 SQL 写回即可.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
    HAS_PSYCOG = True
except ImportError:
    HAS_PSYCOG = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("batch_repair")

BACKUP_DIR = Path("/tmp")
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0  # 秒 (指数退避: 1s, 2s, 4s)


def _conn_str() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("ERROR: DATABASE_URL env 未设置, 需 postgresql://user:pass@host:port/db")
    return url


# ----------------- 复用 repair_meeting_64_speakers.py 的核心函数 -----------------


async def fetch_meeting(cur, meeting_id: int) -> dict:
    """取会议全部相关字段 (与 repair_meeting_64_speakers.fetch_meeting 同构)."""
    await cur.execute(
        """
        SELECT id, title, transcript, transcript_polished, speaker_mapping,
               speaker_stats, summary, key_points, decisions, created_at
          FROM meetings
         WHERE id = %s
        """,
        (meeting_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise SystemExit(f"ERROR: meeting id={meeting_id} 不存在")
    return row


async def backup_to_file(m: dict, meeting_id: int) -> Path:
    """备份 5 字段 + 标识信息."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"meeting_{meeting_id}_backup_{ts}.json"
    payload = {
        "meeting_id": meeting_id,
        "title": m.get("title"),
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
    logger.info(f"[meeting={meeting_id}] 备份写入 {path}")
    return path


def fix_transcript_polished(m: dict) -> list:
    """镜像 transcript[i].speaker 到 transcript_polished[i].speaker."""
    transcript = list(m["transcript"] or [])
    polished = [dict(seg) for seg in (m["transcript_polished"] or [])]
    if len(transcript) != len(polished):
        logger.warning(
            f"[meeting={m.get('id')}] 长度不匹配: transcript={len(transcript)} "
            f"vs polished={len(polished)}, 跳过 polished 修复"
        )
        return polished
    for i, seg in enumerate(polished):
        seg["speaker"] = transcript[i]["speaker"]
    return polished


def compute_speaker_stats_local(transcript_entries: list) -> list:
    """纯本地计算 speaker_stats (与 meeting_analysis_service 同 schema)."""
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


async def call_llm_regen(transcript_entries: list, allowed_speakers: list[str], forbidden_speakers: list[str]) -> dict:
    """调 LLM 重生成 summary/key_points/decisions.

    复用 app 内的 mimo cloud 客户端 + parse_llm_json + extract_text_from_response.
    显式约束: 只允许出现 allowed_speakers, 严禁 forbidden_speakers.
    """
    sys.path.insert(0, "/app")
    from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

    # transcript 转 build_transcript_text 风格 (合并连续同 speaker 段)
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

    allowed_str = "、".join(allowed_speakers) if allowed_speakers else "未知"
    forbidden_str = "、".join(forbidden_speakers) if forbidden_speakers else "(无)"

    system_prompt = (
        "你是微纳米气泡课题组的会议纪要生成助手。"
        f"**重要约束**: 本次会议的实际参与者只有 {allowed_str}, "
        f"严禁在输出中出现 {forbidden_str} (他们并未参加此会议)。"
        "按要求输出严格 JSON。"
    )
    user_prompt = (
        "你是一个专业的会议纪要生成助手。请分析以下会议转录内容。\n"
        "按课题组标准会议纪要格式输出 (3-6 句摘要 / 5-8 条 key_points / 决议事项)。\n"
        f"【强制约束】输出中所有发言人只能从 [{allowed_str}] 中选择, "
        f"绝不允许出现 [{forbidden_str}] 或其他未参会人员。\n\n"
        f"会议转录:\n{transcript_text}\n\n"
        "请输出严格 JSON:\n"
        '{"summary": "...", "key_points": ["【xxx】..."], "decisions": ["【xxx】..."]}'
    )

    client = get_anthropic_client()
    model = get_default_model()
    logger.info(f"调 LLM (model={model}, transcript {len(transcript_text)} 字符) ...")

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


def diff_summary(before: dict, after: dict, forbidden_speakers: list[str]) -> str:
    """生成可读 diff."""
    lines = []
    lines.append("--- summary ---")
    lines.append(f"BEFORE: {(before.get('summary') or '')[:80]}...")
    lines.append(f"AFTER:  {(after.get('summary') or '')[:80]}...")
    for fn in forbidden_speakers:
        bc = (before.get("summary") or "").count(fn)
        ac = (after.get("summary") or "").count(fn)
        if bc or ac:
            lines.append(f"  {fn}: before={bc} after={ac}")
    lines.append("--- key_points ---")
    for i, kp in enumerate(after.get("key_points", [])):
        bad = [fn for fn in forbidden_speakers if fn in kp]
        tag = f"⚠ 含 {bad}" if bad else "ok"
        lines.append(f"  [{i}] {tag}: {kp[:60]}...")
    lines.append("--- decisions ---")
    for i, dec in enumerate(after.get("decisions", [])):
        bad = [fn for fn in forbidden_speakers if fn in dec]
        tag = f"⚠ 含 {bad}" if bad else "ok"
        lines.append(f"  [{i}] {tag}: {dec[:60]}...")
    lines.append("--- speaker_stats ---")
    for s in after.get("speaker_stats", []):
        lines.append(f"  {s['name']}: turns={s['turn_count']} words={s['word_count']}")
    return "\n".join(lines)


# ----------------- 单会议处理 (含 retry) -----------------


async def repair_one_meeting(
    cur,
    conn,
    meeting_id: int,
    candidate: dict,
    apply: bool,
    max_retries: int,
) -> dict:
    """处理一个会议, 返回结果 dict (status/backup_path/error).

    Args:
        cur/cursor/conn: psycopg 连接
        meeting_id: 会议 ID
        candidate: scan 脚本输出的 candidate dict (含 real_participant_names / summary_suspected_names)
        apply: 是否落库
        max_retries: LLM 调用失败 retry 次数
    """
    result = {
        "meeting_id": meeting_id,
        "title": candidate.get("title"),
        "status": "pending",
        "backup_path": None,
        "error": None,
    }

    try:
        m = await fetch_meeting(cur, meeting_id)
        backup_path = await backup_to_file(m, meeting_id)
        result["backup_path"] = str(backup_path)

        fixed_polished = fix_transcript_polished(m)
        new_stats = compute_speaker_stats_local(list(m["transcript"]))

        logger.info(f"[meeting={meeting_id}] transcript 实际发言人分布:")
        for s in new_stats:
            logger.info(f"  {s['name']}: turns={s['turn_count']} words={s['word_count']}")

        # 用 candidate 中 real_participant_names 约束 LLM
        allowed = candidate.get("real_participant_names", [])
        forbidden = candidate.get("summary_suspected_names", [])

        new_llm = None
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                new_llm = await call_llm_regen(
                    list(m["transcript"]), allowed_speakers=allowed, forbidden_speakers=forbidden
                )
                break
            except Exception as e:
                last_error = e
                delay = DEFAULT_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"[meeting={meeting_id}] LLM 失败 attempt {attempt}/{max_retries}: {e}, "
                    f"{delay:.1f}s 后重试"
                )
                if attempt < max_retries:
                    await asyncio.sleep(delay)
        if new_llm is None:
            raise RuntimeError(f"LLM 连续 {max_retries} 次失败: {last_error}")

        new_payload = {
            "transcript_polished": fixed_polished,
            "speaker_stats": new_stats,
            "summary": (new_llm.get("summary", "") or "").strip(),
            "key_points": new_llm.get("key_points", []),
            "decisions": new_llm.get("decisions", []),
        }

        logger.info("=" * 60)
        logger.info(diff_summary(m, new_payload, forbidden))
        logger.info("=" * 60)

        if not apply:
            result["status"] = "dry_run_ok"
            logger.info(f"[meeting={meeting_id}] DRY-RUN: 加 --apply 才落库")
            return result

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
                meeting_id,
            ),
        )
        await conn.commit()
        result["status"] = "applied"
        logger.info(f"[meeting={meeting_id}] 落库完成 ({cur.rowcount} 行)")

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        logger.error(f"[meeting={meeting_id}] 处理失败: {e}", exc_info=True)

    return result


# ----------------- 主流程 -----------------


async def main():
    parser = argparse.ArgumentParser(description="批量修复会议误识")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="candidate_meetings.json 路径 (scan 脚本输出)",
    )
    parser.add_argument("--apply", action="store_true", help="实际落库 (默认 dry-run)")
    parser.add_argument(
        "--min-severity",
        type=str,
        choices=["low", "medium", "high"],
        default="low",
        help="最低严重等级 (默认 low 全跑)",
    )
    parser.add_argument("--limit", type=int, default=0, help="最多处理前 N 个 (0=全部)")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help=f"LLM 失败 retry 次数 (默认 {DEFAULT_MAX_RETRIES})")
    args = parser.parse_args()

    if not HAS_PSYCOG:
        logger.error("psycopg 未安装, 请 pip install psycopg[binary]")
        sys.exit(1)

    # 读 candidate
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"--input 路径不存在: {input_path}")
        sys.exit(1)
    candidates = json.loads(input_path.read_text(encoding="utf-8"))
    logger.info(f"读入 {len(candidates)} 个候选")

    # 过滤严重等级
    severity_rank = {"high": 3, "medium": 2, "low": 1}
    candidates = [c for c in candidates if severity_rank.get(c.get("mismatch_severity", "low"), 0) >= severity_rank[args.min_severity]]
    logger.info(f"严重等级 >= {args.min_severity} 的候选: {len(candidates)}")

    # 限定 limit
    if args.limit and args.limit > 0:
        candidates = candidates[: args.limit]
        logger.info(f"应用 --limit {args.limit}: 最终处理 {len(candidates)} 个")

    if not candidates:
        logger.info("无可处理会议, 退出")
        return

    if args.apply:
        logger.warning("=" * 60)
        logger.warning("⚠️  --apply 模式: 将实际修改生产数据库!")
        logger.warning("⚠️  按 Ctrl-C 中断 (3s 内)")
        logger.warning("=" * 60)
        await asyncio.sleep(3)

    conn_str = _conn_str()
    results: list[dict] = []

    async with await psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            for i, candidate in enumerate(candidates, 1):
                meeting_id = candidate["meeting_id"]
                logger.info(f"[{i}/{len(candidates)}] 处理 meeting_id={meeting_id} ...")
                r = await repair_one_meeting(
                    cur=cur,
                    conn=conn,
                    meeting_id=meeting_id,
                    candidate=candidate,
                    apply=args.apply,
                    max_retries=args.max_retries,
                )
                results.append(r)
                # 进度条
                pct = round(i / len(candidates) * 100, 1)
                logger.info(f"PROGRESS: {pct}% ({i}/{len(candidates)})")

    # 汇总
    status_count: dict[str, int] = {}
    for r in results:
        status_count[r["status"]] = status_count.get(r["status"], 0) + 1
    logger.info("=" * 60)
    logger.info("BATCH REPAIR 汇总:")
    for st in ("applied", "dry_run_ok", "failed"):
        if status_count.get(st):
            logger.info(f"  {st}: {status_count[st]}")
    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        logger.error(f"失败 {len(failed)} 个:")
        for r in failed:
            logger.error(f"  meeting_id={r['meeting_id']}: {r['error']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())