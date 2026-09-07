# -*- coding: utf-8 -*-
"""GPU 会议处理 worker 包 — 会议生命周期 = 显存生命周期

架构（详见 docs/vibevoice-evaluation-2026-09-07.md §6.1）:
  平时: worker 进程不存在 → 显存占用 0 GB
  会议: manager 拉起独立子进程 meeting_worker → 载入 VibeVoice-ASR-7B (~16GB)
        → 转写(Who/When/What) + 声纹名字映射 → 写结果 JSON → 进程退出
  关键依据: 项目实测 in-process 卸载后残留 4.3GB 显存不可释放
  (docs/asr-benchmark-2026-06-30.md §2.1)，进程退出是唯一能保证显存归零的方式。
"""
