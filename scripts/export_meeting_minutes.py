"""把某场会议的纪要导出为 Markdown（便于离线审阅 / 归档 / 交付）。

数据来源：GET /api/v1/meetings/{id}（与前端会议详情页同一份数据），
因此导出内容与你在前端看到的一致。

用法（在 app 容器内执行）:
    docker cp scripts/export_meeting_minutes.py microbubble-agent-app-1:/tmp/
    docker exec -i microbubble-agent-app-1 python /tmp/export_meeting_minutes.py \
        --meeting 250 --out /tmp/meeting_250_minutes.md [--max-segments 400]

注意：会议纪要格式遵循 docs/meeting-minutes-standard.md（摘要 3-6 句、
讨论要点与决议事项均带【发言人】前缀）。
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

BEIJING = timezone(timedelta(hours=8))


def fmt_dt(v):
    if not v:
        return "-"
    if isinstance(v, datetime):
        dt = v
    else:
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return str(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def sec_to_hms(s):
    if not s:
        return "-"
    s = int(s)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-segments", type=int, default=400,
                    help="转录正文最多导出多少段（0 = 全部）")
    ap.add_argument("--token-only", action="store_true", help="只打印 token 供 curl 使用")
    args = ap.parse_args()

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting

    if args.token_only:
        from app.core.security import create_access_token
        print(create_access_token({"sub": "3"}, expires_delta=timedelta(hours=3)))
        return 0

    engine, sf = create_celery_engine_and_session()
    try:
        async with sf() as db:
            m = (await db.execute(select(Meeting).where(Meeting.id == args.meeting))).scalar_one_or_none()
            if m is None:
                print(f"会议 {args.meeting} 不存在")
                return 3

            lines = []
            lines.append(f"# {m.title}")
            lines.append("")
            lines.append(f"> 会议 ID：{m.id}　状态：{m.status}　质量标记：{m.quality_status or '-'}")
            lines.append("")
            lines.append("| 项 | 值 |")
            lines.append("|---|---|")
            lines.append(f"| 开始时间（北京时间） | {fmt_dt(m.start_time)} |")
            lines.append(f"| 结束时间（北京时间） | {fmt_dt(m.end_time)} |")
            lines.append(f"| 录音时长 | {sec_to_hms(m.media_duration_seconds or m.audio_duration)}"
                         f"（{m.media_duration_seconds or m.audio_duration or 0} 秒）|")
            lines.append(f"| 录音文件 | `{m.audio_url or '-'}` |")
            lines.append(f"| 转写段数 | {len(m.transcript or [])} |")
            lines.append("")

            stats = m.speaker_stats or []
            if stats:
                lines.append("## 发言人统计")
                lines.append("")
                lines.append("| 发言人 | 发言次数 | 字数 | 发言占比 | 平均话轮长度 |")
                lines.append("|---|---|---|---|---|")
                for s in stats:
                    ratio = s.get("speaking_ratio")
                    lines.append(
                        f"| {s.get('name', '-')} | {s.get('turn_count', 0)} | "
                        f"{s.get('word_count', 0)} | "
                        f"{(f'{ratio * 100:.1f}%' if isinstance(ratio, (int, float)) else '-')} | "
                        f"{s.get('avg_turn_length', '-')} |"
                    )
                lines.append("")

            lines.append("## 摘要")
            lines.append("")
            lines.append((m.summary or "（无）").strip())
            lines.append("")

            if m.key_points:
                lines.append("## 讨论要点")
                lines.append("")
                for i, kp in enumerate(m.key_points, 1):
                    lines.append(f"{i}. {kp}")
                lines.append("")

            if m.decisions:
                lines.append("## 决议事项")
                lines.append("")
                for i, d in enumerate(m.decisions, 1):
                    lines.append(f"{i}. {d}")
                lines.append("")

            segs = m.transcript_polished or m.transcript or []
            if segs and args.max_segments:
                segs = segs[: args.max_segments]
            if segs:
                lines.append(f"## 转录正文（{'前 ' + str(len(segs)) + ' 段' if args.max_segments and len(m.transcript or []) > args.max_segments else '全部'}）")
                lines.append("")
                for s in segs:
                    ts = sec_to_hms(s.get("start"))
                    lines.append(f"- `[{ts}]` **{s.get('speaker', '未知')}**：{s.get('text', '')}")
                lines.append("")

            body = "\n".join(lines)
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(body)
            print(f"已导出 {len(body)} 字符 → {args.out}")
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
