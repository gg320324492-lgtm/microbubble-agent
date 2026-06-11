"""会议转录段落智能切分脚本 (2026-06-11)

为长同发言人段落按主题信号词自动切分，提升阅读体验。

使用：
    # 容器内执行
    docker exec -i microbubble-agent-app-1 python -c "
    import sys; sys.path.insert(0, '/app')
    exec(open('/tmp/split.py').read().replace('83', '你的会议ID'))
    "

策略：
- 按 。！？ 切分为句子
- 遇到主题信号词（但是/我举个例子/接下来/明白吗/第一/第二/此外/另外/所以/因此 等）开头就切段
- 短段（<30字）与下一段同发言人时合并，避免碎片化
"""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models.meeting import Meeting

SPLIT_AT_START = re.compile(
    r"^(?:"
    r"那[么是]?|所以[，,。]?|但是[，,。]?|不过[，,。]?|然而[，,。]?|另外[，,。]?|还有[，,。]?|"
    r"同时[，,。]?|接下来[，,。]?|然后[，,。]?|其次[，,。]?|再者[，,。]?|"
    r"我举(?:个)?例子[，,。]?|比如说[，,。]?|换句话说[，,。]?|也就是说[，,。]?|"
    r"明白(?:吗|了)?[？?]?|对(?:吧|吗)?[？?。]?|是吧[？?。]?|"
    r"这(?:就|是)[，,。]?|具体(?:来说|而言|呢)?[，,。]?|"
    r"首先[，,。]?|总之[，,。]?|我(?:觉|认)为[，,。]?|因此[，,。]?|"
    r"第一[，,：:]?|第二[，,：:]?|第三[，,：:]?|"
    r"此外[，,。]?|接着[，,。]?|现在[，,。]?|"
    r"[一二三四五六七八九十]+、"
    r")"
)


def split_aggressively(text: str) -> list[str]:
    """激进切分：每遇到主题信号词开头就切段"""
    raw = re.split(r"([。！？])", text)
    sents = []
    for i in range(0, len(raw) - 1, 2):
        s = raw[i].strip()
        p = raw[i + 1] if i + 1 < len(raw) else ""
        if s:
            sents.append(s + p)
    if len(raw) % 2 == 1 and raw[-1].strip():
        sents.append(raw[-1].strip())

    paragraphs = []
    cur = ""
    for sent in sents:
        is_new_topic = bool(SPLIT_AT_START.match(sent))
        if is_new_topic and cur.strip():
            paragraphs.append(cur.strip())
            cur = sent
        else:
            cur += sent
    if cur.strip():
        paragraphs.append(cur.strip())
    return paragraphs if paragraphs else [text]


async def split_meeting_paragraphs(meeting_id: int, db_session_factory=None) -> int:
    """对指定会议做段落切分并写回 DB。

    Args:
        meeting_id: 会议 ID
        db_session_factory: 可选，外部传入 session 工厂

    Returns:
        切分后的总段数
    """
    if db_session_factory is None:
        engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        )
        db_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        close_engine = True
    else:
        close_engine = False

    try:
        async with db_session_factory() as db:
            m = await db.get(Meeting, meeting_id)
            if not m:
                raise ValueError(f"Meeting {meeting_id} not found")
            polished = m.transcript_polished or []

            # 合并相邻同发言人段
            merged = []
            cur = None
            for seg in polished:
                spk = seg.get("speaker", "")
                t = seg.get("text", "")
                if cur is None or cur["speaker"] != spk:
                    if cur:
                        merged.append(cur)
                    cur = {"speaker": spk, "text": t}
                else:
                    cur["text"] += t
            if cur:
                merged.append(cur)

            # 激进切分
            new_polished = []
            for seg in merged:
                text = seg["text"]
                if len(text) >= 100:
                    paras = split_aggressively(text)
                    for p in paras:
                        new_polished.append({"speaker": seg["speaker"], "text": p, "ts": 0})
                else:
                    new_polished.append({"speaker": seg["speaker"], "text": text, "ts": 0})

            # 合并太短的小段（<30字且同发言人）
            final = []
            i = 0
            while i < len(new_polished):
                cur = dict(new_polished[i])
                while (
                    i + 1 < len(new_polished)
                    and new_polished[i + 1]["speaker"] == cur["speaker"]
                    and len(cur["text"]) < 30
                ):
                    cur["text"] += new_polished[i + 1]["text"]
                    i += 1
                final.append(cur)
                i += 1

            m.transcript_polished = final
            await db.commit()
            return len(final)
    finally:
        if close_engine:
            await engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="为会议转录做段落切分")
    parser.add_argument("meeting_id", type=int, help="会议 ID")
    args = parser.parse_args()

    n = asyncio.run(split_meeting_paragraphs(args.meeting_id))
    print(f"会议 {args.meeting_id} 切分完成，共 {n} 段")
