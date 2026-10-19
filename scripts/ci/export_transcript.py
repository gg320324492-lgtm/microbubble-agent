"""导出会议转录为可读文本，供人工核对说话人。

用法: python scripts/ci/export_transcript.py <meeting_id> <out_path>
"""
import json
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402


def main() -> int:
    meeting_id = int(sys.argv[1])
    out_path = sys.argv[2]

    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT title, location, start_time, end_time, transcript, "
                "speaker_mapping, status FROM meetings WHERE id = :mid"
            ),
            {"mid": meeting_id},
        ).mappings().one()

    entries = row["transcript"]
    if isinstance(entries, str):
        entries = json.loads(entries)

    lines = [
        f"# 会议 {meeting_id} — {row['title']}",
        f"地点: {row['location']}",
        f"起止(UTC): {row['start_time']} ~ {row['end_time']}",
        f"状态: {row['status']}",
        "",
        f"段落数: {len(entries)}",
        "",
        "## 说话人原始标签计数",
    ]
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.get("speaker", "?")] = counts.get(e.get("speaker", "?"), 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {k}: {v}")

    lines.append("")
    lines.append("## 转录全文")
    for e in entries:
        st = e.get("start", "")
        en = e.get("end", "")
        spk = e.get("speaker", "?")
        txt = (e.get("text") or "").strip()
        if not txt:
            continue
        lines.append(f"[{st}-{en}] {spk}: {txt}")

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {out_path} ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
