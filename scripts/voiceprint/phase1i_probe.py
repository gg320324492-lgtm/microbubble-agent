"""Phase 1i 探测: ERes2NetV2 的 **w24s4ep4** 变体在容器里能否落地。

用途: 升级文档列的嵌入候选里, **中文数最好的**是 ERes2NetV2_w24s4ep4
(CN-Celeb 2.31%, 同 192 维 ⇒ 表结构不用改)。Phase 1 已实测**基础版** V2 全面略差
⇒ 需要量「w24s4ep4」是否不同。

本脚本只做: 找到/下载模型 → 直驱 nn.Module 加载 → 跑一条真实音频 → 报耗时与嵌入维度。
⛔ 不写生产表。

用法 (容器内):
    python /tmp/vp/phase1i_probe.py
"""
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CANDIDATES = [
    "iic/speech_eres2netv2_w24s4ep4_sv_zh-cn_16k-common",
    "iic/speech_eres2netv2_sv_zh-cn_16k-common",
]


def log(m):
    print("[phase1i] " + m, flush=True)


def main():
    from modelscope.hub.snapshot_download import snapshot_download
    from modelscope.models.audio.sv.ERes2NetV2 import ERes2NetV2
    import torch
    import torchaudio.compliance.kaldi as Kaldi

    local_dir = None
    for mid in CANDIDATES:
        try:
            log("尝试下载 %s ..." % mid)
            t0 = time.time()
            local_dir = snapshot_download(mid)
            log("  成功: %s (%.0fs)" % (local_dir, time.time() - t0))
            break
        except Exception as e:
            log("  失败: %s" % repr(e)[:160])
    if not local_dir:
        log("全部候选都下载失败")
        return

    import json as _json
    with open(os.path.join(local_dir, "configuration.json"), encoding="utf-8") as fh:
        cfg = _json.load(fh)
    mc = cfg["model"]["model_config"]
    log("model_config: %s" % mc)
    ckpt = os.path.join(local_dir, cfg["model"]["pretrained_model"])
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    net = ERes2NetV2(embed_dim=mc["embed_dim"], baseWidth=mc["baseWidth"],
                      scale=mc["scale"], expansion=mc["expansion"])
    sd = torch.load(ckpt, map_location="cpu")
    net.load_state_dict(sd, strict=True)
    net.to(dev).eval()
    log("加载 OK: %.1fM 参数, embed_dim=%s, baseWidth=%s, scale=%s, expansion=%s" % (
        sum(p.numel() for p in net.parameters()) / 1e6, mc["embed_dim"],
        mc["baseWidth"], mc["scale"], mc["expansion"]))

    # 真实音频 3s
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "300", "-t", "3", "-i",
         "/tmp/vp/src_recordings__255__merged.m4a", "-ac", "1", "-ar", "16000",
         "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).copy()
    a = torch.from_numpy(x).unsqueeze(0)
    feat = Kaldi.fbank(a, num_mel_bins=80)
    feat = feat - feat.mean(dim=0, keepdim=True)
    feat = feat.unsqueeze(0)
    with torch.no_grad():
        t0 = time.time()
        out = net(feat.to(dev))
        torch.cuda.synchronize() if dev == "cuda" else None
        dt = time.time() - t0
    emb = out.squeeze().float().cpu().numpy()
    n = float(np.linalg.norm(emb))
    log("真实 3s 段: 输出 %s, |e|=%.4f, 耗时 %.3fs" % (emb.shape, n, dt))
    log("yesOrno_thr=%s" % cfg["model"].get("yesOrno_thr"))


if __name__ == "__main__":
    main()
