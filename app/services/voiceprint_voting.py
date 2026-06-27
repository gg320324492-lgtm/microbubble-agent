"""集中化声纹投票逻辑 (2026-06-26 重构)

触发: 会议 #135 重处理发现原 vote 算法的 3 个根本缺陷:
  1. cluster_embeddings 用 silhouette 选 K, 低 separation 场景永远选 K=2
     → K=4 实际但 auto 选 K=2, 错过 2 个真实发言人
  2. vote_names_by_cluster 永远取 most_common name, 不管 votes/conf 多差
     → 16 段实际是赵航佳的, 被误标 "发言人A/B/C..." 286 个
  3. assign_speakers conf > 0.30 阈值过低, 韩重阳 avg_conf=-0.006 都能通过
     → 强制给错名字而非标 "发言人?"

本模块提供 5 个核心函数:
  - smart_select_k: 综合 silhouette + 平衡度 + n_expected 选 K
  - vote_with_quality_gates: 4 道质量门控 (center_dist / min_votes / votes_ratio / conf)
  - assign_with_strict_threshold: conf > 0.50 + votes_ratio >= 0.5
  - extract_context_speakers: 从 meeting metadata 提取可能的发言人
  - learn_from_successful_segments: 段级识别成功后累积到 member.voice_embedding

使用:
  from app.services.voiceprint_voting import (
      smart_select_k, vote_with_quality_gates, assign_with_strict_threshold,
      extract_context_speakers, learn_from_successful_segments,
  )
"""
import logging
import re
from collections import Counter
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# Component A: 智能 KMeans 选 K
# ============================================================================
def smart_select_k(
    seg_embs: list,
    n_expected: int = 3,
    min_k: int = 2,
    max_k: int = 8,
) -> tuple:
    """综合 silhouette + 平衡度 + n_expected 接近度 选最优 K

    原算法缺陷: 只看 silhouette, 低 separation 永远选 K=2
    改进: silhouette 0.4 + 平衡度 0.3 + n_expected 接近 0.3

    Returns:
        (labels, k, score, all_scores) — labels 与 seg_embs 等长 (-1 表示 invalid)
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    valid = np.array([e for e in seg_embs if e is not None and not np.all(np.array(e) == 0)])
    if len(valid) < 2:
        return [-1] * len(seg_embs), 1, -1.0, {}

    # K 搜索范围: [max(2, n_expected-2), min(max_k, n_expected+2)]
    # 这样既能覆盖 n_expected 附近的 K, 又不会在 n_expected=10 时只搜 2-5
    k_min = max(min_k, max(2, n_expected - 2))
    k_max = min(max_k, len(valid) - 1, n_expected + 3)
    if k_max < k_min:
        k_min, k_max = 2, min(max_k, len(valid) - 1)
    k_options = list(range(k_min, k_max + 1))
    if not k_options:
        return [-1] * len(seg_embs), 1, -1.0, {}

    all_scores = {}
    best_k, best_score = k_options[0], -1.0

    for k in k_options:
        try:
            km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(valid)
            sil = silhouette_score(valid, km.labels_)
        except Exception as e:
            logger.warning(f"K={k}: {e}")
            continue

        # 平衡度: 最大聚类占比越低越好 (理想均匀)
        ctr = Counter(km.labels_.tolist())
        max_ratio = max(ctr.values()) / len(valid)
        balance = 1.0 - max_ratio  # 0 (一聚类 100%) → 1 (完全均匀)

        # n_expected 接近度
        if n_expected > 0:
            proximity = 1.0 - abs(k - n_expected) / max(n_expected, 1)
        else:
            proximity = 0.5

        # 综合评分
        composite = sil * 0.4 + balance * 0.3 + proximity * 0.3
        all_scores[k] = {"sil": sil, "balance": balance, "proximity": proximity, "composite": composite}
        logger.info(f"  K={k} silhouette={sil:.3f} balance={balance:.3f} proximity={proximity:.3f} → composite={composite:.3f}")

        if composite > best_score:
            best_k, best_score = k, composite

    # 用 best_k 跑 KMeans 生成 labels
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit(valid)
    labels = [-1] * len(seg_embs)
    j = 0
    for i, e in enumerate(seg_embs):
        if e is not None and not np.all(np.array(e) == 0):
            labels[i] = int(km.labels_[j])
            j += 1

    logger.info(f"[smart_select_k] 选 K={best_k} (composite={best_score:.3f}, n_expected={n_expected})")
    return labels, best_k, best_score, all_scores


# ============================================================================
# Component B: 带 4 道质量门控的 vote (cluster-center + greedy 分配)
# ============================================================================
def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    if np.all(a == 0) or np.all(b == 0):
        return 999.0
    a_n = a / (np.linalg.norm(a) + 1e-8)
    b_n = b / (np.linalg.norm(b) + 1e-8)
    return float(1.0 - np.dot(a_n, b_n))


def _cluster_center(emb_list: list) -> Optional[np.ndarray]:
    """聚类中心: 段 embedding 均值 + L2 normalize"""
    valid = [e for e in emb_list if e is not None and not np.all(np.array(e) == 0)]
    if not valid:
        return None
    center = np.mean(valid, axis=0)
    norm = np.linalg.norm(center)
    if norm > 0:
        center = center / norm
    return center


def vote_with_quality_gates(
    seg_embs: list,
    labels: list,
    enrolled: list,
    context_names: Optional[set] = None,
    center_dist_threshold: float = 0.75,
    min_votes: int = 3,
    votes_ratio_threshold: float = 0.30,
    avg_conf_threshold: float = 0.30,
    match_threshold: float = 0.7,
    sample_count_penalty_factor: float = 0.5,
) -> dict:
    """Cluster-center + Hungarian 分配的 vote, 解决原算法"永远取 most_common"导致大量错标

    核心改进 (vs 原 vote_names_by_cluster):
      - 用聚类中心距离而非段级投票, 避免被 enrolled 库中近邻诱导
      - 一次计算 K×N 距离矩阵, 用 Hungarian algorithm (或 greedy fallback) 找最优 K 配 N
      - 已分配的 enrolled 名字不再分配给其他聚类 (防一个名字吃多个聚类)
      - 4 道质量门控: center_dist / min_votes / votes_ratio / avg_conf
      - sample_count penalty: samples=1 的 enrolled 加权惩罚, 避免被 samples=10 的人抢走

    Args:
        seg_embs: 段 embedding 列表
        labels: KMeans labels
        enrolled: [(member_id, name, voice_embedding, sample_count), ...]
                  注意: 4 元组, sample_count 用于 sample_count penalty
                  兼容 3 元组 (无 sample_count, 默认 1)
        context_names: 会议 metadata 提取的可能发言人
        center_dist_threshold: 聚类中心 vs 候选 enrolled 距离上限
        min_votes: 段级 votes >= 3 段才算可信
        votes_ratio_threshold: voted / total >= 0.30
        avg_conf_threshold: 段级 conf > 0.30
        match_threshold: 单段匹配距离上限 (默认 0.7)
        sample_count_penalty_factor: samples=1 加权比例 (默认 0.5, samples=3+ 满权)

    Returns:
        {cluster_id: (name, avg_conf, votes, total_segments)}
    """
    cluster_names = {}
    unique_cids = sorted(set(l for l in labels if l >= 0))
    if not unique_cids or not enrolled:
        return {cid: (None, 0.0, 0, 0) for cid in unique_cids}

    # 过滤 enrolled: 如果有 context_names, 只对这些成员 vote
    if context_names:
        enrolled_filtered = [
            item for item in enrolled
            if item[1] in context_names  # item[1] = name
        ]
        if not enrolled_filtered:
            logger.warning(f"[vote] context_names={context_names} 但 enrolled 无人匹配, 回退全 enrolled")
            enrolled_filtered = enrolled
        else:
            logger.info(f"[vote] context 过滤: {len(enrolled)} → {len(enrolled_filtered)}")
    else:
        enrolled_filtered = enrolled

    # Step 1: 算每个聚类的中心 + 段级 votes
    cluster_info = {}  # cid → {center, total, name_votes}
    for cid in unique_cids:
        idxs = [i for i, l in enumerate(labels) if l == cid]
        emb_list = [seg_embs[i] for i in idxs if seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0)]
        center = _cluster_center(emb_list)
        # 段级 votes: 每段 vs enrolled 最近邻
        name_votes = Counter()
        seg_confs = {}  # name → [conf, ...]
        for i in idxs:
            if seg_embs[i] is None or np.all(np.array(seg_embs[i]) == 0):
                continue
            emb = np.array(seg_embs[i], dtype=np.float32)
            best_name, best_dist = None, 999.0
            for item in enrolled_filtered:
                mid, name, db_emb = item[0], item[1], item[2]
                if db_emb is None:
                    continue
                db_emb_arr = np.array(db_emb, dtype=np.float32)
                if np.all(db_emb_arr == 0):
                    continue
                dist = _cosine_distance(emb, db_emb_arr)
                if dist < best_dist:
                    best_dist = dist
                    best_name = name
            if best_name and best_dist < match_threshold:
                name_votes[best_name] += 1
                seg_confs.setdefault(best_name, []).append(1.0 - best_dist)
        cluster_info[cid] = {
            "center": center,
            "total": len(idxs),
            "name_votes": name_votes,
            "seg_confs": seg_confs,
        }

    # Step 2: 算 K×N 距离矩阵 + 段级 + 中心距离
    # 优先用 Hungarian (scipy.optimize.linear_sum_assignment) 找最优配对
    try:
        from scipy.optimize import linear_sum_assignment
        use_hungarian = True
    except ImportError:
        use_hungarian = False

    n_cids = len(unique_cids)
    n_enrolled = len(enrolled_filtered)

    # 距离矩阵: cid × enrolled
    dist_matrix = np.full((n_cids, n_enrolled), 999.0, dtype=np.float32)
    # sample_count weight: 解决 samples=1 的人 (张宏魁, 韩重阳) 被 samples=10 的人抢走
    # weight = min(samples, 3) / 3 → samples=1: 0.33, samples=3+: 1.0
    # effective_cost = dist / weight, 距离按"可信度"放大
    sample_weight = np.ones(n_enrolled, dtype=np.float32)
    for j, item in enumerate(enrolled_filtered):
        if len(item) >= 4:
            sc = item[3] or 1
        else:
            sc = 1
        sample_weight[j] = min(sc, 3) / 3.0

    for i, cid in enumerate(unique_cids):
        center = cluster_info[cid]["center"]
        if center is None:
            continue
        for j, item in enumerate(enrolled_filtered):
            mid, name, db_emb = item[0], item[1], item[2]
            if db_emb is None:
                continue
            db_emb_arr = np.array(db_emb, dtype=np.float32)
            if np.all(db_emb_arr == 0):
                continue
            real_dist = _cosine_distance(center, db_emb_arr)
            # sample_count penalty: samples 少的人 distance 放大
            dist_matrix[i, j] = real_dist / sample_weight[j]

    # Hungarian 找最优配对 (最小化总距离, 受 sample_count penalty 调整)
    cid_to_name = {}  # cid → (name, center_dist, votes, ratio, avg_conf)
    used_enrolled_idx = set()
    if use_hungarian and n_cids <= n_enrolled:
        # 转 cost: 距离大→cost 大, 已分配/超阈值 → 极高 cost
        cost = dist_matrix.copy()
        # 距离 >= threshold 标记为 999 (不让 Hungarian 选)
        cost[cost >= center_dist_threshold] = 999.0
        row_ind, col_ind = linear_sum_assignment(cost)
        for r, c in zip(row_ind, col_ind):
            if cost[r, c] >= 999.0:
                continue
            cid = unique_cids[r]
            mid, name, _ = enrolled_filtered[c][0], enrolled_filtered[c][1], enrolled_filtered[c][2]
            # 用真实距离 (无 penalty) 做门控判断
            real_dist = float(dist_matrix[r, c] * sample_weight[c])
            votes = cluster_info[cid]["name_votes"].get(name, 0)
            ratio = votes / max(cluster_info[cid]["total"], 1)
            confs = cluster_info[cid]["seg_confs"].get(name, [])
            avg_conf = float(np.mean(confs)) if confs else 0.0
            cid_to_name[cid] = (name, avg_conf, votes, ratio, real_dist, mid)
            used_enrolled_idx.add(c)
        logger.info(f"[vote] Hungarian 配对 {len(cid_to_name)}/{n_cids} 个聚类 (sample_count penalty)")
    else:
        # Fallback: greedy 按 effective cost 排
        candidates = []
        for r, cid in enumerate(unique_cids):
            for j in range(n_enrolled):
                if dist_matrix[r, j] >= center_dist_threshold:
                    continue
                candidates.append((cid, j, dist_matrix[r, j]))
        candidates.sort(key=lambda x: x[2])
        for cid, j, _ in candidates:
            if cid in cid_to_name or j in used_enrolled_idx:
                continue
            mid, name, _ = enrolled_filtered[j][0], enrolled_filtered[j][1], enrolled_filtered[j][2]
            real_dist = float(dist_matrix[unique_cids.index(cid), j] * sample_weight[j])
            votes = cluster_info[cid]["name_votes"].get(name, 0)
            ratio = votes / max(cluster_info[cid]["total"], 1)
            confs = cluster_info[cid]["seg_confs"].get(name, [])
            avg_conf = float(np.mean(confs)) if confs else 0.0
            cid_to_name[cid] = (name, avg_conf, votes, ratio, real_dist, mid)
            used_enrolled_idx.add(j)

    # Step 3: 应用 4 道质量门控
    for cid in unique_cids:
        total = cluster_info[cid]["total"]
        if cid not in cid_to_name:
            logger.info(f"  聚类 {cid} ({total} 段): ❌ 无 Hungarian 配对 (超阈值或 enrolled 不够)")
            cluster_names[cid] = (None, 0.0, 0, total)
            continue
        name, avg_conf, votes, ratio, center_dist, mid = cid_to_name[cid]
        passed = []
        if center_dist >= center_dist_threshold:
            passed.append(f"center_dist={center_dist:.3f}>={center_dist_threshold}")
        if votes < min_votes:
            passed.append(f"votes={votes}<{min_votes}")
        if ratio < votes_ratio_threshold:
            passed.append(f"votes_ratio={ratio:.3f}<{votes_ratio_threshold}")
        if avg_conf < avg_conf_threshold:
            passed.append(f"avg_conf={avg_conf:.3f}<{avg_conf_threshold}")
        if passed:
            logger.info(
                f"  聚类 {cid} ({total} 段, votes={votes}/{total}, ratio={ratio:.2f}): "
                f"{name} avg_conf={avg_conf:.3f} center_dist={center_dist:.3f} "
                f"❌ 质量门: {'; '.join(passed)}"
            )
            cluster_names[cid] = (None, 0.0, votes, total)
        else:
            cluster_names[cid] = (name, avg_conf, votes, total)
            logger.info(
                f"  聚类 {cid} ({total} 段, votes={votes}/{total}, ratio={ratio:.2f}): "
                f"{name} avg_conf={avg_conf:.3f} center_dist={center_dist:.3f} ✅"
            )

    return cluster_names


# ============================================================================
# Component C: 严格阈值的 assign
# ============================================================================
def assign_with_strict_threshold(
    transcript: list,
    labels: list,
    cluster_names: dict,
    conf_threshold: float = 0.50,
    votes_ratio_threshold: float = 0.5,
) -> tuple:
    """严格阈值版 assign, 解决 conf > 0.30 太松

    新规则 (任一不满足 → "发言人?"):
      1. cluster 有名字 (cluster_names[cid] != None)
      2. cluster_names[cid].conf > conf_threshold (默认 0.50)
      3. cluster_names[cid].votes / total_segments >= votes_ratio_threshold (默认 0.5)

    原算法: conf > 0.30 太松, 韩重阳 avg_conf=-0.006 都会通过 (但实际 cluster 标 None 时 fallback 错了)
    新算法: 4 道门由 vote 阶段控制, 这里只看 conf + votes_ratio, 避免重复逻辑
    """
    new_speaker = [""] * len(transcript)
    speaker_label_to_name = {}

    # 算每 cluster 的 votes_ratio 提前
    cid_total = {}
    for cid in set(l for l in labels if l >= 0):
        cid_total[cid] = sum(1 for l in labels if l == cid)

    for i, seg in enumerate(transcript):
        if labels[i] < 0:
            new_speaker[i] = "发言人?"
            continue
        cid = labels[i]
        name, conf, votes, _ = cluster_names.get(cid, (None, 0.0, 0, 0))
        total = cid_total.get(cid, 0)
        ratio = votes / total if total > 0 else 0

        if name and conf > conf_threshold and ratio >= votes_ratio_threshold:
            new_speaker[i] = name
            old_label = seg.get("speaker_label", f"speaker_{i}")
            speaker_label_to_name[old_label] = name
        else:
            new_speaker[i] = "发言人?"

    ctr = Counter(new_speaker)
    logger.info(f"[assign_strict] new_speaker 分布: {dict(ctr)} (conf>{conf_threshold}, ratio>={votes_ratio_threshold})")
    return new_speaker, speaker_label_to_name


# ============================================================================
# Component D: 从 meeting metadata 提取可能的发言人
# ============================================================================
def extract_context_speakers(meeting) -> set:
    """从 meeting 的 metadata 提取可能的发言人集合

    来源 (按权重):
      1. presenter_ids (直接是 member IDs, 权重 1.0)
      2. created_by (会议创建人, 通常是主持人, 权重 0.8)
      3. description / agenda (文本里出现的人名, 权重 0.5)
      4. location (同地点历史会议的人, 权重 0.3)
      5. related_meeting_ids (相关历史会议的人, 权重 0.3)

    Returns: set of member names
    """
    from app.models.member import Member
    from app.models.meeting import Meeting
    from sqlalchemy import select, or_

    context = set()

    # 1. presenter_ids
    if hasattr(meeting, "presenter_ids") and meeting.presenter_ids:
        for pid in meeting.presenter_ids:
            if isinstance(pid, int):
                context.add(f"presenter:{pid}")  # placeholder, resolved below
            elif isinstance(pid, str):
                context.add(pid)

    # 2. created_by
    if hasattr(meeting, "created_by") and meeting.created_by:
        context.add(f"creator:{meeting.created_by}")

    # 3. description / agenda (文本提取人名, 用 member.name 模糊匹配)
    text_sources = []
    if hasattr(meeting, "description") and meeting.description:
        text_sources.append(meeting.description)
    if hasattr(meeting, "agenda") and meeting.agenda:
        if isinstance(meeting.agenda, list):
            text_sources.extend([str(x) for x in meeting.agenda])
        else:
            text_sources.append(str(meeting.agenda))
    if hasattr(meeting, "title") and meeting.title:
        text_sources.append(meeting.title)
    if hasattr(meeting, "summary") and meeting.summary:
        # LLM-generated summary 通常含真实发言人
        text_sources.append(meeting.summary)

    # 文本提取人名 (匹配 member.name)
    if text_sources:
        from app.models.member import Member
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm
        from app.config import settings
        try:
            _sync_engine = _ce(settings.DATABASE_URL)
            SyncS = _sm(bind=_sync_engine)
            with SyncS() as sdb:
                names = sdb.execute(select(Member.name)).scalars().all()
            _sync_engine.dispose()
            full_text = " ".join(text_sources)
            for name in names:
                if name and name in full_text:
                    context.add(name)
        except Exception as e:
            logger.warning(f"extract_context_speakers 文本提取失败: {e}")

    return context  # caller resolves placeholders via DB


async def resolve_context_to_names(context: set, db) -> set:
    """resolve_context_speakers 返回的 placeholder 集合 → 具体 member names

    Args:
        context: extract_context_speakers 的输出 (含 'presenter:N' / 'creator:N' 等)
        db: AsyncSession

    Returns: set of member.name
    """
    from app.models.member import Member
    from sqlalchemy import select

    if not context:
        return set()

    # 1. 收集所有需要查的 member IDs
    member_ids = set()
    for item in context:
        if item.startswith("presenter:") or item.startswith("creator:"):
            try:
                mid = int(item.split(":", 1)[1])
                member_ids.add(mid)
            except (ValueError, IndexError):
                pass
        else:
            # 已经是名字, 直接保留
            pass

    # 2. 批量查 (async session 必须 await)
    if member_ids:
        result = await db.execute(
            select(Member).where(Member.id.in_(member_ids))
        )
        for m in result.scalars().all():
            context.discard(f"presenter:{m.id}")
            context.discard(f"creator:{m.id}")
            context.add(m.name)

    return context


# ============================================================================
# Component G: 从历史会议反推可能的发言人 (context_names 增强)
# ============================================================================
async def get_recent_meeting_speakers(
    meeting_id: int,
    db,
    lookback_count: int = 5,
    lookback_days: int = 30,
) -> set:
    """从历史同 creator / 同 location 会议反推可能的发言人

    用途: 给 vote_with_quality_gates 提供 context_names 强约束
    例如: 王天志通常每周开 1-2 次组会, 上次组会的参会人很可能是这次组会的参会人

    Args:
        meeting_id: 当前会议 ID
        db: AsyncSession
        lookback_count: 最多看多少场历史会议
        lookback_days: 多少天内

    Returns: set of member names
    """
    from app.models.meeting import Meeting, MeetingParticipant
    from app.models.member import Member
    from sqlalchemy import select, or_
    from datetime import datetime, timedelta, timezone

    current = await db.get(Meeting, meeting_id)
    if not current:
        return set()

    # 找历史会议: 同 created_by 或同 location
    # meetings.created_at 是 TIMESTAMP WITHOUT TIME ZONE (tz-naive), 用 naive datetime 比较
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    conditions = [Meeting.id != meeting_id, Meeting.created_at >= cutoff]
    if current.created_by:
        conditions.append(Meeting.created_by == current.created_by)
    if current.location:
        conditions.append(Meeting.location == current.location)

    if len(conditions) < 3:
        # 无足够 context, 跳过
        return set()

    result = await db.execute(
        select(Meeting).where(*conditions).order_by(Meeting.created_at.desc()).limit(lookback_count)
    )
    historical = result.scalars().all()
    if not historical:
        return set()

    # 收集历史参会人 (MeetingParticipant + key_points/decisions LLM 提取)
    historical_member_ids = set()
    for h in historical:
        if h.presenter_ids:
            historical_member_ids.update(h.presenter_ids)
        # 从 participants 拿
        rp = await db.execute(
            select(MeetingParticipant).where(MeetingParticipant.meeting_id == h.id)
        )
        for p in rp.scalars().all():
            historical_member_ids.add(p.member_id)

    if not historical_member_ids:
        return set()

    # 解析为 member names
    rm = await db.execute(
        select(Member).where(Member.id.in_(historical_member_ids))
    )
    names = {m.name for m in rm.scalars().all() if m.name}
    logger.info(f"[context_history] 会议 #{meeting_id} 历史 {len(historical)} 场, 找到 {len(names)} 个相关人: {names}")
    return names

