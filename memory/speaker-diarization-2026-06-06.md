---
name: speaker-diarization-2026-06-06
description: 2026.06.06 声纹识别系统重大优化
metadata:
  type: project
---

# 声纹识别系统优化 (2026-06-06)

1. VAD 精细化: 合并 0.3→0.1s, speech 300→200ms, silence 200→100ms
2. 语义断句: 问答/转折/回应词检测, 本地规则, 零延迟
3. KMeans 强制分裂: std>0.15 硬分 2 簇
4. 同名聚类检测: embedding 识别后检同名, 保留差异
5. 名字校对: 谐音+编辑距离+精确匹配
6. MATCH_THRESHOLD: 0.55→0.7

**How to apply:** 参考 post_meeting_tasks.py 阶段 2 完整流程
