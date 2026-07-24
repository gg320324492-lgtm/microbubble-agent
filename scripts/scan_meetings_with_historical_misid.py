"""扫描含历史声纹误识的会议清单 (data-only, 不改生产代码)

历史背景 (W68 第 4 批 Plan #2 meeting-64-repair 留尾):
- 2026-06-27 12:00 之前录制的会议, 杜同贺 / 吴孟铨 等成员声纹尚未录入
- 当时的声纹库可能只匹配到李胜景等少数成员
- 会议后处理 summary / key_points / decisions 字段可能含历史误识 (写入其他成员姓名)

本脚本:
  1. 直连 PostgreSQL (DATABASE_URL env)
  2. 扫描所有 created_at < 2026-06-27 12:00:00 的会议
  3. 用 meeting_participants 真实参会成员 vs summary/key_points/decisions 文本中的姓名
     找出 summary 中含"非参会成员姓名"的疑似误识会议
  4. 同时用 transcript_polished 的真实 speaker_label 反推 + summary 比对
  5. 输出 candidate_meetings JSON list 到 stdout / 文件

输出格式:
  [
    {
      "meeting_id": 64,
      "title": "...",
      "created_at": "...",
      "real_participant_names": ["杜同贺", "吴孟铨"],
      "summary_mentioned_names": ["李胜景"],     # 误识嫌疑
      "transcript_real_speakers": ["杜同贺", "吴孟铨"],
      "mismatch_severity": "high" | "medium" | "low",
      "evidence": "summary 含 '李胜景' 但 transcript 0 段归属"
    }
  ]

用法:
  # 干跑 (无 DATABASE_URL 时返回空 + 提示)
  python scripts/scan_meetings_with_historical_misid.py

  # 实际扫描, 输出到 JSON 文件
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/scan_meetings_with_historical_misid.py \\
    --output /tmp/meetings_candidates.json

  # 限定时间窗口 (默认 2026-06-27 12:00:00)
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbubble \\
    python scripts/scan_meetings_with_historical_misid.py \\
    --cutoff 2026-06-27T12:00:00
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
logger = logging.getLogger("scan_misid")

# 默认 cutoff: 杜同贺 / 吴孟铨 声纹录入 (大约 2026-06-27 上午)
DEFAULT_CUTOFF = datetime(2026, 6, 27, 12, 0, 0)


def _conn_str() -> str | None:
    """读取 DATABASE_URL, 缺失返回 None (允许 fallback dry-run)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return url


