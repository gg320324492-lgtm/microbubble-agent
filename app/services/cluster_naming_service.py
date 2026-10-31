"""会议说话人**簇级命名**的人工裁决写入（可选开关，默认关）。

## 背景

Phase 1f/1h 的实测结论: 在「自动聚类 + 人工给簇命名」的形态下,
**命名是瓶颈** —— 簇纯度 0.85 但簇命名正确率仅 0.64, 且「簇名错 ⇒ 整簇皆错」。

于是产品形态被拆成两半:
  ① **聚类** —— 纯声学, 已由 Phase 1b/1h 证明可用 (簇纯度 0.85 / 主导簇占比 0.83);
  ② **命名** —— 需要人给簇起名字。

人起完名字之后, **重跑流水线不能把它冲掉**（类 20.244 记过「重标会把刚修好的
bug 重新装回去」的同型风险）⇒ 命名必须**固化进裁决表**。

## ⭐ 为什么用**独立表** `meeting_cluster_adjudications`, 不复用段级表

两张表的**决策粒度不同**:

| 表 | 粒度 | 一次决策的语义 |
|---|---|---|
| `meeting_speaker_adjudications` (146) | **段** | 「这一小段是某人」—— 逐段听辨的定点纠正 |
| `meeting_cluster_adjudications` (148) | **簇** | 「这一整簇是某人」—— 听一段样本后给整簇起名 |

⇒ 混在一张表会: ① 丢掉「这是簇级决策」这一事实; ② 一次批量重标动辄上千行,
回滚粒度从「一个簇」退化成「上千行」; ③ 两类裁决冲突时无从消解。

⇒ **冲突消解 = 段级优先**（类 20.244 的「裁决更细 ⇒ 优先」）：
段级是定点证据, 簇级是整簇推广 ⇒ 见 :func:`build_combined_resolver`。

## 簇的身份: member_spans

簇号只在**一次聚类运行内**有意义 ⇒ 不能拿 cluster_id 当稳定标识。
⇒ 本表存 `member_spans` (簇内各段时间区间) + `member_fingerprint`;
应用时靠「段中点落入任一 member_span」把转录段映射回簇;
指纹变了 ⇒ 重跑聚类后这个簇已经不是当初那个 ⇒ 旧裁决不得沿用。

## 开关

``settings.CLUSTER_NAMING_ENABLED``（默认 **False**）⇒ 关闭时
`record_cluster_naming` **拒绝写库** ⇒ **生产行为零变化**。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_cluster_adjudication import (
    MeetingClusterAdjudication,
    member_fingerprint,
)

logger = logging.getLogger(__name__)

#: 簇级命名的 source 前缀约定 (便于按前缀清空/审计)
CLUSTER_SOURCE_PREFIX = "cluster-naming"


def _source_for(cluster_key) -> str:
    return f"{CLUSTER_SOURCE_PREFIX}:{cluster_key}"


def clusters_to_adjudication_rows(
    clusters: Sequence[Dict],
) -> List[Dict]:
    """把「簇」列表转成**簇级**裁决行 (一行一簇, 不展开成逐段)。

    ``clusters`` 每项形如::

        {"cluster_key": "c3", "cluster_id": 3, "speaker": "王天志",
         "segments": [{"start": 12.0, "end": 14.5, "seg_index": 7}, ...]}

    ⇒ 返回每项形如
    ``{cluster_key, cluster_id, speaker, n_members, member_spans,
    member_fingerprint, source, note}``。

    ⚠️ **不展开成逐段**: 展开会丢掉「这是簇级决策」的事实, 且把回滚粒度
    从「一个簇」压成「上千行」。段↔簇的映射靠 ``member_spans`` 表达。
    """
    rows: List[Dict] = []
    for c in clusters:
        key = (c.get("cluster_key") or "").strip()
        speaker = (c.get("speaker") or "").strip()
        if not key or not speaker:
            continue
        spans = []
        for seg in c.get("segments") or []:
            s = seg.get("start")
            e = seg.get("end")
            if s is None or e is None or float(e) <= float(s):
                continue
            spans.append([round(float(s), 3), round(float(e), 3)])
        if not spans:
            continue
        spans.sort()
        rows.append({
            "cluster_key": key,
            "cluster_id": c.get("cluster_id"),
            "speaker": speaker,
            "n_members": len(spans),
            "member_spans": spans,
            "member_fingerprint": member_fingerprint(spans),
            "source": _source_for(key),
            "note": c.get("note"),
        })
    return rows


async def clear_cluster_naming(
    db: AsyncSession,
    meeting_id: int,
    commit: bool = True,
) -> int:
    """清掉某场会议的**全部簇级命名裁决**（不动段级人工听辨裁决）。

    ⇒ 重新起名时先清后写 ⇒ **幂等**: 重跑不会累积成多份。
    """
    res = await db.execute(
        delete(MeetingClusterAdjudication).where(
            MeetingClusterAdjudication.meeting_id == meeting_id,
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
    """把「簇 → 人工起的名字」写进**簇级裁决表**。

    :param clusters: 见 :func:`clusters_to_adjudication_rows`。
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

    rows = clusters_to_adjudication_rows(clusters)
    cleared = 0
    if replace:
        cleared = await clear_cluster_naming(db, meeting_id, commit=False)
    for r in rows:
        db.add(MeetingClusterAdjudication(
            meeting_id=meeting_id,
            cluster_key=r["cluster_key"],
            cluster_id=r["cluster_id"],
            speaker=r["speaker"],
            n_members=r["n_members"],
            member_spans=r["member_spans"],
            member_fingerprint=r["member_fingerprint"],
            source=r["source"],
            note=r["note"],
        ))
    if commit:
        await db.commit()
    logger.info(
        "簇级命名裁决写入 meeting=%s: %d 簇 (清掉旧 %d 簇)",
        meeting_id, len(rows), cleared)
    return {"written": len(rows), "cleared": cleared, "skipped": 0}


