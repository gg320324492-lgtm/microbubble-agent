"""ERes2NetV2 嵌入器 —— 直驱 nn.Module, **逐条**路径。

为什么这么写
------------
1. **不能用 modelscope 的 pipeline** —— modelscope 1.40.2 没给 `eres2netv2-sv` 注册
   preprocessor ⇒ pipeline 路径必然失败（与现役 ERes2Net 同病）。
   ⇒ 直接实例化 `ERes2NetV2` 这个 nn.Module 并 `load_state_dict(strict=True)`。

2. ⛔ **不做真批量**（这是本文件最重要的一条）
   modelscope 的 `TSTP` 池化**没有 mask**：
       pooling_mean = x.mean(dim=-1)
       pooling_std  = torch.sqrt(torch.var(x, dim=-1) + 1e-8)
   ⇒ 批量必须把不同长度的 fbank 特征 **pad 到同一长度** ⇒ 补零帧会进 conv 栈、
   再进 stats pooling 的均值与方差 ⇒ **嵌入被静默改掉**（实测最大差 3.10e+01）。
   3D-Speaker 的 `speakerlab` 用 attention mask 解决，但 `speakerlab` **不在 pip 包里**
   （它是 GitHub 仓）⇒ 要在本仓实现 mask 化 TSTP 是一笔有风险的改造。
   ⇒ **本项目规模下逐条就够快**（现役 ERes2Net 实测 0.052 s/段 ⇒ 1.1 万段约 10 分钟），
   **逐条路径零风险且与各模型自己的官方 `__extract_feature` 逐行一致**。
   `extract_padded_batch()` 仅供**量化 padding 危害**的对照实验用，不做生产路径。

3. **逐条路径必须逐行复刻官方 `__extract_feature`**：
       feature = Kaldi.fbank(audio, num_mel_bins=80)
       feature = feature - feature.mean(dim=0, keepdim=True)   # ← 逐条减自己的均值
       feature = feature.unsqueeze(0)                          # (1, frames, 80)
       emb = model.embedding_model(feature.to(device))
   ⚠️ 漏掉「逐条减自己的均值」或误用 batch 的均值 ⇒ 嵌入不可比（静默）。

用法 (容器内):
    from eres2netv2_embedder import ERes2NetV2Embedder
    e = ERes2NetV2Embedder()
    v = e.extract(pcm_16k_float32)
"""
import glob
import json
import os

import numpy as np
import torch
import torchaudio.compliance.kaldi as Kaldi

EMBEDDING_DIM = 192
SR = 16000
MODEL_ID = "iic/speech_eres2netv2_sv_zh-cn_16k-common"
# modelscope 两种缓存布局都要认 (老的 models/<id>/ 与新的 models/<owner>--<name>/)
CACHE_ROOTS = [
    os.environ.get("MODELSCOPE_CACHE", "/root/.cache/modelscope") + "/models",
]


def _find_model_dir():
    name = MODEL_ID.replace("/", "--")
    for root in CACHE_ROOTS:
        for pat in (os.path.join(root, name, "snapshots", "*"),
                    os.path.join(root, MODEL_ID.replace("/", os.sep))):
            hits = sorted(glob.glob(pat))
            hits = [h for h in hits if os.path.isfile(os.path.join(h, "configuration.json"))]
            if hits:
                return hits[-1]
    raise RuntimeError("找不到 %s 的本地缓存 (查过 %s)" % (MODEL_ID, CACHE_ROOTS))


class ERes2NetV2Embedder:
    """ERes2NetV2 逐条嵌入器 (192 维, L2 归一化)。"""

    def __init__(self, device=None):
        from modelscope.models.audio.sv.ERes2NetV2 import ERes2NetV2

        self.model_dir = _find_model_dir()
        with open(os.path.join(self.model_dir, "configuration.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
        mc = cfg["model"]["model_config"]
        self.ckpt = os.path.join(self.model_dir, cfg["model"]["pretrained_model"])
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = ERes2NetV2(
            embed_dim=mc["embed_dim"], baseWidth=mc["baseWidth"],
            scale=mc["scale"], expansion=mc["expansion"])
        sd = torch.load(self.ckpt, map_location="cpu")
        missing, unexpected = self.model.load_state_dict(sd, strict=True)
        self.model.to(self.device).eval()
        self.n_params = sum(p.numel() for p in self.model.parameters())
        self.yesorno_thr = cfg["model"].get("yesOrno_thr")

    # ---------- 官方参考路径 (逐条) ----------
    def _features(self, audio: np.ndarray) -> torch.Tensor:
        """复刻 modelscope 的 __extract_feature: fbank → 逐条减均值 → (1, frames, 80)"""
        a = torch.from_numpy(np.asarray(audio, dtype=np.float32))
        if a.dim() == 1:
            a = a.unsqueeze(0)
        feat = Kaldi.fbank(a, num_mel_bins=80)
        feat = feat - feat.mean(dim=0, keepdim=True)
        return feat.unsqueeze(0)

    def extract(self, audio: np.ndarray) -> np.ndarray:
        """单条嵌入 (L2 归一化); 失败返回全零向量 (与生产服务语义一致)。"""
        try:
            if audio is None or len(audio) < SR // 10:
                return np.zeros(EMBEDDING_DIM, dtype=np.float32)
            with torch.no_grad():
                out = self.model(self._features(audio).to(self.device))
            if isinstance(out, tuple):
                out = out[0]
            emb = out.squeeze().float().cpu().numpy()
            if len(emb) < EMBEDDING_DIM:
                pad = np.zeros(EMBEDDING_DIM, dtype=np.float32)
                pad[:len(emb)] = emb
                emb = pad
            emb = emb[:EMBEDDING_DIM]
            n = float(np.linalg.norm(emb))
            if n < 1e-6:
                return emb
            return emb / n
        except Exception:
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

    def extract_many(self, audios):
        """逐条提取 (无并行; 模型前向在 GPU 上, 逐条避免 pad 污染)。"""
        return [self.extract(a) for a in audios]

    # ---------- 仅用于「量化 padding 危害」的对照实验 ----------
    def extract_padded_batch(self, audios):
        """**朴素批量**: 逐条算 fbank → 特征 pad 到同一长度 → 一次喂模型 (无 mask)。

        ⛔ **这不是生产路径** —— 它存在的唯一目的是量化「padding 会静默改掉嵌入」这件事。
        """
        feats = [self._features(a)[0] for a in audios]        # (frames_i, 80)
        lens = [f.shape[0] for f in feats]
        T = max(lens)
        batch = torch.zeros(len(feats), T, 80)
        for i, f in enumerate(feats):
            batch[i, :f.shape[0], :] = f
        with torch.no_grad():
            out = self.model(batch.to(self.device))
        out = out.squeeze(1).float().cpu().numpy()
        res = []
        for v in out:
            n = float(np.linalg.norm(v))
            res.append(v / n if n > 1e-6 else v)
        return res, lens
