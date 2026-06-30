#!/usr/bin/env python3
"""从会议音频反推/重建 3 人的纯净声纹

v2026-06-27 设计：用会议 153 的 m4a 音频 + cluster_id 分组
反推 cluster_0/1/2 的纯净 embedding，覆盖污染的 members.voice_embedding。

思路:
  1. 会议 153 audio_url 已有（recordings/44c95a01575d4e08bb99700ba8d32882.m4a）
  2. 重跑 VAD 切段 + batch_extract_embeddings（374 段，2026-06-19 修复后 100% 有效）
  3. 按 transcript[].cluster_id 分组 → 每组求均值 → cluster_center
  4. 用 cluster_center 与 backup 污染的 voice_embedding 对比
     - 距离 < 0.5: 用反推公式还原为纯净样本
     - 距离 0.5-0.7: 直接覆盖（backup 污染严重）
     - 距离 > 0.7: 跳过（cluster_center 与 member 距离太远，可能 cluster 标错）
  5. 写 member_voice_history audit

用法:
  python scripts/purify_voiceprints_from_meeting.py --meeting 153 \\
      --cluster-to-member 'cluster_0:王天志,cluster_1:杜同贺,cluster_2:张宏魁' \\
      [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.member_voice_history import MemberVoiceHistory
from app.models.meeting import Meeting


async def extract_cluster_centers(
    session_factory,
    meeting_id: int,
    cluster_member_map: Dict[int, str],
) -> Dict[int, dict]:
    """从会议音频提取 cluster centers

    Returns:
        {cid: {member_id, member_name, center, seg_count, seg_indices}}
    """
    from app.services.audio_processor import audio_processor
    from app.services.file_service import file_service
    from app.services.voiceprint_service import voiceprint_service

    async with session_factory() as db:
        # 1. 读会议
        result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
        meeting = result.scalar_one_or_none()
        if not meeting:
            raise ValueError(f"会议 {meeting_id} 不存在")
        if not meeting.audio_url:
            raise ValueError(f"会议 {meeting_id} 没有 audio_url")
        if not meeting.transcript:
            raise ValueError(f"会议 {meeting_id} transcript 为空，请先跑 post_meeting_process")

        # 2. 校验 cluster_id 与 member 映射
        name_to_id = {}
        for cid, name in cluster_member_map.items():
            r = await db.execute(select(Member).where(Member.name == name))
            m = r.scalar_one_or_none()
            if not m:
                raise ValueError(f"Member '{name}' (cluster_{cid}) 不存在")
            name_to_id[name] = m.id

        # 3. 下载音频 + VAD 切段
        print(f"下载会议 {meeting_id} 音频: {meeting.audio_url}")
        audio_data = await file_service.download_file(meeting.audio_url)
        if not audio_data:
            raise ValueError("音频下载失败")
        print(f"音频大小: {len(audio_data)} bytes")

        audio_pcm, segments, sample_rate = await audio_processor.convert_and_segment(audio_data)
        print(f"VAD 切段完成: {len(segments)} 段, sample_rate={sample_rate}")

        # 4. 按 cluster_id 分组
        cluster_segs = {cid: [] for cid in cluster_member_map}
        for i, seg in enumerate(segments):
            if i < len(meeting.transcript):
                trans_seg = meeting.transcript[i]
                if isinstance(trans_seg, dict):
                    cid = trans_seg.get("cluster_id", -1)
                    if cid in cluster_segs:
                        cluster_segs[cid].append(i)

        # 5. 提取每段 embedding
        seg_audios = [
            audio_pcm[int(seg.start_time * sample_rate): int(seg.end_time * sample_rate)]
            for seg in segments
        ]
        seg_embeddings = voiceprint_service.batch_extract_embeddings(seg_audios)
        valid_count = sum(1 for e in seg_embeddings if e is not None and not np.all(np.array(e) == 0))
        print(f"段级 embedding 提取: {valid_count}/{len(seg_embeddings)} 段有效")

        # 6. 每 cluster 求均值
        results = {}
        for cid, member_name in cluster_member_map.items():
            seg_indices = cluster_segs[cid]
            valid_embeddings = [
                seg_embeddings[i] for i in seg_indices
                if i < len(seg_embeddings)
                and seg_embeddings[i] is not None
                and not np.all(np.array(seg_embeddings[i]) == 0)
            ]
            if not valid_embeddings:
                print(f"  cluster_{cid} → {member_name}: 无有效段，跳过")
                continue
            arr = np.array(valid_embeddings, dtype=np.float32)
            center = np.mean(arr, axis=0)
            norm = np.linalg.norm(center)
            if norm > 0:
                center = center / norm
            member_id = name_to_id[member_name]
            results[cid] = {
                "member_id": member_id,
                "member_name": member_name,
                "center": center.tolist(),
                "seg_count": len(valid_embeddings),
                "seg_indices": seg_indices,
            }
            print(
                f"  cluster_{cid} → {member_name} (id={member_id}): "
                f"{len(valid_embeddings)} 段均值得 embedding (192 维)"
            )

        return results


async def apply_recovery(
    session_factory,
    meeting_id: int,
    cluster_results: Dict[int, dict],
    distance_threshold_skip: float = 0.7,
    strategy_mode: str = "strict",
    distance_strict_skip: float = 0.50,
    distance_strict_warn: float = 0.40,
    dry_run: bool = False,
) -> dict:
    """对每位 member 应用反推/合并/覆盖策略

    策略模式 (--strategy):
      - "strict" (默认, 2026-06-27 P0-3 新增):
          cos_dist > 0.50 → BLOCKED (拒绝合并, 不写 DB)
          cos_dist > 0.40 → merge_with_strict_warning (合并但 audit 强标记)
          否则 → merge_weighted_avg (加权平均)
        083 事件防护: cos_dist 杜同贺=0.78 → BLOCKED, 避免污染 embedding
      - "merge":     旧行为, 用加权平均公式合并, 距离 > 0.7 仍合并仅 audit 警告
      - "overwrite": 直接覆盖为 cluster_center (旧行为, sample_count 重置为 M)

    Returns:
        report: 每位 member 的处理结果 (含 blocked 列表)
    """
    assert strategy_mode in ("strict", "merge", "overwrite"), f"strategy 必须是 strict/merge/overwrite，得到 {strategy_mode}"

    async with session_factory() as db:
        report = {
            "applied": [],
            "skipped": [],
            "warning": [],
            "blocked": [],  # 2026-06-27 P0-3: strict 模式被拒绝的合并
        }
        for cid, info in cluster_results.items():
            member_id = info["member_id"]
            member_name = info["member_name"]
            new_center = np.array(info["center"], dtype=np.float32)
            new_seg_count = info["seg_count"]  # cluster 内的有效段数

            # 读 member 当前 voice_embedding
            result = await db.execute(select(Member).where(Member.id == member_id))
            member = result.scalar_one_or_none()
            if not member:
                continue

            # ✅ 2026-06-28 Anchor skip (增量 Cross-Anchor 策略):
            # 已 confirmed 的成员 embedding 永不再修改
            if member.voice_confirmed_at is not None:
                report["applied"].append({
                    "member": member_name,
                    "cluster_id": cid,
                    "cos_dist": None,
                    "strategy": "skipped_confirmed",
                    "weight_old": None,
                    "sample_count_before": member.voice_sample_count or 0,
                    "sample_count_after": member.voice_sample_count or 0,
                    "notes": f"voice_confirmed_at={member.voice_confirmed_at.isoformat()} → anchor immutable, 跳过累积"
                })
                continue

            old_embedding = None
            if member.voice_embedding is not None and len(member.voice_embedding) > 0:
                old_embedding = np.array(member.voice_embedding, dtype=np.float32)
            old_count = member.voice_sample_count or 0

            # 计算 cluster_center 与旧 embedding 的 cosine distance
            if old_embedding is not None and np.any(old_embedding):
                a_n = old_embedding / (np.linalg.norm(old_embedding) + 1e-8)
                b_n = new_center / (np.linalg.norm(new_center) + 1e-8)
                cos_dist = float(1.0 - np.dot(a_n, b_n))
            else:
                cos_dist = 0.0  # 没有旧 embedding，distance 无意义

            # === 决策 ===
            if strategy_mode == "overwrite":
                # 旧行为：直接覆盖
                if old_embedding is None or not np.any(old_embedding):
                    strategy = "set_clean"
                    new_embedding = new_center
                    new_count = max(1, new_seg_count)
                elif cos_dist > distance_threshold_skip:
                    strategy = "skip_too_far"
                    new_embedding = None
                    new_count = None
                else:
                    strategy = "overwrite"
                    new_embedding = new_center
                    new_count = max(1, new_seg_count)
            elif strategy_mode == "strict":
                # 2026-06-27 P0-3: strict 模式 — 距离 > 0.50 拒绝合并
                if old_embedding is None or not np.any(old_embedding):
                    # 旧 embedding 为空, 直接用 cluster_center
                    strategy = "merge_set_initial"
                    new_embedding = new_center
                    new_count = max(1, new_seg_count)
                    weight_old = 0.0
                elif cos_dist > distance_strict_skip:
                    # ❗ 距离过大 → 拒绝合并, 不写 DB, 不更新 member, 不写 history
                    strategy = "BLOCKED_distance_too_far"
                    new_embedding = None
                    new_count = None
                    report["blocked"].append({
                        "member_id": member_id,
                        "member_name": member_name,
                        "cid": cid,
                        "cos_dist_to_old": round(cos_dist, 3),
                        "skip_threshold": distance_strict_skip,
                        "msg": f"距离 {cos_dist:.3f} > {distance_strict_skip} → 拒绝合并, 不污染现有 embedding (P0-3 strict 策略)",
                    })
                    print(
                        f"  ❌ {member_name} (id={member_id}): BLOCKED (cos_dist={cos_dist:.3f} > {distance_strict_skip}), "
                        f"距离过远可能 cluster→member 映射错误, 不修改 voice_embedding"
                    )
                    continue  # 跳过写 DB / audit
                elif cos_dist > distance_strict_warn:
                    # 距离警告: 仍合并但 audit 强标记
                    N = old_count
                    M = new_seg_count
                    total = N + M
                    weight_old = N / total
                    weight_new = M / total
                    new_embedding = weight_old * old_embedding + weight_new * new_center
                    norm = np.linalg.norm(new_embedding)
                    if norm > 0:
                        new_embedding = new_embedding / norm
                    new_count = N + M
                    strategy = "merge_with_strict_warning"
                    report["warning"].append({
                        "member_id": member_id,
                        "member_name": member_name,
                        "cid": cid,
                        "cos_dist_to_old": round(cos_dist, 3),
                        "threshold": distance_strict_warn,
                        "level": "strict",
                        "msg": f"距离 {cos_dist:.3f} 超过 strict 警告阈值 {distance_strict_warn}, 合并但 audit 强标记",
                    })
                else:
                    # 距离正常: 正常 merge
                    N = old_count
                    M = new_seg_count
                    total = N + M
                    weight_old = N / total
                    weight_new = M / total
                    new_embedding = weight_old * old_embedding + weight_new * new_center
                    norm = np.linalg.norm(new_embedding)
                    if norm > 0:
                        new_embedding = new_embedding / norm
                    new_count = N + M
                    strategy = "merge_weighted_avg"
            else:
                # merge 模式：用加权平均公式 (旧行为, 083 前版本)
                # 公式: emb_{N+M} = (N/(N+M)) * emb_N + (M/(N+M)) * emb_avg(M segs)
                if old_embedding is None or not np.any(old_embedding):
                    # 没有旧 embedding → 直接用 cluster_center
                    strategy = "merge_set_initial"
                    new_embedding = new_center
                    new_count = max(1, new_seg_count)
                    weight_old = 0.0
                else:
                    # 加权平均合并
                    N = old_count
                    M = new_seg_count
                    total = N + M
                    weight_old = N / total
                    weight_new = M / total
                    # 合并前对 new_center 再 normalize 一遍 (l2 norm) 保证数学一致
                    # (cluster_center 在 extract 阶段已 l2 normalized)
                    new_embedding = weight_old * old_embedding + weight_new * new_center
                    # 重新 l2 normalize (合并后 norm 可能偏离 1)
                    norm = np.linalg.norm(new_embedding)
                    if norm > 0:
                        new_embedding = new_embedding / norm
                    new_count = N + M

                    # 距离警告（merge 模式不阻断，但 audit 标记）
                    if cos_dist > distance_threshold_skip:
                        strategy = "merge_with_distance_warning"
                        report["warning"].append({
                            "member_id": member_id,
                            "member_name": member_name,
                            "cid": cid,
                            "cos_dist_to_old": round(cos_dist, 3),
                            "threshold": distance_threshold_skip,
                            "msg": f"距离 {cos_dist:.3f} > {distance_threshold_skip} 但用户已确认 cluster→member 映射，仍合并",
                        })
                    else:
                        strategy = "merge_weighted_avg"

            entry = {
                "member_id": member_id,
                "member_name": member_name,
                "cid": cid,
                "seg_count": new_seg_count,
                "old_sample_count": old_count,
                "new_sample_count": new_count,
                "cos_dist_to_old": round(cos_dist, 3),
                "strategy": strategy,
                "weight_old": round(weight_old, 3) if old_embedding is not None else None,
                "weight_new": round(1.0 - weight_old, 3) if old_embedding is not None else None,
            }

            if not dry_run and strategy != "skip_too_far":
                # 备份旧 embedding
                old_backup = list(member.voice_embedding) if member.voice_embedding is not None else None

                # 写 member_voice_history audit
                history = MemberVoiceHistory(
                    member_id=member_id,
                    source="recover_from_meeting",
                    old_embedding=old_backup,
                    new_embedding=new_embedding.tolist(),
                    sample_count_before=old_count,
                    sample_count_after=new_count,
                    weight=weight_old if old_embedding is not None else None,
                    notes=(
                        f"meeting {meeting_id} cluster_{cid} "
                        f"({new_seg_count} new segs, {strategy}, "
                        f"cos_dist={entry['cos_dist_to_old']}, "
                        f"weight_old={entry['weight_old']})"
                    ),
                )
                db.add(history)

                # 更新 member
                member.voice_embedding = new_embedding.tolist()
                member.voice_sample_count = new_count
                member.voice_enrolled_at = datetime.utcnow()

                report["applied"].append(entry)
                if strategy == "merge_weighted_avg":
                    print(
                        f"  ✓ {member_name} (id={member_id}): MERGE 加权平均 "
                        f"sample_count {old_count}+{new_seg_count}={new_count}, "
                        f"weight_old={entry['weight_old']}, cos_dist={entry['cos_dist_to_old']}"
                    )
                elif strategy == "merge_with_distance_warning":
                    print(
                        f"  ⚠️ {member_name} (id={member_id}): MERGE 距离过大仍合并 "
                        f"sample_count {old_count}+{new_seg_count}={new_count}, "
                        f"cos_dist={cos_dist:.3f} > {distance_threshold_skip}"
                    )
                elif strategy == "merge_set_initial":
                    print(
                        f"  ✓ {member_name} (id={member_id}): MERGE 初始赋值 "
                        f"sample_count 0→{new_count} (cluster {new_seg_count} 段)"
                    )
                else:
                    # overwrite / set_clean
                    print(
                        f"  ✓ {member_name} (id={member_id}): {strategy.upper()} "
                        f"sample_count {old_count}→{new_count}, cos_dist={entry['cos_dist_to_old']}"
                    )
            elif strategy == "skip_too_far":
                report["skipped"].append(entry)
                print(
                    f"  ✗ {member_name} (id={member_id}): 跳过（cos_dist={cos_dist:.3f} > {distance_threshold_skip}）"
                )
            else:
                # dry-run
                report.setdefault("applied_dry", []).append(entry)
                print(
                    f"  [DRY-RUN] {member_name} (id={member_id}): {strategy}, "
                    f"sample_count {old_count}→{new_count}"
                )

        if not dry_run:
            await db.commit()
            print(f"\n✅ 已写入 {len(report.get('applied', []))} 条 audit + 更新 voice_embedding")
            if report["warning"]:
                print(f"⚠️  {len(report['warning'])} 条合并时距离超出阈值（已合并，audit 标记警告）")
        return report


async def amain():
    parser = argparse.ArgumentParser(
        description="从会议音频反推/重建 3 人纯净声纹"
    )
    parser.add_argument("--meeting", type=int, required=True, help="会议 ID")
    parser.add_argument(
        "--cluster-to-member",
        type=str,
        required=True,
        help='cluster → member 映射，逗号分隔，如 "cluster_0:王天志,cluster_1:杜同贺,cluster_2:张宏魁"',
    )
    parser.add_argument(
        "--skip-distance",
        type=float,
        default=0.7,
        help="[merge/overwrite 模式] cluster_center 与旧 voice_embedding 距离阈值（> 此值处理方式取决于 --strategy）",
    )
    parser.add_argument(
        "--distance-strict-skip",
        type=float,
        default=0.50,
        help="[strict 模式] cos_dist > 此值 → 拒绝合并, 不修改 voice_embedding (2026-06-27 P0-3)",
    )
    parser.add_argument(
        "--distance-strict-warn",
        type=float,
        default=0.40,
        help="[strict 模式] cos_dist > 此值 → 合并但 audit 强警告 (2026-06-27 P0-3)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=("strict", "merge", "overwrite"),
        default="strict",
        help="处理策略: strict=距离过大拒绝合并（默认, 防 083 类污染）; merge=加权平均合并（旧行为）; overwrite=直接覆盖",
    )
    parser.add_argument("--dry-run", action="store_true", help="只输出报告，不修改 DB")
    args = parser.parse_args()

    # 解析 cluster 映射
    cluster_member_map = {}
    for item in args.cluster_to_member.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            print(f"WARN: 跳过无效项 '{item}'（格式：cluster_N:member_name）")
            continue
        cid_str, name = item.split(":", 1)
        cid_str = cid_str.strip()
        if cid_str.startswith("cluster_"):
            cid_str = cid_str[8:]
        try:
            cid = int(cid_str)
        except ValueError:
            print(f"WARN: 跳过无效 cluster_id '{cid_str}'")
            continue
        cluster_member_map[cid] = name.strip()
    if not cluster_member_map:
        print("错误：--cluster-to-member 解析为空")
        sys.exit(1)

    # 准备 session
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    print(f"=== 从会议 {args.meeting} 音频反推/合并纯净声纹 ===")
    print(f"cluster 映射: {cluster_member_map}")
    print(f"距离阈值: {args.skip_distance}（cluster_center 与旧 voice_embedding 距离）")
    print(f"处理策略: {args.strategy.upper()}")
    print(f"模式: {'DRY-RUN' if args.dry_run else '实际执行'}")
    print()

    # Step 1: 提取 cluster centers
    cluster_results = await extract_cluster_centers(
        session_factory, args.meeting, cluster_member_map
    )
    if not cluster_results:
        print("错误：没有提取到任何 cluster_center")
        await engine.dispose()
        sys.exit(1)

    print()

    # Step 2: 应用反推/合并/覆盖
    report = await apply_recovery(
        session_factory,
        args.meeting,
        cluster_results,
        args.skip_distance,
        args.strategy,
        args.distance_strict_skip,
        args.distance_strict_warn,
        args.dry_run,
    )

    print()
    print("=== 报告 ===")
    print(f"已应用: {len(report.get('applied', []))} 人")
    print(f"跳过: {len(report.get('skipped', []))} 人")
    print(f"警告 (距离过大仍合并): {len(report.get('warning', []))} 人")
    if report.get("blocked"):
        print(f"❌ 拒绝合并 (strict 模式, cos_dist > skip 阈值): {len(report['blocked'])} 人")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(amain())