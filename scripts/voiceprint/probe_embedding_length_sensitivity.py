"""探针: 量 ERes2Net(现役声纹模型) 对「音频长度」的敏感度与整段嵌入的算力代价。

为什么需要它
------------
Phase 0 (docs/voiceprint-enrollment-rebuild-2026-10-31.md) 的结论取决于一个前提:
**「长 enrollment 质心」与「短段查询」是不是同一个表征空间?**
本探针直接量它:

  ① 长度敏感性: 同一段 10s 音频后面接 0/5/20/60s 静音 ⇒ 嵌入还剩多少相似度
     ⇒ 若掉得厉害, 长段质心与短段查询之间存在**系统性长度偏置**
  ② 整段嵌入的算力: 10/30/60/120/300/600s 各要多久
     ⇒ 决定「长段能不能整段嵌入」在工程上是否可行
  ③ 嵌入吞吐: 现役 batch_extract_embeddings 的每段成本

实测结论 (2026-10-31, RTX 5090, 容器内):
  - 2.3s 段: 0.052 s/段
  - 整段: 10s 0.06 / 30s 0.11 / 60s 0.18 / 120s 0.32 / 300s 0.87 / **600s 231.9s**
    ⇒ 300s → 600s 是 **267 倍**的非线性爆炸 ⇒ 长于 300s 的整段嵌入工程上不可用
  - 长度敏感性 (10s + 静音): +5s ⇒ 余弦 0.766 / +20s ⇒ 0.629 / +60s ⇒ **0.507**
    ⇒ 嵌入**强烈依赖音频总长度**, 不只是说话人

⛔ 不写任何生产数据。纯只读探针。

用法 (容器内):
    python /tmp/vp/probe_embedding_length_sensitivity.py
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, "/app")

SR = 16000


def main():
    from app.services.voiceprint_service import VoiceprintService

    svc = VoiceprintService()
    svc._load_pipeline()
    if svc._pipeline is None:
        print("PROBE: 模型加载失败")
        return
    import torch

    model = svc._pipeline.model
    dev = next(model.parameters()).device
    print("PROBE: device =", dev)

    # (1) 短段耗时 (模拟 2.3s 生产段)
    rng = np.random.default_rng(0)
    short = (0.1 * rng.standard_normal(int(2.3 * SR))).astype(np.float32)
    t0 = time.time()
    e = svc.extract_embedding(short)
    t1 = time.time()
    print("PROBE: 单条 2.3s 嵌入耗时 %.3fs, |e|=%.4f" % (t1 - t0, float(np.linalg.norm(e))))

    # (2) 批量 20 条短段耗时 (走生产 batch_extract_embeddings)
    segs = [(0.1 * rng.standard_normal(int(2.3 * SR))).astype(np.float32) for _ in range(20)]
    t0 = time.time()
    es = svc.batch_extract_embeddings(segs)
    t1 = time.time()
    print("PROBE: batch_extract_embeddings 20 条耗时 %.2fs (%.3fs/条)" % (t1 - t0, (t1 - t0) / 20))

    # (3) 长音频: 用真实语音的话噪声没意义, 但能测"能不能跑"与"耗时长短"
    for secs in (10, 30, 60, 120, 300, 600):
        a = (0.1 * rng.standard_normal(secs * SR)).astype(np.float32)
        torch.cuda.synchronize() if dev.type == "cuda" else None
        t0 = time.time()
        try:
            e = svc.extract_embedding(a)
            torch.cuda.synchronize() if dev.type == "cuda" else None
            t1 = time.time()
            n = float(np.linalg.norm(e))
            print("PROBE: %4ds 长音频 -> 耗时 %.2fs, |e|=%.4f, 首维=%.5f" % (secs, t1 - t0, n, float(e[0])))
        except Exception as ex:
            print("PROBE: %4ds 长音频 -> 失败: %s" % (secs, repr(ex)[:200]))
            break

    # (4) 不同长度音频的嵌入是否"长度相关" (若长度主导, 短段质心必然不可比)
    print("PROBE: 同一段音频 + 尾部静音 的嵌入相似度 (检验长度敏感性)")
    base = (0.1 * rng.standard_normal(10 * SR)).astype(np.float32)
    e_base = svc.extract_embedding(base)
    for pad in (0, 5, 20, 60):
        a = np.concatenate([base, np.zeros(int(pad * SR), dtype=np.float32)])
        e = svc.extract_embedding(a)
        print("PROBE:   +%3ds 静音 -> 与基准余弦 %.5f" % (pad, float(np.dot(e_base, e) / (np.linalg.norm(e) * np.linalg.norm(e)))))


if __name__ == "__main__":
    main()
