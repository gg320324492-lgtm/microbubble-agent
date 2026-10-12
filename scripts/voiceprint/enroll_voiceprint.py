r"""
从会议录音里提取某段发言，给成员录入声纹

配套 `fix_meeting_speakers.py`（用已有声纹订正误识别）。两者分工:
  本脚本 = **给还没有声纹的人建档**（他是"被误认"的根源之一）
  那个脚本 = **拿已有声纹去纠正已被误标的人**

2026-10-13 会议 256 的两个真实案例:
  赵航佳 (id=2) —— 论文汇报 209 段被整段标成「蒋芦笛」
  耿嘉栋 (id=6) —— 臭氧发生器主讲 699 段被整段标成「王天志」
  ⚠️ **"没录声纹"不是完整解释**: 实测赵航佳的音频与蒋芦笛的声纹 cosine 距离
  **0.59 < MATCH_THRESHOLD 0.7** ⇒ 阈值内, 会被**主动判成蒋芦笛**,
  而不是走「发言人?」兜底。所以补录是必要的, 但**不充分**。

⚠️ 判据纪律（都踩过，别改）:
  1. **默认 dry-run**, 只有 `--apply` 才写 members 表。
  2. **只用某个 speaker 名下的段落**（`--from-speaker`）—— 不要全量, 否则会把
     多个人的声音混进一个 embedding。
  3. **录完必须用未参与录入的区间独立验证**（`--verify-range`）——
     拿参与录入的音频自证是循环论证（类 20.220）。本脚本会把
     "本区间是否落在录入范围内"一并打印, 避免无意自证。
  4. `enroll_member` 支持多次录入取加权平均, **录错可以重录**。
  5. ⚠️⚠️ **长音频必须分块，且必须自己判全零**（2026-10-13 实测，两个坑叠在一起）：
     - `_extract_via_model` 把**整段音频一次性**送进 `model.forward()`, **不分块不截断**。
       实测 **1800 秒音频 → CUDA OOM，需要 13.73 GiB 显存**（31.8 GiB 的卡直接爆），
       连 dry-run 都会挂。而 737 秒能过 —— 所以这不是"偶发"，是**按音频长度线性增长**，
       长到某个点必炸。
     - 它失败时**只 `logger.error` 然后返回全零向量**，注释写明"调用方有
       `np.all(embedding==0)` 检查"。`enroll_member` / `identify_speaker` 都有，
       **但脚本调 `extract_embedding` 时必须自己加** —— 不加就会拿着一串全零
       embedding 去比距离，得到 10 个整齐的 `dist=1.0000`，**看起来像"跟谁都不像"
       的正常结论，实际是模型压根没跑成**（类 20.220：失败被伪装成了正常数据）。
       本次就是这样被骗了一次。
     - ⇒ 故本脚本：`--apply` 时**逐块**调用 `enroll_member`（每块 ≤30 秒，走标准
       路径 + `sample_count` 语义正确 + 单块失败不拖累整体）；dry-run / verify 走
       `extract_long_embedding()`（分块 + 按块长加权平均 + 逐块丢弃全零）。
       **任何分支拿到全零都立即中止，不许继续算距离。**

⚠️ 必须在 **app 容器内**跑（要 modelscope 声纹模型 + MinIO 音频）:
    MSYS_NO_PATHCONV=1 docker cp scripts/voiceprint/enroll_voiceprint.py \
        microbubble-agent-app-1:/tmp/
    MSYS_NO_PATHCONV=1 docker exec microbubble-agent-app-1 \
        python /tmp/enroll_voiceprint.py <args>

⚠️ 若要设 anchor（voice_confirmed_at，语义是"embedding 永不再修改"），
   **第一次录不要设** —— 录完先独立验证、多录几次不同片段，再由人决定。

Usage:
    # 1) dry-run：看会录成什么样（不写库）
    python enroll_voiceprint.py --meeting 256 --member 6 --from-speaker 王天志 --range 1740-3720

    # 2) 确认后录入
    python enroll_voiceprint.py --meeting 256 --member 6 --from-speaker 王天志 \
        --range 1740-3720 --apply

    # 3) 独立验证（用未参与录入的区间）
    python enroll_voiceprint.py --meeting 256 --member 6 \
        --verify-range 4300-4700
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys

sys.path.insert(0, "/app")

MERGE_GAP = 2.0
MIN_SEG_SEC = 1.0


def to_py(v):
    return v if isinstance(v, (list, dict)) else (json.loads(v) if v else v)


def merge_intervals(spans):
    out = []
    for a, b in sorted(spans):
        if out and a - out[-1][1] <= MERGE_GAP:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def cut_audio(m4a, intervals, workdir):
    import numpy as np
    from scipy.io import wavfile

    os.makedirs(workdir, exist_ok=True)
    chunks, durs = [], []
    for i, (a, b) in enumerate(intervals):
        seg = f"{workdir}/s{i:03d}.wav"
        r = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", m4a,
             "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", seg],
            capture_output=True, text=True)
        if r.returncode != 0:
            durs.append(0.0)
            continue
        sr, data = wavfile.read(seg)
        if data.ndim > 1:
            data = data.mean(axis=1)
        chunks.append(data.astype(np.float32) / 32768.0)
        durs.append(len(data) / sr)
    return (np.concatenate(chunks) if chunks else None), durs


def hhmmss(x):
    return f"{int(x)//60:>3}分{int(x)%60:>02d}秒"


# 每次送进模型的秒数上限。ERes2Net 的特征提取随音频线性增长，实测
# **1800 秒要 13.73 GiB 显存** ⇒ 31.8 GiB 的卡直接 OOM。30 秒约 230 MiB，安全。
CHUNK_SEC = 30
MAX_CHUNKS = 60          # 均匀采样上限，避免几十秒音频跑几分钟


def extract_long_embedding(vps, audio, sr=16000):
    """长音频分块提取 + 按块长加权平均。

    ⚠️ 必须分块 —— `voiceprint_service._extract_via_model` 把**整段音频一次性**
    送进 model.forward()，不分块也不截断（实测 1800 秒 → CUDA OOM 13.73 GiB）。

    ⚠️⚠️ **并且必须自己判全零** —— 该方法在 OOM/异常时只 `logger.error` 然后
    **返回全零向量**，其注释写明"调用方有 np.all(embedding==0) 检查"。
    `enroll_member` / `identify_speaker` 都做了，**调用它的脚本也得做** ——
    2026-10-13 实测踩过：不检查就会拿着一串全零 embedding 去比距离，
    得到 10 个整齐的 `dist=1.0000`，看起来像"跟谁都不像"的正常结论，
    实际是模型压根没跑成（类 20.220：失败被伪装成了正常数据）。

    Returns: (embedding|None, 实际用了几块, 说明)
    """
    import numpy as np

    n = len(audio)
    size = CHUNK_SEC * sr
    if n <= size:
        starts = [0]
    else:
        step = max(size // 2, 1)          # 50% 重叠，相邻块不至于割裂音节
        starts = list(range(0, n - size + 1, step))
        if len(starts) > MAX_CHUNKS:     # 均匀降采样到 MAX_CHUNKS
            picks = [round(i * (len(starts) - 1) / (MAX_CHUNKS - 1))
                     for i in range(MAX_CHUNKS)]
            starts = [starts[i] for i in sorted(set(picks))]

    embs, weights = [], []
    for st in starts:
        seg = audio[st:st + size]
        if len(seg) < sr * 3:             # 少于 3 秒噪声大，跳过
            continue
        try:
            e = vps.extract_embedding(seg)
        except Exception as exc:          # 块级失败也不能让整批变成全零
            print(f"      [WARN] 块 @{st/sr:.0f}s 提取失败: {exc}")
            continue
        if np.allclose(e, 0):             # ← 该方法失败时返回的全零向量
            print(f"      [WARN] 块 @{st/sr:.0f}s 返回全零 embedding，丢弃")
            continue
        embs.append(e)
        weights.append(len(seg))

    if not embs:
        return None, 0, "所有块都失败（全零或异常）—— **模型没跑成，不要用这个结果**"
    total = float(sum(weights))
    out = sum(e * (w / total) for e, w in zip(embs, weights))
    nrm = float(np.linalg.norm(out))
    if nrm < 1e-6:
        return None, 0, "加权平均后近零"
    return out / nrm, len(embs), f"{len(embs)} 块 × ≤{CHUNK_SEC}s（覆盖 {n/sr:.0f}s 音频）"


async def run(args):
    import numpy as np
    from sqlalchemy import text
    from app.core.database import async_session
    from app.models.member import Member
    from app.services.file_service import file_service
    from app.services.voiceprint_service import voiceprint_service

    async with async_session() as db:
        r = await db.execute(text(
            "SELECT transcript, audio_url FROM meetings WHERE id=:i"), {"i": args.meeting})
        segs, audio_url = r.one()
        segs, audio_url = to_py(segs) or [], audio_url
        if not audio_url:
            raise SystemExit(f"会议 {args.meeting} 没有 audio_url")

        # ---------- 验证模式 ----------
        if args.verify_range:
            a, b = [float(x) for x in args.verify_range.split("-")]
            r2 = await db.execute(text(
                "SELECT id, name, voice_embedding FROM members "
                "WHERE voice_embedding IS NOT NULL AND is_active=true "
                "AND voice_sample_count>0"))
            voices = [(mid, nm, np.array(to_py(e), dtype="float32"))
                      for mid, nm, e in r2.all()]
            target = next((v for v in voices if v[0] == args.member), None)
            if target is None:
                raise SystemExit(f"成员 id={args.member} 还没有声纹，先 --apply 录入")

            m4a = f"/tmp/ev/m{args.meeting}.m4a"
            os.makedirs("/tmp/ev", exist_ok=True)
            if not os.path.exists(m4a):
                with open(m4a, "wb") as f:
                    f.write(file_service.download_file_sync(audio_url))
            spans = [(float(s["start"]), float(s["end"])) for s in segs
                     if s.get("speaker") == args.from_speaker and a <= float(s["start"]) <= b]
            if not spans:
                print(f"  ⚠️ 该范围内没有「{args.from_speaker}」的段落，换 --from-speaker")
                return
            audio, durs = cut_audio(m4a, merge_intervals(spans), "/tmp/ev/v")
            print(f"  验证音频 {sum(durs):.1f}s（{hhmmss(a)}-{hhmmss(b)}）")
            emb, nchunk, note = extract_long_embedding(voiceprint_service, audio)
            if emb is None:
                raise SystemExit(f"❌ 提取失败: {note}")
            print(f"  分块提取: {note}")
            rs = sorted((1.0 - float(np.dot(emb, v) /
                                      (np.linalg.norm(emb) * np.linalg.norm(v) + 1e-8)), nm, mid)
                        for mid, nm, v in voices)
            print("  距离排名:")
            for i, (d, nm, mid) in enumerate(rs, 1):
                mark = "  ← 目标" if mid == args.member else ""
                print(f"    #{i:<2} {nm:8}(id={mid:<3}) dist={d:.4f}{mark}")
            print(f"  → 最像: {rs[0][1]} (dist={rs[0][0]:.4f})"
                  f"  判定: {'✅ 正确' if rs[0][2] == args.member else '❌ 不符预期'}")
            return

        # ---------- 正常模式 ----------
        m = (await db.execute(text(
            "SELECT id, name, voice_embedding, voice_sample_count FROM members "
            "WHERE id=:i"), {"i": args.member})).one()
        if not m:
            raise SystemExit(f"member_id={args.member} 不存在")
        print(f"  目标: id={m[0]} {m[1]} | 现有 embedding={m[2] is not None} "
              f"| sample_count={m[3] or 0}")

        lo, hi = (0.0, 1e9)
        if args.range:
            lo, hi = [float(x) for x in args.range.split("-")]
        spans = [(float(s["start"]), float(s["end"])) for s in segs
                 if s.get("speaker") == args.from_speaker and lo <= float(s["start"]) <= hi]
        ivs = merge_intervals(spans)
        print(f"  「{args.from_speaker}」{len(spans)} 段 -> {len(ivs)} 区间 / "
              f"{sum(b-a for a,b in ivs):.1f}s"
              + (f"（限定 {args.range}s）" if args.range else ""))
        if not ivs:
            raise SystemExit("没有符合条件的区间")
        print(f"  覆盖 {hhmmss(ivs[0][0])} - {hhmmss(ivs[-1][1])}")

        m4a = f"/tmp/ev/m{args.meeting}.m4a"
        os.makedirs("/tmp/ev", exist_ok=True)
        if not os.path.exists(m4a):
            print("  下载会议录音 ...")
            with open(m4a, "wb") as f:
                f.write(file_service.download_file_sync(audio_url))
        audio, durs = cut_audio(m4a, ivs, "/tmp/ev/e")
        good = sum(d for d in durs if d >= MIN_SEG_SEC)
        print(f"  提取 {sum(durs):.1f}s（{good:.1f}s 在 {MIN_SEG_SEC}s 阈值以上）")
        if not args.apply:
            emb, nchunk, note = extract_long_embedding(voiceprint_service, audio)
            if emb is None:
                raise SystemExit(f"❌ 提取失败: {note}")
            print(f"  分块提取: {note} | L2={float(np.linalg.norm(emb)):.4f}")
            r2 = await db.execute(text(
                "SELECT id, name, voice_embedding FROM members "
                "WHERE voice_embedding IS NOT NULL AND is_active=true "
                "AND voice_sample_count>0"))
            voices = [(mid, nm, np.array(to_py(e), dtype="float32"))
                      for mid, nm, e in r2.all()]
            print(f"  DRY-RUN（未写库）; 与现有 {len(voices)} 个声纹的距离:")
            for d, nm, mid in sorted((1.0 - float(np.dot(emb, v) /
                                                 (np.linalg.norm(emb) * np.linalg.norm(v) + 1e-8)),
                                     nm, mid) for mid, nm, v in voices):
                print(f"    {nm:8}(id={mid:<3}) dist={d:.4f}")
            print("  ⚠️ 验证请另取**未参与录入**的区间跑 --verify-range，不要用这里的音频自证")
            return

        # ⚠️ 必须**逐块**调用 enroll_member —— 它内部同样调不分块的 extract_embedding，
        #    整段喂进去会 OOM。每块 ≤CHUNK_SEC 秒 ⇒ 安全；
        #    且每块算"一次采样"，与 voice_sample_count 的语义一致；
        #    单块失败只丢一块，不影响整体。
        print(f"  分块录入（每块 ≤{CHUNK_SEC}s，逐块调 enroll_member）...")
        size = CHUNK_SEC * 16000
        n = len(audio)
        starts = ([0] if n <= size
                  else list(range(0, n - size + 1, size // 2)))
        if len(starts) > MAX_CHUNKS:
            picks = [round(i * (len(starts) - 1) / (MAX_CHUNKS - 1))
                     for i in range(MAX_CHUNKS)]
            starts = [starts[i] for i in sorted(set(picks))]
        ok_cnt = fail_cnt = 0
        for st in starts:
            seg = audio[st:st + size]
            if len(seg) < 16000 * 3:
                continue
            try:
                if await voiceprint_service.enroll_member(db, args.member, seg):
                    ok_cnt += 1
                else:
                    fail_cnt += 1
            except Exception as exc:
                fail_cnt += 1
                print(f"      [WARN] 块 @{st/16000:.0f}s 失败: {exc}")
                await db.rollback()
        await db.commit()
        after = (await db.execute(text(
            "SELECT voice_sample_count, voice_embedding FROM members WHERE id=:i"),
            {"i": args.member})).one()
        if not after[1]:
            raise SystemExit("❌ 录入后 embedding 仍为空 —— 已中止")
        import numpy as _np
        if _np.allclose(to_py(after[1]), 0):
            raise SystemExit("❌ 录入的是**全零 embedding**，已中止（请查容器日志）")
        print(f"  ✅ 成功 {ok_cnt} 块 / 失败 {fail_cnt} 块 | "
              f"sample_count={after[0]} | 维度={len(to_py(after[1]))} | "
              f"L2={float(_np.linalg.norm(to_py(after[1]))):.4f}")
        print("  ⚠️ 下一步：用未参与录入的区间跑 --verify-range 做独立验证")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--meeting", type=int, required=True)
    p.add_argument("--member", type=int, required=True, help="目标成员 id")
    p.add_argument("--from-speaker", default="王天志", help="取哪个 speaker 名下的音频")
    p.add_argument("--range", help="限定 START-END 秒")
    p.add_argument("--verify-range", help="验证区间 START-END（必须未参与录入）")
    p.add_argument("--apply", action="store_true", help="写库（默认 dry-run）")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
