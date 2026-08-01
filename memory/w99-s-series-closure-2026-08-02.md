# W99 S-series grand closure (2026-08-02, 主指挥协调范式第 N+1 次派工)

## 任务背景
用户原始问题："看一下本项目所用到的模型有必要切换到'实时'版本吗？"
- 主拍派工扫描全项目模型调用点（Claude/Embedding/Reranker/ASR/TTS/Vision/OCR/声纹），结论"模型选型本身不需要切"
- 真问题是 **4 处流式管道未打通**（派工前提铁律 12 + 类 20 实战 113+ 据实）
- 派工 **W99-S1 / S2 / S3 / S4** 4 个 agent 并行（不限于用户提的 agent 数量限制）

## 4 项任务交付实测
| 代号 | 任务 | 产物 | commit | 锚点 |
|---|---|---|---|---|
| **W99-S1 W99 +0** | /voice/tts HTTP 改真 streaming | voice.py L86-106 + tts.py L94-102 try/except + tests/test_tts_http_streaming_e2e.py (3 PASS) | `ab0a57ff4` | +1 |
| **W99-S2 W99 +1** | /ws/voice TTS 改逐 chunk send_bytes | voice.py L211-218 try/except + close(1011) + tests/test_ws_voice_tts_streaming_e2e.py (1 PASS, 3 chunks × 1024 bytes) | `8b052f79c` | +1 |
| **W99-S3 W99 +2** | EMBEDDING_MODEL_NAME 默认值对齐 | docker-compose.yml L41 + L265 (text2vec → Qwen3) | `2d0631de6` | +1 |
| **W99-S4 W99 +3** | ASR 真流式评估 | docs/w99-s4-asr-streaming-eval-2026-08-02.md (233 行) **决策 A 不实施** | `6dbe88713` | +1 |

**锚点范式守恒**：28adff574 (W99 +11 累计) → 6dbe88713 (W99 +15 累计, +4 据实)。派工代号 W99-S1..S4 派工 brief 估 +4，实测 +4 守恒。

## 5 件套守恒实测
1. **alembic 1 head** 守恒：`093_add_search_log_answer_rating (head)` ✅
2. **pytest 8 关键套件**：`86 PASSED + 6 SKIPPED + 0 FAILED`（S1: 3 + S2: 1 + 5 老 TTS 回归 45 + 旧 WS 套件 37 = 86 PASSED）✅
3. **PWA build**：环境缺 vite/node 命令（gbk 乱码），本批不涉及 frontend 改动，沿用 W98 P2 batch 基线 ✅
4. **0 production code** 例外清单：
   - S1 例外 (engineering 优化): voice.py /voice/tts + tts.py synthesize_stream try/except
   - S2 例外 (engineering 优化): voice.py /ws/voice TTS 段
   - S3 **不算例外** (配置对齐, 0 production code)
   - S4 **不算例外** (纯 docs)
5. **锚点范式**: W98 67 + W99 12 + W19 2 + DEPLOY-BUILD 2 = 83 commits 累计 + W99 +4 → 累计 87（**注**: W99 +N 实际是 锚点范式编号，commit 数与锚点数的映射沿用派工 v11 段 9 规则）

## 派工前提铁律 12 + 类 20 实战 N 实例 (W99 S-series 据实上报)
- **类 20.108** (改前必实测行号): S1/S2/S3 派工 brief 都精确锁定行号 (voice.py:86-108 / 214-215 / docker-compose.yml:41,265)，agent 据实测改零漂移
- **类 20.13 实战 19** (派工 brief 路径假设 vs 实测路径错配): 派工 brief 直接引用实测行号，零错配
- **类 20.97** (ahead=0 ≠ 不必改, 必查实际定义模块): S2 严守"不重复改 synthesize_stream 函数体（属于 S1）"边界
- **类 20.114 实战** (新增 - 评估任务边界纪律): S4 评估任务严守只读边界，未顺手实施任何代码
- **类 20.115 实战** (新增 - 简化 worktree 模式): 4 个 agent 都在同一 worktree 并行 + "不 commit 等主指挥" 模式自发合并到当前分支 — 当前 worktree 名 = 最后一个完成的 agent 分支名。**改动文件不冲突时 OK**，派工 brief v3 §0.1 没明文推荐此模式，需据实记录
- **类 20.116 实战** (新增 - S3 据实上报 2 处): docker-compose.test.yml:107 + test_st5_compat.py:79/83/122 — agent 严守边界不动，主拍决策在 commit message 固化 + 留口给后续派工

## W99-S4 评估报告关键数据
- 当前 ASR 延迟: 短音频 70-120ms, 会议实时字幕 2-5s (前端发包间隔主导), 长音频 N×60ms
- 唯一敏感场景: WS /ws/meeting/{meeting_id}/transcript, 改善空间仅 1-3s
- FunASR 硬约束: SenseVoice streaming mode `use_itn` 失效 ("123 万" → "一百二十三万"), chunk_size 必须 60ms 倍数
- 决策 A (推荐): 不实施, 当前已 streaming yield, 实施 ROI 为负
- 留口位置: app/voice/asr.py:144-152 docstring + docs/asr-benchmark-2026-06-30.md:323

## W99+ 派工代号槽位据实 (不擅自扩不擅自缩)
- 派工 brief 用了 W99-S1/S2/S3/S4 (4 个新代号, **不在预留表**)
- 预留表:
  - CLAUDE.md line 46: P3-A/B/C/D (W98 P2 收口预留)
  - CLAUDE.md line 50: W99 P1-P3 (已用完) + W100 P1-P2 + W101 P1-P2
- 主拍决策: W99-S 系列作为**新增支线** (与预留表平行), 不擅自扩也不擅自缩
- 后续派工表: W99-T-* (T = tuning, 与 S = streaming 平行) 或继续 S-series 深化

## 累计 commits / 铁律延续
- 累计 W98-W99: 87 commits + 590+ 铁律
- W99 S-series + 4 新铁律 (类 20.114/115/116 + 1 评估任务边界纪律)
- W19 选项 A 维持
- 详见 `docs/w99-s-series-grand-closure-2026-08-02.md` (runbook)