async def get_cluster_naming(
    db: AsyncSession,
    meeting_id: int,
) -> List[MeetingClusterAdjudication]:
    """读回某场会议的簇级命名裁决。"""
    result = await db.execute(
        select(MeetingClusterAdjudication)
        .where(MeetingClusterAdjudication.meeting_id == meeting_id)
        .order_by(MeetingClusterAdjudication.cluster_key)
    )
    return list(result.scalars().all())


async def cluster_naming_lookup(
    db: AsyncSession,
    meeting_id: int,
) -> Dict[str, str]:
    """簇级命名裁决的 ``cluster_key -> speaker`` 映射 (供审计/展示)。"""
    rows = await get_cluster_naming(db, meeting_id)
    return {r.cluster_key: r.speaker for r in rows}


class ClusterAdjudicationResolver:
    """把簇级裁决编成「段 [start,end] → 说话人」的查询器。

    匹配口径 = **段中点落入该簇的任一 member_span**（与段级表同口径）。
    None = 无簇级裁决, 调用方应走正常的声纹识别 / 段级裁决。
    """

    def __init__(self, rows: Sequence[MeetingClusterAdjudication]):
        self._rows = list(rows)
        # 展开成 (start, end, speaker) 的扁平表, 按 start 排序 ⇒ bisect 定位
        flat: List[tuple] = []
        for r in self._rows:
            for span in (r.member_spans or []):
                try:
                    a, b = float(span[0]), float(span[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if b > a:
                    flat.append((a, b, r.speaker))
        flat.sort()
        self._flat = flat
        self._starts = [f[0] for f in flat]

    def __len__(self) -> int:
        return len(self._rows)

    def lookup(self, start: Optional[float], end: Optional[float]) -> Optional[str]:
        """段中点落入某簇的 member_span 则返回该簇的 speaker, 否则 None。"""
        if start is None or end is None or not self._flat:
            return None
        import bisect
        mid = (float(start) + float(end)) / 2.0
        i = bisect.bisect_right(self._starts, mid) - 1
        while i >= 0:
            a, b, sp = self._flat[i]
            if a <= mid <= b:
                return sp
            i -= 1
        return None


async def build_cluster_resolver(
    db: AsyncSession, meeting_id: int
) -> ClusterAdjudicationResolver:
    return ClusterAdjudicationResolver(await get_cluster_naming(db, meeting_id))


def build_combined_resolver(segment_resolver, cluster_resolver):
    """组合**段级**与**簇级**裁决: **段级优先**（裁决更细 ⇒ 优先, 类 20.244）。

    :param segment_resolver: 有 ``lookup(start, end)`` 的对象（如 AdjudicationResolver）。
    :param cluster_resolver: 有 ``lookup(start, end)`` 的对象（如 ClusterAdjudicationResolver）。
    """

    class _Combined:
        def lookup(self, start, end):
            if segment_resolver is not None:
                got = segment_resolver.lookup(start, end)
                if got:
                    return got
            if cluster_resolver is not None:
                return cluster_resolver.lookup(start, end)
            return None

        def __len__(self):
            n = 0
            for r in (segment_resolver, cluster_resolver):
                if r is not None:
                    n += len(r)
            return n

    return _Combined()


__all__ = [
    "CLUSTER_SOURCE_PREFIX",
    "ClusterAdjudicationResolver",
    "build_cluster_resolver",
    "build_combined_resolver",
    "clear_cluster_naming",
    "cluster_naming_lookup",
    "clusters_to_adjudication_rows",
    "get_cluster_naming",
    "record_cluster_naming",
]
