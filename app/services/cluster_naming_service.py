"""会议说话人**簇级命名**的人工裁决写入（可选开关，默认关）。

## 背景

Phase 1f 的实测结论: 在「自动聚类 + 人工给簇命名」的形态下,
**命名是瓶颈** —— 簇纯度 0.85 但簇命名正确率仅 0.64, 且「簇名错 ⇒ 整簇皆错」。

于是产品形态被拆成两半:
  ① **聚类** —— 纯声学, 已由 Phase 1b 证明可用 (簇纯度 0.85 / 主导簇占比 0.83);
  ② **命名** —— 需要人给簇起名字。

人起完名字之后, **重跑流水线不能把它冲掉**（类 20.244 记过「重标会把刚修好的
bug 重新装回去」的同型风险）⇒ 命名必须**固化进裁决表**。

## 为什么复用 `meeting_speaker_adjudications` 而不是新建表

该表已经按 **段中点落入 [seg_start, seg_end]** 匹配, 且
`post_meeting_tasks.py` 在重跑时**命中裁决的段直接采用裁决、不再过声纹匹配**
⇒ 簇级命名只要能被表达成「这些段是这个人」, 整条「重跑优先应用」的链路**已经存在**,
**零 schema 变更、零流水线改动**。

## ⭐ 关键设计: 簇级裁决必须**逐段**写, 不能按「簇的时间区间」写

聚类是按**内容**分的, 同一个人在不同簇里 ⇒ **簇在时间轴上是交错的**。
若把一个簇写成一条 `[min(start), max(end)]` 的区间裁决, 那些**落在区间内但属于别的簇**
的段会被误判成这个簇的人。

⇒ 因此本服务把「簇 → 段」的映射**展开成逐段裁决**: 簇 C 里有多少段就写多少行,
每行覆盖**那一段自己的** [start, end]。
⇒ 段级区间互不重叠 ⇒ 中点匹配唯一归属, 与人工听辨裁决的语义完全一致。

## 开关

``settings.CLUSTER_NAMING_ENABLED``（默认 **False**）⇒ 关闭时
`record_cluster_naming` **拒绝写库** ⇒ **生产行为零变化**。
开启后本服务只负责**写入裁决表**; 「重跑时优先应用」由既有裁决机制负责
（无需改 `post_meeting_tasks.py`）。
"""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication

logger = logging.getLogger(__name__)

#: 簇级命名的 source 前缀约定 (便于按前缀清空/审计)
CLUSTER_SOURCE_PREFIX = "cluster-naming"


def _source_for(cluster_id) -> str:
    return f"{CLUSTER_SOURCE_PREFIX}:{cluster_id}"


def segments_to_adjudication_rows(
    clusters: Sequence[Dict],
) -> List[Dict]:
    """把「簇 → 段」的映射展开成逐段裁决行。

    ``clusters`` 每项形如::

        {"cluster_id": "c3", "speaker": "王天志",
         "segments": [{"start": 12.0, "end": 14.5, "seg_index": 7}, ...]}

    ⇒ 返回每项形如 ``{seg_start, seg_end, seg_index, speaker, source, note}``。
    ⇒ **逐段**写 (见模块 docstring 的关键设计说明)。
    """
    rows: List[Dict] = []
    for c in clusters:
        cid = c.get("cluster_id")
        speaker = (c.get("speaker") or "").strip()
        if not speaker:
            continue
        src = _source_for(cid)
        for seg in c.get("segments") or []:
            s = seg.get("start")
            e = seg.get("end")
            if s is None or e is None or float(e) <= float(s):
                continue
            rows.append({
                "seg_start": float(s),
                "seg_end": float(e),
                "seg_index": seg.get("seg_index"),
                "speaker": speaker,
                "source": src,
                "note": c.get("note"),
            })
    return rows


async def clear_cluster_naming(
    db: AsyncSession,
    meeting_id: int,
    commit: bool = True,
) -> int:
    """清掉某场会议的**全部簇级命名裁决**（不动人工听辨裁决）。

    ⇒ 重新起名时先清后写 ⇒ **幂等**: 重跑不会累积成多份。
    """
    res = await db.execute(
        delete(MeetingSpeakerAdjudication).where(
            MeetingSpeakerAdjudication.meeting_id == meeting_id,
            MeetingSpeakerAdjudication.source.like(f"{CLUSTER_SOURCE_PREFIX}:%"),
        )
    )
    if commit:
        await db.commit()
    return int(res.rowcount or 0)


async def record_cluster_naming(
    db: AsyncSession,
    meeting_id: int,
    clusters: Sequence[Dict],
    replace: bool = True,
    commit: bool = True,
) -> Dict[str, int]:
    """把「簇 → 人工起的名字」写进裁决表。

    :param clusters: 见 :func:`segments_to_adjudication_rows`。
    :param replace: 先清掉本场已有的簇级命名 (幂等重写)。
    :returns: ``{"written": n, "cleared": m, "skipped": k}``。

    ⚠️ **开关默认关**: ``settings.CLUSTER_NAMING_ENABLED`` 为假时**不写库**,
    返回 ``written=0`` ⇒ 生产行为零变化。
    """
    from app.config import settings

    if not getattr(settings, "CLUSTER_NAMING_ENABLED", False):
        logger.info(
            "CLUSTER_NAMING_ENABLED 关闭 ⇒ 不写入簇级命名裁决 (meeting=%s)", meeting_id)
        return {"written": 0, "cleared": 0, "skipped": 0}

    rows = segments_to_adjudication_rows(clusters)
    cleared = 0
    if replace:
        cleared = await clear_cluster_naming(db, meeting_id, commit=False)
    for r in rows:
        db.add(MeetingSpeakerAdjudication(
            meeting_id=meeting_id,
            seg_start=r["seg_start"],
            seg_end=r["seg_end"],
            seg_index=r["seg_index"],
            speaker=r["speaker"],
            source=r["source"],
            note=r["note"],
        ))
    if commit:
        await db.commit()
    logger.info(
        "簇级命名裁决写入 meeting=%s: %d 行 (清掉旧 %d 行)",
        meeting_id, len(rows), cleared)
    return {"written": len(rows), "cleared": cleared, "skipped": 0}


async def get_cluster_naming(
    db: AsyncSession,
    meeting_id: int,
) -> List[MeetingSpeakerAdjudication]:
    """读回某场会议的簇级命名裁决。"""
    result = await db.execute(
        select(MeetingSpeakerAdjudication)
        .where(
            MeetingSpeakerAdjudication.meeting_id == meeting_id,
            MeetingSpeakerAdjudication.source.like(f"{CLUSTER_SOURCE_PREFIX}:%"),
        )
        .order_by(MeetingSpeakerAdjudication.seg_start)
    )
    return list(result.scalars().all())


async def cluster_naming_lookup(
    db: AsyncSession,
    meeting_id: int,
) -> Dict[str, str]:
    """簇级命名裁决的 ``(seg_start, seg_end) -> speaker`` 映射 (供审计/展示)。"""
    rows = await get_cluster_naming(db, meeting_id)
    return {f"{r.seg_start:.3f}-{r.seg_end:.3f}": r.speaker for r in rows}


__all__ = [
    "CLUSTER_SOURCE_PREFIX",
    "clear_cluster_naming",
    "cluster_naming_lookup",
    "get_cluster_naming",
    "record_cluster_naming",
    "segments_to_adjudication_rows",
]