async def fetch_all_members(conn) -> dict[int, str]:
    """取 members 表 id -> name 映射, 用于 participant 解析."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, name FROM members")
        rows = await cur.fetchall()
        return {r["id"]: r["name"] for r in rows}


async def scan_meetings(
    conn,
    cutoff: datetime,
    min_severity: str = "low",
) -> list[dict]:
    """扫描含历史误识嫌疑的会议.

    Args:
        conn: psycopg AsyncConnection
        cutoff: created_at 上限
        min_severity: 'low' | 'medium' | 'high', 过滤掉低于此等级的疑似

    Returns:
        candidate_meetings list
    """
    members_map = await fetch_all_members(conn)
    candidate_meetings: list[dict] = []

    async with conn.cursor() as cur:
        # 取所有 cutoff 之前的会议 + 参与者 + summary/key_points/decisions + transcript
        await cur.execute(
            """
            SELECT m.id, m.title, m.created_at, m.transcript, m.transcript_polished,
                   m.summary, m.key_points, m.decisions, m.speaker_mapping
              FROM meetings m
             WHERE m.created_at < %s
               AND m.status IN ('completed', 'processing')
             ORDER BY m.created_at
            """,
            (cutoff,),
        )
        meetings = await cur.fetchall()
        logger.info(f"扫描到 {len(meetings)} 个会议 (created_at < {cutoff.isoformat()})")

        for m in meetings:
            meeting_id = m["id"]
            # 取参与者姓名
            await cur.execute(
                """
                SELECT mp.member_id, m.name AS member_name
                  FROM meeting_participants mp
                  JOIN members m ON m.id = mp.member_id
                 WHERE mp.meeting_id = %s
                """,
                (meeting_id,),
            )
            participants = await cur.fetchall()
            real_participant_names = {p["member_name"] for p in participants}

            # 从 transcript_polished 提取真实 speaker_label
            transcript_polished = list(m["transcript_polished"] or [])
            transcript_real_speakers: set[str] = set()
            for seg in transcript_polished:
                sp = seg.get("speaker") if isinstance(seg, dict) else None
                if sp and sp != "未知" and not sp.startswith("发言人"):
                    transcript_real_speakers.add(sp)

            # 拼接 summary + key_points + decisions 全文
            text_chunks: list[str] = []
            if m["summary"]:
                text_chunks.append(str(m["summary"]))
            if m["key_points"]:
                text_chunks.extend([str(kp) for kp in (m["key_points"] or [])])
            if m["decisions"]:
                text_chunks.extend([str(d) for d in (m["decisions"] or [])])
            full_text = "\n".join(text_chunks)

            # 检测: 出现在文本中但不在真实参与者名单的成员姓名
            suspected_names: list[str] = []
            for member_name in members_map.values():
                if not member_name or len(member_name) < 2:
                    continue
                if member_name in real_participant_names:
                    continue
                # 出现在文本中
                if member_name in full_text:
                    suspected_names.append(member_name)

            if not suspected_names:
                continue  # 无误识嫌疑

            # 评估严重等级
            severity = _assess_severity(
                real_participant_names=real_participant_names,
                transcript_real_speakers=transcript_real_speakers,
                suspected_names=suspected_names,
                summary=str(m["summary"] or ""),
            )
            severity_rank = {"high": 3, "medium": 2, "low": 1}
            if severity_rank[severity] < severity_rank[min_severity]:
                continue

            evidence = _build_evidence(
                summary=str(m["summary"] or ""),
                suspected_names=suspected_names,
                transcript_speakers=transcript_real_speakers,
            )

            candidate_meetings.append({
                "meeting_id": meeting_id,
                "title": m["title"],
                "created_at": m["created_at"].isoformat() if m["created_at"] else None,
                "real_participant_names": sorted(real_participant_names),
                "transcript_real_speakers": sorted(transcript_real_speakers),
                "summary_suspected_names": sorted(suspected_names),
                "mismatch_severity": severity,
                "evidence": evidence,
            })

    return candidate_meetings


def _assess_severity(
    real_participant_names: set[str],
    transcript_real_speakers: set[str],
    suspected_names: list[str],
    summary: str,
) -> str:
    """评估误识严重等级.

    high:   summary 中含多个未参会姓名, 且 transcript 中 0 段归属该姓名 (纯误识)
    medium: summary 中含未参会姓名, transcript 中少数段归属 (可能跨会议串话)
    low:    summary 中含未参会姓名, 但 transcript 中该姓名出现次数较多 (可能真参会但未在 participants 表)
    """
    if not suspected_names or not summary:
        return "low"

    # 检查 transcript 0 段归属 (纯误识)
    fully_misid = []
    partial_misid = []
    for name in suspected_names:
        if name in transcript_real_speakers:
            partial_misid.append(name)
        else:
            fully_misid.append(name)

    if len(fully_misid) >= 2 or (len(fully_misid) == 1 and len(suspected_names) >= 2):
        return "high"
    if len(fully_misid) >= 1:
        return "medium"
    if partial_misid:
        # 出现在 transcript 但未在 participants 表 - 需人工 review
        return "low"

    return "low"


def _build_evidence(
    summary: str,
    suspected_names: list[str],
    transcript_speakers: set[str],
) -> str:
    """生成可读的 evidence 字符串."""
    parts: list[str] = []
    for name in suspected_names[:3]:  # 最多 3 个证据
        idx = summary.find(name)
        if idx >= 0:
            snippet = summary[max(0, idx - 20):idx + len(name) + 20]
            in_transcript = name in transcript_speakers
            tag = "transcript 0 段" if not in_transcript else f"transcript 有 {name}"
            parts.append(f"summary 含 {snippet!r} ({tag})")
    if len(suspected_names) > 3:
        parts.append(f"... 共 {len(suspected_names)} 个误识姓名")
    return " | ".join(parts) if parts else "无具体 evidence"


async def main():
    parser = argparse.ArgumentParser(description="扫描含历史声纹误识的会议清单")
    parser.add_argument(
        "--cutoff",
        type=str,
        default=DEFAULT_CUTOFF.isoformat(),
        help=f"created_at 上限 ISO 格式 (默认 {DEFAULT_CUTOFF.isoformat()})",
    )
    parser.add_argument(
        "--min-severity",
        type=str,
        choices=["low", "medium", "high"],
        default="low",
        help="最低严重等级 (默认 low 不过滤)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 JSON 文件路径 (默认 stdout)",
    )
    args = parser.parse_args()

    try:
        cutoff = datetime.fromisoformat(args.cutoff)
    except ValueError as e:
        logger.error(f"--cutoff 格式错误: {e}")
        sys.exit(1)

    conn_str = _conn_str()
    if not conn_str:
        if not HAS_PSYCOG:
            logger.warning("psycopg 未安装且 DATABASE_URL 缺失, 跳过 dry-run")
            _emit_empty_output(args.output)
            return
        logger.warning("DATABASE_URL 未设置, 输出空清单 (dry-run fallback)")
        _emit_empty_output(args.output)
        return

    if not HAS_PSYCOG:
        logger.error("psycopg 未安装, 请 pip install psycopg[binary]")
        sys.exit(1)

    async with await psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row) as conn:
        candidates = await scan_meetings(conn, cutoff, min_severity=args.min_severity)

    logger.info(f"扫描完成, 共 {len(candidates)} 个候选误识会议")
    severity_counts = {}
    for c in candidates:
        severity_counts[c["mismatch_severity"]] = severity_counts.get(c["mismatch_severity"], 0) + 1
    for sev in ("high", "medium", "low"):
        logger.info(f"  {sev}: {severity_counts.get(sev, 0)}")

    payload = json.dumps(candidates, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        logger.info(f"已写入 {args.output}")
    else:
        print(payload)


def _emit_empty_output(output_path: str | None) -> None:
    """fallback dry-run: 输出空清单 + 提示."""
    payload = json.dumps([], ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(payload, encoding="utf-8")
        logger.info(f"已写入空清单 {output_path}")
    else:
        print(payload)
    logger.info(
        "提示: 本地无 PostgreSQL, 请在云服务器 / 本地 docker exec -e DATABASE_URL=... 跑"
    )


if __name__ == "__main__":
    asyncio.run(main())