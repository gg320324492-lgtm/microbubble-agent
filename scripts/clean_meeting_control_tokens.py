"""清除转录里的 SenseVoice 控制 token(<|EMO_UNKNOWN|> 等)。

为什么: 质量门 `control_token_leak` 规定"落库前必须 0 泄漏"(>0% 即 fail),
而实测有 5 场会议存在泄漏(202:37/399, 203:636/3331, 229:55/284, 242:236/591, 243:141/613)。
这些是**ASR 噪声**不是内容 ⇒ 用 `sanitize_text`(质量评估自己用的那个正则)清掉,
不改动任何真实文字。⚠️ 写 JSON 列必须**重建 list 与 dict**(原地改 + 赋回同一对象
⇒ SQLAlchemy 判定值未变 ⇒ **不生成 UPDATE**, 类 20.220 的静默失效)。
"""
import asyncio
import sys

sys.path.insert(0, "/app")


async def main():
    from sqlalchemy import select, text as sqlt
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.meeting_quality_service import SENSEVOICE_TAG_RE, sanitize_text

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        for m in (await db.execute(
                select(Meeting).where(Meeting.transcript.isnot(None)).order_by(Meeting.id))).scalars().all():
            t = m.transcript or []
            if not t:
                continue
            hit_t = sum(1 for s in t if s.get("text") and SENSEVOICE_TAG_RE.search(s["text"]))
            pol = m.transcript_polished or []
            hit_p = sum(1 for s in pol if s.get("text") and SENSEVOICE_TAG_RE.search(s["text"]))
            if not hit_t and not hit_p:
                continue
            bk = "meeting_%d_backup_pre_control_token_clean" % m.id
            await db.execute(sqlt("DROP TABLE IF EXISTS %s" % bk))
            await db.execute(sqlt("CREATE TABLE %s AS SELECT * FROM meetings WITH NO DATA" % bk))
            await db.execute(sqlt("INSERT INTO %s SELECT * FROM meetings WHERE id = :i" % bk),
                             {"i": m.id})
            await db.commit()

            new_t = []
            for s in t:
                d = dict(s)                       # 新 dict
                if d.get("text"):
                    d["text"] = sanitize_text(d["text"])
                new_t.append(d)
            new_p = []
            for s in pol:
                d = dict(s)
                if d.get("text"):
                    d["text"] = sanitize_text(d["text"])
                new_p.append(d)
            m.transcript = new_t                 # 新 list
            if pol:
                m.transcript_polished = new_p
            await db.commit()
            await db.refresh(m)
            left = sum(1 for s in (m.transcript or [])
                       if s.get("text") and SENSEVOICE_TAG_RE.search(s["text"]))
            print("[vp] 会议%-4d 清掉 transcript %d/%d 段, polished %d 段; 残留 %d  (备份 %s)" % (
                m.id, hit_t, len(t), hit_p, left, bk), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
