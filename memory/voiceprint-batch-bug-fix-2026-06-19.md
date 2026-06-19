# 声纹 batch bug 修复 (2026-06-19) — 推到主路径

## 根因

`modelscope ERes2Net_aug.py:__extract_feature` 强制 `unsqueeze(0)` 折叠 batch。

```python
# modelscope/models/audio/sv/ERes2Net_aug.py:__extract_feature
def __extract_feature(self, audio):
    feature = Kaldi.fbank(audio, num_mel_bins=self.feature_dim)
    feature = feature - feature.mean(dim=0, keepdim=True)
    feature = feature.unsqueeze(0)  # ← 强制 batch=1
    return feature
```

输入 `(4, 32000)` → feature `(1, ?, ?)` → embedding `(1, 192)` — **只处理第 1 段**。

实测：
```python
batch2d = torch.randn(4, 32000)
with torch.no_grad():
    out2d = model(batch2d)
print(out2d.shape)  # torch.Size([1, 192])  ← bug
```

## 影响范围

`app/services/voiceprint_service.py:batch_extract_embeddings` 旧版用 `torch.from_numpy(padded).float().to(device)` 把 32 段一次性塞给模型 → 实际只处理第 1 段 → 89/2830 段有效（其余 31 段返回零向量）。

**所有通过 `post_meeting_tasks.py` 自动处理的会议都受影响**（hangup 后 Celery 跑全流程）。**97% 沉默失败**——程序不报错，但绝大多数段识别为空。

## 修复

[`app/services/voiceprint_service.py:batch_extract_embeddings`](../../app/services/voiceprint_service.py) 改用 `ThreadPoolExecutor(8)` + `threading.Lock` 并行单条调用：

```python
def batch_extract_embeddings(self, audio_segments, batch_size=32):
    # ThreadPoolExecutor + Lock 修复 ERes2Net batch bug
    if not hasattr(self, '_batch_extract_lock'):
        self._batch_extract_lock = threading.Lock()

    def _extract_one(audio):
        with self._batch_extract_lock:
            return self._extract_via_model(audio)

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_extract_one, a): i for i, a in enumerate(valid_audio)}
        for fut in futures:
            results[valid_indices[futures[fut]]] = fut.result()
    return results
```

## 验证

| 测试 | 旧版 | 新版 |
|------|------|------|
| 50 段真实音频 | 89/2830 ≈ 3% | 50/50 = 100% |
| 100 段真实音频 | (同样 3%) | 100/100 = 100% |
| 2830 段会议 #120 | 89 段有效 | 2830 段有效 |

## 为什么 push 到主路径

用户的反馈："不仅是漏掉发言人的情况，就算不漏掉发言人的正常识别，识别效果也要像本次一样或者更好"。

旧 `batch_extract_embeddings` 即使没漏识别，所有段都只用 batch 第 1 段那一份 embedding（重复）。修复后每段都得到真实 embedding，聚类质量自然提升。

**影响**：所有未来会议通过 `post_meeting_tasks.py` 自动跑全流程时，**无需手动 re-process 即可获得 100% 段有效 + 正确聚类**。

## 部署必做（CLAUDE.md 752 行铁律）

```bash
# volume 挂载只换文件不换 Python 模块缓存，必须重启
docker restart microbubble-agent-app-1 microbubble-agent-celery-worker-1

# 验证
docker exec microbubble-agent-app-1 python -c "
from app.services.voiceprint_service import voiceprint_service
import numpy as np, wave, random
with wave.open('/tmp/meeting_120_16k.wav', 'rb') as wf:
    pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
random.seed(42)
chunks = [pcm[i:i+48000] for i in random.sample(range(0, len(pcm)-48000), 50)]
embs = voiceprint_service.batch_extract_embeddings(chunks, batch_size=32)
print(f'{sum(1 for e in embs if e is not None and not np.all(e == 0))}/50 valid')
# 期望: 50/50 valid
"
```

## 7 条铁律

1. **上游库的 bug 必须 app 层绕开** — modelscope 不会修 `__extract_feature` 强制 batch=1，app 层必须用并行单条
2. **所有会议识别质量改进要 push 到主路径** — 不能只 re-process 老会议，新会议必须自动获得改进
3. **ThreadPoolExecutor + Lock 组合** — 并行提速 + 保护 `pipeline.model` 跨线程访问
4. **声纹 embedding 验证不能只看长度** — 89 个非零 vs 89 个真正 embedding 是两回事
5. **沉默失败比明显错误更可怕** — 旧版不报错但 97% 失败，要用 verify pattern 主动检测
6. **重启后端是 volume 挂载的硬要求** — 代码改完不 restart = 永远在跑旧逻辑
7. **100% 段有效是默认值** — 不接受"50% 有效就够了"的态度，识别质量要么 100% 要么找出问题
